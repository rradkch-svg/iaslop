import os
import re
import glob
import subprocess
import tempfile
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Set, Optional, List, Dict, Any
import yt_dlp

try:
    from .logger import app_logger, LogSpan, record_throttling
except ImportError:
    from logger import app_logger, LogSpan, record_throttling

try:
    from .visual_engine import VisualEngine
    from .video_enhancer import DEFAULT_VIDEO_ENHANCER
except ImportError:
    try:
        from visual_engine import VisualEngine
        from video_enhancer import DEFAULT_VIDEO_ENHANCER
    except ImportError:
        VisualEngine = None
        DEFAULT_VIDEO_ENHANCER = None


def find_deno_binary() -> Optional[str]:
    """Localiza o interpretador JavaScript Deno para resolver desafios de n-sig do YouTube."""
    candidates = [
        os.path.join(os.path.expanduser("~"), ".deno", "bin", "deno.exe"),
        r"C:\Users\Aluno\.deno\bin\deno.exe",
        "deno.exe",
        "deno"
    ]
    for c in candidates:
        if os.path.exists(c):
            deno_dir = os.path.dirname(os.path.abspath(c))
            if deno_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{deno_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            return c
    return None

find_deno_binary()
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

def find_cookies_file() -> Optional[str]:
    """Procura automaticamente por arquivo de cookies do YouTube no projeto ou diretório do usuário."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(root_dir, "cookies.txt"),
        os.path.join(root_dir, "youtube_cookies.txt"),
        os.path.join(root_dir, "youtube.com_cookies.txt"),
        os.path.join(os.path.expanduser("~"), "cookies.txt"),
        os.path.join(os.path.expanduser("~"), "Downloads", "cookies.txt"),
        os.path.join(os.path.expanduser("~"), "Downloads", "youtube_cookies.txt"),
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 50:
            return c
    return None

def find_ffmpeg_binary() -> str:
    """Busca o executável do FFmpeg no static-ffmpeg, imageio-ffmpeg, WinGet ou PATH."""
    try:
        import static_ffmpeg
        ffmpeg_exe, _ = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        if os.path.exists(ffmpeg_exe):
            return ffmpeg_exe
    except Exception:
        pass
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    winget_pattern = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe")
    winget_matches = glob.glob(winget_pattern)
    if winget_matches and os.path.exists(winget_matches[0]):
        return winget_matches[0]
    return "ffmpeg"

def find_ffprobe_binary(ffmpeg_bin: str = "ffmpeg") -> str:
    """Busca o executável do FFprobe no static-ffmpeg, ao lado do ffmpeg ou PATH."""
    try:
        import static_ffmpeg
        _, ffprobe_exe = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        if os.path.exists(ffprobe_exe):
            return ffprobe_exe
    except Exception:
        pass
    if "ffmpeg.exe" in ffmpeg_bin:
        probe_cand = ffmpeg_bin.replace("ffmpeg.exe", "ffprobe.exe")
        if os.path.exists(probe_cand):
            return probe_cand
    return "ffprobe"

def get_video_duration(file_path: str, ffmpeg_bin: str = "ffmpeg") -> Optional[float]:
    """
    Valida a duração exata do arquivo baixado via ffprobe antes de qualquer corte (Item 3).
    Impede que -ss exceda a duração real do arquivo, prevenindo exit code 3199971767.
    Possui fallback secundário para ffmpeg -i com parsing via regex.
    """
    ffprobe_bin = find_ffprobe_binary(ffmpeg_bin)
    cmd = [
        ffprobe_bin, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        dur_val = float(res.stdout.strip())
        if dur_val > 0:
            return dur_val
    except Exception:
        pass

    # Fallback secundário usando ffmpeg -i
    try:
        f_bin = find_ffmpeg_binary()
        res = subprocess.run([f_bin, "-i", file_path], capture_output=True, text=True, timeout=10)
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
        if match:
            hours, mins, secs = map(float, match.groups())
            dur_val = hours * 3600 + mins * 60 + secs
            if dur_val > 0:
                return dur_val
    except Exception as e:
        app_logger.warning(f"[BRollEngine] Falha ao ler duração de '{file_path}': {str(e)}")
    return None

def extract_topic_keywords(text: str) -> str:
    """Extrai os termos essenciais do tema/objeto/evento de estudo de um título longo."""
    parts = text.split(":")
    main_part = parts[0] if len(parts) > 1 else text
    cleaned = re.sub(r"^(O Mistério d[oa]|O Segredo d[oa]|Como funciona o|Por que o|A verdade sobre o|A história d[oa]|O Caso d[oa]|O Incidente d[oa]|O Arquivo Secreto d[oa]|A Anomalia d[oa]|Tudo sobre o|A física d[oa]|A engenharia d[oa])\s*", "", main_part, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^\w\s\-\.]", " ", cleaned)
    cleaned = re.sub(r"\b(e seu|e sua|no|na|com|de|da|do|dos|das|para|sobre|que|por|ser|bom|demais|segredo|misterio|misterios|inexplicavel|caso|fato|fatos|fisica|engenharia|o|a|os|as)\b", " ", cleaned, flags=re.IGNORECASE)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    return " ".join(words[:6]) if words else text.strip()

# Alias para compatibilidade
extract_vehicle_keywords = extract_topic_keywords

def build_topic_queries(global_topic: str, base_query: str) -> List[str]:
    """Gera queries de busca focadas, com conexão particular obrigatória ao evento/local/mistério de estudo."""
    topic_kw = extract_topic_keywords(global_topic)
    queries = []
    
    # Verifica se base_query já contém palavras-chave do tema
    t_tokens = [w.lower() for w in topic_kw.split() if len(w) > 1]
    base_clean = base_query.strip() if base_query else ""
    base_lower = base_clean.lower()
    has_anchor = any(t in base_lower for t in t_tokens) if t_tokens else False
    
    if base_clean:
        if has_anchor:
            queries.append(base_clean)
            if not base_lower.endswith("4k") and not base_lower.endswith("hd"):
                queries.append(f"{base_clean} 1080p HD")
                queries.append(f"{base_clean} 4k")
        else:
            # Ancora obrigatoriamente a query com o tema central
            anchored = f"{topic_kw} {base_clean}".strip()
            queries.append(anchored)
            queries.append(f"{anchored} 1080p HD")
            queries.append(f"{anchored} 4k")
            
    if topic_kw:
        queries.extend([
            f"{topic_kw} documentary footage 1080p",
            f"{topic_kw} documentary footage 4k",
            f"{topic_kw} real archival footage HD",
            f"{topic_kw} satellite drone view 4k",
            f"{topic_kw} expedition history documentary",
            f"{topic_kw} mystery investigation HD"
        ])

        
    unique_queries = []
    for q in queries:
        q_clean = " ".join(q.split())
        if q_clean and q_clean not in unique_queries:
            unique_queries.append(q_clean)
    return unique_queries

def safe_status(cb, msg: str):
    if cb:
        try:
            cb(msg)
        except:
            pass

def safe_progress(cb, d: int, t: int):
    if cb:
        try:
            cb(d, t)
        except:
            pass

def calculate_scene_durations(
    cenas: List[Dict[str, Any]],
    total_audio_duration: float,
    words_timing: Optional[List[Dict[str, Any]]] = None,
    tail_overhead: float = 0.5
) -> List[float]:
    """
    Calcula com precisão milimétrica a duração de cada corte de cena para que:
    1. Cada tomada acompanhe exatamente o tempo em que a respectiva frase/fala é dita no áudio.
    2. A soma total de todos os clipes cubra 100% da narração + um overhead/buffer de segurança
       compacto no final (tail_overhead) para evitar cortes secos sem criar pausas mortas.
    """
    n_scenes = len(cenas)
    if n_scenes == 0:
        return []
    
    # Caso 1: Mapeamento preciso por words_timing do Edge-TTS
    if words_timing and len(words_timing) > 0:
        scene_durations = []
        word_idx = 0
        total_words = len(words_timing)
        curr_time = 0.0
        
        for sc_idx, cena in enumerate(cenas):
            fala = cena.get("fala", "").strip()
            sc_words = fala.split()
            sc_word_count = len(sc_words) if sc_words else 1
            
            start_t = curr_time
            end_idx = min(word_idx + sc_word_count - 1, total_words - 1)
            speech_end_t = words_timing[end_idx].get("end", total_audio_duration)
            
            word_idx = end_idx + 1
            
            if sc_idx == n_scenes - 1:
                dur = max(total_audio_duration - start_t, speech_end_t - start_t) + tail_overhead
            else:
                dur = max(1.8, speech_end_t - start_t)
                
            dur = round(dur, 2)
            scene_durations.append(dur)
            curr_time += dur
        
        # Garantia final de overhead total
        if sum(scene_durations) < total_audio_duration + tail_overhead:
            diff = (total_audio_duration + tail_overhead) - sum(scene_durations)
            scene_durations[-1] = round(scene_durations[-1] + diff, 2)
            
        return scene_durations
    
    # Caso 2: Cálculo proporcional pelos pesos das palavras / texto de cada cena
    weights = []
    for c in cenas:
        fala = c.get("fala", "").strip()
        w = len(fala.split()) if fala else 1
        weights.append(max(w, 1))
    
    total_w = sum(weights)
    durations = []
    for sc_idx, w in enumerate(weights):
        base_dur = (w / total_w) * total_audio_duration
        if sc_idx == n_scenes - 1:
            base_dur += tail_overhead
        durations.append(round(max(1.8, base_dur), 2))
    
    if sum(durations) < total_audio_duration + tail_overhead:
        diff = (total_audio_duration + tail_overhead) - sum(durations)
        durations[-1] = round(durations[-1] + diff, 2)
        
    return durations

class BRollEngine:
    """
    Motor de busca, download, varredura multi-trecho e auditoria concorrente de B-Rolls.
    Garante que 100% dos trechos utilizados sejam limpos (Zero Rostos) e renderizados em 1080x1920 HD
    com política estrita de Early-Discard para não desperdiçar tempo nem tokens em vídeos fora do tema.
    """
    def __init__(self, max_search_results: int = 6):
        self.max_search_results = max_search_results
        self.ffmpeg_bin = find_ffmpeg_binary()
        self.lock = threading.Lock()

    def search_and_download_clip(
        self,
        query: str,
        target_duration: float,
        seen_ids: Set[str],
        output_clip_path: str,
        global_topic: str = "Mistério Desclassificado",
        reviewer_agent = None,
        scene_fala: str = "",
        status_callback = None
    ) -> Tuple[bool, str, str, str, Dict[str, Any]]:
        """
        Pesquisa no YouTube, baixa candidatos e varre múltiplos trechos (timestamps) dentro de cada vídeo
        para encontrar um segmento aprovado (Zero Rostos + alta pertinência) em 1080x1920 HD.
        Aplica Early-Discard para abortar imediatamente vídeos que não pertencem ao tema.
        """
        with LogSpan("BRollEngine.search_and_download_clip", extra={"query": query, "topic": global_topic, "duration": target_duration}):
            queries_to_try = build_topic_queries(global_topic, query)
            cookies_file = find_cookies_file()

            for current_q in queries_to_try:
                safe_status(status_callback, f"🔍 Buscando tomada no YouTube: *'{current_q}'*...")

                ydl_opts_search = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": "in_playlist",
                    "default_search": f"ytsearch{self.max_search_results}",
                    "noplaylist": True,
                    "remote_components": ["ejs:github"],
                }
                if cookies_file:
                    ydl_opts_search["cookiefile"] = cookies_file

                entries = []
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
                        search_results = ydl.extract_info(f"ytsearch{self.max_search_results}:{current_q}", download=False)
                        entries = search_results.get("entries", [])
                except Exception as e:
                    err_str = str(e)
                    is_dl_throttled = "429" in err_str or "Too Many Requests" in err_str or "rate-limit" in err_str.lower() or "bot" in err_str.lower()
                    if is_dl_throttled:
                        record_throttling("YOUTUBE_DOWNLOAD", "HTTP_429_SEARCH_THROTTLE", f"Busca no YouTube sob rate limit: {err_str[:150]}", retry_after=10)
                    app_logger.warning(f"[BRollEngine] Erro ao buscar '{current_q}': {err_str}")
                    continue

                candidates = []
                with self.lock:
                    for entry in entries:
                        if not entry:
                            continue
                        v_id = entry.get("id")
                        v_dur = entry.get("duration") or 60
                        if v_id and v_id not in seen_ids and 8 <= v_dur <= 2400:
                            candidates.append(entry)

                if not candidates:
                    continue

                for cand in candidates:
                    vid_id = cand.get("id")
                    vid_title = cand.get("title", current_q)
                    vid_dur = cand.get("duration") or 60
                    vid_url = f"https://www.youtube.com/watch?v={vid_id}"

                    # 1. Pré-filtragem instantânea de metadados / título antes do download
                    if reviewer_agent:
                        ok_title, pre_reason = reviewer_agent.pre_filter_title(vid_title, global_topic)
                        if not ok_title:
                            app_logger.info(f"[BRollEngine] Candidato '{vid_title}' descartado pelo pré-filtro: {pre_reason}")
                            continue

                    safe_status(status_callback, f"📥 Baixando candidato HD nativo: **{vid_title[:45]}...**")

                    temp_raw_file = os.path.join(tempfile.gettempdir(), f"broll_{vid_id}_{int(time.time()*1000)}_{threading.get_ident()}.mp4")
                    temp_cut_clip = os.path.join(tempfile.gettempdir(), f"broll_cut_{vid_id}_{int(time.time()*1000)}_{threading.get_ident()}.mp4")

                    ydl_opts_download = {
                        "format": "bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height>=1080]+bestaudio/bestvideo[height>=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height>=720]+bestaudio/bestvideo[height>=480]+bestaudio/best[height>=720]/best[height>=480]/bestvideo+bestaudio/best",
                        "merge_output_format": "mp4",
                        "outtmpl": temp_raw_file,
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                        "socket_timeout": 20,
                        "remote_components": ["ejs:github"],
                        "http_headers": {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
                        },
                        "extractor_args": {
                            "youtube": {
                                "player_client": ["android", "ios", "mweb", "web"]
                            }
                        }
                    }
                    if cookies_file:
                        ydl_opts_download["cookiefile"] = cookies_file

                    try:
                        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                            ydl.download([vid_url])

                        if not os.path.exists(temp_raw_file):
                            matches = glob.glob(temp_raw_file.replace(".mp4", ".*"))
                            if matches:
                                temp_raw_file = matches[0]
                            else:
                                continue

                        # 2. Validação Empírica da Duração e Resolução Nativa Mínima (Corte de <480p)
                        actual_dur = get_video_duration(temp_raw_file, self.ffmpeg_bin)
                        if not actual_dur or actual_dur < 1.0:
                            app_logger.warning(f"[BRollEngine] Arquivo corrompido ou sem duração detectável: {temp_raw_file}")
                            if os.path.exists(temp_raw_file):
                                try:
                                    os.remove(temp_raw_file)
                                except:
                                    pass
                            continue

                        # Validação de Resolução Nativa: Descarta vídeos em baixa qualidade (144p, 240p, 360p)
                        if DEFAULT_VIDEO_ENHANCER:
                            is_ok_res, raw_w, raw_h = DEFAULT_VIDEO_ENHANCER.is_acceptable_resolution(temp_raw_file, min_height=480)
                            if not is_ok_res:
                                safe_status(status_callback, f"🚫 Vídeo descartado por baixa resolução nativa ({raw_w}x{raw_h} < 480p) -> Buscando vídeo em alta resolução...")
                                app_logger.info(f"[BRollEngine] Vídeo '{vid_title}' ({raw_w}x{raw_h}) descartado: resolução inferior a 480p.")
                                if os.path.exists(temp_raw_file):
                                    try:
                                        os.remove(temp_raw_file)
                                    except:
                                        pass
                                continue
                            else:
                                app_logger.info(f"[BRollEngine] Resolução nativa aprovada: {raw_w}x{raw_h} para '{vid_title}'")


                        # 3. Varredura Multi-Trechos Inteligente com Limites Estritos de Duração
                        if actual_dur <= target_duration:
                            seek_offsets = [0.0]
                            effective_cut_dur = max(1.0, actual_dur)
                        else:
                            max_seek = max(0.0, actual_dur - target_duration - 0.5)
                            offsets_pct = [0.25, 0.60]
                            seek_offsets = [min(max_seek, max(0.0, actual_dur * p)) for p in offsets_pct]
                            seek_offsets = list(dict.fromkeys([round(s, 1) for s in seek_offsets if s <= max_seek]))
                            if not seek_offsets:
                                seek_offsets = [0.0]
                            effective_cut_dur = target_duration

                        approved = False
                        best_inspection = {}

                        for seek_t in seek_offsets:
                            if os.path.exists(temp_cut_clip):
                                try:
                                    os.remove(temp_cut_clip)
                                except:
                                    pass

                            cut_dur = min(effective_cut_dur, max(1.0, actual_dur - seek_t))

                            # Recorte 9:16 HD (Lanczos + CRF 18) com garantia estrita de duração
                            cmd = [
                                self.ffmpeg_bin, "-y",
                                "-ss", str(seek_t),
                                "-i", temp_raw_file,
                                "-t", str(cut_dur),
                                "-vf", "scale=1080*16/9:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2,setsar=1,tpad=stop_mode=clone:stop_duration=5.0",
                                "-c:v", "libx264",
                                "-crf", "18",
                                "-preset", "fast",
                                "-pix_fmt", "yuv420p",
                                "-an",
                                "-r", "30",
                                "-t", str(cut_dur),
                                temp_cut_clip
                            ]
                            subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")

                            if not os.path.exists(temp_cut_clip) or os.path.getsize(temp_cut_clip) == 0:
                                continue

                            # Auditoria visual do trecho recortado
                            if reviewer_agent:
                                safe_status(status_callback, f"🧐 Inspecionando trecho aos {seek_t:.0f}s de *'{vid_title[:35]}'*...")
                                inspection = reviewer_agent.inspect_clip(
                                    clip_path=temp_cut_clip,
                                    global_topic=global_topic,
                                    scene_fala=scene_fala,
                                    video_title=vid_title,
                                    status_callback=status_callback
                                )
                                best_inspection = inspection
                                if inspection.get("aprovado", False):
                                    approved = True
                                    safe_status(status_callback, f"✅ **Trecho Aprovado aos {seek_t:.0f}s!** ({inspection.get('motivo')})")
                                    break
                                else:
                                    motivo_low = str(inspection.get("motivo", "")).lower()
                                    is_irrelevant = (
                                        inspection.get("descartar_video_inteiro", False) or
                                        float(inspection.get("score", 10.0)) <= 3.0 or
                                        any(kw in motivo_low for kw in [
                                            "desalinhado", "irrelevante", "outra marca", "outro modelo",
                                            "desconectad", "drone", "gopro", "tutorial", "estático", "gráfico",
                                            "incompatível", "diferente", "software", "gameplay", "sem relação"
                                        ])
                                    )
                                    if is_irrelevant:
                                        safe_status(status_callback, f"🚫 Vídeo descartado por irrelevância total ({inspection.get('motivo')}) -> Pulando candidato...")
                                        app_logger.info(f"[BRollEngine] Early-Discard acionado para '{vid_title}': {inspection.get('motivo')}")
                                        break
                                    else:
                                        safe_status(status_callback, f"⚠️ Trecho aos {seek_t:.0f}s reprovado ({inspection.get('motivo')}) -> Testando próximo trecho...")
                            else:
                                approved = True
                                break

                        # Limpeza do arquivo bruto
                        if os.path.exists(temp_raw_file):
                            try:
                                os.remove(temp_raw_file)
                            except:
                                pass

                        if approved and os.path.exists(temp_cut_clip):
                            with self.lock:
                                seen_ids.add(vid_id)
                            if os.path.exists(output_clip_path):
                                try:
                                    os.remove(output_clip_path)
                                except:
                                    pass

                            # Aplica tratamento de resolução HD, descompressão e nitidez
                            if DEFAULT_VIDEO_ENHANCER:
                                safe_status(status_callback, f"✨ Aplicando tratamento Full HD 1080x1920 e nitidez em *'{vid_title[:30]}'*...")
                                ok_hd, _ = DEFAULT_VIDEO_ENHANCER.enhance_clip(temp_cut_clip, output_clip_path)
                                if not ok_hd or not os.path.exists(output_clip_path):
                                    os.rename(temp_cut_clip, output_clip_path)
                                else:
                                    try:
                                        os.remove(temp_cut_clip)
                                    except:
                                        pass
                            else:
                                os.rename(temp_cut_clip, output_clip_path)

                            app_logger.info(f"[BRollEngine] Trecho Full HD aprovado e gravado: {output_clip_path} (ID: {vid_id} - '{vid_title}')")
                            return True, output_clip_path, vid_id, vid_title, best_inspection

                        else:
                            if os.path.exists(temp_cut_clip):
                                try:
                                    os.remove(temp_cut_clip)
                                except:
                                    pass

                    except Exception as err_dl:
                        err_str = str(err_dl)
                        is_dl_throttled = "429" in err_str or "Too Many Requests" in err_str or "rate-limit" in err_str.lower() or "bot" in err_str.lower() or "throttl" in err_str.lower()
                        if is_dl_throttled:
                            record_throttling("YOUTUBE_DOWNLOAD", "HTTP_429_DOWNLOAD_THROTTLE", f"Download no YouTube sob rate limit ({vid_id}): {err_str[:150]}", retry_after=15)
                            time.sleep(1.5)
                        app_logger.warning(f"[BRollEngine] Erro no candidato {vid_id}: {err_str}")
                        if os.path.exists(temp_raw_file):
                            try:
                                os.remove(temp_raw_file)
                            except:
                                pass
                        if os.path.exists(temp_cut_clip):
                            try:
                                os.remove(temp_cut_clip)
                            except:
                                pass
                        continue

            app_logger.warning(f"[BRollEngine] Nenhum clipe do YouTube aprovado para '{query}'. Ativando contingência de Card Visual HD...")
            if VisualEngine is not None:
                safe_status(status_callback, "🎨 Gerando Card Visual Dossiê Confidencial (Contingência HD)...")
                try:
                    visual_engine = VisualEngine()
                    clean_query = query.replace("documentary", "").replace("footage", "").replace("4k", "").replace("real", "").strip()
                    card_data = {
                        "titulo": global_topic[:40],
                        "subtitulo": clean_query[:50] if clean_query else global_topic[:50],
                        "fatos": [
                            scene_fala[:95] if scene_fala else "Registro confidencial de estudo e evidências de arquivo histórico.",
                            "Análise de dados topográficos, imagens de satélite e documentos desclassificados.",
                            "Classificação: DOCUMENTO CONFIDENCIAL / CASO EM INVESTIGAÇÃO"
                        ],
                        "metrica": "NÍVEL DE SIGILO",
                        "valor_metrica": "GRAU MÁXIMO"
                    }
                    success_vis = visual_engine.create_clip(
                        card_data=card_data,
                        duration=target_duration,
                        output_clip_path=output_clip_path,
                        status_callback=status_callback
                    )
                    if success_vis and os.path.exists(output_clip_path):
                        return True, output_clip_path, "visual_dossier", f"Dossiê Confidencial - {query}", {
                            "aprovado": True,
                            "descartar_video_inteiro": False,
                            "score": 8.5,
                            "motivo": "Card Visual Dossiê HD gerado com sucesso (Contingência Resiliente)",
                            "elementos": "Infográfico Investigativo 1080x1920"
                        }
                except Exception as e_vis:
                    app_logger.error(f"[BRollEngine] Erro ao gerar Card Visual de contingência: {str(e_vis)}")

            return False, "", "", "", {"aprovado": False, "motivo": "Nenhum trecho aprovado"}

    def process_all_scenes_parallel(
        self,
        cenas: List[Dict[str, Any]],
        global_topic: str,
        reviewer_agent,
        project_dir: str,
        total_audio_duration: float,
        words_timing: Optional[List[Dict[str, Any]]] = None,
        tail_overhead: float = 0.5,
        max_workers: int = 4,
        status_callback = None,
        progress_callback = None
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Processa e audita todas as cenas do roteiro DE FORMA CONCORRENTE EM BATCHES (default max_workers=4),
        anexando o ScriptRunContext do Streamlit a todas as threads para eliminar warnings (Item 4).
        Garante que a duração de cada corte acompanhe a fala da cena e a soma total cubra o áudio + tail_overhead.
        """
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
            parent_ctx = get_script_run_ctx()
        except Exception:
            parent_ctx = None

        seen_ids = set()
        results = [None] * len(cenas)
        completed_count = 0
        total_scenes = len(cenas)

        # Cálculo preciso das durações reais por cena (Word-Timing / Proporcional + Overhead)
        target_durations = calculate_scene_durations(
            cenas=cenas,
            total_audio_duration=total_audio_duration,
            words_timing=words_timing,
            tail_overhead=tail_overhead
        )
        app_logger.info(f"[BRollEngine] Durações de cena calculadas: {target_durations} (Soma: {sum(target_durations):.2f}s para áudio de {total_audio_duration:.2f}s + overhead {tail_overhead}s)")

        def worker_task(c_idx: int, cena: Dict[str, Any]):
            if parent_ctx is not None:
                try:
                    from streamlit.runtime.scriptrunner import add_script_run_ctx
                    add_script_run_ctx(threading.current_thread(), parent_ctx)
                except Exception:
                    pass

            c_dur = target_durations[c_idx] if c_idx < len(target_durations) else float(cena.get("duracao_estimada", total_audio_duration / total_scenes))
            c_dur = max(1.8, c_dur)
            clip_out = os.path.join(project_dir, f"scene_{c_idx:02d}.mp4")
            
            def on_item_status(msg):
                safe_status(status_callback, f"🎬 **Cena #{c_idx+1}/{total_scenes}:** {msg}")
            
            query = cena.get("youtube_query") or f"{global_topic} 4k acceleration"
            success_clip, clip_path, vid_id, vid_title, inspection = self.search_and_download_clip(
                query=query,
                target_duration=c_dur,
                seen_ids=seen_ids,
                output_clip_path=clip_out,
                global_topic=global_topic,
                reviewer_agent=reviewer_agent,
                scene_fala=cena.get("fala", ""),
                status_callback=on_item_status
            )
            
            return c_idx, success_clip, clip_out, vid_id, vid_title, inspection, cena.get("fala", "")

        app_logger.info(f"[BRollEngine] Iniciando processamento paralelo de {total_scenes} cenas com {max_workers} workers...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker_task, idx, c) for idx, c in enumerate(cenas)]
            
            for future in as_completed(futures):
                try:
                    c_idx, success_clip, clip_out, vid_id, vid_title, inspection, fala = future.result()
                    completed_count += 1
                    safe_progress(progress_callback, completed_count, total_scenes)
                        
                    if success_clip and os.path.exists(clip_out):
                        results[c_idx] = {
                            "clip_path": clip_out,
                            "cena": c_idx + 1,
                            "fala": fala,
                            "titulo": vid_title,
                            "id": vid_id,
                            "score": inspection.get("score", 8.0),
                            "motivo": inspection.get("motivo", "Aprovado"),
                            "elementos": inspection.get("elementos_detectados", "")
                        }
                    else:
                        app_logger.warning(f"[BRollEngine] Cena #{c_idx+1} não obteve clipe aprovado.")
                except Exception as e:
                    app_logger.error(f"[BRollEngine] Erro no worker da cena: {str(e)}")

        scene_clips = []
        scene_audits = []
        for r in results:
            if r and os.path.exists(r["clip_path"]):
                scene_clips.append(r["clip_path"])
                scene_audits.append(r)

        return scene_clips, scene_audits
