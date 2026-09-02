import os
import sys
import unittest
import tempfile
import shutil
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from checkpoint_manager import CheckpointManager

class TestBatchCleanup(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ckpt_mgr = CheckpointManager(root_dir=self.test_dir, videos_per_batch=2)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_batch_cleanup_script(self):
        """Verifica a geração do script limpar_conteudo.bat no diretório do batch."""
        script_path = self.ckpt_mgr.generate_batch_cleanup_script(0)
        self.assertTrue(os.path.exists(script_path))
        self.assertTrue(script_path.endswith("limpar_conteudo.bat"))
        
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("metadata.txt", content)
        self.assertIn("*.mp4", content)

    def test_clean_batch_media_preserves_metadata(self):
        """Verifica que a limpeza remove mídias pesadas mas preserva metadata.txt e checkpoint.json."""
        v_dir = self.ckpt_mgr.get_video_dir(0, 0)
        
        # Cria arquivos simulados
        meta_file = os.path.join(v_dir, "metadata.txt")
        ckpt_file = os.path.join(v_dir, "checkpoint.json")
        mp4_file = os.path.join(v_dir, "final_video.mp4")
        mp3_file = os.path.join(v_dir, "audio.mp3")
        ass_file = os.path.join(v_dir, "subtitles.ass")
        
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write("TÍTULO: Teste de Mistério\nDESCRIÇÃO: Descrição de teste\nHASHTAGS: #teste")
        with open(ckpt_file, "w", encoding="utf-8") as f:
            json.dump({"status": "COMPLETED", "completed_at": "2026-09-02T12:00:00"}, f)
        with open(mp4_file, "wb") as f:
            f.write(b"0" * 1024 * 1024)  # 1MB
        with open(mp3_file, "wb") as f:
            f.write(b"0" * 100 * 1024)   # 100KB
        with open(ass_file, "w", encoding="utf-8") as f:
            f.write("[Script Info]\nTitle: Test Sub")

        # Cria pasta broll simulada
        broll_dir = os.path.join(v_dir, "broll")
        os.makedirs(broll_dir, exist_ok=True)
        with open(os.path.join(broll_dir, "clip.mp4"), "wb") as f:
            f.write(b"0" * 500 * 1024)

        # Executa limpeza
        res = self.ckpt_mgr.clean_batch_media(0)

        # Verifica arquivos preservados
        self.assertTrue(os.path.exists(meta_file), "metadata.txt DEVE ser preservado!")
        self.assertTrue(os.path.exists(ckpt_file), "checkpoint.json DEVE ser preservado!")
        
        # Verifica arquivos removidos
        self.assertFalse(os.path.exists(mp4_file), "final_video.mp4 deve ser removido!")
        self.assertFalse(os.path.exists(mp3_file), "audio.mp3 deve ser removido!")
        self.assertFalse(os.path.exists(ass_file), "subtitles.ass deve ser removido!")
        self.assertFalse(os.path.exists(broll_dir), "broll/ deve ser removido!")
        
        # Verifica estatísticas de liberação
        self.assertGreater(res["freed_bytes"], 1024 * 1024)
        self.assertEqual(res["removed_files"], 4)

        # Verifica se o vídeo limpo mantém status COMPLETED
        stage, ckpt_data = self.ckpt_mgr.determine_video_resume_stage(0, 0)
        self.assertEqual(stage, "COMPLETED")
        self.assertTrue(ckpt_data.get("cleaned"))

if __name__ == "__main__":
    unittest.main()
