import os
import shutil
from pathlib import Path
from typing import List, Optional
from backend.app.config import settings
from backend.app.models.schemas import SceneModel, VideoFormat, SubtitleStyle, BGMTrack
from backend.app.utils.ffmpeg_helper import (
    run_ffmpeg,
    generate_ken_burns_clip,
    escape_ffmpeg_path,
    get_media_duration
)
from backend.app.services.audio_mixer import audio_mixer

class VideoEngine:
    def render_complete_video(
        self,
        project_dir: Path,
        scenes: List[SceneModel],
        voice_audio_path: Path,
        ass_subtitle_path: Path,
        output_video_path: Path,
        video_format: VideoFormat = VideoFormat.SHORTS_9_16,
        bgm_track: BGMTrack = BGMTrack.CINEMATIC,
        bgm_volume: float = 0.15
    ) -> bool:
        """
        Step 7: Compiles all visual scene clips with Ken Burns camera motion,
        mixes audio with background music, and burns interactive karaoke subtitles.
        """
        temp_dir = project_dir / "video" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        is_short = video_format == VideoFormat.SHORTS_9_16
        res = settings.RESOLUTIONS["shorts_9_16" if is_short else "long_16_9"]
        width, height, fps = res["width"], res["height"], res["fps"]

        # 1. Render Ken Burns clips for each scene
        scene_clip_paths: List[Path] = []
        for scene in scenes:
            img_path = Path(scene.local_image_path) if scene.local_image_path else None
            if not img_path or not img_path.exists():
                print(f"Warning: Missing image for scene {scene.id}")
                continue

            clip_path = temp_dir / f"{scene.id}_clip.mp4"
            duration = max(scene.duration, 1.0)
            
            success = generate_ken_burns_clip(
                image_path=img_path,
                output_path=clip_path,
                duration=duration,
                width=width,
                height=height,
                motion_type=scene.motion_type,
                fps=fps
            )
            if success and clip_path.exists():
                scene_clip_paths.append(clip_path)

        if not scene_clip_paths:
            print("Error: No scene clips were generated.")
            return False

        # 2. Concat all scene clips into visual montage
        concat_list_file = temp_dir / "concat_list.txt"
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for clip_p in scene_clip_paths:
                # Format for ffmpeg concat demuxer
                clean_p = str(clip_p.resolve()).replace("\\", "/")
                f.write(f"file '{clean_p}'\n")

        raw_visual_path = temp_dir / "visual_montage.mp4"
        concat_args = [
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            str(raw_visual_path)
        ]
        ok_concat, err = run_ffmpeg(concat_args)
        if not ok_concat:
            print(f"Concat error: {err}")
            return False

        # 3. Mix audio (Voice + BGM)
        mixed_audio_path = temp_dir / "mixed_audio.aac"
        audio_mixer.mix_voice_and_bgm(
            voice_path=voice_audio_path,
            output_path=mixed_audio_path,
            bgm_type=bgm_track,
            bgm_volume=bgm_volume
        )

        total_audio_duration = get_media_duration(mixed_audio_path)
        if total_audio_duration <= 0:
            total_audio_duration = get_media_duration(raw_visual_path)

        # 4. Final Compositing: Video + Mixed Audio + Subtitle Burn
        escaped_sub_path = escape_ffmpeg_path(ass_subtitle_path)
        
        # Check if subtitle file exists
        if ass_subtitle_path.exists():
            vf_filter = f"subtitles='{escaped_sub_path}'"
        else:
            vf_filter = "null"

        final_args = [
            "-i", str(raw_visual_path),
            "-i", str(mixed_audio_path),
            "-vf", vf_filter,
            "-t", f"{total_audio_duration:.3f}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "19",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            str(output_video_path)
        ]

        success, err = run_ffmpeg(final_args)
        if not success:
            print(f"Final render error: {err}. Attempting fallback without subtitles filter...")
            # Fallback without subtitle filter if libass error
            fb_args = [
                "-i", str(raw_visual_path),
                "-i", str(mixed_audio_path),
                "-t", f"{total_audio_duration:.3f}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-pix_fmt", "yuv420p",
                str(output_video_path)
            ]
            success, err2 = run_ffmpeg(fb_args)

        # Clean temp directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

        return success and output_video_path.exists()

video_engine = VideoEngine()
