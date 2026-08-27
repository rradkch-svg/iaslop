import os
import sys
import unittest
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
for p in (SRC_DIR, SCRIPTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from algorithm_memory import AlgorithmMemorySystem
from sync_metrics import sync_from_csv

class TestMetricsFileSync(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.memory = AlgorithmMemorySystem(memory_dir=self.test_dir)
        self.csv_path = os.path.join(self.test_dir, "test_metrics.csv")
        with open(self.csv_path, "w", encoding="utf-8") as f:
            f.write("batch,video,titulo,visualizacoes,retencao_3s_pct,apv_pct,ctr_pct,likes,comentarios,observacoes\n")
            f.write("batch_0,video_0,A Base Nuclear Secreta,30000,80.0,85.0,10.0,2000,300,Otimo engajamento\n")
            f.write("batch_0,video_1,O Poco Mais Fundo de Kola,60000,88.0,92.0,14.0,5000,700,Viralizou no TikTok\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sync_from_csv(self):
        """Verifica a ingestão do CSV e o preenchimento da memória."""
        synced = sync_from_csv(self.csv_path, self.memory)
        self.assertEqual(synced, 2)
        
        history = self.memory.load_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["video_id"], "batch_0/video_0")
        self.assertEqual(history[1]["views"], 60000)

if __name__ == "__main__":
    unittest.main()
