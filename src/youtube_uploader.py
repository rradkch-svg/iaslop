"""
Módulo de Automação de Publicação de Shorts no YouTube Studio via Playwright / Chrome.

Responsável por:
1. Gerenciar sessão autenticada persistente no YouTube Studio (perfil isolado e seguro em checkpoint/youtube_profile).
2. Carregar e parsear cookies locais (cookies.txt) e dados de autenticação.
3. Fazer upload de vídeos renderizados (final_output.mp4) de cada lote.
4. Preencher Título, Descrição, Tags e selecionar 'Não é conteúdo para crianças'.
5. Suportar publicação imediata (Público/Não-listado/Privado) ou agendamento escalonado de Shorts.
6. Gravar registro de uploads em checkpoint/batch_X/youtube_uploads.json para evitar reenvio duplicado.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

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
        app_logger = logging.getLogger("youtube_uploader")
        if not app_logger.handlers:
            logging.basicConfig(level=logging.INFO)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CHECKPOINT_DIR = os.environ.get("CHECKPOINT_DIR") or os.path.join(PROJECT_ROOT, "checkpoint")
DEFAULT_PROFILE_DIR = os.path.join(DEFAULT_CHECKPOINT_DIR, "youtube_profile")
DEFAULT_COOKIES_TXT = os.path.join(PROJECT_ROOT, "cookies.txt")

# Caminhos padrão do Google Chrome no Windows
CHROME_CANDIDATE_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_system_browser() -> Optional[str]:
    """Localiza o executável do Google Chrome ou Edge no sistema Windows."""
    for path in CHROME_CANDIDATE_PATHS:
        if os.path.exists(path):
            return path
    return None


def parse_netscape_cookies(cookie_file_path: str) -> List[Dict[str, Any]]:
    """
    Converte cookies no formato Netscape (cookies.txt) para o formato aceito pelo Playwright.
    """
    if not os.path.exists(cookie_file_path):
        return []

    cookies = []
    now = time.time()
    try:
        with open(cookie_file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split("\t")
                if len(parts) >= 7:
                    domain = parts[0]
                    path = parts[2]
                    secure = parts[3].lower() == "true"
                    try:
                        expires = float(parts[4])
                    except (ValueError, IndexError):
                        expires = -1

                    name = parts[5]
                    value = parts[6]

                    # Filtra apenas cookies relacionados ao YouTube / Google
                    if "youtube.com" not in domain and "google.com" not in domain:
                        continue

                    # Ignora cookies expirados
                    if expires > 0 and expires < now:
                        continue

                    cookie_dict: Dict[str, Any] = {
                        "name": name,
                        "value": value,
                        "domain": domain if domain.startswith(".") else f".{domain}",
                        "path": path,
                        "secure": secure,
                        "sameSite": "Lax",
                    }
                    if expires > 0:
                        cookie_dict["expires"] = expires

                    cookies.append(cookie_dict)
    except Exception as e:
        app_logger.warning(f"[YouTubeUploader] Erro ao ler cookies de {cookie_file_path}: {e}")

    return cookies


def parse_video_metadata(video_dir: str) -> Dict[str, Any]:
    """
    Extrai título, descrição e tags de um vídeo a partir de metadata.txt ou checkpoint.json.
    """
    meta_path = os.path.join(video_dir, "metadata.txt")
    ckpt_path = os.path.join(video_dir, "checkpoint.json")

    title = ""
    description = ""
    tags = []

    # 1. Tenta ler checkpoint.json primeiro (dados mais estruturados)
    if os.path.exists(ckpt_path):
        try:
            with open(ckpt_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                topic = cdata.get("topic", {})
                title = topic.get("tema", "")
                description = topic.get("descricao", "")
                tags = topic.get("tags", [])
        except Exception:
            pass

    # 2. Complementa com metadata.txt caso campos estejam vazios
    if (not title or not description) and os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            current_section = None
            desc_lines = []
            for line in lines:
                sline = line.strip()
                if sline.startswith("TÍTULO:") or sline.startswith("TITULO:"):
                    current_section = "title"
                    t_val = sline.split(":", 1)[1].strip()
                    if t_val:
                        title = t_val
                    continue
                elif sline.startswith("DESCRIÇÃO:") or sline.startswith("DESCRICAO:"):
                    current_section = "desc"
                    continue
                elif sline.startswith("HASHTAGS:") or sline.startswith("TAGS:"):
                    current_section = "tags"
                    continue

                if current_section == "title" and sline and not title:
                    title = sline
                elif current_section == "desc" and sline:
                    desc_lines.append(sline)
                elif current_section == "tags" and sline:
                    found_tags = [t.strip() for t in sline.split() if t.startswith("#")]
                    if found_tags:
                        tags.extend(found_tags)

            if desc_lines and not description:
                description = "\n".join(desc_lines)
        except Exception:
            pass

    # Garante hashtag #Shorts no título se ainda não estiver presente (teto de 100 caracteres)
    if title and "#Shorts" not in title and "#shorts" not in title:
        if len(title) + len(" #Shorts") <= 100:
            title = f"{title} #Shorts"
        else:
            title = f"{title[:90]}... #Shorts"

    return {
        "title": title or "Mistério Inexplicável #Shorts",
        "description": description or "Mais um mistério factual e documental investigado pelo Minuto Inexplicável.",
        "tags": tags or ["#Shorts", "#MinutoInexplicavel", "#Misterio", "#Documentario"],
    }


def get_batch_videos_to_upload(
    batch_index: int,
    checkpoint_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Varre o batch e retorna a lista de vídeos prontos que ainda não foram postados no YouTube.
    """
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    batch_dir = os.path.join(base_dir, f"batch_{batch_index}")
    if not os.path.exists(batch_dir):
        return []

    # Carrega histórico de uploads anteriores deste batch
    history_file = os.path.join(batch_dir, "youtube_uploads.json")
    uploaded_history: Dict[str, Any] = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as hf:
                uploaded_history = json.load(hf)
        except Exception:
            uploaded_history = {}

    targets = []
    for item in sorted(os.listdir(batch_dir)):
        item_path = os.path.join(batch_dir, item)
        if not os.path.isdir(item_path) or not item.startswith("video_"):
            continue

        try:
            v_idx = int(item.split("_")[1])
        except (IndexError, ValueError):
            continue

        v_key = f"video_{v_idx}"
        if v_key in uploaded_history and uploaded_history[v_key].get("success"):
            # Já enviado anteriormente com sucesso
            continue

        final_mp4 = os.path.join(item_path, "final_output.mp4")
        if not os.path.exists(final_mp4):
            alt_mp4 = os.path.join(item_path, "final_video.mp4")
            if os.path.exists(alt_mp4):
                final_mp4 = alt_mp4

        if not os.path.exists(final_mp4) or os.path.getsize(final_mp4) < 10_000:
            continue

        meta = parse_video_metadata(item_path)
        targets.append({
            "batch_index": batch_index,
            "video_index": v_idx,
            "video_key": v_key,
            "video_dir": item_path,
            "video_file": final_mp4,
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
        })

    return targets


def save_upload_record(
    batch_index: int,
    video_key: str,
    record_data: Dict[str, Any],
    checkpoint_dir: Optional[str] = None
):
    """Registra o status e URL do vídeo postado no arquivo youtube_uploads.json do batch."""
    base_dir = os.path.abspath(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    batch_dir = os.path.join(base_dir, f"batch_{batch_index}")
    os.makedirs(batch_dir, exist_ok=True)
    history_file = os.path.join(batch_dir, "youtube_uploads.json")

    current = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = {}

    current[video_key] = record_data
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)


class YouTubeStudioUploader:
    """
    Robô de automação inteligente do YouTube Studio utilizando Playwright e perfil persistente do Chrome.
    """

    def __init__(
        self,
        profile_dir: Optional[str] = None,
        cookies_txt_path: Optional[str] = None,
        headless: bool = False
    ):
        self.profile_dir = os.path.abspath(profile_dir or DEFAULT_PROFILE_DIR)
        os.makedirs(self.profile_dir, exist_ok=True)
        self.cookies_path = cookies_txt_path or DEFAULT_COOKIES_TXT
        self.headless = headless
        self.browser_exe = find_system_browser()

    def launch_browser(self, p):
        """Inicializa o contexto persistente do navegador com perfil dedicado."""
        app_logger.info(f"[YouTubeUploader] 🌐 Inicializando navegador (Headless={self.headless})...")
        if self.browser_exe:
            app_logger.info(f"[YouTubeUploader] 🚀 Executável do navegador detectado: {self.browser_exe}")

        context = p.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            executable_path=self.browser_exe,
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )

        # Injeta cookies do cookies.txt caso existam e sejam novos
        if os.path.exists(self.cookies_path):
            netscape_cookies = parse_netscape_cookies(self.cookies_path)
            if netscape_cookies:
                try:
                    context.add_cookies(netscape_cookies)
                    app_logger.info(f"[YouTubeUploader] 🍪 {len(netscape_cookies)} cookies importados de '{self.cookies_path}'.")
                except Exception as e:
                    app_logger.warning(f"[YouTubeUploader] Erro ao injetar cookies: {e}")

        return context

    def open_interactive_login(self):
        """
        Abre uma janela visível do navegador para o usuário fazer login no YouTube Studio.
        A sessão fica salva de forma definitiva no perfil local isolado.
        """
        from playwright.sync_api import sync_playwright

        print("\n" + "=" * 75)
        print("🔑 MODO DE AUTENTICAÇÃO INTERATIVA DO YOUTUBE STUDIO")
        print("Uma janela do Google Chrome será aberta.")
        print("1. Faça login na sua conta do YouTube associada ao canal.")
        print("2. Quando a tela do YouTube Studio (studio.youtube.com) carregar com sucesso,")
        print("   volte a este terminal e pressione ENTER para salvar a sessão.")
        print("=" * 75 + "\n")

        with sync_playwright() as p:
            # Força janela visível
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                executable_path=self.browser_exe,
                headless=False,
                viewport={"width": 1280, "height": 850},
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            page = context.new_page()
            page.goto("https://studio.youtube.com", timeout=60000)

            input("👉 Pressione ENTER assim que estiver autenticado e vendo o painel do YouTube Studio...")

            # Salva o estado de armazenamento para reuso confiável
            storage_path = os.path.join(self.profile_dir, "storage_state.json")
            context.storage_state(path=storage_path)
            print(f"✅ Sessão persistente salva com sucesso em: {self.profile_dir}")
            context.close()

    def upload_video(
        self,
        video_data: Dict[str, Any],
        visibility: str = "PUBLIC",  # 'PUBLIC', 'UNLISTED', 'PRIVATE', 'SCHEDULE'
        schedule_time: Optional[datetime] = None,
        status_callback=None
    ) -> Dict[str, Any]:
        """
        Executa o fluxo completo de upload de um vídeo individual no YouTube Studio.
        """
        from playwright.sync_api import sync_playwright

        def log(msg: str):
            if status_callback:
                status_callback(msg)
            app_logger.info(f"[YouTubeUploader] {msg}")
            print(f"  {msg}")

        video_path = video_data["video_file"]
        title = video_data["title"]
        description = video_data["description"]
        tags = video_data.get("tags", [])

        if not os.path.exists(video_path):
            return {"success": False, "error": f"Arquivo de vídeo não encontrado: {video_path}"}

        log(f"🎬 Iniciando envio de: '{title}' ({os.path.getsize(video_path) / (1024*1024):.2f} MB)")

        with sync_playwright() as p:
            context = self.launch_browser(p)
            page = context.pages[0] if context.pages else context.new_page()

            try:
                log("📡 Navegando para o YouTube Studio...")
                page.goto("https://studio.youtube.com", timeout=60000, wait_until="domcontentloaded")
                time.sleep(3)

                # Verifica se caiu em tela de login
                if "accounts.google.com" in page.url or "signin" in page.url:
                    context.close()
                    return {
                        "success": False,
                        "error": "Sessão não autenticada no YouTube Studio. Execute o comando com '--login' para conectar sua conta uma vez."
                    }

                # 1. Localiza e clica no botão Criar / Create
                log("🖱️ Abrindo menu de envio de vídeos...")
                create_btn = page.locator("#create-icon, button[aria-label*='Criar'], button[aria-label*='Create'], ytcp-button#create-icon").first
                create_btn.wait_for(state="visible", timeout=30000)
                create_btn.click()
                time.sleep(1.5)

                # 2. Clica em Enviar Vídeos / Upload videos
                upload_option = page.locator("ytcp-text-menu-item#text-item-0, [test-id='upload-video'], paper-item:has-text('Enviar vídeos'), paper-item:has-text('Upload videos')").first
                upload_option.wait_for(state="visible", timeout=15000)
                upload_option.click()
                time.sleep(2)

                # 3. Input de arquivo (envia o arquivo MP4 diretamente)
                log(f"📤 Fazendo upload do arquivo: {os.path.basename(video_path)}...")
                file_input = page.locator("input[type='file']").first
                file_input.wait_for(state="attached", timeout=20000)
                file_input.set_input_files(video_path)
                time.sleep(5)

                # Aguarda o modal de detalhes do vídeo carregar
                dialog = page.locator("ytcp-uploads-dialog, ytcp-video-metadata-editor").first
                dialog.wait_for(state="visible", timeout=45000)
                log("✍️ Preenchendo metadados do vídeo...")

                # 4. Preenche o Título
                title_box = page.locator("#textbox[aria-label*='título'], #textbox[aria-label*='Title'], div#title-textarea #textbox").first
                title_box.wait_for(state="visible", timeout=15000)
                title_box.click()
                # Limpa título padrão inserido pelo YouTube Studio
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                title_box.fill(title[:100])
                time.sleep(1)

                # 5. Preenche a Descrição
                desc_box = page.locator("div#description-textarea #textbox, #textbox[aria-label*='descrição'], #textbox[aria-label*='Description']").first
                if desc_box.is_visible():
                    desc_box.click()
                    full_desc = f"{description}\n\n{' '.join(tags)}"
                    desc_box.fill(full_desc[:4900])
                    time.sleep(1)

                # 6. Seleciona "Não é conteúdo para crianças" (obrigatório pelo YouTube)
                log("👶 Definindo restrição de audiência (Não é para crianças)...")
                not_for_kids_radio = page.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']").first
                not_for_kids_radio.scroll_into_view_if_needed()
                not_for_kids_radio.click()
                time.sleep(1)

                # 7. Preenche Tags (clica em 'Mostrar mais' / 'Show more')
                try:
                    show_more = page.locator("#toggle-button, button:has-text('Mostrar mais'), button:has-text('Show more')").first
                    if show_more.is_visible():
                        show_more.click()
                        time.sleep(1)
                        tags_input = page.locator("input[aria-label*='Tags'], #tags-container input").first
                        if tags_input.is_visible() and tags:
                            raw_tags = ", ".join([t.replace("#", "") for t in tags])
                            tags_input.fill(raw_tags[:450])
                            page.keyboard.press("Enter")
                except Exception as e_tags:
                    app_logger.warning(f"[YouTubeUploader] Erro ao preencher tags (não crítico): {e_tags}")

                # 8. Avança pelas abas de verificação clicando em 'Próximo' / 'Next'
                log("⏭️ Avançando etapas de elementos e direitos autorais...")
                for _ in range(3):
                    next_btn = page.locator("#next-button, button:has-text('Próximo'), button:has-text('Next')").first
                    next_btn.wait_for(state="visible", timeout=15000)
                    next_btn.click()
                    time.sleep(2)

                # 9. Configura Visibilidade ou Agendamento
                log(f"🔒 Configurando visibilidade: {visibility}...")
                if visibility == "PUBLIC":
                    pub_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC']").first
                    pub_radio.scroll_into_view_if_needed()
                    pub_radio.click()
                elif visibility == "UNLISTED":
                    unlisted_radio = page.locator("tp-yt-paper-radio-button[name='UNLISTED']").first
                    unlisted_radio.scroll_into_view_if_needed()
                    unlisted_radio.click()
                elif visibility == "PRIVATE":
                    priv_radio = page.locator("tp-yt-paper-radio-button[name='PRIVATE']").first
                    priv_radio.scroll_into_view_if_needed()
                    priv_radio.click()
                elif visibility == "SCHEDULE" and schedule_time:
                    sched_tab = page.locator("#second-container-expand-button, button:has-text('Programar'), button:has-text('Schedule')").first
                    sched_tab.click()
                    time.sleep(1.5)
                    # Preenche data e horário programado
                    date_input = page.locator("#datepicker-trigger input").first
                    if date_input.is_visible():
                        date_input.fill(schedule_time.strftime("%d/%m/%Y"))
                        page.keyboard.press("Enter")
                    time_input = page.locator("input[aria-label*='Horário'], input[aria-label*='Time']").first
                    if time_input.is_visible():
                        time_input.fill(schedule_time.strftime("%H:%M"))
                        page.keyboard.press("Enter")

                time.sleep(2)

                # Captura link do vídeo gerado antes de salvar
                video_url = ""
                try:
                    url_elem = page.locator("a.ytcp-video-info, a[href*='youtu.be']").first
                    if url_elem.is_visible():
                        video_url = url_elem.get_attribute("href") or ""
                except Exception:
                    pass

                # 10. Conclui e Publica
                log("💾 Finalizando e publicando no YouTube...")
                done_btn = page.locator("#done-button, button:has-text('Salvar'), button:has-text('Publicar'), button:has-text('Save'), button:has-text('Publish')").first
                done_btn.wait_for(state="visible", timeout=20000)
                done_btn.click()

                # Aguarda confirmação final de processamento
                time.sleep(6)
                log(f"🎉 Vídeo publicado com sucesso! {video_url}")

                context.close()
                return {
                    "success": True,
                    "title": title,
                    "url": video_url,
                    "published_at": datetime.now().isoformat(),
                    "visibility": visibility
                }

            except Exception as e:
                err_msg = f"Falha durante o upload no YouTube Studio: {str(e)}"
                app_logger.error(f"[YouTubeUploader] {err_msg}")
                try:
                    # Tira screenshot de diagnóstico para facilitar depuração visual
                    diag_shot = os.path.join(self.profile_dir, "upload_error_diagnostic.png")
                    page.screenshot(path=diag_shot)
                    app_logger.info(f"[YouTubeUploader] Screenshot do erro salva em: {diag_shot}")
                except Exception:
                    pass
                context.close()
                return {"success": False, "error": err_msg}


def upload_batch_to_youtube(
    batch_index: int,
    visibility: str = "PUBLIC",
    schedule_interval_hours: float = 0.0,
    headless: bool = False,
    checkpoint_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Coordena o envio de todos os vídeos pendentes de um lote específico.
    """
    targets = get_batch_videos_to_upload(batch_index, checkpoint_dir=checkpoint_dir)
    if not targets:
        return {
            "success": True,
            "message": f"Nenhum vídeo pendente para envio no batch_{batch_index} (todos já postados ou ausentes).",
            "batch_index": batch_index,
            "uploaded_count": 0
        }

    uploader = YouTubeStudioUploader(headless=headless)
    uploaded_count = 0
    results = []

    print(f"\n{'=' * 75}")
    print(f"🚀 INICIANDO POSTAGEM NO YOUTUBE: BATCH {batch_index} ({len(targets)} vídeos encontrados)")
    print(f"{'=' * 75}\n")

    current_time = datetime.now()

    for idx, item in enumerate(targets):
        print(f"\n[{idx + 1}/{len(targets)}] Postando {item['video_key']}...")
        
        # Define agendamento progressivo se intervalo for maior que zero
        sched_time = None
        cur_vis = visibility
        if schedule_interval_hours > 0:
            cur_vis = "SCHEDULE"
            sched_time = current_time + timedelta(hours=schedule_interval_hours * (idx + 1))

        res = uploader.upload_video(
            video_data=item,
            visibility=cur_vis,
            schedule_time=sched_time
        )

        save_upload_record(
            batch_index=batch_index,
            video_key=item["video_key"],
            record_data=res,
            checkpoint_dir=checkpoint_dir
        )

        if res.get("success"):
            uploaded_count += 1
            results.append(res)
        else:
            print(f"❌ Erro ao enviar {item['video_key']}: {res.get('error')}")
            # Se for erro de autenticação, interrompe para não tentar repetidamente
            if "não autenticada" in res.get("error", "").lower():
                break

    return {
        "success": uploaded_count == len(targets),
        "batch_index": batch_index,
        "total_targets": len(targets),
        "uploaded_count": uploaded_count,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="Automação de Upload de Vídeos e Shorts no YouTube Studio via Playwright")
    parser.add_argument("--batch", type=int, default=None, help="Índice do batch para postar (ex: 1, 2, 3)")
    parser.add_argument("--login", action="store_true", help="Abre o navegador visível para login interativo e salva a sessão")
    parser.add_argument("--headless", action="store_true", help="Executa o navegador em modo oculto (headless)")
    parser.add_argument("--visibility", type=str, default="PUBLIC", choices=["PUBLIC", "UNLISTED", "PRIVATE"], help="Visibilidade padrão")
    parser.add_argument("--schedule-hours", type=float, default=0.0, help="Intervalo em horas entre cada vídeo programado")
    args = parser.parse_args()

    if args.login:
        uploader = YouTubeStudioUploader(headless=False)
        uploader.open_interactive_login()
        return

    if args.batch is not None:
        res = upload_batch_to_youtube(
            batch_index=args.batch,
            visibility=args.visibility,
            schedule_interval_hours=args.schedule_hours,
            headless=args.headless
        )
        print("\nResultado da Operação:", res)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
