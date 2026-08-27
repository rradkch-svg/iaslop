import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pronunciation import PronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE

class TestPronunciationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PronunciationEngine()

    def test_mystery_names_phonetic_replacement(self):
        """Verifica a substituição de termos e nomes históricos de mistérios."""
        text = "O incidente no passo Dyatlov e os segredos de Camp Century na Groenlândia."
        spoken = self.engine.apply_pronunciation_to_text(text)
        
        self.assertIn("Di-át-lov", spoken)
        self.assertIn("Kemp Sênturi", spoken)

    def test_units_and_quantities(self):
        """Verifica expansão de unidades científicas (km, hz, rpm)."""
        text = "A perfuração atingiu 12km e detectou uma frequência de 10hz com rotação de 3000rpm."
        spoken = self.engine.apply_pronunciation_to_text(text)
        
        self.assertIn("12 quilômetros", spoken)
        self.assertIn("10 hérts", spoken)
        self.assertIn("3000 érre-pê-eme", spoken)

    def test_custom_rule_addition(self):
        """Verifica adição de regra customizada em tempo de execução."""
        self.engine.add_custom_rule("Area 51", "Área Cinquenta e Um Secreta")
        text = "Eles entraram na Area 51 ontem."
        spoken = self.engine.apply_pronunciation_to_text(text)
        self.assertIn("Área Cinquenta e Um Secreta", spoken)

    def test_preserves_casing_context(self):
        """Verifica que maiúsculas são respeitadas na substituição."""
        text = "DERINKUYU foi esculpida na rocha."
        spoken = self.engine.apply_pronunciation_to_text(text)
        self.assertIn("DE-RIN-CÚ-IU", spoken)

if __name__ == "__main__":
    unittest.main()
