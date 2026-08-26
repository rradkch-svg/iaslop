import subprocess
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
from backend.app.config import settings

def run_ffmpeg(args: List[str]) -> Tuple[bool, str]:
    """Runs FFmpeg command and returns (success, output_or_error)"""
    cmd = [settings.FFMPEG_EXE, "-y"] + args
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"FFmpeg Error (Exit {process.returncode}):\n{stderr}")
            return False, stderr
        return True, stdout
    except Exception as e:
        print(f"FFmpeg Execution Exception: {e}")
        return False, str(e)

def get_media_duration(file_path: Path) -> float:
    """Extracts duration in seconds using FFmpeg/ffprobe or reading headers"""
    cmd = [
        settings.FFMPEG_EXE,
        "-i", str(file_path)
    ]
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        _, stderr = process.communicate()
        # Parse Duration: 00:00:12.34
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
        if match:
            hours = float(match.group(1))
            minutes = float(match.group(2))
            seconds = float(match.group(3))
            return hours * 3600 + minutes * 60 + seconds
    except Exception as e:
        print(f"Error getting media duration: {e}")
    return 0.0

def escape_ffmpeg_path(path: Path) -> str:
    """Escapes Windows path for FFmpeg filter arguments (subtitles filter)"""
    s = str(path.resolve()).replace("\\", "/")
    s = s.replace(":", "\\:")
    return s

def generate_ken_burns_clip(
    image_path: Path,
    output_path: Path,
    duration: float,
    width: int = 1080,
    height: int = 1920,
    motion_type: str = "zoom_in",
    fps: int = 30
) -> bool:
    """
    Creates a dynamic animated MP4 clip from a still image using Ken Burns effect.
    Supports zoom_in, zoom_out, pan_left, pan_right.
    """
    total_frames = max(int(duration * fps), fps)
    
    # Calculate smooth zoom/pan expressions for zoompan filter
    # zoompan takes input image and outputs width x height at fps
    if motion_type == "zoom_in":
        # Zooms in from 1.0 to 1.18 smoothly
        zoom_expr = f"min(zoom+0.0012,1.20)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion_type == "zoom_out":
        # Zooms out from 1.20 to 1.0
        zoom_expr = f"if(eq(on,1),1.20,max(1.0,zoom-0.0012))"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion_type == "pan_left":
        # Slow pan from right to left with slight 1.15 zoom
        zoom_expr = "1.15"
        x_expr = f"min(iw-iw/zoom,max(0,(1-(on/{total_frames}))*(iw-iw/zoom)))"
        y_expr = "ih/2-(ih/zoom/2)"
    else:  # pan_right or default
        zoom_expr = "1.15"
        x_expr = f"min(iw-iw/zoom,max(0,(on/{total_frames})*(iw-iw/zoom)))"
        y_expr = "ih/2-(ih/zoom/2)"

    # Pre-scale image to 4K / high-res canvas so zoompan has high source resolution without pixelation
    scale_canvas = f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,crop={width*2}:{height*2}"
    filter_chain = (
        f"{scale_canvas},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s={width}x{height}:fps={fps},"
        f"setsar=1,format=yuv420p"
    )
    
    args = [
        "-loop", "1",
        "-i", str(image_path),
        "-vf", filter_chain,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    
    success, err = run_ffmpeg(args)
    return success
