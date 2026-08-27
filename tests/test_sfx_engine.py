import os
import sys
import unittest
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from sfx_engine import SFXEngine, DEFAULT_SFX_ENGINE

class TestSFXEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.engine = SFXEngine(sfx_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sfx_soundbank_initialization(self):
        """Verifica a inicialização e presença de whooshes, sinos, clicks e sub-impacts."""
        tracks = self.engine.list_available_sfx()
        self.assertGreaterEqual(len(tracks), 6)
        
        filenames = [t["filename"] for t in tracks]
        self.assertIn("whoosh_fast.wav", filenames)
        self.assertIn("bell_mystery_chime.wav", filenames)
        self.assertIn("click_mechanical.wav", filenames)
        self.assertIn("sub_impact_hit.wav", filenames)

    def test_detect_sfx_cues_transitions_and_keywords(self):
        """Verifica a detecção automática de transições de cena e palavras-chave."""
        storyboard = [
            {"scene_id": 1, "fala": "Este documento confidencial revela o projeto secreto.", "duracao_estimada": 5.0},
            {"scene_id": 2, "fala": "Uma anomalia impossível foi registrada nas coordenadas polares.", "duracao_estimada": 5.0},
            {"scene_id": 3, "fala": "Ninguém jamais explicou este mistério do abismo.", "duracao_estimada": 5.0}
        ]
        words_timing = [
            {"word": "Este", "start": 0.2, "end": 0.5},
            {"word": "documento", "start": 0.6, "end": 1.2},
            {"word": "confidencial", "start": 1.3, "end": 2.0},
            {"word": "anomalia", "start": 6.0, "end": 6.8},
            {"word": "mistério", "start": 11.0, "end": 11.7}
        ]

        cues = self.engine.detect_sfx_cues(storyboard, words_timing, total_duration=15.0)
        self.assertGreaterEqual(len(cues), 4)

        cue_types = [c["type"] for c in cues]
        self.assertIn("sub_impact", cue_types) # Gancho aos 0.05s
        self.assertIn("whoosh", cue_types)     # Transição entre cenas
        self.assertTrue("click" in cue_types or "bell" in cue_types) # Palavras misteriosas

    def test_build_sfx_audio_track(self):
        """Verifica a montagem de uma trilha de áudio SFX multicanal sincronizada."""
        cues = [
            {"type": "sub_impact", "file": os.path.join(self.test_dir, "sub_impact_hit.wav"), "timestamp": 0.05, "volume": 0.5},
            {"type": "whoosh", "file": os.path.join(self.test_dir, "whoosh_fast.wav"), "timestamp": 2.0, "volume": 0.4},
            {"type": "bell", "file": os.path.join(self.test_dir, "bell_mystery_chime.wav"), "timestamp": 4.0, "volume": 0.35}
        ]
        out_wav = os.path.join(self.test_dir, "test_sfx_track.wav")
        res = self.engine.build_sfx_audio_track(cues, out_wav, total_duration=6.0)

        self.assertTrue(os.path.exists(res))
        self.assertGreater(os.path.getsize(res), 100000)

if __name__ == "__main__":
    unittest.main()
