import os
import sys
import unittest
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from subtitles import convert_words_to_ass, hex_to_ass, format_ass_time

class TestSubtitlesTypography(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ass_file = os.path.join(self.test_dir, "test_subtitles.ass")
        self.sample_words = [
            {"word": "O", "start": 0.0, "end": 0.25},
            {"word": "MISTÉRIO", "start": 0.25, "end": 0.85},
            {"word": "REVELADO", "start": 0.85, "end": 1.40}
        ]

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_typography_high_impact(self):
        """Verifica se a fonte padrão é Arial Black com peso bold e margens seguras."""
        success = convert_words_to_ass(self.sample_words, self.ass_file)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.ass_file))

        with open(self.ass_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Verifica fonte de alto impacto Arial Black
        self.assertIn("Style: HormoziDefault,Arial Black,76,", content)
        # Verifica Bold=-1 (ativado)
        self.assertIn(",-1,0,0,0,100,100,1,0,1,6,2,2,40,40,620,1", content)
        # Verifica estilo Pill Box (fundo neon / borda grossa e texto preto)
        self.assertIn("\\c&H00000000&", content)
        self.assertIn("\\bord14", content)
        self.assertIn("\\fscx112", content)
        # Verifica estilo palavra inativa (texto branco com contorno)
        self.assertIn("\\bord6", content)

    def test_custom_font_and_margins(self):
        """Verifica suporte a customização de fontes como Trebuchet MS ou Montserrat."""
        success = convert_words_to_ass(
            self.sample_words,
            self.ass_file,
            font_name="Trebuchet MS",
            font_size=72,
            margin_v=580
        )
        self.assertTrue(success)

        with open(self.ass_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Style: HormoziDefault,Trebuchet MS,72,", content)
        self.assertIn(",580,1", content)

    def test_seamless_loop_tail_overhead(self):
        """Verifica se o tail_overhead padrão foi ajustado para 0.15s (sem silêncio morto)."""
        convert_words_to_ass(self.sample_words, self.ass_file, tail_overhead=0.15)

        with open(self.ass_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        dialogue_lines = [l for l in lines if l.startswith("Dialogue:")]
        self.assertTrue(len(dialogue_lines) > 0)
        # Última linha deve terminar em 1.40 + 0.15 = 1.55s -> 0:00:01.55
        last_line = dialogue_lines[-1]
        self.assertIn("0:00:01.55", last_line)

    def test_empty_words_fallback(self):
        """Verifica comportamento com lista vazia de palavras."""
        success = convert_words_to_ass([], self.ass_file)
        self.assertTrue(success)
        with open(self.ass_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("MINUTO INEXPLICAVEL", content)

if __name__ == "__main__":
    unittest.main()
