import os
import sys
import unittest
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from checkpoint_manager import CheckpointManager
from agents import SemanticAuditorAgent

class TestDeepSemanticBlacklist(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ckpt_mgr = CheckpointManager(root_dir=self.test_dir)
        
        # Popula a blacklist com alguns temas conhecidos
        initial_topics = [
            {
                "tema": "A Base Nuclear Secreta Enterrada Sob o Gelo ❄️☢️",
                "core_entity": "Camp Century",
                "hook": "Em plena Guerra Fria, uma cidade militar inteira com reator nuclear foi enterrada sob o gelo polar.",
                "explicacao_tecnica": "O Projeto Camp Century foi uma base ultrassecreta escavada na calota de gelo da Groenlândia com túneis para mísseis balísticos nucleares.",
                "tags": ["#CampCentury", "#GuerraFria", "#Groenlandia", "#Misterios"]
            },
            {
                "tema": "O Poço Mais Fundo da Terra e os Sons de Kola 🕳️🇷🇺",
                "core_entity": "Poço de Kola",
                "hook": "Eles cavaram doze quilômetros em direção ao centro da Terra e o que encontraram desafiou a física.",
                "explicacao_tecnica": "O Poço Superprofundo de Kola atingiu 12.262 metros de profundidade, revelando anomalias térmicas extremas.",
                "tags": ["#PocoDeKola", "#URSS", "#Geologia", "#SonsDoInferno"]
            },
            {
                "tema": "O Enigma do Passo Dyatlov nos Montes Urais 🏔️❄️",
                "core_entity": "Passo Dyatlov",
                "hook": "Nove montanhistas rasgaram a própria barraca por dentro e fugiram descalços na neve a menos trinta graus.",
                "explicacao_tecnica": "O Incidente do Passo Dyatlov em 1959 resultou na morte inexplicada de nove expedicionários soviéticos com traumas severos e radiação nas roupas.",
                "tags": ["#PassoDyatlov", "#MontesUrais", "#1959", "#MisteriosReais"]
            },
            {
                "tema": "Derinkuyu: A Cidade Subterrânea de 18 Andares ⛏️🏛️",
                "core_entity": "Derinkuyu",
                "hook": "Debaixo do solo da Turquia, uma cidade inteira de dezoito andares foi esculpida na rocha sólida.",
                "explicacao_tecnica": "Derinkuyu possui túneis com até 85 metros de profundidade, equipados com dutos de ar e portas circulares de pedra maciça.",
                "tags": ["#Derinkuyu", "#Capadocia", "#Subterraneo", "#Arqueologia"]
            }
        ]
        for i, top in enumerate(initial_topics):
            self.ckpt_mgr.add_to_blacklist(top, "batch_0", f"video_{i}")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_exact_title_match(self):
        """Garante bloqueio de título idêntico."""
        is_blk, reason = self.ckpt_mgr.is_in_blacklist("A Base Nuclear Secreta Enterrada Sob o Gelo ❄️☢️")
        self.assertTrue(is_blk)
        self.assertIn("Título idêntico", reason)

    def test_paraphrased_same_entity(self):
        """Garante bloqueio quando o título é parafraseado mas a entidade é a mesma (Kola)."""
        candidate = {
            "tema": "A Perfuração Soviética Superprofunda de 12km 🇷🇺⚒️",
            "hook": "Cientistas da URSS perfuraram o buraco mais fundo do planeta na península de Kola.",
            "explicacao_tecnica": "O projeto soviético em Kola cavou mais de 12 mil metros e registrou anomalias térmicas."
        }
        is_blk, reason = self.ckpt_mgr.is_in_blacklist(candidate)
        self.assertTrue(is_blk, "Deveria bloquear tema sobre o Poço de Kola mesmo com título diferente")
        self.assertTrue("KOLA" in reason.upper() or "POÇO" in reason.upper() or "SOVIÉTIC" in reason.upper())

    def test_dyatlov_different_title_same_hook_and_year(self):
        """Garante bloqueio quando Dyatlov é abordado com título sem o nome Dyatlov mas com mesmo evento em essência."""
        candidate = {
            "tema": "O Mistério dos 9 Alpinistas na Neve Soviética 🏔️⛺",
            "hook": "Em 1959 nos Montes Urais, nove esquiadores experientes rasgaram a barraca por dentro e morreram sem explicação.",
            "explicacao_tecnica": "A expedição soviética nos Urais em 1959 deixou corpos com traumas misteriosos e traços radioativos."
        }
        is_blk, reason = self.ckpt_mgr.is_in_blacklist(candidate)
        self.assertTrue(is_blk, "Deveria bloquear mesmo evento histórico de Dyatlov 1959 em essência")

    def test_derinkuyu_underground_city_variation(self):
        """Garante bloqueio de Derinkuyu com título focado na Capadócia."""
        candidate = {
            "tema": "O Labirinto Secreto Escavado Debaixo da Capadócia 🇹🇷",
            "hook": "Uma civilização inteira de 20 mil pessoas viveu em 18 andares subterrâneos na Turquia.",
            "explicacao_tecnica": "A cidade subterrânea na rocha vulcânica da Turquia abrigava milhares com ventilação e portas de pedra."
        }
        is_blk, reason = self.ckpt_mgr.is_in_blacklist(candidate)
        self.assertTrue(is_blk, "Deveria bloquear Derinkuyu pela essência de 18 andares subterrâneos na Capadócia")

    def test_genuinely_novel_topic_passes(self):
        """Garante que um mistério genuinamente inédito NÃO seja bloqueado."""
        novel_candidate = {
            "tema": "O Manuscrito Voynich: O Livro Mais Enigmático da História 📜",
            "core_entity": "Manuscrito Voynich",
            "hook": "Escrito em um código botânico medieval que nenhum criptógrafo do mundo jamais conseguiu decifrar.",
            "explicacao_tecnica": "O Manuscrito Voynich data do século XV com ilustrações botânicas e astronômicas desconhecidas.",
            "tags": ["#Voynich", "#Manuscrito", "#Criptografia", "#IdadeMedia"]
        }
        is_blk, reason = self.ckpt_mgr.is_in_blacklist(novel_candidate)
        self.assertFalse(is_blk, f"Tema inédito (Voynich) não deveria ser bloqueado! Motivo dado: {reason}")

    def test_another_novel_topic_passes(self):
        """Garante que as Linhas de Nazca passem sem falso positivo."""
        novel_candidate = {
            "tema": "Os Geoglifos Gigantes do Deserto de Nazca 🏜️🦅",
            "core_entity": "Linhas de Nazca",
            "hook": "Figuras colossais visíveis apenas do céu foram desenhadas na terra há mais de dois mil anos.",
            "explicacao_tecnica": "As Linhas de Nazca no sul do Peru representam centenas de figuras geométricas e zoomórficas.",
            "tags": ["#Nazca", "#Peru", "#Arqueologia", "#Geoglifos"]
        }
        is_blk, reason = self.ckpt_mgr.is_in_blacklist(novel_candidate)
        self.assertFalse(is_blk, f"Tema inédito (Nazca) não deveria ser bloqueado! Motivo dado: {reason}")

if __name__ == "__main__":
    unittest.main()
