import os
import sys
import unittest
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from bgm_engine import BGMEngine, DEFAULT_BGM_ENGINE, BGM_THEME_PROFILES

class TestBGMEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.engine = BGMEngine(bgm_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_soundbank_initialization(self):
        """Verifica que o soundbank de suspense é inicializado e criado no disco."""
        tracks = self.engine.list_available_tracks()
        self.assertGreaterEqual(len(tracks), len(BGM_THEME_PROFILES))
        for t in tracks:
            self.assertTrue(os.path.exists(t["path"]))
            self.assertGreater(t["size_kb"], 10)

    def test_topic_affinity_matching(self):
        """Verifica a seleção de trilhas com base nas palavras-chave do tema."""
        track_ocean = self.engine.get_bgm_for_topic(
            topic_title="O Som Estranho da Fossa das Marianas e o Bloop",
            topic_context="Sinais oceânicos detectados por hidrofones em águas profundas."
        )
        self.assertIn("abyss_oceanic", track_ocean)

        track_cold_war = self.engine.get_bgm_for_topic(
            topic_title="A Base Nuclear de Camp Century na Groenlândia",
            topic_context="Cidade militar secreta sob a calota de gelo."
        )
        self.assertIn("cold_war", track_cold_war)

        track_space = self.engine.get_bgm_for_topic(
            topic_title="O Sinal Wow e a Origem do Mistério Cósmico",
            topic_context="O radiotelescópio Big Ear captou um sinal inexplicável no espaço."
        )
        self.assertIn("cosmic_space", track_space)

    def test_random_bgm_selection(self):
        """Verifica se a seleção randômica retorna um arquivo de áudio válido."""
        track = self.engine.get_random_bgm()
        self.assertTrue(os.path.exists(track))
        self.assertTrue(track.endswith((".wav", ".mp3")))

    def test_procedural_drone_synthesis(self):
        """Valida a síntese procedural de um novo drone de suspense."""
        out_wav = os.path.join(self.test_dir, "test_custom_drone.wav")
        res = self.engine._synthesize_suspense_drone(out_wav, duration_sec=5.0)
        self.assertTrue(os.path.exists(res))
        self.assertGreater(os.path.getsize(res), 100000)

if __name__ == "__main__":
    unittest.main()
