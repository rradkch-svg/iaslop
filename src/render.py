import os
import subprocess
import glob
from typing import List, Tuple, Optional, Any, Union, Dict

try:
    from .logger import app_logger, LogSpan
    from .bgm_engine import DEFAULT_BGM_ENGINE
    from .video_enhancer import DEFAULT_VIDEO_ENHANCER, find_ffmpeg_binary
    from .sfx_engine import DEFAULT_SFX_ENGINE
except ImportError:
    from logger import app_logger, LogSpan
    try:
        from bgm_engine import DEFAULT_BGM_ENGINE
    except ImportError:
        DEFAULT_BGM_ENGINE = None
    try:
        from video_enhancer import DEFAULT_VIDEO_ENHANCER, find_ffmpeg_binary
    except ImportError:
        DEFAULT_VIDEO_ENHANCER = None
        def find_ffmpeg_binary() -> str:
            return "ffmpeg"
    try:
        from sfx_engine import DEFAULT_SFX_ENGINE
    except ImportError:
        DEFAULT_SFX_ENGINE = None

def assemble_multi_scene_video(
    clip_paths: Optional[List[Any]] = None,
    audio_path: Optional[str] = None,
    ass_path: Optional[str] = None,
    output_path: Optional[str] = None,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.12,
    sfx_path: Optional[str] = None,
    sfx_volume: float = 0.35,
    subtitles_path: Optional[str] = None,
    media_scenes: Optional[List[Any]] = None,
    topic_context: Optional[Dict[str, Any]] = None,
    status_callback = None,
    *args,
    **kwargs
) -> Tuple[bool, str]:
    """
    Concatena múltiplos clipes 9:16, aplica tratamento de resolução HD e nitidez,
    funde com narração de voz, trilha sonora BGM (ducking) e efeitos sonoros SFX (whooshes, sinos, clicks)
    e queima legendas dinâmicas ASS em alta definição 1080x1920.
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

        # 2. Concatenação de vídeo com escala Lanczos e qualidade HD limpa
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


        # 3. Determina a trilha BGM de suspense
        chosen_bgm = bgm_path
        if not chosen_bgm and DEFAULT_BGM_ENGINE:
            topic_str = ""
            if topic_context and isinstance(topic_context, dict):
                topic_str = f"{topic_context.get('tema', '')} {topic_context.get('hook', '')}"
            chosen_bgm = DEFAULT_BGM_ENGINE.get_bgm_for_topic(topic_title=topic_str)

        has_bgm = bool(chosen_bgm and os.path.exists(chosen_bgm))
        if has_bgm:
            app_logger.info(f"[RenderEngine] Trilha BGM: {chosen_bgm} (Volume: {bgm_volume:.2f})")

        # 4. Determina a trilha SFX sincronizada
        has_sfx = bool(sfx_path and os.path.exists(sfx_path) and os.path.getsize(sfx_path) > 1000)
        if has_sfx:
            app_logger.info(f"[RenderEngine] Trilha SFX: {sfx_path} (Volume: {sfx_volume:.2f})")

        # 5. Composição Master Final Multi-Track (Vídeo + Voz + BGM + SFX + Legendas ASS)
        has_ass = bool(actual_ass and os.path.exists(actual_ass))
        safe_ass_path = os.path.abspath(actual_ass).replace("\\", "/").replace(":", "\\:") if has_ass else ""

        if status_callback:
            status_callback("🎨 Renderizando Composição Master (Vídeo HD + Voz + BGM Ducked + SFX + Legendas ASS)...")

        # Montagem dinâmica do comando FFmpeg
        # input 0 = combined_scenes_mp4 (video), input 1 = actual_audio (voice)
        cmd_inputs = [ffmpeg_bin, "-y", "-i", combined_scenes_mp4, "-i", actual_audio]
        current_input_idx = 2

        filter_complex_parts = [f"[1:a]volume=1.0[voice]"]
        audio_mix_inputs = ["[voice]"]

        # Entrada 2: BGM
        if has_bgm:
            cmd_inputs.extend(["-i", chosen_bgm])
            bgm_in_idx = current_input_idx
            current_input_idx += 1
            filter_complex_parts.append(f"[{bgm_in_idx}:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.3f},afade=t=in:ss=0:d=1.0[bgm]")
            audio_mix_inputs.append("[bgm]")

        # Entrada 3: SFX
        if has_sfx:
            cmd_inputs.extend(["-i", sfx_path])
            sfx_in_idx = current_input_idx
            current_input_idx += 1
            filter_complex_parts.append(f"[{sfx_in_idx}:a]volume={sfx_volume:.3f}[sfx]")
            audio_mix_inputs.append("[sfx]")

        # Mixagem de áudio
        if len(audio_mix_inputs) > 1:
            mix_str = "".join(audio_mix_inputs) + f"amix=inputs={len(audio_mix_inputs)}:duration=first:dropout_transition=2[aout]"
            filter_complex_parts.append(mix_str)
            audio_map = "[aout]"
        else:
            audio_map = "1:a"

        # Legendas ASS no vídeo
        if has_ass:
            filter_complex_parts.insert(0, f"[0:v]ass='{safe_ass_path}'[vout]")
            video_map = "[vout]"
        else:
            video_map = "0:v"

        cmd_final = list(cmd_inputs)
        if filter_complex_parts:
            cmd_final.extend(["-filter_complex", ";".join(filter_complex_parts)])
            cmd_final.extend(["-map", video_map, "-map", audio_map])
        else:
            cmd_final.extend(["-map", "0:v", "-map", "1:a"])

        cmd_final.extend([
            "-c:v", "libx264",
            "-crf", "17",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            actual_out
        ])

        try:
            subprocess.run(cmd_final, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            app_logger.info(f"[RenderEngine] Composição final Full HD renderizada: {actual_out} ({os.path.getsize(actual_out)} bytes)")
            return True, "Vídeo 9:16 Full HD renderizado com sucesso!"
        except subprocess.CalledProcessError as e:
            app_logger.warning(f"[RenderEngine] Falha na composição avançada ({e.stderr}). Tentando fallback de mixagem direta...")
            
            # Fallback de contingência
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
                app_logger.info(f"[RenderEngine] Vídeo final renderizado via fallback: {actual_out}")
                return True, "Vídeo renderizado com sucesso (modo de contingência)!"
            except subprocess.CalledProcessError as e2:
                err_msg = f"Erro crítico no FFmpeg: {e2.stderr}"
                app_logger.error(err_msg)
                return False, err_msg

# Alias para retrocompatibilidade
render_final_video = assemble_multi_scene_video
