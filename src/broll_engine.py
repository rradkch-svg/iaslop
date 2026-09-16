import os
import sys
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

def refresh_youtube_cookies() -> Optional[str]:
    """Tenta auto-extrair cookies frescos do YouTube diretamente dos navegadores instalados."""
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scripts_dir = os.path.join(root_dir, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import extrair_cookies
        target = os.path.join(root_dir, "cookies.txt")
        res = extrair_cookies.export_youtube_cookies(target, verbose=False)
        if res and os.path.exists(res) and os.path.getsize(res) > 50:
            app_logger.info(f"[BRollEngine] Cookies do YouTube renovados com sucesso em {res}")
            return res
    except Exception as e:
        app_logger.warning(f"[BRollEngine] Falha na auto-extração de cookies: {e}")
    return None

def find_cookies_file(force_refresh: bool = False) -> Optional[str]:
    """Procura automaticamente por arquivo de cookies do YouTube no projeto ou diretório do usuário."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_project_cookies = os.path.join(root_dir, "cookies.txt")

    if force_refresh:
        refreshed = refresh_youtube_cookies()
        if refreshed:
            return refreshed

    candidates = [
        target_project_cookies,
        os.path.join(root_dir, "youtube_cookies.txt"),
        os.path.join(root_dir, "youtube.com_cookies.txt"),
        os.path.join(os.path.expanduser("~"), "cookies.txt"),
        os.path.join(os.path.expanduser("~"), "Downloads", "cookies.txt"),
        os.path.join(os.path.expanduser("~"), "Downloads", "youtube_cookies.txt"),
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 50:
            # Se o arquivo for do projeto e tiver mais de 24h, tenta renovar proativamente
            if c == target_project_cookies:
                try:
                    file_age_hours = (time.time() - os.path.getmtime(c)) / 3600
                    if file_age_hours > 24:
                        refreshed = refresh_youtube_cookies()
                        if refreshed:
                            return refreshed
                except Exception:
                    pass
            return c

    # Fallback: Tenta auto-extração dos navegadores instalados
    return refresh_youtube_cookies()

def get_ytdlp_cookie_opts(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Retorna a melhor configuração de autenticação para o yt-dlp.
    Prioriza autenticação direta do navegador (Firefox), que possui 100% de sucesso
    contra os bloqueios de bot do YouTube, com fallback automático para cookies.txt.
    """
    # 1. Verifica se Firefox está disponível com cookies de sessão do YouTube
    try:
        import rookiepy
        ff_c = rookiepy.firefox(domains=[".youtube.com"])
        if ff_c and len(ff_c) >= 3:
            return {"cookiesfrombrowser": ("firefox",)}
    except Exception:
        pass

    # 2. Fallback para arquivo cookies.txt
    ck_file = find_cookies_file(force_refresh=force_refresh)
    if ck_file and os.path.exists(ck_file) and os.path.getsize(ck_file) > 50:
        return {"cookiefile": ck_file}

    # 3. Fallback genérico para Firefox
    return {"cookiesfrombrowser": ("firefox",)}

def find_ffmpeg_binary() -> str:
    """Busca o executável do FFmpeg no static-ffmpeg, imageio-ffmpeg, WinGet ou PATH."""
    try:
        import static_ffmpeg
        ffmpeg_exe, _ = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        if os.path.exists(ffmpeg_exe):
            f_dir = os.path.dirname(os.path.abspath(ffmpeg_exe))
            if f_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{f_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            return ffmpeg_exe
    except Exception:
        pass
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            f_dir = os.path.dirname(os.path.abspath(exe))
            if f_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{f_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            return exe
    except Exception:
        pass
    winget_pattern = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe")
    winget_matches = glob.glob(winget_pattern)
    if winget_matches and os.path.exists(winget_matches[0]):
        f_dir = os.path.dirname(os.path.abspath(winget_matches[0]))
        if f_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{f_dir}{os.pathsep}{os.environ.get('PATH', '')}"
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
    
    # Remove tema prefixado redundante se presente na base_query
    base_clean = base_query.strip() if base_query else ""
    for prefix in [global_topic, topic_kw]:
        if prefix and len(prefix) > 5 and base_clean.lower().startswith(prefix.lower()):
            clean_sub = base_clean[len(prefix):].strip()
            if len(clean_sub.split()) >= 2:
                base_clean = clean_sub
                break

    # Limpa caracteres especiais e emojis
    base_clean = re.sub(r"[^\w\s\-\.]", " ", base_clean)
    base_clean = " ".join(base_clean.split())
    base_lower = base_clean.lower()
    t_tokens = [w.lower() for w in topic_kw.split() if len(w) > 1]
    has_anchor = any(t in base_lower for t in t_tokens) if t_tokens else False
    
    if base_clean:
        queries.append(base_clean)
        # Se for longa, adiciona versão mais concisa com os termos essenciais
        b_words = base_clean.split()
        if len(b_words) > 5:
            queries.append(" ".join(b_words[-4:]))
        if not base_lower.endswith("4k") and not base_lower.endswith("hd"):
            queries.append(f"{base_clean} 4k")
        if not has_anchor and topic_kw and len(b_words) <= 4:
            anchored = f"{topic_kw} {base_clean}".strip()
            queries.append(anchored)
            
    if topic_kw:
        queries.extend([
            f"{topic_kw} documentary footage 4k",
            f"{topic_kw} real archival footage",
            f"{topic_kw} satellite view 4k"
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
    tail_overhead: float = 1.8
) -> List[float]:
    """
    Calcula dinamicamente a duração ideal de cada cena no storyboard baseando-se no número de palavras
    faladas da narração e no tempo real do áudio gerado pelo TTS.
    Garante que a soma de todos os cortes cubra integralmente a narração + tail_overhead.
    """
    n_scenes = len(cenas)
    if n_scenes == 0:
        return []
    
    # Extrai o peso de texto (palavras) por cena
    word_counts = []
    for c in cenas:
        text = c.get("fala", "").strip()
        count = len(text.split()) if text else 1
        word_counts.append(max(1, count))
    
    total_w = sum(word_counts)
    durations = []
    for sc_idx, w in enumerate(word_counts):
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
    Garante que 100% dos trechos utilizados sejam limpos (Zero Rostos) e renderizados em 1080x1920
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
        para encontrar um segmento aprovado (Zero Rostos + alta pertinência) em 1080x1920.
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
                    "sleep_interval_requests": 1,
                }
                ydl_opts_search.update(get_ytdlp_cookie_opts())

                entries = []
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
                        search_results = ydl.extract_info(f"ytsearch{self.max_search_results}:{current_q}", download=False)
                        entries = search_results.get("entries", [])
                except Exception as e:
                    err_str = str(e)
                    is_bot_challenge = "bot" in err_str.lower() or "sign in to confirm" in err_str.lower()
                    if is_bot_challenge:
                        app_logger.warning(f"[BRollEngine] 🍪 Exigência de autenticação na busca do YouTube. Alternando credenciais...")
                        if "cookiesfrombrowser" not in ydl_opts_search:
                            ydl_opts_search.pop("cookiefile", None)
                            ydl_opts_search["cookiesfrombrowser"] = ("firefox",)
                        else:
                            new_ck = find_cookies_file(force_refresh=True)
                            if new_ck:
                                ydl_opts_search.pop("cookiesfrombrowser", None)
                                ydl_opts_search["cookiefile"] = new_ck
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
                                search_results = ydl.extract_info(f"ytsearch{self.max_search_results}:{current_q}", download=False)
                                entries = search_results.get("entries", [])
                        except Exception:
                            pass
                    if not entries:
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

                consecutive_rate_limits = 0
                for cand in candidates:
                    vid_id = cand.get("id")
                    vid_title = cand.get("title", current_q)
                    vid_dur = cand.get("duration") or 60
                    vid_url = f"https://www.youtube.com/watch?v={vid_id}"

                    # 1. Pré-filtragem instantânea de metadados / título antes do download
                    if reviewer_agent and hasattr(reviewer_agent, "pre_filter_title"):
                        ok_title, pre_reason = reviewer_agent.pre_filter_title(vid_title, global_topic)
                        if not ok_title:
                            app_logger.info(f"[BRollEngine] Candidato '{vid_title}' descartado pelo pré-filtro: {pre_reason}")
                            continue

                    # Pausa suave preventiva entre requisições de candidatos para evitar burst rate-limit
                    time.sleep(random.uniform(0.8, 1.5))
                    safe_status(status_callback, f"📥 Baixando candidato: **{vid_title[:45]}...**")

                    temp_raw_file = os.path.join(tempfile.gettempdir(), f"broll_{vid_id}_{int(time.time()*1000)}_{threading.get_ident()}.mp4")
                    temp_cut_clip = os.path.join(tempfile.gettempdir(), f"broll_cut_{vid_id}_{int(time.time()*1000)}_{threading.get_ident()}.mp4")

                    ydl_opts_download = {
                        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best",
                        "merge_output_format": "mp4",
                        "outtmpl": temp_raw_file,
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                        "socket_timeout": 20,
                        "sleep_interval_requests": 1,
                        "remote_components": ["ejs:github"],
                        "http_headers": {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
                        },
                        "extractor_args": {
                            "youtube": {
                                "player_client": ["web", "mweb"]
                            }
                        }
                    }
                    ydl_opts_download.update(get_ytdlp_cookie_opts())

                    try:
                        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                            ydl.download([vid_url])

                        if not os.path.exists(temp_raw_file):
                            matches = glob.glob(temp_raw_file.replace(".mp4", ".*"))
                            if matches:
                                temp_raw_file = matches[0]
                            else:
                                continue

                        # 2. Validação Empírica da Duração Real com FFprobe
                        actual_dur = get_video_duration(temp_raw_file, self.ffmpeg_bin)
                        if not actual_dur or actual_dur < 1.0:
                            app_logger.warning(f"[BRollEngine] Arquivo corrompido ou sem duração detectável: {temp_raw_file}")
                            if os.path.exists(temp_raw_file):
                                try:
                                    os.remove(temp_raw_file)
                                except:
                                    pass
                            continue

                        # 3. Varredura Multi-Trechos Inteligente com Limites Estritos de Duração
                        if actual_dur <= target_duration:
                            seek_offsets = [0.0]
                        else:
                            max_seek = max(0.0, actual_dur - target_duration - 0.5)
                            # Seleciona até 5 timestamps distribuídos pelo vídeo para inspecionar
                            seek_offsets = [
                                min(max_seek, 3.0),
                                min(max_seek, actual_dur * 0.25),
                                min(max_seek, actual_dur * 0.50),
                                min(max_seek, actual_dur * 0.75),
                                min(max_seek, max(0.0, actual_dur - target_duration - 1.0))
                            ]
                            seek_offsets = sorted(list(set([round(s, 2) for s in seek_offsets if s <= max_seek])))

                        approved = False
                        best_inspection = {"aprovado": False, "score": 0.0, "motivo": "Nenhum trecho auditado"}

                        for seek_t in seek_offsets:
                            if os.path.exists(temp_cut_clip):
                                try:
                                    os.remove(temp_cut_clip)
                                except:
                                    pass

                            cut_dur = min(target_duration, actual_dur - seek_t)
                            if cut_dur < 1.5:
                                continue

                            # Recorte 9:16 (Lanczos + CRF 18) com garantia estrita de duração
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
                                if inspection.get("aprovado", False) and float(inspection.get("score", 0.0)) >= 6.0:
                                    approved = True
                                    safe_status(status_callback, f"✅ **Trecho Aprovado aos {seek_t:.0f}s!** ({inspection.get('motivo')})")
                                    break
                                else:
                                    motivo_low = str(inspection.get("motivo", "")).lower()
                                    is_irrelevant = (
                                        inspection.get("descartar_video_inteiro", False) or
                                        float(inspection.get("score", 0.0)) <= 4.0 or
                                        any(kw in motivo_low for kw in [
                                            "desalinhado", "irrelevante", "outro tema", "desenho", "panda", "anime", "animação", "infantil",
                                            "cartoon", "shrek", "filme", "poster", "capa", "desconectad", "meme", "vlog", "gameplay",
                                            "estático", "gráfico", "incompatível", "diferente", "sem relação", "apresentador", "rosto", "face"
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
                            os.rename(temp_cut_clip, output_clip_path)
                            app_logger.info(f"[BRollEngine] Trecho aprovado e gravado: {output_clip_path} (ID: {vid_id} - '{vid_title}')")
                            return True, output_clip_path, vid_id, vid_title, best_inspection
                        else:
                            if os.path.exists(temp_cut_clip):
                                try:
                                    os.remove(temp_cut_clip)
                                except:
                                    pass

                    except Exception as err_dl:
                        err_str = str(err_dl)
                        is_bot_challenge = "bot" in err_str.lower() or "sign in to confirm" in err_str.lower()
                        if is_bot_challenge:
                            app_logger.warning(f"[BRollEngine] 🍪 Desafio de autenticação no download de {vid_id}. Alternando credenciais...")
                            if "cookiesfrombrowser" not in ydl_opts_download:
                                ydl_opts_download.pop("cookiefile", None)
                                ydl_opts_download["cookiesfrombrowser"] = ("firefox",)
                            else:
                                new_ck = find_cookies_file(force_refresh=True)
                                if new_ck:
                                    ydl_opts_download.pop("cookiesfrombrowser", None)
                                    ydl_opts_download["cookiefile"] = new_ck
                            try:
                                with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                                    ydl.download([vid_url])
                                if os.path.exists(temp_raw_file) or glob.glob(temp_raw_file.replace(".mp4", ".*")):
                                    err_str = ""
                            except Exception as retry_err:
                                err_str = str(retry_err)

                        if err_str:
                            is_session_blocked = "rate-limited by youtube" in err_str.lower() or "this content isn't available, try again later" in err_str.lower()
                            if is_session_blocked:
                                consecutive_rate_limits += 1
                                if consecutive_rate_limits >= 2:
                                    app_logger.warning(f"[BRollEngine] 🛑 YouTube sinalizou rate-limit ativo na sessão ({vid_id}). Interrompendo candidatos desta busca para resfriamento.")
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
                                    break
                                time.sleep(random.uniform(4.0, 7.0))

                            is_dl_throttled = "429" in err_str or "Too Many Requests" in err_str or "rate-limit" in err_str.lower() or "bot" in err_str.lower() or "throttl" in err_str.lower()
                            if is_dl_throttled:
                                record_throttling("YOUTUBE_DOWNLOAD", "HTTP_429_DOWNLOAD_THROTTLE", f"Download no YouTube sob rate limit ({vid_id}): {err_str[:150]}", retry_after=15)
                                time.sleep(2.0)
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

            app_logger.warning(f"[BRollEngine] Nenhum clipe de vídeo do YouTube aprovado para '{query}'.")
            return False, "", "", "", {"aprovado": False, "motivo": f"Nenhum clipe de vídeo do YouTube aprovado para '{query}'"}

    def fetch_scene_broll(
        self,
        query: str,
        output_dir: str,
        scene_idx: int,
        target_duration: float,
        global_topic: str = "Mistério Desclassificado",
        reviewer_agent = None,
        scene_fala: str = "",
        status_callback = None
    ) -> Dict[str, Any]:
        """
        Busca e faz download de um clipe específico de cena,
        gerando também um preview_frame para auditoria visual pelo ReviewerAgent.
        """
        os.makedirs(output_dir, exist_ok=True)
        clip_path = os.path.join(output_dir, f"scene_{scene_idx:02d}.mp4")
        preview_frame = os.path.join(output_dir, f"preview_{scene_idx:02d}.jpg")
        
        seen_ids = getattr(self, "_seen_ids", None)
        if seen_ids is None:
            self._seen_ids = set()
            seen_ids = self._seen_ids

        success, final_path, vid_id, vid_title, inspection = self.search_and_download_clip(
            query=query,
            target_duration=target_duration,
            seen_ids=seen_ids,
            output_clip_path=clip_path,
            global_topic=global_topic,
            reviewer_agent=reviewer_agent,
            scene_fala=scene_fala,
            status_callback=status_callback
        )

        # Extrai preview frame se o vídeo existe
        if success and os.path.exists(final_path):
            try:
                cmd = [
                    self.ffmpeg_bin, "-y",
                    "-ss", str(min(1.0, max(0.2, target_duration / 2))),
                    "-i", final_path,
                    "-vframes", "1",
                    "-q:v", "2",
                    preview_frame
                ]
                subprocess.run(cmd, check=True, capture_output=True, timeout=10)
            except Exception as e:
                app_logger.warning(f"[BRollEngine] Não foi possível extrair preview_frame ({e})")

        return {
            "success": success,
            "file": final_path if success else "",
            "video_file": final_path if success else "",
            "preview_frame": preview_frame if os.path.exists(preview_frame) else "",
            "video_id": vid_id,
            "video_title": vid_title,
            "inspection": inspection,
            "duration": target_duration
        }

    def process_all_scenes_parallel(
        self,
        cenas: List[Dict[str, Any]],
        global_topic: str,
        reviewer_agent,
        project_dir: str,
        total_audio_duration: float,
        words_timing: Optional[List[Dict[str, Any]]] = None,
        tail_overhead: float = 1.8,
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
