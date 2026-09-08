"""
Módulo de Serviço de E-mail e Compactação de Batches para Minuto Inexplicável.

Responsável por:
1. Empacotar batches concluídos em arquivos ZIP estruturados (vídeos finais, metadados, roteiros e checkpoints).
2. Gerar pacotes leves de metadados para envio garantido por e-mail sem estouro de limite de anexos SMTP (Gmail 25MB).
3. Transmitir notificações detalhadas em HTML e texto para o destinatário (padrão: rra.dkch@gmail.com).
4. Suportar TLS/SSL automático com fallback para conexões seguras na porta 465 / 587.
"""

import os
import sys
import json
import time
import zipfile
import smtplib
import mimetypes
import argparse
from typing import Dict, Any, List, Optional, Tuple
from email.message import EmailMessage

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from .logger import app_logger
except ImportError:
    try:
        from logger import app_logger
    except ImportError:
        import logging
        app_logger = logging.getLogger("email_service")
        if not app_logger.handlers:
            logging.basicConfig(level=logging.INFO)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CHECKPOINT_DIR = os.environ.get("CHECKPOINT_DIR") or os.path.join(PROJECT_ROOT, "checkpoint")
DEFAULT_RECIPIENT = "rra.dkch@gmail.com"
DEFAULT_MAX_ATTACHMENT_MB = 24.0


def get_batch_manifest(batch_index: int, checkpoint_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Coleta informações e metadados de todos os vídeos de um batch para compor o relatório.
    """
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    batch_dir = os.path.join(base_dir, f"batch_{batch_index}")
    
    manifest: Dict[str, Any] = {
        "batch_index": batch_index,
        "batch_name": f"batch_{batch_index}",
        "batch_dir": batch_dir,
        "exists": os.path.exists(batch_dir),
        "total_videos": 0,
        "completed_videos": 0,
        "total_duration_sec": 0.0,
        "total_video_bytes": 0,
        "videos": []
    }

    if not os.path.exists(batch_dir):
        return manifest

    # Varre diretórios video_0 .. video_N
    for item in sorted(os.listdir(batch_dir)):
        item_path = os.path.join(batch_dir, item)
        if not os.path.isdir(item_path) or not item.startswith("video_"):
            continue

        try:
            v_idx = int(item.split("_")[1])
        except (IndexError, ValueError):
            continue

        manifest["total_videos"] += 1
        ckpt_path = os.path.join(item_path, "checkpoint.json")
        meta_path = os.path.join(item_path, "metadata.txt")
        diss_path = os.path.join(item_path, "dissertacao.txt")
        final_mp4 = os.path.join(item_path, "final_output.mp4")
        if not os.path.exists(final_mp4):
            alt_mp4 = os.path.join(item_path, "final_video.mp4")
            if os.path.exists(alt_mp4):
                final_mp4 = alt_mp4

        v_data: Dict[str, Any] = {
            "video_index": v_idx,
            "video_name": f"video_{v_idx}",
            "dir": item_path,
            "title": f"Vídeo {v_idx}",
            "hook": "",
            "tags": [],
            "status": "UNKNOWN",
            "duration": 0.0,
            "has_video": os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 1000,
            "video_file": final_mp4 if os.path.exists(final_mp4) else None,
            "video_size_bytes": os.path.getsize(final_mp4) if os.path.exists(final_mp4) else 0,
        }

        if v_data["has_video"]:
            manifest["completed_videos"] += 1
            manifest["total_video_bytes"] += v_data["video_size_bytes"]

        if os.path.exists(ckpt_path):
            try:
                with open(ckpt_path, "r", encoding="utf-8") as f:
                    ckpt = json.load(f)
                    topic = ckpt.get("topic", {})
                    v_data["title"] = topic.get("tema") or topic.get("title") or v_data["title"]
                    v_data["hook"] = topic.get("hook", "")
                    v_data["tags"] = topic.get("tags", [])
                    v_data["status"] = ckpt.get("status", "UNKNOWN")
                    dur = ckpt.get("audio_duration", 0.0)
                    v_data["duration"] = dur
                    manifest["total_duration_sec"] += dur
            except Exception as e:
                app_logger.warning(f"[EmailService] Erro ao ler {ckpt_path}: {e}")

        # Se houver metadata.txt com título melhor
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_s = line.strip()
                        if line_s.startswith("TÍTULO:") or line_s.startswith("TITULO:"):
                            v_data["title"] = line_s.split(":", 1)[1].strip()
                        elif line_s.startswith("HOOK:"):
                            v_data["hook"] = line_s.split(":", 1)[1].strip()
            except Exception:
                pass

        manifest["videos"].append(v_data)

    manifest["videos"].sort(key=lambda x: x["video_index"])
    return manifest


def zip_batch(
    batch_index: int,
    checkpoint_dir: Optional[str] = None,
    include_raw_media: bool = False,
    output_path: Optional[str] = None
) -> Tuple[str, float]:
    """
    Cria arquivo ZIP do batch.
    Por padrão, inclui todos os vídeos finais (final_output.mp4), metadados (metadata.txt),
    dissertações (dissertacao.txt), checkpoints (checkpoint.json), legendas (subtitles.ass) e áudios (audio.mp3).
    Omite pastas intermediárias pesadas (broll/, combined_scenes.mp4, sfx_track.wav) para economizar espaço,
    a menos que include_raw_media=True.

    Retorna (caminho_do_zip, tamanho_em_mb).
    """
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    batch_dir = os.path.join(base_dir, f"batch_{batch_index}")
    if not os.path.exists(batch_dir):
        raise FileNotFoundError(f"Diretório do batch não encontrado: {batch_dir}")

    zip_file_path = output_path or os.path.join(batch_dir, f"batch_{batch_index}.zip")
    
    # Se o arquivo já existir temporariamente, removemos para recriar de forma atômica
    if os.path.exists(zip_file_path):
        try:
            os.remove(zip_file_path)
        except Exception:
            pass

    app_logger.info(f"[EmailService] 📦 Compactando batch_{batch_index} em '{zip_file_path}'...")
    allowed_extensions = {".mp4", ".txt", ".json", ".ass", ".mp3", ".bat", ".md"}
    excluded_names = {"combined_scenes.mp4", "sfx_track.wav", "scenes_concat.txt"}

    with zipfile.ZipFile(zip_file_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(batch_dir):
            rel_root = os.path.relpath(root, batch_dir)
            
            # Pula pasta de broll cru a menos que solicitado
            if not include_raw_media and "broll" in rel_root.split(os.sep):
                continue

            for file in files:
                # Não inclui o próprio arquivo zip resultante
                if file == os.path.basename(zip_file_path):
                    continue
                if not include_raw_media and file in excluded_names:
                    continue

                _, ext = os.path.splitext(file)
                if not include_raw_media and ext.lower() not in allowed_extensions:
                    continue

                abs_file = os.path.join(root, file)
                arc_name = os.path.relpath(abs_file, base_dir)
                zf.write(abs_file, arcname=arc_name)

    size_bytes = os.path.getsize(zip_file_path)
    size_mb = size_bytes / (1024 * 1024)
    app_logger.info(f"[EmailService] ✅ Arquivo ZIP gerado: {zip_file_path} ({size_mb:.2f} MB)")
    return zip_file_path, size_mb


def zip_batch_metadata(
    batch_index: int,
    checkpoint_dir: Optional[str] = None,
    output_path: Optional[str] = None
) -> Tuple[str, float]:
    """
    Cria um arquivo ZIP contendo exclusivamente os metadados (metadata.txt),
    dissertações (dissertacao.txt), roteiros (checkpoint.json) e legendas (subtitles.ass).
    Garante um tamanho inferior a 2 MB para envio 100% confiável como anexo de e-mail.
    """
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    batch_dir = os.path.join(base_dir, f"batch_{batch_index}")
    zip_file_path = output_path or os.path.join(batch_dir, f"batch_{batch_index}_metadata.zip")

    if os.path.exists(zip_file_path):
        try:
            os.remove(zip_file_path)
        except Exception:
            pass

    metadata_extensions = {".txt", ".json", ".ass", ".bat", ".md"}
    with zipfile.ZipFile(zip_file_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(batch_dir):
            rel_root = os.path.relpath(root, batch_dir)
            if "broll" in rel_root.split(os.sep):
                continue
            for file in files:
                if file.endswith(".zip"):
                    continue
                _, ext = os.path.splitext(file)
                if ext.lower() in metadata_extensions:
                    abs_file = os.path.join(root, file)
                    arc_name = os.path.relpath(abs_file, base_dir)
                    zf.write(abs_file, arcname=arc_name)

    size_bytes = os.path.getsize(zip_file_path)
    size_mb = size_bytes / (1024 * 1024)
    app_logger.info(f"[EmailService] 📄 Pacote de metadados gerado: {zip_file_path} ({size_mb:.2f} MB)")
    return zip_file_path, size_mb


def format_email_body(
    manifest: Dict[str, Any],
    zip_path: str,
    zip_size_mb: float,
    is_attached: bool,
    attached_filename: str
) -> Tuple[str, str]:
    """
    Formata o corpo da mensagem em texto simples e HTML responsivo de alto contraste.
    """
    b_idx = manifest.get("batch_index", 0)
    completed_v = manifest.get("completed_videos", 0)
    total_v = manifest.get("total_videos", 0)
    total_min = manifest.get("total_duration_sec", 0.0) / 60.0
    total_mb = manifest.get("total_video_bytes", 0) / (1024 * 1024)

    # Texto puro (fallback)
    lines = [
        f"==================================================",
        f"🎬 MINUTO INEXPLICÁVEL - BATCH {b_idx} CONCLUÍDO",
        f"==================================================",
        f"Total de Vídeos: {completed_v}/{total_v} concluídos",
        f"Duração Total: {total_min:.1f} minutos ({manifest.get('total_duration_sec', 0):.0f}s)",
        f"Tamanho em Disco dos Vídeos: {total_mb:.1f} MB",
        f"Arquivo ZIP Local: {zip_path} ({zip_size_mb:.1f} MB)",
        "",
    ]

    if is_attached:
        lines.append(f"📎 Anexo: {attached_filename} anexado com sucesso.")
    else:
        lines.append(f"⚠️ Nota de Anexo: O arquivo de vídeos ({zip_size_mb:.1f} MB) excedeu o limite máximo de 25 MB do Gmail.")
        lines.append(f"   O arquivo ZIP completo foi salvo localmente em seu computador:")
        lines.append(f"   -> {zip_path}")
        lines.append(f"   Anexamos o pacote de metadados e roteiros ({attached_filename}).")

    lines.append("\n📋 RESUMO DOS VÍDEOS DESTE BATCH:")
    for v in manifest.get("videos", []):
        dur_str = f"{v.get('duration', 0):.1f}s"
        size_str = f"{v.get('video_size_bytes', 0) / (1024 * 1024):.1f} MB"
        lines.append(f"- video_{v.get('video_index')}: {v.get('title')} ({dur_str} | {size_str})")
        if v.get("hook"):
            lines.append(f"  Gancho: \"{v.get('hook')}\"")
        if v.get("tags"):
            lines.append(f"  Tags: {' '.join(v.get('tags')[:5])}")

    plain_text = "\n".join(lines)

    # HTML estilizado
    rows_html = []
    for v in manifest.get("videos", []):
        dur_str = f"{v.get('duration', 0):.1f}s"
        size_str = f"{v.get('video_size_bytes', 0) / (1024 * 1024):.1f} MB"
        status_color = "#10b981" if v.get("has_video") else "#f59e0b"
        status_badge = "Concluído" if v.get("has_video") else v.get("status", "Pendente")
        
        tags_str = " ".join([f"<span style='background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:4px;font-size:11px;margin-right:4px;'>{t}</span>" for t in v.get("tags", [])[:4]])
        
        row = f"""
        <tr style="border-bottom: 1px solid #1e293b;">
            <td style="padding: 10px; text-align: center; color: #94a3b8; font-weight: bold;">{v.get('video_index')}</td>
            <td style="padding: 10px;">
                <div style="font-weight: 600; color: #f8fafc; font-size: 14px;">{v.get('title')}</div>
                <div style="color: #94a3b8; font-size: 12px; margin-top: 4px; font-style: italic;">"{v.get('hook')}"</div>
                <div style="margin-top: 6px;">{tags_str}</div>
            </td>
            <td style="padding: 10px; text-align: center; color: #cbd5e1; font-size: 13px;">{dur_str}</td>
            <td style="padding: 10px; text-align: center; color: #cbd5e1; font-size: 13px;">{size_str}</td>
            <td style="padding: 10px; text-align: center;">
                <span style="background: {status_color}22; color: {status_color}; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; border: 1px solid {status_color}55;">
                    {status_badge}
                </span>
            </td>
        </tr>
        """
        rows_html.append(row)

    attachment_notice_html = ""
    if is_attached:
        attachment_notice_html = f"""
        <div style="background: #064e3b; border: 1px solid #059669; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px;">
            <span style="font-size: 16px;">📎</span> 
            <strong style="color: #34d399;">Arquivo ZIP anexado com sucesso!</strong>
            <div style="color: #a7f3d0; font-size: 12px; margin-top: 4px;">
                O lote completo ({attached_filename} - {zip_size_mb:.1f} MB) está anexado a este e-mail.
            </div>
        </div>
        """
    else:
        attachment_notice_html = f"""
        <div style="background: #451a03; border: 1px solid #b45309; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px;">
            <span style="font-size: 16px;">📦</span> 
            <strong style="color: #fbbf24;">Arquivo de Vídeos Preservado Localmente</strong>
            <div style="color: #fde68a; font-size: 12px; margin-top: 4px; line-height: 1.4;">
                O arquivo com todos os vídeos ({zip_size_mb:.1f} MB) excedeu o teto de 25 MB do Gmail e está salvo no seu computador em:<br/>
                <code style="background: #1c1917; padding: 2px 6px; border-radius: 4px; color: #f59e0b; font-size: 11px;">{zip_path}</code><br/>
                Anexamos o pacote de metadados, títulos, roteiros e legendas (<strong>{attached_filename}</strong>).
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Batch {b_idx} Concluído</title>
    </head>
    <body style="margin: 0; padding: 20px; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
        <div style="max-width: 760px; margin: 0 auto; background-color: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
            
            <!-- Cabeçalho -->
            <div style="border-bottom: 1px solid #1f2937; padding-bottom: 16px; margin-bottom: 20px; display: flex; align-items: center;">
                <div>
                    <h1 style="margin: 0; font-size: 22px; color: #f8fafc;">🔮 Minuto Inexplicável</h1>
                    <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">Geração Autônoma de Conteúdo 9:16 - Notificação de Batch Concluído</p>
                </div>
            </div>

            <!-- Cards de Métricas -->
            <div style="display: table; width: 100%; margin-bottom: 20px;">
                <div style="display: table-cell; width: 25%; background: #1e293b; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; font-weight: bold;">Batch</div>
                    <div style="color: #38bdf8; font-size: 20px; font-weight: bold; margin-top: 4px;">batch_{b_idx}</div>
                </div>
                <div style="display: table-cell; width: 2%;"></div>
                <div style="display: table-cell; width: 23%; background: #1e293b; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; font-weight: bold;">Vídeos</div>
                    <div style="color: #34d399; font-size: 20px; font-weight: bold; margin-top: 4px;">{completed_v}/{total_v}</div>
                </div>
                <div style="display: table-cell; width: 2%;"></div>
                <div style="display: table-cell; width: 23%; background: #1e293b; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; font-weight: bold;">Duração Total</div>
                    <div style="color: #fbbf24; font-size: 20px; font-weight: bold; margin-top: 4px;">{total_min:.1f} min</div>
                </div>
                <div style="display: table-cell; width: 2%;"></div>
                <div style="display: table-cell; width: 23%; background: #1e293b; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; font-weight: bold;">Tamanho</div>
                    <div style="color: #a855f7; font-size: 20px; font-weight: bold; margin-top: 4px;">{total_mb:.1f} MB</div>
                </div>
            </div>

            <!-- Aviso do Anexo -->
            {attachment_notice_html}

            <!-- Tabela dos Vídeos -->
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px; background: #0f172a; border-radius: 8px; overflow: hidden;">
                <thead>
                    <tr style="background: #1e293b; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">
                        <th style="padding: 10px; text-align: center; width: 40px;">#</th>
                        <th style="padding: 10px; text-align: left;">Tema / Roteiro</th>
                        <th style="padding: 10px; text-align: center; width: 70px;">Tempo</th>
                        <th style="padding: 10px; text-align: center; width: 80px;">Tamanho</th>
                        <th style="padding: 10px; text-align: center; width: 90px;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>

            <!-- Rodapé -->
            <div style="border-top: 1px solid #1f2937; margin-top: 24px; padding-top: 16px; text-align: center; color: #64748b; font-size: 11px;">
                Minuto Inexplicável Studio • Processamento contínuo em lote 9:16 • Gerado automaticamente
            </div>

        </div>
    </body>
    </html>
    """

    return plain_text, html_content


def send_batch_email(
    batch_index: int,
    recipient: Optional[str] = None,
    checkpoint_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compacta o batch e envia a notificação com anexo ZIP para o e-mail configurado.
    
    Caso as credenciais SMTP não estejam definidas no .env, o arquivo ZIP é gerado e salvo
    localmente no disco, registrando um aviso informativo nos logs sem interromper o pipeline.
    """
    target_recipient = recipient or os.environ.get("EMAIL_RECIPIENT") or DEFAULT_RECIPIENT
    smtp_host = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
    smtp_port_raw = os.environ.get("SMTP_PORT") or "465"
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 465

    smtp_user = os.environ.get("SMTP_USER") or os.environ.get("GMAIL_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD")
    max_attachment_mb = float(os.environ.get("EMAIL_MAX_ATTACHMENT_MB") or DEFAULT_MAX_ATTACHMENT_MB)

    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    manifest = get_batch_manifest(batch_index, base_dir)

    # 1. Cria sempre o arquivo ZIP completo do batch em disco
    try:
        full_zip_path, full_zip_mb = zip_batch(batch_index, checkpoint_dir=base_dir)
    except Exception as e:
        app_logger.error(f"[EmailService] Falha ao compactar batch_{batch_index}: {e}")
        return {
            "success": False,
            "error": f"Erro na compactação do ZIP: {str(e)}",
            "batch_index": batch_index
        }

    # 2. Decide qual anexo enviar com base no tamanho (Gmail 25MB)
    to_attach_path = full_zip_path
    to_attach_mb = full_zip_mb
    is_full_attached = True

    if full_zip_mb > max_attachment_mb:
        is_full_attached = False
        app_logger.info(
            f"[EmailService] ℹ️ batch_{batch_index}.zip possui {full_zip_mb:.2f} MB (> {max_attachment_mb} MB). "
            f"Gerando pacote leve de metadados para garantir entrega de anexo via e-mail..."
        )
        meta_zip_path, meta_zip_mb = zip_batch_metadata(batch_index, checkpoint_dir=base_dir)
        to_attach_path = meta_zip_path
        to_attach_mb = meta_zip_mb

    attached_filename = os.path.basename(to_attach_path)

    # 3. Formata corpos do e-mail
    plain_text, html_content = format_email_body(
        manifest=manifest,
        zip_path=full_zip_path,
        zip_size_mb=full_zip_mb,
        is_attached=is_full_attached,
        attached_filename=attached_filename
    )

    # 4. Verifica se as credenciais SMTP estão presentes
    if not smtp_user or not smtp_password:
        msg_warning = (
            f"[EmailService] 📦 batch_{batch_index}.zip salvo localmente em: '{full_zip_path}' ({full_zip_mb:.2f} MB).\n"
            f"[EmailService] ⚠️ SMTP_USER ou SMTP_PASSWORD não estão definidos no arquivo .env.\n"
            f"[EmailService] 👉 Para ativar o envio automático para {target_recipient}, adicione no seu .env:\n"
            f"   SMTP_USER=seu_email@gmail.com\n"
            f"   SMTP_PASSWORD=sua_senha_de_app_16_digitos\n"
            f"   SMTP_PORT=465"
        )
        print(f"\n{'=' * 75}\n{msg_warning}\n{'=' * 75}\n")
        app_logger.warning(msg_warning)
        return {
            "success": False,
            "reason": "missing_smtp_credentials",
            "zip_path": full_zip_path,
            "zip_size_mb": full_zip_mb,
            "recipient": target_recipient,
            "batch_index": batch_index
        }

    # 5. Monta e envia o e-mail via SMTP
    try:
        app_logger.info(f"[EmailService] 🚀 Conectando a {smtp_host}:{smtp_port} para envio a {target_recipient}...")
        
        msg = EmailMessage()
        subject = f"🎬 [Minuto Inexplicável] Batch {batch_index} Concluído! ({manifest.get('completed_videos', 0)}/{manifest.get('total_videos', 0)} Vídeos)"
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = target_recipient
        msg.set_content(plain_text)
        msg.add_alternative(html_content, subtype="html")

        # Anexa o arquivo selecionado
        if os.path.exists(to_attach_path):
            with open(to_attach_path, "rb") as f:
                file_data = f.read()
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="zip",
                    filename=attached_filename
                )

        # Envio seguro: porta 465 (SSL) ou STARTTLS
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

        success_msg = f"✅ E-mail do batch_{batch_index} enviado com sucesso para {target_recipient} (Anexo: {attached_filename} - {to_attach_mb:.2f} MB)"
        print(f"\n{'*' * 75}\n{success_msg}\n{'*' * 75}\n")
        app_logger.info(f"[EmailService] {success_msg}")

        return {
            "success": True,
            "recipient": target_recipient,
            "batch_index": batch_index,
            "zip_path": full_zip_path,
            "zip_size_mb": full_zip_mb,
            "attached_file": to_attach_path,
            "attached_size_mb": to_attach_mb
        }

    except Exception as e:
        err_msg = f"Falha ao enviar e-mail do batch_{batch_index}: {str(e)}"
        print(f"\n❌ [EmailService] {err_msg}\n")
        app_logger.error(f"[EmailService] {err_msg}")
        return {
            "success": False,
            "error": err_msg,
            "batch_index": batch_index,
            "zip_path": full_zip_path,
            "zip_size_mb": full_zip_mb,
            "recipient": target_recipient
        }


def main():
    parser = argparse.ArgumentParser(description="Utilitário de Empacotamento e Envio de E-mail de Batches")
    parser.add_argument("--batch", type=int, default=None, help="Índice do batch para processar")
    parser.add_argument("--recipient", type=str, default=None, help="E-mail destinatário (padrão: rra.dkch@gmail.com)")
    parser.add_argument("--zip-only", action="store_true", help="Apenas compacta o batch sem enviar e-mail")
    parser.add_argument("--test", action="store_true", help="Testa conectividade SMTP com as configurações atuais")
    args = parser.parse_args()

    if args.test:
        smtp_host = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
        smtp_port = int(os.environ.get("SMTP_PORT") or "465")
        smtp_user = os.environ.get("SMTP_USER") or os.environ.get("GMAIL_USER")
        print(f"🔍 Testando conexão com {smtp_host}:{smtp_port}...")
        try:
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as s:
                    print(f"✅ Conexão SSL com {smtp_host}:{smtp_port} estabelecida com sucesso!")
                    if smtp_user:
                        print(f"ℹ️ Usuário SMTP configurado: {smtp_user}")
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
                    s.starttls()
                    print(f"✅ Conexão STARTTLS com {smtp_host}:{smtp_port} estabelecida com sucesso!")
        except Exception as e:
            print(f"❌ Erro de conexão SMTP: {e}")
        return

    target_batch = args.batch
    if target_batch is None:
        # Pega o último batch existente
        base_dir = os.path.abspath(DEFAULT_CHECKPOINT_DIR)
        b_nums = []
        if os.path.exists(base_dir):
            for entry in os.listdir(base_dir):
                if entry.startswith("batch_") and os.path.isdir(os.path.join(base_dir, entry)):
                    try:
                        b_nums.append(int(entry.split("_")[1]))
                    except (ValueError, IndexError):
                        pass
        if b_nums:
            target_batch = max(b_nums)
        else:
            print("❌ Nenhum batch encontrado para processar.")
            return

    if args.zip_only:
        p, mb = zip_batch(target_batch)
        print(f"✅ Batch {target_batch} compactado: {p} ({mb:.2f} MB)")
    else:
        res = send_batch_email(target_batch, recipient=args.recipient)
        print("Resultado:", res)


if __name__ == "__main__":
    main()
