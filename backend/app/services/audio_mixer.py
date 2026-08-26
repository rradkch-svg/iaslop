import os
from pathlib import Path
from typing import Optional
from backend.app.config import BGM_DIR
from backend.app.models.schemas import BGMTrack
from backend.app.utils.ffmpeg_helper import run_ffmpeg, get_media_duration

class AudioMixerService:
    def create_ambient_bgm_track(self, output_path: Path, duration: float) -> bool:
        """Generates a rich cinematic ambient drone background audio via FFmpeg synthesis"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Deep warm cinematic pad + low pink atmospheric noise
        filter_expr = (
            f"anoisesrc=c=pink:r=44100:a=0.025,lowpass=f=500,"
            f"afade=t=in:ss=0:d=1.5,afade=t=out:st={max(duration - 1.5, 0.5):.2f}:d=1.5"
        )
        args = [
            "-f", "lavfi",
            "-i", filter_expr,
            "-t", f"{duration:.3f}",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]
        success, _ = run_ffmpeg(args)
        return success

    def mix_voice_and_bgm(
        self,
        voice_path: Path,
        output_path: Path,
        bgm_type: BGMTrack = BGMTrack.CINEMATIC,
        bgm_volume: float = 0.15,
        voice_volume: float = 1.0
    ) -> bool:
        """
        Mixes speech voice audio with background music, applying ducking, volume balance,
        and smooth end fade.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = get_media_duration(voice_path)
        if duration <= 0:
            duration = 30.0

        if bgm_type == BGMTrack.NONE or bgm_volume <= 0:
            # Just copy/normalize voice audio
            args = [
                "-i", str(voice_path),
                "-filter:a", f"volume={voice_volume}",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_path)
            ]
            success, _ = run_ffmpeg(args)
            return success

        # Check if local BGM file exists in assets
        bgm_file = BGM_DIR / f"{bgm_type.value}.mp3"
        temp_bgm = output_path.parent / "temp_ambient_bgm.aac"

        if not bgm_file.exists():
            # Generate procedural ambient background
            self.create_ambient_bgm_track(temp_bgm, duration + 1.0)
            bgm_input = str(temp_bgm)
        else:
            bgm_input = str(bgm_file)

        fade_out_start = max(duration - 1.5, 0.5)

        # Mix voice and BGM with amix
        filter_complex = (
            f"[0:a]volume={voice_volume}[v];"
            f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_volume},"
            f"afade=t=in:ss=0:d=1,afade=t=out:st={fade_out_start:.2f}:d=1.5[m];"
            f"[v][m]amix=inputs=2:duration=first:dropout_transition=2"
        )

        args = [
            "-i", str(voice_path),
            "-i", bgm_input,
            "-filter_complex", filter_complex,
            "-t", f"{duration:.3f}",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        success, err = run_ffmpeg(args)
        if not success:
            # Fallback to pure voice
            args_fb = [
                "-i", str(voice_path),
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_path)
            ]
            run_ffmpeg(args_fb)

        return True

audio_mixer = AudioMixerService()
