import os
import sys
import time
import json
import re
import subprocess
from pathlib import Path
import httpx
import imageio_ffmpeg
from PIL import Image

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"
STORAGE_DIR = Path(__file__).resolve().parent / "storage" / "projects"
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

def probe_video(video_path: Path):
    """Probes video metadata using FFmpeg"""
    cmd = [FFMPEG_EXE, "-i", str(video_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    stderr = proc.stderr

    # Extract Resolution: e.g. 1920x1080
    res_match = re.search(r"Video:.*,\s*(\d{3,4})x(\d{3,4})", stderr)
    width, height = (int(res_match.group(1)), int(res_match.group(2))) if res_match else (None, None)

    # Extract Duration: e.g. 00:00:27.46
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    duration = None
    if dur_match:
        h, m, s = float(dur_match.group(1)), float(dur_match.group(2)), float(dur_match.group(3))
        duration = round(h * 3600 + m * 60 + s, 2)

    # Extract fps
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
    fps = float(fps_match.group(1)) if fps_match else None

    # Extract Video Codec
    codec_match = re.search(r"Video:\s*([a-zA-Z0-9_-]+)", stderr)
    v_codec = codec_match.group(1) if codec_match else None

    # Extract Audio Codec
    a_match = re.search(r"Audio:\s*([a-zA-Z0-9_-]+)", stderr)
    a_codec = a_match.group(1) if a_match else None

    return {
        "width": width,
        "height": height,
        "duration": duration,
        "fps": fps,
        "video_codec": v_codec,
        "audio_codec": a_codec,
        "raw_info": stderr
    }

def run_test():
    print("=" * 70)
    print("AUTOMATED TEST: 1-Click Auto-Pilot on YouTube AI Video Studio")
    print("Target Format: Long-Form (long_16_9, 1920x1080 horizontal)")
    print("=" * 70)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # 1. Check API Formats
    print("\n[Test 1] Verifying server API and format definitions...")
    r = client.get("/api/formats")
    assert r.status_code == 200, f"Failed to get formats: {r.text}"
    formats_data = r.json()
    long_format = next((f for f in formats_data["formats"] if f["id"] == "long_16_9"), None)
    assert long_format is not None, "long_16_9 format not found in /api/formats"
    print(f"  [OK] Verified long_16_9 format: {long_format['name']} (aspect {long_format['aspect']})")

    # 2. Trigger Auto-Pilot Pipeline
    print("\n[Test 2] Triggering /api/autopilot for Long-Form video...")
    autopilot_payload = {
        "topic": "The Mysteries of Deep Space",
        "video_format": "long_16_9",
        "voice_id": "en-US-ChristopherNeural",
        "subtitle_style": "hormozi",
        "bgm_track": "cinematic",
        "art_style": "hyperrealistic cinematic 8k, space nebula, unreal engine 5"
    }
    
    t_start = time.time()
    r = client.post("/api/autopilot", json=autopilot_payload)
    assert r.status_code == 200, f"Auto-pilot initiation failed: {r.text}"
    initial_proj = r.json()
    project_id = initial_proj["id"]
    print(f"  [OK] Auto-Pilot queued successfully!")
    print(f"  [OK] Project ID: {project_id}")
    print(f"  [OK] Initial Status: {initial_proj['status']}, Progress: {initial_proj['progress']}%")

    # 3. Poll project status until completed
    print(f"\n[Test 3] Polling /api/projects/{project_id} until completed...")
    last_progress = -1
    seen_logs = set()
    completed_proj = None
    max_wait_seconds = 300
    poll_interval = 2.0
    start_poll = time.time()

    while time.time() - start_poll < max_wait_seconds:
        time.sleep(poll_interval)
        try:
            r = client.get(f"/api/projects/{project_id}")
            if r.status_code != 200:
                print(f"  Poll warning (HTTP {r.status_code}): {r.text}")
                continue

            proj_state = r.json()
            status = proj_state.get("status")
            progress = proj_state.get("progress", 0)
            logs = proj_state.get("logs", [])

            # Print newly added logs
            for log in logs:
                if log not in seen_logs:
                    print(f"    [{progress}%] {log}")
                    seen_logs.add(log)

            if progress != last_progress:
                last_progress = progress

            if status == "completed":
                completed_proj = proj_state
                break
            elif status == "error":
                raise RuntimeError(f"Auto-pilot pipeline failed with error status! Logs: {logs}")

        except Exception as e:
            if "Auto-pilot pipeline failed" in str(e):
                raise
            print(f"  Polling exception: {e}")

    total_time = round(time.time() - t_start, 2)
    assert completed_proj is not None, f"Pipeline timed out after {max_wait_seconds}s without reaching 'completed'"
    print(f"\n  [OK] Pipeline finished in {total_time}s with status: '{completed_proj['status']}', progress: {completed_proj['progress']}%")

    # 4. Verify Project Assets & Data in Storage
    print("\n[Test 4] Verifying all generated project artifacts in storage/...")
    proj_dir = STORAGE_DIR / project_id
    assert proj_dir.exists(), f"Project directory does not exist: {proj_dir}"
    print(f"  [OK] Project folder verified: {proj_dir}")

    # 4.1 project.json
    project_json_file = proj_dir / "project.json"
    assert project_json_file.exists(), "project.json is missing"
    with open(project_json_file, "r", encoding="utf-8") as f:
        disk_proj = json.load(f)
    assert disk_proj["status"] == "completed"
    assert disk_proj["video_format"] == "long_16_9"
    print(f"  [OK] disk project.json validated (Status: {disk_proj['status']}, Format: {disk_proj['video_format']})")

    # 4.2 Narration Audio
    audio_file = proj_dir / "audio" / "narration.mp3"
    assert audio_file.exists(), "narration.mp3 is missing"
    audio_size = audio_file.stat().st_size
    assert audio_size > 1024, f"narration.mp3 is suspiciously small ({audio_size} bytes)"
    print(f"  [OK] Narration audio verified: {audio_file.name} ({audio_size:,} bytes, duration: {disk_proj.get('audio_duration', 0):.2f}s)")

    # 4.3 Subtitles (.ass)
    sub_file = proj_dir / "subtitles" / "karaoke.ass"
    assert sub_file.exists(), "karaoke.ass is missing"
    with open(sub_file, "r", encoding="utf-8") as f:
        ass_content = f.read()
    assert "PlayResX: 1920" in ass_content, "ASS Subtitle PlayResX is not 1920 for 16:9 format"
    assert "PlayResY: 1080" in ass_content, "ASS Subtitle PlayResY is not 1080 for 16:9 format"
    assert "Dialogue:" in ass_content, "ASS Subtitle does not contain Dialogue lines"
    print(f"  [OK] ASS Karaoke subtitles verified (PlayResX: 1920, PlayResY: 1080, format: long_16_9)")

    # 4.4 Scene Images
    images_dir = proj_dir / "images"
    assert images_dir.exists(), "images/ directory missing"
    image_files = list(images_dir.glob("scene_*.jpg"))
    assert len(image_files) >= 3, f"Expected at least 3 scene images, found {len(image_files)}"
    for img_p in image_files:
        with Image.open(img_p) as im:
            iw, ih = im.size
            assert iw > 0 and ih > 0, f"Invalid image size for {img_p}"
    print(f"  [OK] Verified {len(image_files)} scene illustrations")

    # 4.5 Thumbnail
    thumb_file = proj_dir / "thumbnail" / "thumbnail.jpg"
    assert thumb_file.exists(), "thumbnail.jpg missing"
    with Image.open(thumb_file) as thumb_img:
        tw, th = thumb_img.size
        assert tw == 1280 and th == 720, f"Expected thumbnail 1280x720, got {tw}x{th}"
    print(f"  [OK] High-CTR YouTube Thumbnail verified ({tw}x{th}, overlay: '{disk_proj.get('thumbnail', {}).get('suggested_overlay_text')}')")

    # 4.6 Metadata
    meta = disk_proj.get("metadata")
    assert meta is not None, "Metadata object missing in project"
    assert len(meta.get("titles", [])) >= 1, "No titles generated"
    assert len(meta.get("description", "")) > 10, "Description empty"
    assert len(meta.get("tags", [])) >= 1, "Tags empty"
    print(f"  [OK] YouTube SEO Package verified:")
    print(f"    - Title 1: \"{meta['titles'][0]}\"")
    print(f"    - Tags: {', '.join(meta['tags'][:5])}...")

    # 5. Final Video Resolution & Quality Verification
    print("\n[Test 5] Probing and validating final_video.mp4...")
    final_video_path = proj_dir / "video" / "final_video.mp4"
    assert final_video_path.exists(), f"final_video.mp4 does not exist at {final_video_path}"
    video_size = final_video_path.stat().st_size
    assert video_size > 10000, f"final_video.mp4 is too small ({video_size} bytes)"

    v_info = probe_video(final_video_path)
    print(f"  [OK] Video File Size: {video_size:,} bytes ({video_size / (1024*1024):.2f} MB)")
    print(f"  [OK] Video Resolution: {v_info['width']}x{v_info['height']}")
    print(f"  [OK] Video Duration: {v_info['duration']} seconds")
    print(f"  [OK] Frame Rate: {v_info['fps']} fps")
    print(f"  [OK] Video Codec: {v_info['video_codec']}")
    print(f"  [OK] Audio Codec: {v_info['audio_codec']}")

    # Strict Assertions
    assert v_info["width"] == 1920, f"Expected video width 1920, but got {v_info['width']}"
    assert v_info["height"] == 1080, f"Expected video height 1080, but got {v_info['height']}"
    assert v_info["duration"] is not None and v_info["duration"] > 5.0, f"Video duration too short: {v_info['duration']}s"

    print("\n" + "=" * 70)
    print("ALL CRITERIA PASSED SUCCESSFULLY! [OK]")
    print("=" * 70)
    print(f"Summary:")
    print(f" - Project ID: {project_id}")
    print(f" - Format: long_16_9 (1920x1080)")
    print(f" - Execution Mode: 1-Click Auto-Pilot (/api/autopilot)")
    print(f" - Final Status: {disk_proj['status']}")
    print(f" - Final Resolution: {v_info['width']}x{v_info['height']}")
    print(f" - Audio Duration: {disk_proj.get('audio_duration', 0):.2f}s")
    print(f" - Video Duration: {v_info['duration']}s")
    print(f" - Output File: {final_video_path}")
    print("=" * 70)

    return {
        "success": True,
        "project_id": project_id,
        "format": "long_16_9",
        "status": disk_proj["status"],
        "width": v_info["width"],
        "height": v_info["height"],
        "duration": v_info["duration"],
        "video_path": str(final_video_path),
        "total_elapsed_seconds": total_time
    }

if __name__ == "__main__":
    result = run_test()
    sys.exit(0 if result["success"] else 1)
