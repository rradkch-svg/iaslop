import os
import sys
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from agents import DissertationAgent, DirectorAgent

class TestDissertationAndDistillation(unittest.TestCase):
    def setUp(self):
        self.topic = {
            "tema": "A Base Nuclear Secreta Enterrada Sob o Gelo ❄️☢️",
            "hook": "Em plena Guerra Fria, uma cidade militar com reator nuclear foi construída sob o gelo polar.",
            "explicacao_tecnica": "O Projeto Camp Century foi uma base ultrassecreta escavada na calota de gelo da Groenlândia com túneis para mísseis balísticos nucleares."
        }

    @patch("agents.generate_with_resilience")
    def test_dissertation_generation_structure(self, mock_gen):
        """Verifica se o DissertationAgent constrói a monografia factual estruturada."""
        mock_gen.return_value = '{"entidade_principal": "Camp Century", "dados_quantitativos": {"profundidade": "30m", "ano": 1959}, "anomalia_ou_enigma_central": "Mísseis sob o gelo", "teorias_e_evidencias": "Desclassificado em 1996", "dissertacao_completa": "Camp Century foi construída pelo Exército dos EUA..."}'
        
        agent = DissertationAgent()
        diss = agent.generate_dissertation(self.topic)
        
        self.assertEqual(diss["entidade_principal"], "Camp Century")
        self.assertIn("dissertacao_completa", diss)

    @patch("agents.generate_with_resilience")
    def test_director_distillation_consumes_dissertation(self, mock_gen):
        """Verifica se o DirectorAgent recebe a dissertação e destila o plano de cenas."""
        mock_gen.return_value = '{"cenas": [{"scene_id": 1, "fala": "Uma cidade nuclear no gelo.", "youtube_query": "Camp century real footage", "duracao_estimada": 5.0}]}'
        
        diss_data = {
            "entidade_principal": "Camp Century",
            "dados_quantitativos": {"ano": 1959},
            "anomalia_ou_enigma_central": "Reator sob o gelo",
            "dissertacao_completa": "Camp Century continha 30 túneis..."
        }
        
        director = DirectorAgent()
        scenes = director.generate_storyboard(self.topic, dissertacao_data=diss_data)
        
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["scene_id"], 1)

if __name__ == "__main__":
    unittest.main()
