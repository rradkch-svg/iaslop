"""
Testes unitários para o módulo youtube_uploader.py.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from datetime import datetime, timezone, timedelta
from checkpoint_manager import CheckpointManager
from youtube_uploader import (
    find_system_browser,
    parse_netscape_cookies,
    parse_video_metadata,
    get_batch_videos_to_upload,
    save_upload_record,
    load_scheduled_slots,
    save_scheduled_slots,
    get_next_available_gmt_slot,
    reserve_gmt_slot,
    upload_and_clean_single_video,
    DEFAULT_GMT_SLOTS,
    YouTubeStudioUploader
)


class TestYouTubeUploader(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir, ignore_errors=True)

    def test_find_system_browser(self):
        """Verifica detecção de navegador instalador ou retorno controlado."""
        res = find_system_browser()
        if res:
            self.assertTrue(os.path.exists(res))
            self.assertTrue(res.endswith(".exe"))

    def test_parse_netscape_cookies(self):
        """Verifica conversão correta de cookies no formato Netscape."""
        cookie_path = os.path.join(self.test_dir, "test_cookies.txt")
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSESSION_ID\txyz123\n")
            f.write(".google.com\tTRUE\t/\tTRUE\t2147483647\tLOGIN_INFO\tabc456\n")
            f.write(".outro.com\tTRUE\t/\tFALSE\t2147483647\tOTHER\tval789\n")

        cookies = parse_netscape_cookies(cookie_path)
        self.assertEqual(len(cookies), 2)
        self.assertEqual(cookies[0]["name"], "SESSION_ID")
        self.assertEqual(cookies[0]["value"], "xyz123")
        self.assertEqual(cookies[0]["domain"], ".youtube.com")
        self.assertTrue(cookies[0]["secure"])

    def test_parse_video_metadata_from_txt(self):
        """Verifica extração correta a partir de metadata.txt."""
        v_dir = os.path.join(self.test_dir, "video_0")
        os.makedirs(v_dir, exist_ok=True)
        meta_file = os.path.join(v_dir, "metadata.txt")
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write("TÍTULO:\nO Mistério do Voo MH370\n\n")
            f.write("DESCRIÇÃO:\nO que aconteceu com a aeronave mais rastreada do mundo?\n\n")
            f.write("HASHTAGS:\n#Aviação #MH370 #Mistério\n")

        res = parse_video_metadata(v_dir)
        self.assertIn("MH370", res["title"])
        self.assertIn("#Shorts", res["title"])
        self.assertIn("aeronave", res["description"])
        self.assertIn("#MH370", res["tags"])

    def test_parse_video_metadata_from_checkpoint(self):
        """Verifica extração prioritária a partir de checkpoint.json."""
        v_dir = os.path.join(self.test_dir, "video_1")
        os.makedirs(v_dir, exist_ok=True)
        ckpt_file = os.path.join(v_dir, "checkpoint.json")
        with open(ckpt_file, "w", encoding="utf-8") as f:
            json.dump({
                "topic": {
                    "tema": "O Triângulo das Bermudas",
                    "descricao": "Explicação científica sobre anomalias magnéticas.",
                    "tags": ["#Bermudas", "#Oceano"]
                }
            }, f)

        res = parse_video_metadata(v_dir)
        self.assertIn("Triângulo das Bermudas", res["title"])
        self.assertIn("#Shorts", res["title"])
        self.assertIn("magnéticas", res["description"])
        self.assertIn("#Bermudas", res["tags"])

    def test_get_batch_videos_to_upload(self):
        """Testa varredura de vídeos concluídos pendentes de envio."""
        b_dir = os.path.join(self.test_dir, "batch_1")
        os.makedirs(b_dir, exist_ok=True)
        
        # Cria video_0 válido com mp4 de tamanho razoável
        v0 = os.path.join(b_dir, "video_0")
        os.makedirs(v0, exist_ok=True)
        with open(os.path.join(v0, "final_output.mp4"), "wb") as f:
            f.write(b"0" * 20000)
        with open(os.path.join(v0, "metadata.txt"), "w", encoding="utf-8") as f:
            f.write("TÍTULO:\nTeste Video 0\n")

        # Cria video_1 sem mp4
        v1 = os.path.join(b_dir, "video_1")
        os.makedirs(v1, exist_ok=True)

        targets = get_batch_videos_to_upload(1, checkpoint_dir=self.test_dir)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["video_key"], "video_0")

    def test_get_next_available_gmt_slot(self):
        """Verifica se o slot retornado pertence aos horários fixos e avança quando ocupado."""
        slot1 = get_next_available_gmt_slot(safety_buffer_minutes=1, checkpoint_dir=self.test_dir)
        self.assertIn(slot1.hour, DEFAULT_GMT_SLOTS)
        self.assertEqual(slot1.minute, 0)
        self.assertEqual(slot1.tzinfo, timezone.utc)

        # Reserva o slot1 e calcula o próximo
        reserve_gmt_slot(slot1, {"batch_index": 1, "video_index": 0}, checkpoint_dir=self.test_dir)
        slot2 = get_next_available_gmt_slot(safety_buffer_minutes=1, checkpoint_dir=self.test_dir)
        self.assertNotEqual(slot1, slot2)
        self.assertGreater(slot2, slot1)
        self.assertIn(slot2.hour, DEFAULT_GMT_SLOTS)

    def test_clean_single_video_media_preserves_metadata(self):
        """Testa se clean_single_video_media remove apenas arquivos pesados de mídia e atualiza checkpoint."""
        mgr = CheckpointManager(root_dir=self.test_dir)
        b_idx, v_idx = 3, 0
        v_dir = mgr.get_video_dir(b_idx, v_idx)
        os.makedirs(v_dir, exist_ok=True)

        # Cria mídias que devem ser excluídas
        final_v = os.path.join(v_dir, "final_output.mp4")
        with open(final_v, "wb") as f:
            f.write(b"M" * 50000)
        broll_dir = os.path.join(v_dir, "broll")
        os.makedirs(broll_dir, exist_ok=True)
        with open(os.path.join(broll_dir, "clip.mp4"), "wb") as f:
            f.write(b"B" * 20000)

        # Cria metadados que devem ser preservados
        meta_txt = os.path.join(v_dir, "metadata.txt")
        with open(meta_txt, "w", encoding="utf-8") as f:
            f.write("TÍTULO: Teste\n")
        diss_txt = os.path.join(v_dir, "dissertacao.txt")
        with open(diss_txt, "w", encoding="utf-8") as f:
            f.write("DISSERTAÇÃO: Teste\n")
        mgr.save_video_checkpoint(b_idx, v_idx, {"status": "COMPLETED"})

        # Executa limpeza
        res = mgr.clean_single_video_media(
            batch_index=b_idx,
            video_index=v_idx,
            youtube_url="https://youtu.be/test12345",
            scheduled_time="2026-09-15T15:00:00Z"
        )
        self.assertTrue(res["success"])
        self.assertGreater(res["freed_bytes"], 60000)

        # Verifica que arquivos pesados foram removidos
        self.assertFalse(os.path.exists(final_v))
        self.assertFalse(os.path.exists(broll_dir))

        # Verifica que metadados permanecem
        self.assertTrue(os.path.exists(meta_txt))
        self.assertTrue(os.path.exists(diss_txt))

        # Verifica que checkpoint foi atualizado com o link do YouTube
        ckpt = mgr.load_video_checkpoint(b_idx, v_idx)
        self.assertTrue(ckpt.get("cleaned"))
        self.assertEqual(ckpt.get("youtube_url"), "https://youtu.be/test12345")
        self.assertEqual(ckpt.get("youtube_scheduled_time"), "2026-09-15T15:00:00Z")

    @patch("youtube_uploader.YouTubeStudioUploader.upload_video")
    def test_upload_and_clean_single_video_mock(self, mock_upload):
        """Testa o fluxo completo: upload bem-sucedido seguido de alocação de slot e limpeza da mídia."""
        mock_upload.return_value = {
            "success": True,
            "title": "Mistério Fake #Shorts",
            "url": "https://youtu.be/fake_url_99"
        }

        mgr = CheckpointManager(root_dir=self.test_dir)
        b_idx, v_idx = 4, 0
        v_dir = mgr.get_video_dir(b_idx, v_idx)
        os.makedirs(v_dir, exist_ok=True)
        final_mp4 = os.path.join(v_dir, "final_output.mp4")
        with open(final_mp4, "wb") as f:
            f.write(b"V" * 30000)
        with open(os.path.join(v_dir, "metadata.txt"), "w", encoding="utf-8") as f:
            f.write("TÍTULO:\nMistério Fake\n")
        mgr.save_video_checkpoint(b_idx, v_idx, {"status": "COMPLETED"})

        res = upload_and_clean_single_video(b_idx, v_idx, checkpoint_dir=self.test_dir, headless=True)
        self.assertTrue(res["success"])
        self.assertTrue(res["cleaned"])
        self.assertEqual(res["url"], "https://youtu.be/fake_url_99")

        # Garante que o arquivo MP4 foi removido do disco
        self.assertFalse(os.path.exists(final_mp4))

        # Garante que o slot foi reservado
        reserved = load_scheduled_slots(self.test_dir)
        self.assertEqual(len(reserved), 1)


if __name__ == "__main__":
    unittest.main()

