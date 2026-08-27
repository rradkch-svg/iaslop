import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from agents import resolve_gemini_api_keys, resolve_gemini_api_key

class TestKeyFallbackAndResolution(unittest.TestCase):
    def test_explicit_key_resolution(self):
        """Verifica resolução com chave explícita simples e múltipla."""
        key1 = "AIzaSyTestKeyOneForUnitTest12345"
        key2 = "AIzaSyTestKeyTwoForUnitTest67890"
        
        keys = resolve_gemini_api_keys([key1, key2])
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys[0], key1)
        self.assertEqual(keys[1], key2)

    def test_comma_separated_keys(self):
        """Verifica resolução de múltiplas chaves separadas por vírgula."""
        raw = "AIzaSyKeyA12345678901234567890, AIzaSyKeyB12345678901234567890"
        keys = resolve_gemini_api_keys(raw)
        self.assertEqual(len(keys), 2)

    def test_ignores_placeholders(self):
        """Garante que placeholders sejam ignorados por segurança."""
        keys = resolve_gemini_api_keys("sua_chave_gemini_aqui")
        for k in keys:
            self.assertNotEqual(k, "sua_chave_gemini_aqui")

if __name__ == "__main__":
    unittest.main()
