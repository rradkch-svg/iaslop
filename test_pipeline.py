import httpx
import time
import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def test_full_pipeline():
    print("=" * 60)
    print("🧪 Testing Complete 9-Step AI Video Pipeline")
    print("=" * 60)

    client = httpx.Client(base_url=BASE_URL, timeout=120.0)

    # 0. Check Voices & Config
    print("\n[Step 0] Checking API health and voices...")
    r = client.get("/api/voices")
    assert r.status_code == 200, f"Voices failed: {r.text}"
    voices = r.json().get("voices", [])
    print(f"✓ Found {len(voices)} available voices: {[v['id'] for v in voices[:2]]}")

    # 1. Create Project
    print("\n[Step 1] Creating new project for YouTube Shorts...")
    r = client.post("/api/projects/create", json={
        "topic": "The Bloop Mystery 1997",
        "video_format": "shorts_9_16"
    })
    assert r.status_code == 200
    proj = r.json()
    proj_id = proj["id"]
    print(f"✓ Created Project ID: {proj_id}")

    # 2. Step 1: Generate Script
    print("\n[Step 1] Generating Structured Script with speech blocks...")
    r = client.post(f"/api/projects/{proj_id}/script", json={
        "topic": "The Bloop Mystery 1997",
        "video_format": "shorts_9_16",
        "tone": "mysterious",
        "target_duration": 30
    })
    assert r.status_code == 200
    proj = r.json()
    print(f"✓ Script generated with {len(proj['speech_blocks'])} speech blocks:")
    for i, b in enumerate(proj["speech_blocks"][:3]):
        print(f"   Block {i+1}: {b}")

    # 3. Step 2 & 3: Audio & Alignment
    print("\n[Step 2 & 3] Synthesizing Voice (Edge-TTS) & Aligning Pauses...")
    r = client.post(f"/api/projects/{proj_id}/audio", json={
        "project_id": proj_id,
        "script_text": proj["full_script"],
        "voice_id": "en-US-ChristopherNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    })
    assert r.status_code == 200
    proj = r.json()
    print(f"✓ Voice audio created! Duration: {proj['audio_duration']:.2f}s")
    print(f"✓ Aligned into {len(proj['scenes'])} visual scenes:")
    for s in proj["scenes"]:
        print(f"   Scene {s['index']} [{s['start_time']:.1f}s - {s['end_time']:.1f}s] ({s['duration']:.1f}s) Motion: {s['motion_type']}")

    # 4. Step 4: Scene Prompts
    print("\n[Step 4] Generating Cinematographic Visual Prompts...")
    r = client.post(f"/api/projects/{proj_id}/prompts", json={
        "project_id": proj_id,
        "topic": "The Bloop Mystery 1997",
        "style_preference": "cinematic realistic 8k, underwater bioluminescence, unreal engine 5"
    })
    assert r.status_code == 200
    proj = r.json()
    print("✓ Scene prompts created:")
    for s in proj["scenes"]:
        print(f"   Scene {s['index']} Prompt: {s['visual_prompt'][:80]}...")

    # 5. Step 5: Visual Illustrations
    print("\n[Step 5] Generating Image Illustrations for all scenes...")
    t0 = time.time()
    r = client.post(f"/api/projects/{proj_id}/images", json={
        "project_id": proj_id
    })
    assert r.status_code == 200
    proj = r.json()
    print(f"✓ All scene images generated in {time.time() - t0:.1f}s!")

    # 6. Step 6: Interactive Karaoke Subtitles (ASS)
    print("\n[Step 6] Building Interactive Karaoke Subtitles (.ass)...")
    r = client.post(f"/api/projects/{proj_id}/subtitles?style=hormozi")
    assert r.status_code == 200
    proj = r.json()
    print(f"✓ Subtitles generated: {proj['subtitle_path']}")

    # 7. Step 7: Render Video
    print("\n[Step 7] Rendering Complete Video with Ken Burns Motion & Audio Mix...")
    t0 = time.time()
    r = client.post(f"/api/projects/{proj_id}/render", json={
        "project_id": proj_id,
        "video_format": "shorts_9_16",
        "subtitle_style": "hormozi",
        "bgm_track": "cinematic",
        "bgm_volume": 0.15
    })
    assert r.status_code == 200, f"Render error: {r.text}"
    proj = r.json()
    print(f"✓ Video rendered successfully in {time.time() - t0:.1f}s!")
    print(f"   Video URL: {proj['final_video_path']}")

    # 8. Step 8: SEO Metadata
    print("\n[Step 8] Generating SEO Metadata (Titles, Description, Tags)...")
    r = client.post(f"/api/projects/{proj_id}/metadata")
    assert r.status_code == 200
    proj = r.json()
    meta = proj["metadata"]
    print("✓ Top Viral Title:", meta["titles"][0])
    print(f"✓ Description length: {len(meta['description'])} chars")
    print("✓ Tags:", ", ".join(meta["tags"]))

    # 9. Step 9: Thumbnail
    print("\n[Step 9] Generating High-CTR Thumbnail...")
    r = client.post(f"/api/projects/{proj_id}/thumbnail?custom_text=THE%20BLOOP")
    assert r.status_code == 200
    proj = r.json()
    print("✓ Thumbnail URL:", proj["thumbnail"]["thumbnail_url"])

    print("\n" + "=" * 60)
    print("🎉 ALL 9 STEPS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_full_pipeline()
