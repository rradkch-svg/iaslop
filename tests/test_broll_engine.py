import os
import sys
import unittest
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from broll_engine import BRollEngine, build_topic_queries, calculate_scene_durations

class TestBRollEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.engine = BRollEngine(max_search_results=3)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_build_topic_queries(self):
        """Verifica se a geração de queries inclui termos HD e âncoras temáticas."""
        queries = build_topic_queries(
            global_topic="A Base Secreta de Camp Century na Groenlândia ❄️☢️",
            base_query="Camp Century nuclear tunnels"
        )
        self.assertTrue(len(queries) >= 2)
        # Verifica se termos de alta definição estão presentes
        has_hd = any("1080p" in q or "4k" in q or "HD" in q for q in queries)
        self.assertTrue(has_hd, "Deveria conter termos de alta definição (1080p/4k/HD)")

    def test_calculate_scene_durations(self):
        """Verifica se a soma das durações das cenas cobre o tempo total do áudio + tail overhead."""
        cenas = [
            {"scene_id": 1, "fala": "Esta é a cena um com dez palavras para teste."},
            {"scene_id": 2, "fala": "Esta é a cena dois com mais algumas palavras."},
            {"scene_id": 3, "fala": "Esta é a terceira cena final de encerramento."}
        ]
        durations = calculate_scene_durations(
            cenas=cenas,
            total_audio_duration=15.0,
            words_timing=None,
            tail_overhead=0.5
        )
        self.assertEqual(len(durations), 3)
        self.assertAlmostEqual(sum(durations), 15.5, delta=0.1)

    def test_fetch_scene_broll_fallback(self):
        """Verifica se fetch_scene_broll retorna a estrutura padrão esperada mesmo sem rede."""
        res = self.engine.fetch_scene_broll(
            query="test query for non existing video 9999999",
            output_dir=self.test_dir,
            scene_idx=1,
            target_duration=3.0,
            global_topic="Mistério Teste"
        )
        self.assertIsInstance(res, dict)
        self.assertIn("file", res)
        self.assertIn("video_file", res)
        self.assertIn("preview_frame", res)
        self.assertIn("duration", res)

if __name__ == "__main__":
    unittest.main()
