import os
import sys
import json
import tempfile

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "tests" else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

from agents import ProposerAgent, EvaluatorAgent, DirectorAgent, ReviewerAgent, resolve_gemini_api_key
from audio import AudioEngine
from broll_engine import BRollEngine
from subtitles import convert_words_to_ass
from render import assemble_multi_scene_video

api_key = resolve_gemini_api_key()
if api_key:
    os.environ["GEMINI_API_KEY"] = api_key
else:
    print("ℹ️ Chave Gemini API não detectada no ambiente. Testando modo de contingência/resiliência offline...")

print("=" * 60)
print("🚀 TESTE DO BACKEND 9:16 - MINUTO INEXPLICÁVEL COM REVIEWER AGENT")
print("=" * 60)

test_dir = os.path.join(PROJECT_ROOT, "data", "test_output_new")
os.makedirs(test_dir, exist_ok=True)

# 1. Testar ProposerAgent
print("\n[1/6] Testando ProposerAgent...")
proposer = ProposerAgent()
topics = proposer.generate_topics(count=1)
print("Tema:", topics[0].get("tema"))
assert isinstance(topics, list) and len(topics) > 0, "Proposer falhou"
print("✅ ProposerAgent: PASSOU")

# 2. Testar DirectorAgent (Global Topic Anchoring)
print("\n[2/6] Testando DirectorAgent com ancoragem de mistério...")
director = DirectorAgent()
cenas = director.generate_storyboard(topics[0])
print(f"Storyboard com {len(cenas)} cenas.")
assert isinstance(cenas, list) and len(cenas) > 0, "DirectorAgent falhou"
for c in cenas[:3]:
    print(f"  Query cena #{c.get('scene_id')}: '{c.get('youtube_query')}'")
print("✅ DirectorAgent: PASSOU")

# 3. Testar AudioEngine
print("\n[3/6] Testando AudioEngine...")
audio_engine = AudioEngine()
mp3_path = os.path.join(test_dir, "test_audio.mp3")
success_audio, words_timing = audio_engine.generate_audio(topics[0]["hook"], mp3_path)
assert success_audio and os.path.exists(mp3_path), "AudioEngine falhou"
print("✅ AudioEngine: PASSOU")

# 4. Testar Subtitles
print("\n[4/6] Testando Subtitles...")
ass_path = os.path.join(test_dir, "test_subs.ass")
convert_words_to_ass(words_timing, ass_path, highlight_color="FFE500")
assert os.path.exists(ass_path), "Subtitles falhou"
print("✅ Subtitles: PASSOU")

# 5. Testar BRollEngine + ReviewerAgent
print("\n[5/6] Testando BRollEngine + ReviewerAgent (Auditoria de Clipes)...")
reviewer = ReviewerAgent()
broll_engine = BRollEngine(max_search_results=4)
clip_out = os.path.join(test_dir, "reviewed_clip.mp4")
seen_ids = set()

test_topic = "Projeto Camp Century: A Base Nuclear Enterrada Sob o Gelo da Groenlândia"
camp_century_cenas = director.generate_storyboard({
    "tema": test_topic,
    "hook": "Em plena Guerra Fria, uma cidade militar com reator nuclear foi escondida no gelo polar.",
    "explicacao_tecnica": "O Projeto Camp Century possuía quilômetros de túneis escavados na calota de gelo."
})
print("\nQueries geradas pelo DirectorAgent para Camp Century (Zero Pessoas):")
for pc in camp_century_cenas[:4]:
    print(f"  Query: '{pc.get('youtube_query')}'")

test_query = camp_century_cenas[0].get("youtube_query") or "Camp Century Greenland nuclear ice documentary 4k"

success_clip, c_path, vid_id, vid_title, inspection = broll_engine.search_and_download_clip(
    query=test_query,
    target_duration=3.5,
    seen_ids=seen_ids,
    output_clip_path=clip_out,
    global_topic=test_topic,
    reviewer_agent=reviewer,
    scene_fala=cenas[0].get("fala", ""),
    status_callback=lambda m: print("  📡", m)
)
print("Resultado da Auditoria:", json.dumps(inspection, indent=2, ensure_ascii=False))
assert success_clip and os.path.exists(clip_out), "BRollEngine + Reviewer falhou"
assert inspection.get("aprovado") is True, "ReviewerAgent deveria aprovar o clipe final"
print("✅ BRollEngine + ReviewerAgent: PASSOU")

# 6. Testar RenderEngine
print("\n[6/6] Testando RenderEngine...")
final_video_path = os.path.join(test_dir, "final_reviewed_output.mp4")
success_render, render_msg = assemble_multi_scene_video([clip_out], mp3_path, ass_path, final_video_path)
assert success_render and os.path.exists(final_video_path), "RenderEngine falhou"
print(f"🎬 VÍDEO FINAL AUDITADO: {final_video_path} ({os.path.getsize(final_video_path)} bytes)")
print("✅ RenderEngine: PASSOU")

print("\n" + "=" * 60)
print("🎉 TODOS OS TESTES DO BACKEND COM AUDITORIA PASSARAM!")
print("=" * 60)
