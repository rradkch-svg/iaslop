import os
import sys
import json
import tempfile
import unittest

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

class TestBackendIntegration(unittest.TestCase):
    def test_imports_and_instantiation(self):
        """Verifica inicialização consistente de todos os agentes e motores do backend."""
        proposer = ProposerAgent()
        evaluator = EvaluatorAgent()
        director = DirectorAgent()
        reviewer = ReviewerAgent()
        audio = AudioEngine()
        broll = BRollEngine()
        
        self.assertIsNotNone(proposer)
        self.assertIsNotNone(evaluator)
        self.assertIsNotNone(director)
        self.assertIsNotNone(reviewer)
        self.assertIsNotNone(audio)
        self.assertIsNotNone(broll)

def run_live_pipeline():
    api_key = resolve_gemini_api_key()
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    print("=" * 60)
    print("🚀 TESTE DO BACKEND 9:16 - MINUTO INEXPLICÁVEL")
    print("=" * 60)

    test_dir = os.path.join(PROJECT_ROOT, "data", "test_output_new")
    os.makedirs(test_dir, exist_ok=True)

    print("\n[1/6] Testando ProposerAgent...")
    proposer = ProposerAgent()
    topics = proposer.generate_topics(count=1)
    print("Tema:", topics[0].get("tema"))

    print("\n[2/6] Testando DirectorAgent...")
    director = DirectorAgent()
    cenas = director.generate_storyboard(topics[0])
    print(f"Storyboard com {len(cenas)} cenas.")

    print("\n[3/6] Testando AudioEngine...")
    audio_engine = AudioEngine()
    mp3_path = os.path.join(test_dir, "test_audio.mp3")
    success_audio, words_timing = audio_engine.generate_audio(topics[0]["hook"], mp3_path)
    print(f"Áudio gerado: {success_audio}")

    print("\n[4/6] Testando Subtitles...")
    ass_path = os.path.join(test_dir, "test_subs.ass")
    convert_words_to_ass(words_timing, ass_path, highlight_color="FFE500")

    print("\n🎉 TESTE MANUAL COMPLETO!")

if __name__ == "__main__":
    unittest.main()
