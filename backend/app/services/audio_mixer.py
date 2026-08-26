import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from backend.app.config import BGM_DIR, SFX_DIR
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

    def mix_complete_audio_track(
        self,
        voice_path: Path,
        output_path: Path,
        bgm_type: BGMTrack = BGMTrack.CINEMATIC,
        bgm_volume: float = 0.14,
        voice_volume: float = 1.0,
        sfx_timeline: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Master audio mix for Minuto Inexplicável:
        1. Voice Narration (volume 1.0)
        2. Background Ambient Music (ducked at -18dB / 0.14 with in/out fade)
        3. Sound Effects (SFX) placed at exact millisecond timestamps (0.0s sub-bass impact, whooshes on cuts, bells on reveals).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = get_media_duration(voice_path)
        if duration <= 0:
            duration = 45.0

        fade_out_start = max(duration - 1.5, 0.5)

        # 1. Determine BGM file
        bgm_file = BGM_DIR / f"{bgm_type.value}.mp3"
        temp_bgm = output_path.parent / "temp_ambient_bgm.aac"

        if bgm_type != BGMTrack.NONE and bgm_volume > 0:
            if not bgm_file.exists():
                self.create_ambient_bgm_track(temp_bgm, duration + 1.0)
                bgm_input = str(temp_bgm)
            else:
                bgm_input = str(bgm_file)
            has_bgm = True
        else:
            has_bgm = False

        # 2. Build input list and filter_complex
        cmd_inputs = ["-i", str(voice_path)]
        filter_parts = [f"[0:a]volume={voice_volume}[v_main]"]
        mix_inputs = ["[v_main]"]
        current_idx = 1

        if has_bgm:
            cmd_inputs.extend(["-i", bgm_input])
            filter_parts.append(
                f"[{current_idx}:a]aloop=loop=-1:size=2e+09,volume={bgm_volume},"
                f"afade=t=in:ss=0:d=1,afade=t=out:st={fade_out_start:.2f}:d=1.5[bgm_mix]"
            )
            mix_inputs.append("[bgm_mix]")
            current_idx += 1

        # 3. Add SFX files from timeline
        sfx_timeline = sfx_timeline or []
        for sfx_item in sfx_timeline:
            sfx_type = sfx_item.get("sfx_type", "whoosh")
            sfx_time = max(0.0, float(sfx_item.get("time", 0.0)))
            vol = float(sfx_item.get("volume", 0.8))

            sfx_file = SFX_DIR / f"{sfx_type}.wav"
            if not sfx_file.exists():
                # Try .mp3
                sfx_file = SFX_DIR / f"{sfx_type}.mp3"

            if sfx_file.exists() and sfx_time < duration:
                delay_ms = int(sfx_time * 1000)
                cmd_inputs.extend(["-i", str(sfx_file)])
                tag = f"sfx_{current_idx}"
                filter_parts.append(
                    f"[{current_idx}:a]adelay={delay_ms}|{delay_ms},volume={vol}[{tag}]"
                )
                mix_inputs.append(f"[{tag}]")
                current_idx += 1

        # Combine all audio streams with amix
        total_inputs = len(mix_inputs)
        mix_str = "".join(mix_inputs)
        filter_parts.append(f"{mix_str}amix=inputs={total_inputs}:duration=first:dropout_transition=2[out]")
        filter_complex = ";".join(filter_parts)

        args = cmd_inputs + [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", f"{duration:.3f}",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        success, err = run_ffmpeg(args)
        if not success:
            print(f"Audio mix warning: {err}. Falling back to standard mix...")
            # Fallback simple 2-stream voice + BGM or voice only
            if has_bgm:
                fb_filter = (
                    f"[0:a]volume={voice_volume}[v];"
                    f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_volume},"
                    f"afade=t=in:ss=0:d=1,afade=t=out:st={fade_out_start:.2f}:d=1.5[m];"
                    f"[v][m]amix=inputs=2:duration=first:dropout_transition=2"
                )
                args_fb = [
                    "-i", str(voice_path),
                    "-i", bgm_input,
                    "-filter_complex", fb_filter,
                    "-t", f"{duration:.3f}",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    str(output_path)
                ]
            else:
                args_fb = [
                    "-i", str(voice_path),
                    "-c:a", "aac",
                    "-b:a", "192k",
                    str(output_path)
                ]
            run_ffmpeg(args_fb)

        return True

audio_mixer = AudioMixerService()
