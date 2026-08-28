import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from audio import AudioEngine

class TestAudioEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AudioEngine()

    def test_sanitize_text_for_pacing(self):
        text = '**Aviso**... Segredo — Revelado!'
        cleaned = self.engine._sanitize_text_for_pacing(text)
        self.assertEqual(cleaned, 'Aviso. Segredo, Revelado!')

    def test_generate_audio_synthesis(self):
        output_file = os.path.join(PROJECT_ROOT, 'tests', 'temp_test_audio.mp3')
        try:
            ok, timing = self.engine.generate_audio('Este é um teste do motor de áudio.', output_file)
            self.assertTrue(ok)
            self.assertTrue(len(timing) > 0)
            self.assertTrue(os.path.exists(output_file))
            self.assertTrue(os.path.getsize(output_file) > 1000)
        finally:
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass

if __name__ == '__main__':
    unittest.main()
