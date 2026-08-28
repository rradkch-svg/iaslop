"""
Módulo de Tratamento de Resolução, Upscaling HD e Pós-Processamento Visual.
Garante que todos os clipes baixados e aprovados atinjam no mínimo a resolução Full HD 1080x1920 (9:16 Vertical),
aplicando filtros avançados de nitidez (Unsharp Masking), descompressão de ruído (Deband/Denoise)
e equalização de contraste cinematográfico para vídeos de mistério e documentários.
"""

import os
import re
import subprocess
import glob
from typing import Tuple, Optional, List, Dict, Any

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

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

class VideoResolutionEnhancer:
    """
    Motor de Upscaling, Restauração de Nitidez e Tratamento de Resolução HD para Clipes 9:16.
    """

    def __init__(self, target_width: int = 1080, target_height: int = 1920, min_source_resolution: int = 480):
        self.target_width = target_width
        self.target_height = target_height
        self.min_source_resolution = min_source_resolution
        self.ffmpeg_bin = find_ffmpeg_binary()
        self.ffprobe_bin = find_ffprobe_binary(self.ffmpeg_bin)

    def get_video_dimensions(self, video_path: str) -> Tuple[int, int]:
        """Obtém as dimensões atuais (largura, altura) de um arquivo de vídeo via ffprobe."""
        if not video_path or not os.path.exists(video_path):
            return 0, 0
        cmd = [
            self.ffprobe_bin, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            parts = res.stdout.strip().split("x")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return int(parts[0]), int(parts[1])
        except Exception:
            pass

        # Fallback usando ffmpeg -i caso ffprobe não esteja no PATH
        try:
            res = subprocess.run([self.ffmpeg_bin, "-i", video_path], capture_output=True, text=True, timeout=10)
            match = re.search(r"Stream #.*Video:.*,\s*(\d{2,5})x(\d{2,5})", res.stderr)
            if match:
                return int(match.group(1)), int(match.group(2))
        except Exception:
            pass

        return 0, 0

    def is_acceptable_resolution(self, video_path: str, min_height: int = 480) -> Tuple[bool, int, int]:
        """
        Inspeciona dimensões do vídeo para métricas e logs, permitindo upscaling para qualquer resolução.
        """
        w, h = self.get_video_dimensions(video_path)
        return True, w, h


    def build_enhancement_filter_graph(
        self,
        sharpen_strength: float = 0.85,
        denoise: bool = True,
        contrast_boost: float = 1.05,
        saturation_boost: float = 1.08,
        brightness_adjust: float = 0.01
    ) -> str:
        """
        Constrói a cadeia de filtros FFmpeg para upscaling inteligente e tratamento cinematográfico:
        1. Escala Lanczos com preservação de aspect ratio para 1080x1920 (9:16 Vertical)
        2. Recorte central simétrico (Crop 1080x1920)
        3. Redução de ruído e artefatos de compressão (hqdn3d)
        4. Máscara de Nitidez Inteligente (Unsharp Masking)
        5. Equalização de contraste e saturação cinematográfica (eq)
        6. Padronização de SAR 1:1 e cadência fluida de 30 FPS.
        """
        filters = []

        # 1. Escala de alta precisão com interpolação Lanczos e interpolação cromática total
        w = self.target_width
        h = self.target_height
        filters.append(f"scale={w}*16/9:{h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd+full_chroma_int")

        # 2. Recorte 9:16 centralizado
        filters.append(f"crop={w}:{h}:(in_w-{w})/2:(in_h-{h})/2")

        # 3. Denoise sutil para limpar artefatos de compressão em filmagens de arquivo
        if denoise:
            filters.append("hqdn3d=1.0:1.0:2.0:2.0")

        # 4. Unsharp Masking para ganho de micro-contraste e nitidez de borda
        if sharpen_strength > 0:
            la_val = min(1.5, max(0.2, sharpen_strength))
            ca_val = round(la_val * 0.5, 2)
            filters.append(f"unsharp=5:5:{la_val}:3:3:{ca_val}")

        # 5. Equalização de contraste e saturação
        filters.append(f"eq=contrast={contrast_boost:.2f}:brightness={brightness_adjust:.2f}:saturation={saturation_boost:.2f}")

        # 6. Aspect Ratio de Pixel (SAR) e Frame Rate estrito
        filters.append("setsar=1")
        filters.append("fps=30")

        return ",".join(filters)

    def enhance_clip(
        self,
        input_path: str,
        output_path: str,
        sharpen_strength: float = 0.85,
        denoise: bool = True,
        contrast_boost: float = 1.05,
        saturation_boost: float = 1.08,
        status_callback = None
    ) -> Tuple[bool, str]:
        """
        Aplica o tratamento completo de resolução HD e pós-processamento visual em um clipe de vídeo.
        Garante que o arquivo de saída esteja exatamente em 1080x1920 (9:16) com máxima nitidez.
        """
        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            return False, f"Arquivo de entrada inexistente ou vazio: {input_path}"

        with LogSpan("enhance_clip_resolution", extra={"input": input_path, "output": output_path}):
            orig_w, orig_h = self.get_video_dimensions(input_path)
            app_logger.info(f"[VideoEnhancer] Tratando resolução: {input_path} ({orig_w}x{orig_h}) ➔ HD 1080x1920")

            if status_callback:
                status_callback(f"✨ Aprimorando resolução para Full HD 1080x1920 com Unsharp Masking ({orig_w}x{orig_h} ➔ HD)...")

            temp_output = output_path + ".tmp.mp4"
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except:
                    pass

            filter_graph = self.build_enhancement_filter_graph(
                sharpen_strength=sharpen_strength,
                denoise=denoise,
                contrast_boost=contrast_boost,
                saturation_boost=saturation_boost
            )

            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", input_path,
                "-vf", filter_graph,
                "-c:v", "libx264",
                "-crf", "16",
                "-preset", "fast",
                "-profile:v", "high",
                "-level", "4.1",
                "-pix_fmt", "yuv420p",
                "-an",
                temp_output
            ]

            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                os.rename(temp_output, output_path)
                app_logger.info(f"[VideoEnhancer] Clipe aprimorado com sucesso: {output_path} ({os.path.getsize(output_path)} bytes)")
                return True, output_path
            except subprocess.CalledProcessError as e:
                app_logger.warning(f"[VideoEnhancer] Falha no filtro avançado ({e.stderr}). Tentando fallback Lanczos direto...")
                
                # Fallback direto com Lanczos básico
                fallback_filter = f"scale={self.target_width}:{self.target_height}:force_original_aspect_ratio=increase:flags=lanczos,crop={self.target_width}:{self.target_height},setsar=1,fps=30"
                cmd_fallback = [
                    self.ffmpeg_bin, "-y",
                    "-i", input_path,
                    "-vf", fallback_filter,
                    "-c:v", "libx264",
                    "-crf", "16",
                    "-preset", "fast",
                    "-pix_fmt", "yuv420p",
                    "-an",
                    output_path
                ]
                try:
                    subprocess.run(cmd_fallback, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    app_logger.info(f"[VideoEnhancer] Clipe aprimorado via fallback Lanczos: {output_path}")
                    return True, output_path
                except subprocess.CalledProcessError as e2:
                    err_msg = f"Erro no upscaling FFmpeg: {e2.stderr}"
                    app_logger.error(err_msg)
                    return False, err_msg

# Instância padrão global
DEFAULT_VIDEO_ENHANCER = VideoResolutionEnhancer(min_source_resolution=480)
