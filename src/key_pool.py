"""
Módulo de Gerenciamento Prioritário de Chaves da API Gemini (APIKeyPriorityPool).
Controla o rodízio de chaves por prioridade estrita (Chave 1 -> Chave 2 -> Chave 3),
aplica cooldown individual de 1 HORA (3600s) para chaves que esgotarem cota/tokens,
e aciona espera de 30 MINUTOS (1800s) no Watchdog caso todas as chaves estejam em cooldown.
"""

import os
import re
import time
import json
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

try:
    from .logger import app_logger, record_throttling
except ImportError:
    try:
        from logger import app_logger, record_throttling
    except ImportError:
        import logging
        app_logger = logging.getLogger("key_pool")
        def record_throttling(*args, **kwargs): pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "checkpoint")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
KEY_POOL_STATE_FILE = os.path.join(CHECKPOINT_DIR, "api_key_pool_state.json")

KEY_COOLDOWN_DURATION = 3600 # 1 Hora de espera por chave bloqueada/sem tokens
ALL_KEYS_WAIT_DURATION = 1800 # 30 Minutos de espera global no Watchdog

class APIKeyPriorityPool:
    """
    Gerenciador com fila de prioridade estrita e persistência de cooldown para chaves Gemini.
    """

    def __init__(self, state_file: Optional[str] = None, explicit_keys: Optional[Any] = None):
        self.state_file = state_file or KEY_POOL_STATE_FILE
        self.explicit_keys = explicit_keys
        self.lock = threading.RLock()
        self._keys_cache: List[str] = []
        self._load_state()

    def _mask_key(self, key: str) -> str:
        if not key or len(key) < 14:
            return "***"
        return f"{key[:8]}...{key[-6:]}"

    def discover_keys(self, explicit_keys: Optional[Any] = None) -> List[str]:
        """
        Descobre e ordena as chaves da API do Gemini respeitando estritamente a ordem de prioridade:
        Prioridade 1: GEMINI_API_KEY (Chave Primária)
        Prioridade 2: GEMINI_FALLBACK_API_KEY (Chave Secundária)
        Prioridade 3: GEMINI_BACKUP_API_KEY (Chave Terciária)
        Demais fontes: gemini-api.txt, keys.txt, GEMINI_API_KEYS
        """
        with self.lock:
            target_explicit = explicit_keys if explicit_keys is not None else self.explicit_keys
            if target_explicit is not None:
                collected: List[str] = []
                if isinstance(target_explicit, (list, tuple, set)):
                    for k in target_explicit:
                        k_s = str(k).strip().strip("'\"")
                        if len(k_s) >= 20 and k_s not in collected:
                            collected.append(k_s)
                elif isinstance(target_explicit, str):
                    for token in re.split(r"[,;\n\r\s]+", target_explicit.strip()):
                        tok_s = token.strip().strip("'\"")
                        if len(tok_s) >= 20 and tok_s not in collected:
                            collected.append(tok_s)
                if collected:
                    self._keys_cache = collected
                    return collected

            collected = []

            def _add_key(k: Optional[str]):
                if not k:
                    return
                k = k.strip().strip("'\"")
                if not k or k in ("sua_chave_gemini_aqui", "sua_chave_gemini_redundancia_aqui"):
                    return
                if len(k) >= 20 and k not in collected:
                    collected.append(k)


            # 2. Variáveis de ambiente primárias (Ordem de Prioridade 1, 2, 3)
            _add_key(os.environ.get("GEMINI_API_KEY"))
            _add_key(os.environ.get("GEMINI_FALLBACK_API_KEY"))
            _add_key(os.environ.get("GEMINI_API_KEY_FALLBACK"))
            _add_key(os.environ.get("GEMINI_BACKUP_API_KEY"))
            _add_key(os.environ.get("GEMINI_REDUNDANCY_KEY"))

            # 3. Arquivo .env local
            env_path = os.path.join(PROJECT_ROOT, ".env")
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                k_clean = k.strip()
                                v_clean = v.strip().strip("'\"")
                                if k_clean in ("GEMINI_API_KEY", "GEMINI_FALLBACK_API_KEY", "GEMINI_BACKUP_API_KEY", "GEMINI_REDUNDANCY_KEY"):
                                    _add_key(v_clean)
                                elif k_clean == "GEMINI_API_KEYS":
                                    for tok in re.split(r"[,;\s]+", v_clean):
                                        _add_key(tok)
                except Exception:
                    pass

            # 4. Arquivo gemini-api.txt / keys.txt
            txt_files = ["gemini-api.txt", "keys.txt", "gemini_api.txt", "api_key.txt"]
            for sdir in [os.getcwd(), PROJECT_ROOT]:
                for fn in txt_files:
                    fp = os.path.join(sdir, fn)
                    if os.path.exists(fp):
                        try:
                            with open(fp, "r", encoding="utf-8") as f:
                                content = f.read()
                            # Headers curl
                            headers = re.findall(r"X-goog-api-key:\s*['\"]?([A-Za-z0-9_\-\.]+)['\"]?", content, re.IGNORECASE)
                            for h in headers:
                                _add_key(h)
                            # Linhas diretas
                            for line in content.splitlines():
                                l = line.strip()
                                if l and not l.startswith("#") and not l.startswith("//") and " " not in l and len(l) >= 20:
                                    _add_key(l)
                        except Exception:
                            pass

            self._keys_cache = collected
            return collected

    def _load_state(self) -> Dict[str, Any]:
        """Carrega os estados de cooldown persistidos em disco."""
        with self.lock:
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "keys" in data:
                            return data
                except Exception as e:
                    app_logger.warning(f"[KeyPool] Erro ao carregar estado de chaves: {e}")

            default_state = {
                "version": 1,
                "updated_at": datetime.now().isoformat(),
                "keys": {}
            }
            return default_state

    def _save_state(self, state: Dict[str, Any]):
        """Salva atomicamente o estado de cooldown do pool."""
        with self.lock:
            state["updated_at"] = datetime.now().isoformat()
            temp_file = self.state_file + ".tmp"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2, ensure_ascii=False)
                if os.path.exists(self.state_file):
                    try:
                        os.remove(self.state_file)
                    except:
                        pass
                os.rename(temp_file, self.state_file)
            except Exception as e:
                app_logger.error(f"[KeyPool] Erro ao salvar estado de chaves: {e}")

    def mark_key_cooldown(
        self,
        key: str,
        duration_seconds: int = KEY_COOLDOWN_DURATION,
        reason: str = "Quota esgotada (429 Rate Limit) / Sem tokens"
    ):
        """
        Coloca uma chave específica em espera/cooldown de 1 HORA (3600s).
        """
        with self.lock:
            now = time.time()
            cooldown_until = now + duration_seconds
            cooldown_dt = datetime.fromtimestamp(cooldown_until).strftime("%Y-%m-%d %H:%M:%S")

            state = self._load_state()
            keys_dict = state.setdefault("keys", {})
            
            keys_dict[key] = {
                "masked": self._mask_key(key),
                "cooldown_until_ts": cooldown_until,
                "cooldown_until_str": cooldown_dt,
                "duration_seconds": duration_seconds,
                "reason": reason,
                "marked_at": datetime.now().isoformat()
            }
            self._save_state(state)

            masked = self._mask_key(key)
            app_logger.warning(
                f"[KeyPool] ⏳ Chave {masked} colocada em COOLDOWN de {duration_seconds//60} min (até {cooldown_dt}). Motivo: {reason}"
            )
            record_throttling("API_GEMINI_KEY_POOL", "KEY_COOLDOWN_1H", f"Chave {masked} bloqueada por 1h: {reason}", retry_after=duration_seconds)

    def get_next_available_key(self, explicit_keys: Optional[Any] = None) -> Tuple[Optional[str], int, float]:
        """
        Retorna a próxima chave disponível respeitando estritamente a fila de prioridades (1, 2, 3...).
        Retorna (key, priority_index, remaining_cooldown_if_all_blocked).
        Se todas estiverem em cooldown, key será None e remaining será o tempo até a primeira chave liberar.
        """
        with self.lock:
            all_keys = self.discover_keys(explicit_keys)
            if not all_keys:
                return None, -1, 0.0

            state = self._load_state()
            keys_dict = state.get("keys", {})
            now = time.time()

            min_remaining_across_all = float("inf")

            # Varre as chaves na ordem estrita de prioridade (Chave #1 -> Chave #2 -> Chave #3)
            for idx, k in enumerate(all_keys):
                k_data = keys_dict.get(k, {})
                cooldown_until = float(k_data.get("cooldown_until_ts", 0.0))

                if now >= cooldown_until:
                    # Chave disponível e operacional!
                    return k, idx, 0.0
                else:
                    rem = cooldown_until - now
                    if rem < min_remaining_across_all:
                        min_remaining_across_all = rem

            # Todas as chaves estão em cooldown
            remaining_to_wait = min_remaining_across_all if min_remaining_across_all != float("inf") else float(ALL_KEYS_WAIT_DURATION)
            return None, -1, remaining_to_wait

    def get_pool_status_summary(self, explicit_keys: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Retorna o status completo e tempo restante de cada chave no pool."""
        with self.lock:
            all_keys = self.discover_keys(explicit_keys)

            state = self._load_state()
            keys_dict = state.get("keys", {})
            now = time.time()

            summary = []
            for idx, k in enumerate(all_keys):
                k_data = keys_dict.get(k, {})
                cd_ts = float(k_data.get("cooldown_until_ts", 0.0))
                is_active = (now >= cd_ts)
                rem_sec = max(0, int(cd_ts - now)) if not is_active else 0

                summary.append({
                    "priority": idx + 1,
                    "masked": self._mask_key(k),
                    "status": "OPERACIONAL" if is_active else "COOLDOWN_1H",
                    "remaining_seconds": rem_sec,
                    "remaining_minutes": round(rem_sec / 60, 1),
                    "cooldown_until": k_data.get("cooldown_until_str", "Disponível"),
                    "reason": k_data.get("reason", "OK")
                })
            return summary

    def wait_if_all_keys_blocked(self, cooldown_callback=None, status_callback=None) -> Optional[str]:
        """
        Verifica se há chaves operacionais. Se todas estiverem em cooldown, executa
        a espera de 30 MINUTOS do Watchdog (com contagem regressiva ativa), respeitando
        o momento exato em que a primeira chave de prioridade for liberada.
        """
        while True:
            key, priority_idx, remaining_s = self.get_next_available_key()
            if key is not None:
                return key

            # Se todas estão offline/bloqueadas: espera 30 min (ou até o primeiro cooldown expirar)
            wait_time = min(float(ALL_KEYS_WAIT_DURATION), remaining_s)
            wait_time_int = max(5, int(wait_time))

            msg = (
                f"🚨 [KeyPool] Todas as chaves da API Gemini estão em cooldown de 1h!\n"
                f"⏳ Watchdog entrando em espera de {wait_time_int // 60} min e {wait_time_int % 60}s antes de rechecar..."
            )
            app_logger.warning(msg)
            if status_callback:
                status_callback(msg)

            # Contagem regressiva ativa de segundo em segundo
            start_wait = time.time()
            while (time.time() - start_wait) < wait_time_int:
                elapsed = time.time() - start_wait
                left = int(wait_time_int - elapsed)
                if cooldown_callback and left > 0:
                    cooldown_callback(left, wait_time_int, f"Todas as chaves em cooldown. Watchdog aguardando {left}s...")
                time.sleep(1)

            # Re-avalia o pool após a espera
            app_logger.info("[KeyPool] Período de espera do Watchdog concluído. Reavaliando disponibilidade do pool...")

# Instância padrão global
DEFAULT_KEY_POOL = APIKeyPriorityPool()
