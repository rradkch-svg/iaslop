import os
import sys
import unittest
import tempfile
import shutil
import json
import zipfile
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from email_service import (
    get_batch_manifest,
    zip_batch,
    zip_batch_metadata,
    format_email_body,
    send_batch_email,
    DEFAULT_RECIPIENT
)


class TestEmailService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.batch_dir = os.path.join(self.test_dir, "batch_99")
        os.makedirs(self.batch_dir, exist_ok=True)

        # Cria estrutura de 2 vídeos de teste
        for v_idx in range(2):
            v_dir = os.path.join(self.batch_dir, f"video_{v_idx}")
            os.makedirs(v_dir, exist_ok=True)

            # Metadata
            with open(os.path.join(v_dir, "metadata.txt"), "w", encoding="utf-8") as f:
                f.write(f"TÍTULO: Mistério do Vídeo {v_idx} 🛸\n")
                f.write(f"HOOK: Você sabia deste segredo impressionante {v_idx}?\n")
                f.write("HASHTAGS: #misterio #curiosidades\n")

            # Checkpoint
            with open(os.path.join(v_dir, "checkpoint.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "status": "COMPLETED",
                    "audio_duration": 45.5,
                    "topic": {
                        "tema": f"Mistério do Vídeo {v_idx} 🛸",
                        "hook": f"Você sabia deste segredo impressionante {v_idx}?",
                        "tags": ["#misterio", "#curiosidades", "#fatos"]
                    }
                }, f)

            # Dissertação
            with open(os.path.join(v_dir, "dissertacao.txt"), "w", encoding="utf-8") as f:
                f.write(f"Texto detalhado da dissertação para o vídeo {v_idx}.")

            # Subtitles
            with open(os.path.join(v_dir, "subtitles.ass"), "w", encoding="utf-8") as f:
                f.write("[Script Info]\nTitle: Test Sub")

            # Final MP4 (simulado)
            with open(os.path.join(v_dir, "final_output.mp4"), "wb") as f:
                f.write(b"MP4_DATA" * 1000)

            # Raw b-roll temporário (deve ser ignorado por padrão)
            broll_dir = os.path.join(v_dir, "broll")
            os.makedirs(broll_dir, exist_ok=True)
            with open(os.path.join(broll_dir, "temp_broll.mp4"), "wb") as f:
                f.write(b"BROLL_DATA" * 5000)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_batch_manifest(self):
        """Verifica a extração correta de manifestos de batch."""
        manifest = get_batch_manifest(99, checkpoint_dir=self.test_dir)
        self.assertEqual(manifest["batch_index"], 99)
        self.assertEqual(manifest["total_videos"], 2)
        self.assertEqual(manifest["completed_videos"], 2)
        self.assertAlmostEqual(manifest["total_duration_sec"], 91.0, places=1)
        self.assertEqual(len(manifest["videos"]), 2)
        self.assertIn("Mistério do Vídeo 0", manifest["videos"][0]["title"])

    def test_zip_batch_creates_valid_archive(self):
        """Verifica criação do arquivo ZIP do batch com exclusão de arquivos temporários."""
        zip_path, size_mb = zip_batch(99, checkpoint_dir=self.test_dir)
        self.assertTrue(os.path.exists(zip_path))
        self.assertTrue(zip_path.endswith("batch_99.zip"))
        self.assertGreater(size_mb, 0.0)

        # Verifica conteúdo do zip
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            # Deve conter metadados e vídeos finais
            self.assertTrue(any("metadata.txt" in name for name in namelist))
            self.assertTrue(any("final_output.mp4" in name for name in namelist))
            # NÃO deve conter pastas temporárias broll
            self.assertFalse(any("broll" in name for name in namelist))

    def test_zip_batch_metadata_only(self):
        """Verifica criação do pacote leve de metadados sem arquivos de vídeo."""
        meta_zip_path, meta_size_mb = zip_batch_metadata(99, checkpoint_dir=self.test_dir)
        self.assertTrue(os.path.exists(meta_zip_path))
        self.assertLess(meta_size_mb, 2.0)

        with zipfile.ZipFile(meta_zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertTrue(any("metadata.txt" in name for name in namelist))
            self.assertTrue(any("dissertacao.txt" in name for name in namelist))
            self.assertFalse(any(".mp4" in name for name in namelist))

    def test_format_email_body(self):
        """Verifica geração dos formatos plaintext e HTML com métricas e lista de vídeos."""
        manifest = get_batch_manifest(99, checkpoint_dir=self.test_dir)
        plain, html = format_email_body(
            manifest=manifest,
            zip_path="C:/dummy/batch_99.zip",
            zip_size_mb=12.5,
            is_attached=True,
            attached_filename="batch_99.zip"
        )
        self.assertIn("BATCH 99 CONCLUÍDO", plain)
        self.assertIn("Mistério do Vídeo 0", plain)
        self.assertIn("batch_99", html)
        self.assertIn("Mistério do Vídeo 0", html)
        self.assertIn("12.5 MB", html)

    def test_send_batch_email_missing_credentials_graceful(self):
        """Verifica que a ausência de credenciais salva o ZIP localmente sem disparar erro."""
        with patch.dict(os.environ, {}, clear=True):
            res = send_batch_email(99, checkpoint_dir=self.test_dir, recipient="rra.dkch@gmail.com")
            self.assertFalse(res["success"])
            self.assertEqual(res["reason"], "missing_smtp_credentials")
            self.assertTrue(os.path.exists(res["zip_path"]))
            self.assertEqual(res["recipient"], "rra.dkch@gmail.com")

    @patch("smtplib.SMTP_SSL")
    def test_send_batch_email_with_mock_smtp(self, mock_smtp_ssl):
        """Verifica envio de e-mail com sucesso usando credenciais SMTP simuladas."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        env_vars = {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "465",
            "SMTP_USER": "test@gmail.com",
            "SMTP_PASSWORD": "app_password_1234",
            "EMAIL_RECIPIENT": "rra.dkch@gmail.com",
            "EMAIL_MAX_ATTACHMENT_MB": "24.0"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            res = send_batch_email(99, checkpoint_dir=self.test_dir)
            self.assertTrue(res["success"])
            self.assertEqual(res["recipient"], "rra.dkch@gmail.com")
            mock_server.login.assert_called_once_with("test@gmail.com", "app_password_1234")
            mock_server.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
