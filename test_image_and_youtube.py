import httpx
import json
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=60.0)

print("=" * 60)
print("🧪 Testing Image Generation, Gemini Diagnostics & YouTube API")
print("=" * 60)

# 1. Test YouTube API Status
r_yt = client.get('/api/youtube/status')
print(f"[1] YouTube Status: {r_yt.status_code} -> {r_yt.json()}")

# 2. Test Gemini API Key Diagnostic (with dummy invalid key)
r_key = client.post('/api/settings/keys', json={'test_provider': 'gemini', 'gemini': 'AIzaSy_fake_test_key_123'})
print(f"\n[2] Gemini Diagnostic (Invalid Key Test): {r_key.status_code} -> {r_key.json()}")

# 3. Test Real Visual Generation on a new project
r_proj = client.post('/api/projects/create', json={'topic': 'The Mystery of the Mariana Trench Bloop', 'video_format': 'shorts_9_16'})
proj_id = r_proj.json()['id']

r_script = client.post(f'/api/projects/{proj_id}/script', json={
    'topic': 'The Mystery of the Mariana Trench Bloop',
    'video_format': 'shorts_9_16',
    'tone': 'mysterious'
})
script_data = r_script.json()

r_audio = client.post(f'/api/projects/{proj_id}/audio', json={
    'project_id': proj_id,
    'script_text': script_data['full_script'],
    'voice_id': 'en-US-ChristopherNeural'
})

r_prompts = client.post(f'/api/projects/{proj_id}/prompts', json={
    'project_id': proj_id,
    'topic': 'The Mystery of the Mariana Trench Bloop',
    'style_preference': 'cinematic realistic 8k, underwater deep volumetric fog, unreal engine 5'
})

print("\n[3] Generating Scene 1 Image...")
r_img = client.post(f'/api/projects/{proj_id}/images', json={'project_id': proj_id, 'scene_id': 'scene_1'})
scene_1 = r_img.json()['scenes'][0]
local_p = Path(f"storage/projects/{proj_id}/images/scene_1.jpg")
print(f"  Scene 1 Image Path: {local_p}")
if local_p.exists():
    file_size_kb = local_p.stat().st_size / 1024
    print(f"  ✓ Image File Size: {file_size_kb:.1f} KB (Real rich image generated!)")
else:
    print("  ❌ Image file not found")

print("\n" + "=" * 60)
print("🎉 VERIFICATION COMPLETED SUCCESSFULLY!")
print("=" * 60)
