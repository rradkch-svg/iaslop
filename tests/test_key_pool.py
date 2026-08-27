import os
import sys
import time
import unittest
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from key_pool import APIKeyPriorityPool

class TestAPIKeyPriorityPool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.test_dir, "test_key_pool_state.json")
        self.k1 = "AIzaSyDummyKeyNumberOnePrimaryForTesting111111111111111"
        self.k2 = "AIzaSyDummyKeyNumberTwoSecondaryForTesting2222222222222"
        self.k3 = "AIzaSyDummyKeyNumberThreeBackupForTesting33333333333333"
        self.pool = APIKeyPriorityPool(state_file=self.state_file, explicit_keys=[self.k1, self.k2, self.k3])

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_priority_ordering(self):
        """Verifica se a descoberta mantém a prioridade estrita (Chave 1 > Chave 2 > Chave 3)."""
        keys = self.pool.discover_keys()
        self.assertEqual(keys, [self.k1, self.k2, self.k3])

        active_k, p_idx, rem = self.pool.get_next_available_key()
        self.assertEqual(active_k, self.k1)
        self.assertEqual(p_idx, 0)
        self.assertEqual(rem, 0.0)

    def test_key_rotation_on_1h_cooldown(self):
        """Verifica a rotação de Chave 1 para Chave 2 e Chave 3 com 1h de cooldown."""
        # 1. Chave 1 esgota tokens -> Cooldown de 1h
        self.pool.mark_key_cooldown(self.k1, duration_seconds=3600, reason="Quota 429")
        active_k, p_idx, _ = self.pool.get_next_available_key()
        self.assertEqual(active_k, self.k2, "Deveria alternar imediatamente para a Chave 2 (Prioridade 2)")
        self.assertEqual(p_idx, 1)

        # 2. Chave 2 esgota tokens -> Cooldown de 1h
        self.pool.mark_key_cooldown(self.k2, duration_seconds=3600, reason="Quota 429")
        active_k, p_idx, _ = self.pool.get_next_available_key()
        self.assertEqual(active_k, self.k3, "Deveria alternar imediatamente para a Chave 3 (Prioridade 3)")
        self.assertEqual(p_idx, 2)

        # 3. Chave 3 esgota tokens -> Todas bloqueadas
        self.pool.mark_key_cooldown(self.k3, duration_seconds=3600, reason="Quota 429")
        active_k, p_idx, rem_s = self.pool.get_next_available_key()
        self.assertIsNone(active_k, "Nenhuma chave deve estar disponível quando todas estão em cooldown")
        self.assertGreater(rem_s, 3500, "Tempo restante deve refletir a espera da primeira chave")

    def test_priority_restoration_after_cooldown_expires(self):
        """Verifica se a Chave 1 reassume a Prioridade 1 assim que seu cooldown expira."""
        # Coloca Chave 1 com cooldown zerado e Chave 2 e 3 com cooldown de 1h (3600s)
        self.pool.mark_key_cooldown(self.k1, duration_seconds=0, reason="Teste rápido")
        self.pool.mark_key_cooldown(self.k2, duration_seconds=3600, reason="Quota 429")
        self.pool.mark_key_cooldown(self.k3, duration_seconds=3600, reason="Quota 429")

        time.sleep(0.05)
        active_k, p_idx, _ = self.pool.get_next_available_key()
        self.assertEqual(active_k, self.k1, "Chave 1 liberada deve ter prioridade máxima sobre Chaves 2 e 3")
        self.assertEqual(p_idx, 0)

    def test_persistence_of_cooldown_state(self):
        """Verifica se o estado de cooldown é gravado e recarregado do disco."""
        self.pool.mark_key_cooldown(self.k1, duration_seconds=3600, reason="Rate limit")

        # Nova instância com o mesmo arquivo de estado
        new_pool = APIKeyPriorityPool(state_file=self.state_file, explicit_keys=[self.k1, self.k2])

        active_k, p_idx, _ = new_pool.get_next_available_key()
        self.assertEqual(active_k, self.k2, "Nova instância deve respeitar o cooldown persistido da Chave 1")

if __name__ == "__main__":
    unittest.main()
