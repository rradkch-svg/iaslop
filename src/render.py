import os
import subprocess
import glob
from typing import List, Tuple, Optional, Any, Union, Dict

try:
    from .logger import app_logger, LogSpan
    from .bgm_engine import DEFAULT_BGM_ENGINE
except ImportError:
    from logger import app_logger, LogSpan
    try:
        from bgm_engine import DEFAULT_BGM_ENGINE
    except ImportError:
        DEFAULT_BGM_ENGINE = None

def find_ffmpeg_binary() -> str:
    """Busca o executável do FFmpeg em múltiplos locais conhecidos (static-ffmpeg, imageio-ffmpeg, WinGet, PATH)."""
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

def assemble_multi_scene_video(
    clip_paths: Optional[List[Any]] = None,
    audio_path: Optional[str] = None,
    ass_path: Optional[str] = None,
    output_path: Optional[str] = None,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.12,
    subtitles_path: Optional[str] = None,
    media_scenes: Optional[List[Any]] = None,
    topic_context: Optional[Dict[str, Any]] = None,
    status_callback = None,
    *args,
    **kwargs
) -> Tuple[bool, str]:
    """
    Concatena múltiplos clipes 9:16 (1080x1920), funde com a narração de áudio e
    trilha sonora de suspense (BGM com volume reduzido e ducking) e queima as legendas dinâmicas ASS.
    """
    actual_clips = clip_paths or media_scenes or kwargs.get("media_scenes") or []
    actual_ass = ass_path or subtitles_path or kwargs.get("subtitles_path") or ""
    actual_out = output_path or kwargs.get("output_path") or ""
    actual_audio = audio_path or kwargs.get("audio_path") or ""

    with LogSpan("assemble_multi_scene_video", extra={"clips_count": len(actual_clips), "output": actual_out}):
        ffmpeg_bin = find_ffmpeg_binary()
        
        if not actual_clips:
            return False, "Nenhum clipe de vídeo fornecido para montagem."

        # Extrai caminhos válidos de arquivos de vídeo a partir de strings ou dicionários de cena
        raw_clip_files = []
        for item in actual_clips:
            if isinstance(item, str):
                raw_clip_files.append(item)
            elif isinstance(item, dict):
                f = item.get("file") or item.get("video_file") or item.get("path")
                if f:
                    raw_clip_files.append(f)

        valid_clips = [cp for cp in raw_clip_files if os.path.exists(cp) and os.path.getsize(cp) > 0]
        if not valid_clips:
            return False, "Nenhum dos arquivos de clipe existe no disco."

        work_dir = os.path.dirname(actual_out) if actual_out else os.getcwd()
        os.makedirs(work_dir, exist_ok=True)
        concat_txt = os.path.join(work_dir, "scenes_concat.txt")
        combined_scenes_mp4 = os.path.join(work_dir, "combined_scenes.mp4")

        # 1. Gerar arquivo de lista para concatenação segura
        with open(concat_txt, "w", encoding="utf-8") as f:
            for cp in valid_clips:
                safe_cp = os.path.abspath(cp).replace("\\", "/")
                f.write(f"file '{safe_cp}'\n")

        if status_callback:
            status_callback("⚡ Concatenando trilha de cenas (B-rolls e visual 9:16)...")

        # 2. Concatenação de vídeo com escala Lanczos e qualidade HD
        cmd_concat = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-an",
            combined_scenes_mp4
        ]

        try:
            subprocess.run(cmd_concat, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            app_logger.info(f"[RenderEngine] Cenas unificadas em: {combined_scenes_mp4}")
        except subprocess.CalledProcessError as e:
            app_logger.error(f"[RenderEngine] Falha na concatenação de cenas: {e.stderr}")
            return False, f"Falha na união de cenas: {e.stderr}"

        # 3. Determina a trilha de música de fundo (BGM de suspense)
        chosen_bgm = bgm_path
        if not chosen_bgm and DEFAULT_BGM_ENGINE:
            topic_str = ""
            if topic_context and isinstance(topic_context, dict):
                topic_str = f"{topic_context.get('tema', '')} {topic_context.get('hook', '')}"
            chosen_bgm = DEFAULT_BGM_ENGINE.get_bgm_for_topic(topic_title=topic_str)

        has_bgm = bool(chosen_bgm and os.path.exists(chosen_bgm))
        if has_bgm:
            app_logger.info(f"[RenderEngine] Aplicando BGM de suspense: {chosen_bgm} (Volume: {bgm_volume:.2f})")

        # 4. Composição Final com Áudio, BGM e Legendas ASS Queimadas em HD (1080x1920)
        has_ass = bool(actual_ass and os.path.exists(actual_ass))
        safe_ass_path = os.path.abspath(actual_ass).replace("\\", "/").replace(":", "\\:") if has_ass else ""

        if status_callback:
            status_callback("🎨 Queimando legendas dinâmicas ASS e mixando narração + BGM de suspense...")

        if has_bgm:
            # Mixagem com BGM em loop, ducking de volume e fade-in
            filter_complex_parts = [
                f"[1:a]volume=1.0[voice]",
                f"[2:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.3f},afade=t=in:ss=0:d=1.0[bgm]",
                f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            ]
            if has_ass:
                filter_complex_parts.insert(0, f"[0:v]ass='{safe_ass_path}'[vout]")
                cmd_final = [
                    ffmpeg_bin, "-y",
                    "-i", combined_scenes_mp4,
                    "-i", actual_audio,
                    "-i", chosen_bgm,
                    "-filter_complex", ";".join(filter_complex_parts),
                    "-map", "[vout]",
                    "-map", "[aout]",
                    "-c:v", "libx264",
                    "-crf", "18",
                    "-preset", "fast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    actual_out
                ]
            else:
                cmd_final = [
                    ffmpeg_bin, "-y",
                    "-i", combined_scenes_mp4,
                    "-i", actual_audio,
                    "-i", chosen_bgm,
                    "-filter_complex", ";".join(filter_complex_parts),
                    "-map", "0:v",
                    "-map", "[aout]",
                    "-c:v", "libx264",
                    "-crf", "18",
                    "-preset", "fast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    actual_out
                ]
        else:
            # Composição direta sem BGM
            if has_ass:
                cmd_final = [
                    ffmpeg_bin, "-y",
                    "-i", combined_scenes_mp4,
                    "-i", actual_audio,
                    "-vf", f"ass='{safe_ass_path}'",
                    "-af", "apad",
                    "-c:v", "libx264",
                    "-crf", "18",
                    "-preset", "fast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    actual_out
                ]
            else:
                cmd_final = [
                    ffmpeg_bin, "-y",
                    "-i", combined_scenes_mp4,
                    "-i", actual_audio,
                    "-af", "apad",
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    actual_out
                ]

        try:
            subprocess.run(cmd_final, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            app_logger.info(f"[RenderEngine] Vídeo final renderizado com sucesso: {actual_out} ({os.path.getsize(actual_out)} bytes)")
            return True, "Vídeo 9:16 final renderizado com sucesso!"
        except subprocess.CalledProcessError as e:
            app_logger.warning(f"[RenderEngine] Falha na renderização com filtros avançados: {e.stderr}. Executando fallback seguro...")
            
            # Fallback de contingência sem filtro ASS e mixagem direta
            cmd_fallback = [
                ffmpeg_bin, "-y",
                "-i", combined_scenes_mp4,
                "-i", actual_audio,
                "-af", "apad",
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                actual_out
            ]
            try:
                subprocess.run(cmd_fallback, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                app_logger.info(f"[RenderEngine] Vídeo final (modo de contingência) renderizado: {actual_out}")
                return True, "Vídeo renderizado com sucesso (modo de contingência)!"
            except subprocess.CalledProcessError as e2:
                err_msg = f"Erro crítico no FFmpeg: {e2.stderr}"
                app_logger.error(err_msg)
                return False, err_msg

# Alias para retrocompatibilidade
render_final_video = assemble_multi_scene_video
