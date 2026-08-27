import os
import sys
import unittest
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from algorithm_memory import AlgorithmMemorySystem, DEFAULT_AUXILIARY_WEIGHTS

class TestAlgorithmMemorySystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.memory = AlgorithmMemorySystem(memory_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initialization_defaults(self):
        """Verifica carregamento inicial de pesos auxiliares e criação dos arquivos."""
        weights = self.memory.load_weights()
        self.assertIn("hook_curiosity_gap_weight", weights)
        self.assertIn("technical_depth_weight", weights)
        self.assertTrue(os.path.exists(self.memory.weights_file))
        self.assertTrue(os.path.exists(self.memory.history_file))
        self.assertTrue(os.path.exists(self.memory.memory_md_file))

    def test_record_video_metrics_and_recalibration(self):
        """Registra métricas reais e valida recálculo de score e pesos."""
        rec = self.memory.record_video_metrics(
            video_id="batch_0/video_1",
            title="O Poço de Kola e os Sons da Terra",
            views=50000,
            retention_3s=86.5,
            apv=92.0,
            ctr=13.5,
            likes=4200,
            comments=580
        )
        self.assertGreater(rec["composite_score"], 70.0)
        
        history = self.memory.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["video_id"], "batch_0/video_1")

    def test_prompt_context_generation(self):
        """Verifica se o prompt gerado inclui as diretrizes ativas."""
        ctx = self.memory.get_prompt_context_for_generation()
        self.assertIn("DIRETRIZES DA MEMÓRIA ALGORÍTMICA", ctx)
        self.assertIn("Intensidade do Hook", ctx)

if __name__ == "__main__":
    unittest.main()
