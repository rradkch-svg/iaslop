import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from agents import (
    validate_gemini_api_connection,
    ProposerAgent,
    DirectorAgent,
    resolve_gemini_api_key
)
from auto_pipeline import AutoPipelineRunner

class TestPreflightAndFallbacks(unittest.TestCase):
    def test_preflight_validation_with_dummy_key(self):
        """Garante que chave vazia ou placeholder e rejeitada no pre-voo."""
        valid, msg = validate_gemini_api_connection(api_key="sua_chave_gemini_aqui")
        self.assertFalse(valid)
        self.assertIn("não configurada", msg)

    def test_preflight_validation_with_invalid_key(self):
        """Garante que chave invalida e rejeitada no pre-voo."""
        valid, msg = validate_gemini_api_connection(api_key="AIzaSy_CHAVE_INVALIDA_TESTE_12345")
        self.assertFalse(valid)
        self.assertIn("Falha na validação", msg)

    def test_proposer_raises_on_invalid_key(self):
        """Garante que ProposerAgent nao gera topicos falsos/genericos quando LLM falha."""
        proposer = ProposerAgent(api_key="AIzaSy_CHAVE_INVALIDA_TESTE_12345", auto_fallback=False, auto_cooldown=False)
        with self.assertRaises(Exception):
            proposer.generate_topics(count=1)

    def test_director_raises_on_invalid_key(self):
        """Garante que DirectorAgent nao cria roteiro sintetico generico quando LLM falha."""
        director = DirectorAgent(api_key="AIzaSy_CHAVE_INVALIDA_TESTE_12345", auto_fallback=False, auto_cooldown=False)
        dummy_topic = {
            "tema": "Misterio Teste",
            "hook": "Frase de hook",
            "explicacao_tecnica": "Explicacao tecnica factual"
        }
        with self.assertRaises(Exception):
            director.generate_storyboard(dummy_topic)

if __name__ == "__main__":
    unittest.main()

