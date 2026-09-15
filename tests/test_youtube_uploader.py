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

from youtube_uploader import (
    find_system_browser,
    parse_netscape_cookies,
    parse_video_metadata,
    get_batch_videos_to_upload,
    save_upload_record,
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

    def test_save_upload_record_and_skip(self):
        """Garante que vídeos já marcados com sucesso em youtube_uploads.json sejam ignorados."""
        b_dir = os.path.join(self.test_dir, "batch_2")
        v0 = os.path.join(b_dir, "video_0")
        os.makedirs(v0, exist_ok=True)
        with open(os.path.join(v0, "final_output.mp4"), "wb") as f:
            f.write(b"0" * 20000)

        # Salva registro prévio de sucesso
        save_upload_record(2, "video_0", {"success": True, "url": "https://youtu.be/abc"}, checkpoint_dir=self.test_dir)

        # Deve retornar vazio pois já foi postado
        targets = get_batch_videos_to_upload(2, checkpoint_dir=self.test_dir)
        self.assertEqual(len(targets), 0)


if __name__ == "__main__":
    unittest.main()
