import os
import sys
import unittest
import tempfile
import json
import shutil
import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from agents import ReviewerAgent
from analytics_parser import YouTubeAnalyticsZipParser, normalize_column_name, parse_duration_seconds_safe
from algorithm_memory import AlgorithmMemorySystem
from checkpoint_manager import CheckpointManager

class TestPreFilterAndAnalyticsSync(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.memory_dir = os.path.join(self.test_dir, "algorithm_memory")
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoint")
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        self.memory = AlgorithmMemorySystem(memory_dir=self.memory_dir)
        self.checkpoint_mgr = CheckpointManager(root_dir=self.checkpoint_dir, videos_per_batch=2)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_reviewer_pre_filter_title(self):
        """Verifica se o pré-filtro descarta títulos inadequados e aprova documentários."""
        reviewer = ReviewerAgent()
        
        # Casos que DEVEM ser descartados
        bad_titles = [
            "Kung Fu Panda 4 Full Movie Fight Scene",
            "Minecraft Gameplay Episode 5 Survival",
            "Flow Podcast Cortes ao Vivo",
            "Reagindo aos piores memes do TikTok",
            "Roblox Brookhaven RP Vlog",
            "Shrek 2 Scene Animation HD"
        ]
        for bt in bad_titles:
            ok, reason = reviewer.pre_filter_title(bt, "O Mistério do Poço de Kola")
            self.assertFalse(ok, f"Deveria ter descartado: '{bt}'")
            self.assertIn("Termo proibido", reason)

        # Casos que DEVEM ser aprovados
        good_titles = [
            "Camp Century Nuclear City Under Greenland Ice Documentary 4K",
            "Kola Superdeep Borehole USSR Historical Archival Footage",
            "Mariana Trench Deep Ocean Exploration Expedition",
            "Dyatlov Pass Incident Mystery Investigation 1959"
        ]
        for gt in good_titles:
            ok, reason = reviewer.pre_filter_title(gt, "O Mistério do Poço de Kola")
            self.assertTrue(ok, f"Deveria ter aprovado: '{gt}'")

    def test_analytics_column_and_duration_parsing(self):
        """Verifica se o normalizador e o parser de duração tratam o formato do YouTube Studio pt-BR."""
        self.assertEqual(normalize_column_name("Porcentagem visualizada média (%)"), "apv_pct")
        self.assertEqual(normalize_column_name("Continuaram assistindo (%)"), "retention_3s_pct")
        self.assertEqual(normalize_column_name("Taxa de cliques na miniatura (%)"), "ctr_pct")
        self.assertEqual(normalize_column_name("Duração média da visualização"), "avg_view_duration")
        self.assertEqual(normalize_column_name("Duração"), "duration_sec")
        self.assertEqual(normalize_column_name("Visualizações intencionais"), "intentional_views")
        self.assertEqual(normalize_column_name("Visualizações"), "views")

        # Parsing de duração HH:MM:SS e MM:SS
        self.assertEqual(parse_duration_seconds_safe("0:00:53"), 53.0)
        self.assertEqual(parse_duration_seconds_safe("0:01:07"), 67.0)
        self.assertEqual(parse_duration_seconds_safe("0:04:07"), 247.0)
        self.assertEqual(parse_duration_seconds_safe("92"), 92.0)

    def test_analytics_sync_with_memory_system(self):
        """Verifica se a sincronização de dados de analytics atualiza a memória e recalibra pesos."""
        sample_csv = os.path.join(self.test_dir, "Dados da tabela.csv")
        with open(sample_csv, "w", encoding="utf-8-sig") as f:
            f.write(
                "Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações intencionais,Duração média da visualização,Porcentagem visualizada média (%),Continuaram assistindo (%),Alcance único,Visualizações,Tempo de exibição (horas),Inscritos,Impressões de miniaturas,Taxa de cliques na miniatura (%)\n"
                "Total,,,,9758,0:00:49,78.13,55.17,13417,19166,136.553,63,4752,2.21\n"
                "EkEehdHDUJI,O Gigante Porta-Aviões de Gelo da Segunda Guerra Mundial 🧊🚢,\"Aug 27, 2026\",92,944,0:00:53,58.21,75.22,1165,1472,14.1867,5,268,1.12\n"
                "RXedNE9W-B4,Derinkuyu: A Cidade Subterrânea de 18 Andares ⛏️🏛️ #viral #curiosidades,\"Aug 27, 2026\",59,746,0:00:35,60.05,59.82,1149,1324,7.5935,7,199,3.52\n"
            )

        parser = YouTubeAnalyticsZipParser(analytics_dir=self.test_dir)
        synced = parser.sync_with_memory_system(self.memory)
        self.assertEqual(synced, 2)
        
        history = self.memory.load_history()
        self.assertEqual(len(history), 2)
        rec1 = next(r for r in history if "EkEehdHDUJI" in r.get("video_id") or "Porta-Aviões" in r.get("tema"))
        self.assertEqual(rec1["analytics"]["views"], 1472)
        self.assertAlmostEqual(rec1["analytics"]["apv_pct"], 58.21, delta=0.1)
        self.assertAlmostEqual(rec1["analytics"]["retention_3s_pct"], 75.22, delta=0.1)
        self.assertIn(rec1["analytics"]["performance_tier"], ("S", "A"))

    def test_checkpoint_dual_filename_recognition(self):
        """Verifica se o CheckpointManager reconhece tanto final_output.mp4 quanto final_video.mp4."""
        v0_dir = self.checkpoint_mgr.get_video_dir(0, 0)
        v1_dir = self.checkpoint_mgr.get_video_dir(0, 1)

        # Video 0: final_video.mp4
        with open(os.path.join(v0_dir, "final_video.mp4"), "wb") as f:
            f.write(b"x" * 150_000)

        # Video 1: final_output.mp4
        with open(os.path.join(v1_dir, "final_output.mp4"), "wb") as f:
            f.write(b"x" * 150_000)

        stage0, _ = self.checkpoint_mgr.determine_video_resume_stage(0, 0)
        stage1, _ = self.checkpoint_mgr.determine_video_resume_stage(0, 1)
        self.assertEqual(stage0, "COMPLETED")
        self.assertEqual(stage1, "COMPLETED")

        state = self.checkpoint_mgr.rebuild_global_state_from_disk()
        self.assertEqual(state["batches"]["batch_0"]["completed_videos_count"], 2)
        self.assertEqual(state["batches"]["batch_0"]["status"], "COMPLETED")

if __name__ == "__main__":
    unittest.main()
