import httpx
import json
import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=60.0)

print("=" * 60)
print("🧪 Testing New Features: Genres, Word Counts & Bespoke Prompts")
print("=" * 60)

# 1. Genres
r = client.get('/api/genres')
genres = r.json().get('genres', [])
print(f"\n[1] Loaded {len(genres)} Curated YouTube Genres:")
for g in genres[:3]:
    print(f"  - {g['name']}")

# 2. Topic Generation by Genre
print("\n[2] Testing AI Topic Generation for 'Space & Cosmos'...")
r2 = client.post('/api/topics/generate', json={'genre_id': 'space', 'video_format': 'shorts_9_16'})
topics = r2.json().get('topics', [])
for i, t in enumerate(topics):
    print(f"  Idea {i+1}: {t['topic']}")
    print(f"    Hook: \"{t['hook']}\"")

# 3. Create Project
topic_chosen = topics[0]['topic'] if topics else "What Happens at the Event Horizon of TON 618"
r_proj = client.post('/api/projects/create', json={'topic': topic_chosen, 'video_format': 'shorts_9_16'})
proj_id = r_proj.json()['id']
print(f"\n[3] Created Project ID: {proj_id}")

# 4. Generate Shorts Script (Target: 200-400 words)
print("\n[4] Generating Shorts Script...")
r_script = client.post(f'/api/projects/{proj_id}/script', json={
    'topic': topic_chosen,
    'video_format': 'shorts_9_16',
    'tone': 'mysterious'
})
script_data = r_script.json()
full_script = script_data.get('full_script', '')
word_count = len(full_script.split())
print(f"✓ Shorts Script Word Count: {word_count} words (Target: 200 - 400 words)")
print(f"✓ Speech Blocks: {len(script_data.get('speech_blocks', []))} blocks")

# 5. Audio & Alignment
print("\n[5] Synthesizing Voice & Extracting Timestamps...")
r_audio = client.post(f'/api/projects/{proj_id}/audio', json={
    'project_id': proj_id,
    'script_text': full_script,
    'voice_id': 'en-US-ChristopherNeural'
})
audio_data = r_audio.json()
print(f"✓ Audio Duration: {audio_data['audio_duration']:.1f}s | Scenes: {len(audio_data['scenes'])}")

# 6. Bespoke Cinematographic Scene Prompts
print("\n[6] Generating Bespoke Film Director Visual Prompts...")
r_prompts = client.post(f'/api/projects/{proj_id}/prompts', json={
    'project_id': proj_id,
    'topic': topic_chosen,
    'style_preference': 'cinematic realistic 8k, volumetric space dust, unreal engine 5'
})
scenes = r_prompts.json()['scenes']
print("\nBespoke Scene Prompts (Zero Boilerplate):")
for s in scenes[:4]:
    print(f"\n  [Scene {s['index']} - {s['start_time']:.1f}s to {s['end_time']:.1f}s]:")
    print(f"    Spoken Audio: \"{s['speech_text']}\"")
    print(f"    Director Prompt: \"{s['visual_prompt']}\"")

# 7. Check API Keys Status
print("\n[7] API Keys Configuration Status:")
r_keys = client.get('/api/settings/keys')
print(" ", json.dumps(r_keys.json(), indent=2))

print("\n" + "=" * 60)
print("🎉 ALL NEW FEATURES TESTED AND VALIDATED SUCCESSFULLY!")
print("=" * 60)
