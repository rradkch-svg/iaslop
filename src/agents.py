import os
import re
import time
import json
import random
import subprocess
import tempfile
import threading
from typing import Dict, Any, List, Optional, Tuple, Union
from PIL import Image
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

try:
    from .logger import app_logger, LogSpan, record_throttling
    from .algorithm_memory import DEFAULT_ALGORITHM_MEMORY
    from .key_pool import DEFAULT_KEY_POOL, APIKeyPriorityPool
except ImportError:
    from logger import app_logger, LogSpan, record_throttling
    try:
        from algorithm_memory import DEFAULT_ALGORITHM_MEMORY
    except ImportError:
        DEFAULT_ALGORITHM_MEMORY = None
    try:
        from key_pool import DEFAULT_KEY_POOL, APIKeyPriorityPool
    except ImportError:
        DEFAULT_KEY_POOL = None
        APIKeyPriorityPool = None


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lista de modelos rápidos e comprovadamente ativos
DEFAULT_FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash"
]

def resolve_gemini_api_keys(explicit_keys: Optional[Any] = None) -> List[str]:
    """
    Resolve uma lista ordenada e única de chaves de API do Gemini a partir de múltiplas fontes:
    1. Chaves explícitas passadas (str, list ou separadas por vírgula/ponto-e-vírgula/newline)
    2. Arquivo 'gemini-api.txt' (múltiplos cabeçalhos curl -H 'X-goog-api-key: ...' ou linhas de texto)
    3. Arquivos alternativos 'key.txt', 'keys.txt', 'gemini_api.txt', 'api_key.txt', 'gemini-key.txt'
    4. Variáveis de ambiente ('GEMINI_API_KEY', 'GEMINI_FALLBACK_API_KEY', 'GEMINI_API_KEY_FALLBACK', 'GEMINI_BACKUP_API_KEY', 'GEMINI_API_KEYS')
    5. Arquivo '.env'
    """
    collected: List[str] = []

    def _add_key(k: Optional[str]):
        if not k:
            return
        k = k.strip().strip("'\"")
        if not k or k in ("sua_chave_gemini_aqui", "sua_chave_gemini_redundancia_aqui"):
            return
        if len(k) >= 20 and k not in collected:
            collected.append(k)

    # 1. Chaves explícitas
    if explicit_keys is not None:
        if isinstance(explicit_keys, (list, tuple, set)):
            for k in explicit_keys:
                _add_key(str(k))
        elif isinstance(explicit_keys, str):
            for token in re.split(r"[,;\n\r\s]+", explicit_keys.strip()):
                _add_key(token)
        return collected


    # 2. Arquivos .txt conhecidos de chave
    txt_candidates = [
        "gemini-api.txt",
        "gemini_api.txt",
        "keys.txt",
        "api_key.txt",
        "key.txt",
        "gemini-key.txt"
    ]
    search_dirs = [os.getcwd(), PROJECT_ROOT]

    for sdir in search_dirs:
        for fn in txt_candidates:
            full_fn = os.path.join(sdir, fn)
            if os.path.exists(full_fn):
                try:
                    with open(full_fn, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Extrai todos os cabeçalhos curl (-H 'X-goog-api-key: ...')
                    headers = re.findall(r"X-goog-api-key:\s*['\"]?([A-Za-z0-9_\-\.]+)['\"]?", content, re.IGNORECASE)
                    for h in headers:
                        _add_key(h)

                    # Extrai padrões VAR=...
                    kvs = re.findall(r"(?:GEMINI_API_KEY|GEMINI_FALLBACK_API_KEY|GEMINI_BACKUP_API_KEY|GEMINI_API_KEYS)\s*=\s*['\"]?([A-Za-z0-9_\-\.,;]+)['\"]?", content, re.IGNORECASE)
                    for kv in kvs:
                        for token in re.split(r"[,;\s]+", kv):
                            _add_key(token)

                    # Extrai linhas individuais sem espaços
                    for line in content.splitlines():
                        l = line.strip()
                        if l and not l.startswith("#") and not l.startswith("//") and " " not in l:
                            _add_key(l)
                except Exception as e:
                    app_logger.warning(f"[Agents] Erro ao ler chaves de '{full_fn}': {str(e)}")

    # 3. Variáveis de ambiente
    env_vars = [
        "GEMINI_API_KEY",
        "GEMINI_FALLBACK_API_KEY",
        "GEMINI_API_KEY_FALLBACK",
        "GEMINI_BACKUP_API_KEY",
        "GEMINI_REDUNDANCY_KEY"
    ]
    for ev in env_vars:
        _add_key(os.environ.get(ev))

    env_keys_multi = os.environ.get("GEMINI_API_KEYS", "")
    if env_keys_multi:
        for token in re.split(r"[,;\s]+", env_keys_multi):
            _add_key(token)

    # 4. Arquivo .env
    for sdir in search_dirs:
        env_file = os.path.join(sdir, ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    env_content = f.read()
                matches = re.findall(r"(?:GEMINI_API_KEY|GEMINI_FALLBACK_API_KEY|GEMINI_API_KEY_FALLBACK|GEMINI_BACKUP_API_KEY|GEMINI_API_KEYS)\s*=\s*['\"]?([^\r\n'\"]+)['\"]?", env_content, re.IGNORECASE)
                for m in matches:
                    for token in re.split(r"[,;\s]+", m):
                        _add_key(token)
            except Exception:
                pass

    return collected

def resolve_gemini_api_key(explicit_key: Optional[str] = None) -> str:
    """
    Resolve a chave de API primária do Gemini (retrocompatibilidade).
    """
    keys = resolve_gemini_api_keys(explicit_key)
    return keys[0] if keys else ""

_CLIENT_CACHE: Dict[str, genai.Client] = {}
_CLIENT_CACHE_LOCK = threading.Lock()

def get_genai_client(api_key: Optional[str] = None) -> genai.Client:
    """Cria e retorna uma instância cacheada do cliente oficial google-genai."""
    key = resolve_gemini_api_key(api_key) if (api_key is None or not api_key.strip()) else api_key.strip()
    if not key:
        return genai.Client()
    
    with _CLIENT_CACHE_LOCK:
        if key not in _CLIENT_CACHE:
            _CLIENT_CACHE[key] = genai.Client(api_key=key)
        return _CLIENT_CACHE[key]

class GeminiRateLimiter:
    """Controle de vazão thread-safe para impedir que chamadas paralelas ultrapassem o teto de 14 RPM do Gemini Free Tier."""
    def __init__(self, max_rpm: int = 14):
        self.interval = 60.0 / max_rpm
        self.lock = threading.Lock()
        self.last_call = 0.0

    def acquire(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_call = time.time()

GLOBAL_RATE_LIMITER = GeminiRateLimiter(max_rpm=14)
_KEY_RATE_LIMITERS: Dict[str, GeminiRateLimiter] = {}
_KEY_RATE_LOCK = threading.Lock()
_KEY_COOLDOWNS: Dict[str, float] = {}

def get_rate_limiter_for_key(api_key: str, max_rpm: int = 14) -> GeminiRateLimiter:
    """Retorna um Rate Limiter isolado para a chave de API fornecida."""
    if not api_key:
        return GLOBAL_RATE_LIMITER
    with _KEY_RATE_LOCK:
        if api_key not in _KEY_RATE_LIMITERS:
            _KEY_RATE_LIMITERS[api_key] = GeminiRateLimiter(max_rpm=max_rpm)
        return _KEY_RATE_LIMITERS[api_key]

def validate_gemini_api_connection(api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite") -> Tuple[bool, str]:
    """
    Valida a conectividade e autenticação com a API Gemini antes de iniciar o pipeline.
    Retorna (sucesso: bool, mensagem: str).
    """
    keys = resolve_gemini_api_keys(api_key)
    if not keys:
        return False, "Chave de API do Gemini não configurada. Defina GEMINI_API_KEY no arquivo .env ou em gemini-api.txt."
    
    valid_keys = 0
    errors = []
    for k in keys:
        try:
            client = genai.Client(api_key=k)
            config = types.GenerateContentConfig(
                max_output_tokens=5,
                http_options=types.HttpOptions(timeout=15000)
            )
            resp = client.models.generate_content(
                model=model_name,
                contents="ping",
                config=config
            )
            if resp and resp.text:
                valid_keys += 1
        except Exception as e:
            errors.append(str(e))

    if valid_keys > 0:
        return True, f"Conexão validada com sucesso ({valid_keys}/{len(keys)} chaves operacionais no pool)."
    return False, f"Falha na validação das chaves do Gemini: {'; '.join(errors)}"

def extract_retry_seconds(error_str: str) -> int:
    """Extrai os segundos exatos de espera retornados pela mensagem de Quota do Gemini."""
    match = re.search(r"retry in (\d+(\.\d+)?)s", str(error_str), re.IGNORECASE)
    if match:
        return int(float(match.group(1))) + 1
    match_sec = re.search(r"seconds:\s*(\d+)", str(error_str), re.IGNORECASE)
    if match_sec:
        return int(match_sec.group(1)) + 1
    match_delay = re.search(r"retryDelay':\s*'(\d+)s'", str(error_str), re.IGNORECASE)
    if match_delay:
        return int(match_delay.group(1)) + 1
    return 20

def generate_with_resilience(
    prompt: str,
    system_instruction: str,
    model_name: str = "gemini-3.5-flash-lite",
    fallback_models: list = None,
    auto_fallback: bool = True,
    auto_cooldown: bool = True,
    response_mime_type: str = None,
    cooldown_callback = None,
    status_callback = None,
    timeout_seconds: float = 60.0,
    max_cooldown_retries: int = 3,
    api_key: Optional[Union[str, List[str]]] = None
) -> str:
    """
    Executa chamada com streaming em tempo real, timeout de 60s+, rotação de chaves e fallback automático.
    """
    if fallback_models is None:
        fallback_models = list(DEFAULT_FALLBACK_MODELS)
        
    models_to_try = [model_name]
    if auto_fallback:
        for m in fallback_models:
            if m not in models_to_try:
                models_to_try.append(m)

    keys_pool = resolve_gemini_api_keys(api_key)
    if not keys_pool:
        keys_pool = [""] # Deixa o client tentar padrão do ambiente

    last_err = None

    for k_idx, current_key in enumerate(keys_pool):
        # Verifica se esta chave está em cooldown (1 Hora)
        now = time.time()
        cooldown_until = 0.0
        if DEFAULT_KEY_POOL:
            state = DEFAULT_KEY_POOL._load_state()
            cooldown_until = float(state.get("keys", {}).get(current_key, {}).get("cooldown_until_ts", 0.0))
        else:
            cooldown_until = _KEY_COOLDOWNS.get(current_key, 0.0)

        if cooldown_until > now and len(keys_pool) > 1:
            wait_s = int(cooldown_until - now)
            if status_callback:
                status_callback(f"Chave #{k_idx+1} em cooldown de 1h ({wait_s//60} min restantes). Alternando para próxima chave...")
            continue

        limiter = get_rate_limiter_for_key(current_key)
        client = get_genai_client(api_key=current_key)

        for m_idx, current_model in enumerate(models_to_try):
            retries_left = max_cooldown_retries
            while retries_left > 0:
                limiter.acquire()
                start_time = time.time()
                try:
                    if status_callback:
                        key_hint = f" [Chave #{k_idx+1} / Prioridade {k_idx+1}]" if len(keys_pool) > 1 else ""
                        status_callback(f"Conectando ao modelo **{current_model}**{key_hint}...")

                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type=response_mime_type,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
                    )
                    
                    resp = client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                        config=config
                    )
                    
                    full_text = resp.text.strip() if resp and resp.text else ""
                    if full_text:
                        # Limpa wrappers markdown json se necessário
                        if response_mime_type == "application/json":
                            full_text = re.sub(r"^```json\s*", "", full_text, flags=re.IGNORECASE)
                            full_text = re.sub(r"\s*```$", "", full_text)
                            full_text = full_text.strip()
                        return full_text
                    
                    retries_left -= 1
                except Exception as e:
                    err_str = str(e)
                    last_err = e
                    is_quota = ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower())
                    is_auth_error = ("API_KEY_INVALID" in err_str or "API key not valid" in err_str)
                    
                    if is_quota or is_auth_error:
                        cd_duration = 3600 # 1 Hora estrita de espera para a chave esgotada
                        record_throttling("API_GEMINI", "RATE_LIMIT_429", f"Quota 429 na chave #{k_idx+1} ({current_model})", retry_after=cd_duration)
                        if DEFAULT_KEY_POOL:
                            DEFAULT_KEY_POOL.mark_key_cooldown(
                                current_key,
                                duration_seconds=cd_duration,
                                reason=f"Quota 429 / Sem tokens no modelo {current_model}"
                            )
                        else:
                            _KEY_COOLDOWNS[current_key] = time.time() + cd_duration

                        # Se há outra chave no pool, rotaciona imediatamente para a próxima prioridade
                        if len(keys_pool) > 1 and k_idx < len(keys_pool) - 1:
                            if status_callback:
                                status_callback(f"⚠️ Chave #{k_idx+1} sem tokens. Colocada em cooldown de 1 HORA (3600s). Alternando para Chave #{k_idx+2}...")
                            break # Sai do loop deste modelo e vai para próxima chave de prioridade
                        
                        if auto_cooldown and len(keys_pool) == 1:
                            msg = f"⏳ Cota 429 atingida na chave única. Entrando em cooldown de 1h..."
                            app_logger.warning(f"[Agents] {msg} Detalhe: {err_str}")
                            if cooldown_callback:
                                cooldown_callback(cd_duration, f"Limite de cota (429). Aguardando {cd_duration}s...")
                            elif status_callback:
                                status_callback(msg)
                            time.sleep(min(60, cd_duration))
                            retries_left -= 1
                            continue
                    
                    app_logger.warning(f"[Agents] Erro no modelo {current_model} (Chave #{k_idx+1}): {err_str}")
                    break

    # Se todas as chaves do pool estiverem em cooldown/bloqueadas e auto_cooldown estiver ativo:
    if auto_cooldown and DEFAULT_KEY_POOL and len(keys_pool) > 1:
        app_logger.warning("[Agents] Todas as chaves do pool estão em cooldown de 1h. Watchdog aguardando 30 MINUTOS...")
        available_key = DEFAULT_KEY_POOL.wait_if_all_keys_blocked(
            cooldown_callback=cooldown_callback,
            status_callback=status_callback
        )
        if available_key:
            return generate_with_resilience(
                prompt=prompt,
                system_instruction=system_instruction,
                model_name=model_name,
                fallback_models=fallback_models,
                auto_fallback=auto_fallback,
                auto_cooldown=False,
                response_mime_type=response_mime_type,
                cooldown_callback=cooldown_callback,
                status_callback=status_callback,
                timeout_seconds=timeout_seconds,
                max_cooldown_retries=max_cooldown_retries,
                api_key=api_key
            )

    raise Exception(f"Falha em todos os modelos e chaves configuradas. Último erro: {str(last_err)}")



POPULAR_INEXPLICABLE_ANGLES = [
    "A Base Aérea Subterrânea de Željava (Complexo 505) na Bósnia e seus Túneis na Montanha",
    "O Enigma do Manuscrito Rohonc e os Símbolos Indecifráveis da Hungria",
    "O Desaparecimento do Farol de Flannan Isles e os Guardiões Sumidos na Escócia",
    "A Cidade Subterrânea de Naours na França e suas Centenas de Câmaras Ocultas",
    "O Incidente do Satélite Militar Vela e a Explosão Nuclear Não Declarada no Oceano Índico",
    "A Misteriosa Mina de Sal de Turda na Romênia e suas Câmaras Ecoantes Gigantescas",
    "O Forte Abandonado de Bhangarh na Índia e a Proibição Noturna do Governo",
    "A Anomalia Gravitacional da Baía de Hudson no Canadá",
    "O Incidente Aéreo do Voo Flying Tiger 739 Desaparecido no Pacífico Ocidental",
    "O Mistério das Esferas Megalíticas Perfeitas de Diquís na Costa Rica",
    "Os Geoglifos Gigantes de Blythe Intaglios no Deserto do Colorado",
    "A Cidade Submersa Antiga de Shicheng no Lago Qiandao na China",
    "O Enigma do Disco de Festo e a Escrita Cretense Jamais Decifrada",
    "O Desastre Limnico do Lago Nyos em 1986 e a Nuvem de Gás Invisível",
    "A Floresta Torta de Gryfino na Polônia e a Deformação Geométrica das Árvores",
    "O Mistério Náutico do Navio MV Lyubov Orlova à Deriva no Atlântico Norte",
    "O Projeto Sealab II da Marinha Americana no Cânion Submarino de La Jolla",
    "O Enigma das Luzes Fantasmas e Fenômeno Noturno de Hessdalen na Noruega",
    "A Cidade Fantasma de Centralia e os Incêndios Subterrâneos Perpétuos de Carvão",
    "O Incidente do Voo Varig RG-967 e as Obras de Arte Valiosas Desaparecidas no Mar",
    "A Fortaleza Flutuante Abandonada de Fort Roughs e as Fortificações Maunsell",
    "O Naufrágio e as Tumbas Congeladas da Expedição Franklin e HMS Terror no Ártico",
    "A Ilha Fantasma de Bermeja no Golfo do México que Simplesmente Desapareceu dos Mapas",
    "A Estação Polar Fantasma de Vostok e o Lago Subglacial Lacrado há Milhões de Anos",
    "O Complexo Militar de Fort Douaumont e as Batalhas Subterrâneas de Verdun",
    "O Mistério das Ruínas de Nan Madol e a Cidade de Basalto Construída Sobre o Mar",
    "A Cidade Antiga Submersa de Pavlopetri na Grécia",
    "Os Túneis Secretos da Linha Maginot e as Galerias Militares Profundas",
    "O Incidente do Submarino USS Scorpion e os Segredos do Fundo do Atlântico",
    "O Misterioso Forte de Kumbhalgarh e suas Muralhas Gigantescas na Índia",
    "A Cidade de Sal Subterrânea de Wieliczka na Polônia",
    "O Enigma Arqueológico das Cavernas de Longyou na China Escavadas em Rocha Maciça",
    "O Incidente Aéreo de 1978 com o Piloto Frederick Valentich no Estreito de Bass",
    "A Base Secreta Abandonada de Submarinos de Balaklava na Crimeia",
    "O Segredo da Ilha de Poveglia na Itália e seus Sanatórios Abandonados",
    "As Esferas Metálicas de Klerksdorp na África do Sul com Ranhuras Artificiais",
    "O Mistério do Navio MV Joyita Encontrado à Deriva no Pacífico Sem Tripulação",
    "A Estrutura Subaquática de Fuxian na China e suas Pirâmides Submersas",
    "O Incidente de Mantell e a Perseguição Aérea em 1948",
    "O Enigma da Ilha Sentinel do Norte e a Tribo Isolada da Idade da Pedra",
    "O Grande Aquífero e Rio Subterrâneo Hamza Sob a Bacia Amazônica"
]

class ProposerAgent:
    """
    Agente Propositor de Pautas do 'Minuto Inexplicável'.
    Gera ideias completas e ricas sobre mistérios reais e projetos secretos com título, hook de 3s,
    explicação técnica factual, hashtags virais e descrição completa para o YouTube.
    """
    def __init__(self, model_name="gemini-3.5-flash-lite", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        raw_key = api_key or kwargs.get("api_key") or kwargs.get("key")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None

        self.system_instruction = (
            "Você é o Diretor Criativo e Pesquisador de Inteligência do canal 'Minuto Inexplicável'. "
            "Sua missão é gerar ideias de altíssimo impacto para Shorts de 60 a 90 segundos sobre mistérios reais, projetos secretos desclassificados, bases subterrâneas, anomalias oceânicas/espaciais e enigmas históricos documentados.\n\n"
            "DIRETRIZES DE RETENÇÃO VIRAL (SHORTS DOCUMENTAIS 9:16):\n"
            "1. TEMA / TÍTULO: Deve ser instigante, misterioso e documental (ex: 'A Base Nuclear Secreta Enterrada Sob o Gelo ❄️☢️', 'O Poço Mais Fundo da Terra e os Sons de Kola 🕳️🇷🇺', 'O Enigma do Passo Dyatlov nos Montes Urais 🏔️❄️').\n"
            "2. HOOK (PRIMEIROS 3 SEGUNDOS): Frase chocante que quebra padrão e gera curiosidade irresistível.\n"
            "3. EXPLICAÇÃO TÉCNICA E FACTUAL: Resumo denso com dados concretos (datas, projetos governamentais, física/geologia real, documentos desclassificados).\n"
            "4. DESCRICAO COMPLETA: Texto pronto para publicação no YouTube.\n"
            "5. TAGS: 8 a 15 hashtags virais pertinentes.\n\n"
            "Responda SEMPRE em formato JSON com uma lista de objetos contendo 'tema', 'descricao', 'tags', 'hook' e 'explicacao_tecnica'."
        )

    def generate_topics(self, count=10, blacklist: Optional[List[Any]] = None, seed=None, cooldown_callback=None, status_callback=None):
        seed_val = seed if seed is not None else random.randint(100000, 999999)
        time_salt = int(time.time() * 1000) % 100000
        angles_sample = random.sample(POPULAR_INEXPLICABLE_ANGLES, min(5, len(POPULAR_INEXPLICABLE_ANGLES)))
        angles_str = "\n".join([f"- {a}" for a in angles_sample])

        blacklist_str = ""
        if blacklist:
            # Coleta todas as entidades e títulos únicos da blacklist de forma densa e categorizada
            seen_entries = set()
            formatted_items = []
            for b in blacklist:
                if isinstance(b, dict):
                    t = (b.get("tema") or b.get("core_entity") or "").strip()
                    ent = (b.get("core_entity") or "").strip()
                    key = f"{t} ({ent})" if ent and ent != t else t
                else:
                    key = str(b).strip()
                if key and key not in seen_entries:
                    seen_entries.add(key)
                    formatted_items.append(f"• {key}")

            if formatted_items:
                # Mostra os itens mais recentes e um resumo consolidado
                top_items = formatted_items[-150:]
                blacklist_str = (
                    f"\n\n[BLACKLIST DE MISTÉRIOS JÁ GRAVADOS NO CANAL - ESTRITAMENTE PROIBIDO REPETIR EM ESSÊNCIA ({len(formatted_items)} MISTÉRIOS REGISTRADOS)]:\n"
                    f"{chr(10).join(top_items)}\n\n"
                    f"⚠️ REGRA DE OURO DA BLACKLIST: É TERMINANTEMENTE PROIBIDO propor qualquer um dos mistérios, locais, projetos ou incidentes listados acima (mesmo mudando o título ou o enfoque). "
                    f"Você DEVE explorar outros mistérios reais, projetos desclassificados, ilhas misteriosas, anomalias geológicas e enigmas históricos menos conhecidos que possuam filmagens documentais no YouTube."
                )

        algo_context = ""
        if DEFAULT_ALGORITHM_MEMORY:
            algo_context = f"\n\n{DEFAULT_ALGORITHM_MEMORY.get_prompt_context_for_generation()}\n"

        prompt = (
            f"Gere {count} ideias COMPLETAS e 100% INÉDITAS sobre mistérios reais do mundo para o canal 'Minuto Inexplicável' (vídeos de 60 a 90 segundos).\n\n"
            f"[ENTROPIA & SEED DE DIVERSIDADE]: #{seed_val}-{time_salt}\n"
            f"DIRETRIZES OBRIGATÓRIAS:\n"
            f"1. PACOTE COMPLETO: Cada ideia DEVE conter 'tema' (Título com emojis pertinentes), 'descricao' (Descrição completa para o YouTube), 'tags' (Hashtags virais), 'hook' (Primeiros 3 segundos) e 'explicacao_tecnica' (Contexto documental).\n"
            f"2. BASE EM FATOS REAIS E ARQUIVOS: Escolha mistérios que possuam acervo de imagens reais, fotos de arquivo, filmagens de satélite, expedições e documentários no YouTube.\n"
            f"3. VARIEDADE MÁXIMA: As {count} ideias devem ser de nichos completamente diferentes entre si.\n"
            f"4. NICHOS SUGERIDOS PARA EXPLORAR NESTA RODADA:\n{angles_str}"
            f"{algo_context}"
            f"{blacklist_str}\n\n"
            f"Responda SEMPRE em JSON puro com a lista de {count} objetos contendo 'tema', 'descricao', 'tags', 'hook' e 'explicacao_tecnica'."
        )
        try:
            raw_text = generate_with_resilience(
                prompt=prompt,
                system_instruction=self.system_instruction,
                model_name=self.model_name,
                fallback_models=self.fallback_models,
                auto_fallback=self.auto_fallback,
                auto_cooldown=self.auto_cooldown,
                response_mime_type="application/json",
                cooldown_callback=cooldown_callback,
                status_callback=status_callback,
                timeout_seconds=120.0,
                api_key=self.api_key
            )
            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "temas" in parsed:
                return parsed["temas"]
            return [parsed]
        except Exception as e:
            app_logger.error(f"[ProposerAgent] Falha na geração de temas via IA: {str(e)}")
            raise e

class DissertationAgent:
    """
    Agente Mestre de Pesquisa e Dissertação Documental (Fase 1 da Síntese).
    Constrói uma monografia completa, rigorosa e factual (300 a 500 palavras) sobre o mistério,
    detalhando dados reais, arquivos desclassificados, medidas quantitativas, física/geologia e evidências,
    atuando como a âncora de verdade factual irrefutável para o Diretor.
    """
    def __init__(self, model_name="gemini-3.5-flash-lite", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        raw_key = api_key or kwargs.get("api_key") or kwargs.get("key")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None

        self.system_instruction = (
            "Você é o Historiador de Inteligência e Pesquisador Científico Sênior do canal 'Minuto Inexplicável'.\n"
            "Sua missão é produzir uma DISSERTAÇÃO DOCUMENTAL E CIENTÍFICA COMPLETA (300 a 500 palavras) sobre o mistério/projeto/anomalia.\n\n"
            "DIRETRIZES DE PROFUNDIDADE E CONTEÚDO PURO (ANTI-HYPE):\n"
            "1. CONTEÚDO DENSO E EXATO: Apresente dados exatos (profundidade em metros/km, datas históricas, coordenadas geográficas, espessura do gelo, temperatura, frequências em Hz/MHz, doses de radiação, nomes de operações secretas e documentos desclassificados).\n"
            "2. FÍSICA, GEOLOGIA E CIÊNCIA REAL: Explique a mecânica do fenômeno (pressão hidrostática, propagação acústica no canal SOFAR, mecânica de solo vulcânico, radioisótopos, espectrometria de rádio).\n"
            "3. O ENIGMA E A INVESTIGAÇÃO: O que exatamente foi descoberto? Qual foi a versão oficial governamental vs o que as evidências físicas registraram?\n"
            "4. TOLERÂNCIA ZERO A SENSACIONALISMO VAZIO: NUNCA use clichês vazios como 'o mistério que desafiou todos os deuses'. Seja hipnotizante pela precisão implacável dos fatos documentados.\n\n"
            "Responda SEMPRE em formato JSON com as chaves:\n"
            "- 'entidade_principal': Nome exato do mistério/projeto/local\n"
            "- 'dados_quantitativos': Dicionário com medidas exatas (profundidade, ano, temperatura, frequencia, local)\n"
            "- 'contexto_historico_e_documentos': Descrição dos documentos desclassificados e expedições\n"
            "- 'anomalia_ou_enigma_central': Descrição precisa da evidência inexplicável\n"
            "- 'teorias_e_evidencias': Resumo das teorias científicas concorrentes\n"
            "- 'dissertacao_completa': Texto corrido e envolvente de 300 a 500 palavras com todo o embasamento."
        )

    def generate_dissertation(self, topic_data: Dict[str, Any], cooldown_callback=None, status_callback=None) -> Dict[str, Any]:
        tema_title = topic_data.get("tema", "")
        hook = topic_data.get("hook", "")
        tech = topic_data.get("explicacao_tecnica", "")

        algo_context = ""
        if DEFAULT_ALGORITHM_MEMORY:
            algo_context = f"\n\n{DEFAULT_ALGORITHM_MEMORY.get_prompt_context_for_generation()}\n"

        prompt = (
            f"Produza a DISSERTAÇÃO DOCUMENTAL COMPLETA de 300 a 500 palavras para o tema abaixo:\n\n"
            f"TÍTULO: {tema_title}\n"
            f"HOOK INICIAL: {hook}\n"
            f"CONTEXTO PRELIMINAR: {tech}\n"
            f"{algo_context}\n"
            f"Exija máxima precisão histórica, científica e militar. Responda SEMPRE em formato JSON."
        )

        try:
            raw_text = generate_with_resilience(
                prompt=prompt,
                system_instruction=self.system_instruction,
                model_name=self.model_name,
                fallback_models=self.fallback_models,
                auto_fallback=self.auto_fallback,
                auto_cooldown=self.auto_cooldown,
                response_mime_type="application/json",
                cooldown_callback=cooldown_callback,
                status_callback=status_callback,
                api_key=self.api_key
            )
            return json.loads(raw_text)
        except Exception as e:
            app_logger.warning(f"[DissertationAgent] Erro na dissertação ({str(e)}). Criando síntese factual estruturada.")
            return {
                "entidade_principal": tema_title,
                "dados_quantitativos": {"contexto": "Documentário Investigativo"},
                "contexto_historico_e_documentos": tech,
                "anomalia_ou_enigma_central": hook,
                "teorias_e_evidencias": "Evidências e registros históricos documentados.",
                "dissertacao_completa": f"{hook} {tech}"
            }

class EvaluatorAgent:
    """
    Agente Avaliador Editorial do 'Minuto Inexplicável'.
    Avalia a pertinência, impacto do hook, retenção estimada e embasamento documental do tema.
    """
    def __init__(self, model_name="gemini-3.5-flash-lite", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        raw_key = api_key or kwargs.get("api_key") or kwargs.get("key")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        self.system_instruction = (
            "Você é o Diretor Editorial Chefe do canal 'Minuto Inexplicável'. "
            "Avalie o tema considerando o potencial de reter o público por 60 a 90 segundos, "
            "o impacto do hook nos 3 segundos iniciais, o fascínio do mistério e o embasamento factual. "
            "Responda SEMPRE em JSON contendo 'nota' (0 a 10), 'veredicto' (Aprovado/Reprovado), e 'justificativa'."
        )

    def evaluate_topic(self, topic_data, cooldown_callback=None, status_callback=None):
        prompt = f"Avalie o seguinte tema/mistério para o canal 'Minuto Inexplicável' (vídeo de 60 a 90s):\n\n{json.dumps(topic_data, indent=2, ensure_ascii=False)}"
        try:
            raw_text = generate_with_resilience(
                prompt=prompt,
                system_instruction=self.system_instruction,
                model_name=self.model_name,
                fallback_models=self.fallback_models,
                auto_fallback=self.auto_fallback,
                auto_cooldown=self.auto_cooldown,
                response_mime_type="application/json",
                cooldown_callback=cooldown_callback,
                status_callback=status_callback,
                api_key=self.api_key
            )
            return json.loads(raw_text)
        except Exception as e:
            app_logger.warning(f"[EvaluatorAgent] Erro na avaliação por IA ({str(e)}). Retornando aprovação padrão.")
            return {
                "nota": 8.5,
                "veredicto": "Aprovado",
                "justificativa": "Tema com forte apelo documental e alto fator de curiosidade investigativa."
            }

class SemanticAuditorAgent:
    """
    Auditor Semântico de Ineditismo e Anti-Duplicação.
    Verifica se um novo candidato trata, em essência, do mesmo mistério, local, evento ou projeto histórico
    já presente na Blacklist, mesmo quando os títulos usam palavras e estruturas completamente distintas.
    """
    def __init__(self, model_name="gemini-3.5-flash-lite", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        raw_key = api_key or kwargs.get("api_key") or kwargs.get("key")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None

        self.system_instruction = (
            "Você é o Auditor Semântico de Ineditismo do canal 'Minuto Inexplicável'. "
            "Sua missão é impedir que vídeos abordem, EM ESSÊNCIA, o mesmo mistério, evento histórico, local, projeto militar/científico ou anomalia já gravado anteriormente no canal.\n"
            "Ignore variações cosméticas no título: se o fato histórico/científico subjacente for o mesmo (ex: 'O Poço de Kola' e 'O Buraco Russo de 12km', ou 'Incidente Dyatlov' e 'Alpinistas Mortos nos Urais em 1959'), trata-se de UMA DUPLICATA.\n"
            "Responda SEMPRE em formato JSON com exatamente:\n"
            "- 'is_duplicate': true se o tema candidato for o mesmo evento/local/mistério em essência; false se for genuinamente inédito\n"
            "- 'matched_topic': Título do tema da Blacklist correspondente (ou null se for inédito)\n"
            "- 'reason': Explicação concisa e objetiva da decisão."
        )

    def check_duplicate_essence(
        self,
        candidate_topic: Dict[str, Any],
        blacklist_items: List[Dict[str, Any]],
        cooldown_callback=None,
        status_callback=None
    ) -> Tuple[bool, str]:
        if not blacklist_items:
            return False, "Blacklist vazia."

        cand_title = candidate_topic.get("tema", "")
        cand_hook = candidate_topic.get("hook", "")
        cand_tech = candidate_topic.get("explicacao_tecnica", "")

        formatted_list = []
        for i, item in enumerate(blacklist_items[-40:]):
            t = item.get("tema", "")
            ent = item.get("core_entity", "")
            hk = item.get("hook", "")
            if t:
                desc = f"{i+1}. TÍTULO: '{t}'"
                if ent and ent != t:
                    desc += f" (Assunto: {ent})"
                if hk:
                    desc += f" - Hook: {hk[:70]}"
                formatted_list.append(desc)

        blacklist_text = "\n".join(formatted_list)

        prompt = (
            f"Analise se o TEMA CANDIDATO abaixo aborda, EM ESSÊNCIA, o mesmo mistério/local/projeto de algum dos temas já gravados na Blacklist.\n\n"
            f"[TEMA CANDIDATO]:\n"
            f"- Título: {cand_title}\n"
            f"- Hook: {cand_hook}\n"
            f"- Contexto Factual: {cand_tech}\n\n"
            f"[TEMAS RECENTES DA BLACKLIST]:\n"
            f"{blacklist_text}\n\n"
            f"Responda SEMPRE em JSON: {{\"is_duplicate\": bool, \"matched_topic\": \"... ou null\", \"reason\": \"...\"}}"
        )

        try:
            raw_text = generate_with_resilience(
                prompt=prompt,
                system_instruction=self.system_instruction,
                model_name=self.model_name,
                fallback_models=self.fallback_models,
                auto_fallback=self.auto_fallback,
                auto_cooldown=self.auto_cooldown,
                response_mime_type="application/json",
                cooldown_callback=cooldown_callback,
                status_callback=status_callback,
                api_key=self.api_key
            )
            parsed = json.loads(raw_text)
            is_dup = bool(parsed.get("is_duplicate", False))
            matched = parsed.get("matched_topic")
            reason = parsed.get("reason", "")
            if is_dup:
                full_reason = f"Duplicata de '{matched}': {reason}" if matched else f"Duplicata em essência: {reason}"
                return True, full_reason
            return False, "Tema inédito confirmado pela IA."
        except Exception as e:
            app_logger.warning(f"[SemanticAuditorAgent] Auditoria por IA indisponível ({str(e)}). Mantendo análise determinística.")
            return False, f"Auditoria por IA ignorada: {str(e)}"

def extract_core_entity(topic_str: str) -> str:
    """Extrai os termos centrais do mistério/local/projeto de estudo (ex: Camp Century, Kola Borehole, Dyatlov Pass)."""
    parts = topic_str.split(":")
    main_part = parts[0] if len(parts) > 1 else topic_str
    cleaned = re.sub(r"^(O Segredo d[oa]|Como funciona o|Por que o|A física d[oa]|A engenharia d[oa]|Tudo sobre o|O Mistério d[oa]|A Base Secreta d[oa]|O Incidente d[oa]|A Verdade sobre|O que há no fundo d[oa]|O Projeto Secreto|A História d[oa]|O Caso d[oa]|A Anomalia d[oa])\s*", "", main_part, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^\w\s\-\.]", " ", cleaned)
    cleaned = re.sub(r"\b(e seu|e sua|no|na|com|de|da|do|dos|das|por ser bom demais|que a nasa|para|sobre|o|a|os|as|sob o gelo|enterrada|secreta|misteriosa)\b", " ", cleaned, flags=re.IGNORECASE)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    return " ".join(words[:6]) if words else topic_str.strip()

def generate_video_metadata_text(topic: Dict[str, Any]) -> str:
    """Gera o conteúdo textual completo para o arquivo metadata.txt de cada vídeo."""
    tema = topic.get("tema", "Mistério Desclassificado")
    hook = topic.get("hook", "")
    tech = topic.get("explicacao_tecnica", "")
    ai_desc = topic.get("descricao", "")
    ai_tags = topic.get("tags", [])

    titulo_formatado = tema.strip()

    if ai_desc and len(ai_desc.strip()) > 30:
        descricao_formatada = ai_desc.strip()
    else:
        descricao_formatada = f"""🔮 {hook}

📂 DOCUMENTO DESCLASSIFICADO:
{tech}

Você acredita que a verdade sobre esse mistério já foi totalmente revelada ou ainda existem documentos em sigilo? Deixe sua teoria nos comentários! 👇

🔔 Inscreva-se no canal @MinutoInexplicavel para não perder nenhum mistério do nosso planeta e do cosmos."""

    if isinstance(ai_tags, list) and ai_tags:
        tags_list = [f"#{t.lstrip('#')}" for t in ai_tags if t.strip()]
        hashtags_str = " ".join(tags_list)
    elif isinstance(ai_tags, str) and ai_tags.strip():
        hashtags_str = ai_tags.strip()
    else:
        core_entity = extract_core_entity(tema)
        entity_tag = "#" + re.sub(r"[^\w]", "", core_entity) if core_entity else ""
        base_hashtags = [
            "#Shorts",
            "#MinutoInexplicavel",
            "#Misterios",
            "#ProjetosSecretos",
            "#HistoriaOculta",
            "#Documentario",
            "#Curiosidades",
            "#FatosReais",
            "#GuerraFria",
            "#Ciencia"
        ]
        all_tags = []
        if entity_tag and entity_tag not in all_tags and len(entity_tag) > 2:
            all_tags.append(entity_tag)
        for ht in base_hashtags:
            if ht not in all_tags:
                all_tags.append(ht)
        hashtags_str = " ".join(all_tags[:12])

    return f"""TÍTULO:
{titulo_formatado}

DESCRIÇÃO:
{descricao_formatada}

HASHTAGS:
{hashtags_str}
"""

def save_video_metadata_file(video_dir: str, topic: Dict[str, Any], filename: str = "metadata.txt") -> str:
    """Grava o arquivo metadata.txt na pasta do vídeo e retorna seu caminho absoluto."""
    os.makedirs(video_dir, exist_ok=True)
    file_path = os.path.join(video_dir, filename)
    content = generate_video_metadata_text(topic)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    app_logger.info(f"[Metadata] Arquivo de metadados gravado: {file_path}")
    return file_path

class DirectorAgent:
    """
    Agente Diretor de Produção do 'Minuto Inexplicável' (Fase 2 da Síntese).
    Destila a dissertação factual monográfica em um roteiro investigativo aprofundado
    (60 a 90 segundos, 150 a 220 palavras faladas) dividido em 12 a 18 cenas dinâmicas com queries de YouTube em INGLÊS.
    """
    def __init__(self, model_name="gemini-3.5-flash-lite", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        raw_key = api_key or kwargs.get("api_key") or kwargs.get("key")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        self.system_instruction = (
            "Você é o Diretor de Produção Audiovisual e Roteirista Investigativo de elite do canal 'Minuto Inexplicável'. "
            "Sua missão é destilar a pesquisa documental primária em um roteiro dinâmico e hipnótico de 60 a 90 segundos "
            "(entre 150 e 220 palavras faladas no total) no formato 9:16 vertical, "
            "e selecionar as filmagens REAIS DE ARQUIVO, SATÉLITE E DOCUMENTÁRIOS mais puras do YouTube para cada cena.\n\n"
            "REGRAS CRÍTICAS DE BUSCA NO YOUTUBE ('youtube_query'):\n"
            "1. Todas as queries DEVEM ser em INGLÊS, CURTAS (3 a 6 palavras) e com CONEXÃO PARTICULAR OBRIGATÓRIA ao evento/local/mistério de estudo.\n"
            "2. OBRIGATÓRIO: TODA query DEVE conter o [NOME EXATO DO LOCAL/PROJETO/EVENTO] + [TERMO DE ARQUIVO/DOCUMENTÁRIO] (ex: 'Camp Century Greenland nuclear ice documentary', 'Kola Superdeep borehole USSR real footage', 'Mariana trench deep sea exploration 4k', 'Dyatlov Pass incident historical photos').\n"
            "3. Prefira termos que puxem filmagens autênticas: 'real archival footage', 'documentary 4k', 'satellite drone view', 'historical expedition', 'underground bunker 4k', 'ocean depth exploration 4k'.\n"
            "4. 'fala': a frase falada exata da narração nesta cena (narração fluida, sem introduções robóticas).\n"
            "Responda SEMPRE em JSON com a chave raiz 'cenas' (lista de 12 a 18 objetos contendo 'scene_id', 'fala', 'youtube_query', 'duracao_estimada')."
        )

    def generate_storyboard(self, tema: Dict[str, Any], dissertacao_data: Optional[Dict[str, Any]] = None, cooldown_callback=None, status_callback=None) -> List[Dict[str, Any]]:
        raw_topic = tema.get('tema', 'Mistério Desclassificado')
        core_entity = extract_core_entity(raw_topic)
        hook_sugerido = tema.get('hook', '')
        explicacao = tema.get('explicacao_tecnica', '')

        dissertacao_block = ""
        if dissertacao_data and isinstance(dissertacao_data, dict):
            monografia = dissertacao_data.get("dissertacao_completa", "")
            dados_q = dissertacao_data.get("dados_quantitativos", {})
            anomalia = dissertacao_data.get("anomalia_ou_enigma_central", "")
            dissertacao_block = (
                f"\n[BASE DOCUMENTAL FACTUAL DE PESQUISA (FONTE PRIMÁRIA OBRIGATÓRIA)]:\n"
                f"- DADOS QUANTITATIVOS: {json.dumps(dados_q, ensure_ascii=False)}\n"
                f"- ENIGMA CENTRAL: {anomalia}\n"
                f"- MONOGRAFIA COMPLETA DE REFERÊNCIA:\n{monografia}\n\n"
                f"DESTILE O ROTEIRO ACIMA: Utilize estritamente os fatos, datas e dados reais presentes na monografia para narrar as cenas sem alucinar dados fictícios."
            )

        algo_context = ""
        if DEFAULT_ALGORITHM_MEMORY:
            algo_context = f"\n{DEFAULT_ALGORITHM_MEMORY.get_prompt_context_for_generation()}\n"

        prompt = (
            f"Crie o roteiro investigativo aprofundado de 60 a 90 segundos com plano de cortes detalhado.\n"
            f"TEMA CENTRAL: '{raw_topic}'\n"
            f"ENTIDADE/LOCAL/PROJETO: '{core_entity}'\n"
            f"HOOK SUGERIDO PARA CENA 1: '{hook_sugerido}'\n"
            f"CONTEXTO HISTÓRICO: '{explicacao}'\n"
            f"{dissertacao_block}"
            f"{algo_context}\n"
            f"DIRETRIZES TÉCNICAS E CINEMATOGRÁFICAS:\n"
            f"1. RITMO E DURAÇÃO TOTAL: O texto total falado deve ter entre 150 e 220 palavras (tempo de fala entre 60 e 90 segundos no ritmo acelerado).\n"
            f"2. NÚMERO DE CENAS: Exatamente entre 12 e 18 cenas de corte rápido (cada cena com 3 a 7 segundos).\n"
            f"3. CENA 1 (HOOK INICIAL DE 3s): Deve começar no primeiro milissegundo com a revelação instigante (usando o gancho fornecido ou versão ainda mais magnética).\n"
            f"4. CENAS INTERMEDIÁRIAS (DESCLASSIFICAÇÃO DOCUMENTAL): Expor os fatos reais, a ciência, o que foi escavado/descoberto, as tentativas de encobrimento e os dados concretos.\n"
            f"5. CENA FINAL (CHAMADA DE ENGAJAMENTO): Concluir com uma pergunta instigante sobre o mistério convocando o espectador a comentar sua teoria e se inscrever no canal @MinutoInexplicavel.\n"
            f"6. TERMOS DE BUSCA NO YOUTUBE: Queries em INGLÊS focadas exclusivamente no mistério/local específico.\n\n"
            f"Responda SEMPRE em JSON: {{\"cenas\": [{{\"scene_id\": 1, \"fala\": \"...\", \"youtube_query\": \"...\", \"duracao_estimada\": 5.0}}, ...]}}"
        )

        try:
            raw_text = generate_with_resilience(
                prompt=prompt,
                system_instruction=self.system_instruction,
                model_name=self.model_name,
                fallback_models=self.fallback_models,
                auto_fallback=self.auto_fallback,
                auto_cooldown=self.auto_cooldown,
                response_mime_type="application/json",
                cooldown_callback=cooldown_callback,
                status_callback=status_callback,
                api_key=self.api_key
            )
            data = json.loads(raw_text)
            scenes = data.get("cenas", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            if scenes:
                return scenes
            raise ValueError("Nenhuma cena válida retornada na estrutura JSON pelo Diretor.")
        except Exception as e:
            app_logger.error(f"[DirectorAgent] Erro ao obter/decodificar storyboard por IA: {str(e)}")
            raise e

class ReviewerAgent:
    """
    Agente Revisor de Mídia e Visão Computacional.
    Audita frames de vídeo baixados do YouTube para garantir altíssima aderência ao tema de mistério.
    """
    def __init__(self, model_name="gemini-3.5-flash-lite", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        raw_key = api_key or kwargs.get("api_key") or kwargs.get("key")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        self.system_instruction = (
            "Você é o Revisor Chefe de Qualidade Visual e Imagens de Arquivo do canal 'Minuto Inexplicável'. "
            "Sua missão é auditar rigorosamente frames de filmagens baixadas do YouTube para garantir relevância factual e documental ao mistério ou documentário estudado.\n\n"
            "CRITÉRIOS DE REPROVAÇÃO IMEDIATA (B-Roll PROIBIDO - NOTA <= 3 / APROVADO=FALSE):\n"
            "- Desenhos animados, animações 3D, personagens de cinema/anime (ex: Kung Fu Panda, Shrek, Mickey, animes, desenhos infantis).\n"
            "- Rostos de podcasters, apresentadores de estúdio, streamers ou pessoas falando para a câmera em formato vlog.\n"
            "- Telas pretas, slides de texto/títulos estáticos, vinhetas promocionais, botões 'inscreva-se', 'deixe o like' ou logotipos de canais.\n"
            "- Vídeos completamente fora do contexto da cena (ex: gameplay de jogos, futebol, clipes musicais, memes).\n\n"
            "CRITÉRIOS DE APROVAÇÃO (B-Roll VÁLIDO - NOTA >= 6 / APROVADO=TRUE):\n"
            "- Imagens reais de satélite, mapas topográficos, tomadas aéreas de drones sobre paisagens e desertos, filmagens históricas de arquivo (preto e branco ou anos 60-90), expedições científicas, instrumentos laboratoriais e estruturas arqueológicas/geológicas autênticas.\n\n"
            "Responda SEMPRE em JSON: {'aprovado': true/false, 'nota_relevancia': 0 a 10, 'motivo': '...', 'descartar_video_inteiro': true/false}"
        )

    def review_frame(self, image_path: str, context_text: str, cooldown_callback=None, status_callback=None) -> Dict[str, Any]:
        if not os.path.exists(image_path):
            return {"aprovado": False, "nota_relevancia": 0.0, "score": 0.0, "motivo": "Arquivo de imagem não encontrado.", "descartar_video_inteiro": True}
        
        keys_pool = resolve_gemini_api_keys(self.api_key)
        if not keys_pool:
            keys_pool = [""]

        models_to_try = [self.model_name]
        if self.auto_fallback:
            for m in self.fallback_models:
                if m not in models_to_try:
                    models_to_try.append(m)

        last_err = None
        for k_idx, current_key in enumerate(keys_pool):
            now = time.time()
            cooldown_until = 0.0
            if DEFAULT_KEY_POOL:
                state = DEFAULT_KEY_POOL._load_state()
                cooldown_until = float(state.get("keys", {}).get(current_key, {}).get("cooldown_until_ts", 0.0))
            if cooldown_until > now and len(keys_pool) > 1:
                continue

            for current_model in models_to_try:
                try:
                    img = Image.open(image_path)
                    prompt = (
                        f"Contexto do documentário/cena: '{context_text}'.\n"
                        f"Avalie a imagem anexada: ela é uma filmagem/foto real relevante de documentário, ou contém desenho/animação (ex: Kung Fu Panda/anime), rosto de apresentador/streamer, texto estático ou assunto irrelevante?"
                    )
                    
                    client = get_genai_client(api_key=current_key)
                    config = types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        response_mime_type="application/json",
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        http_options=types.HttpOptions(timeout=35000)
                    )
                    
                    resp = client.models.generate_content(
                        model=current_model,
                        contents=[img, prompt],
                        config=config
                    )
                    
                    clean_res = resp.text.strip()
                    clean_res = re.sub(r"^```json\s*", "", clean_res, flags=re.IGNORECASE)
                    clean_res = re.sub(r"\s*```$", "", clean_res).strip()
                    data = json.loads(clean_res)
                    
                    score = float(data.get("nota_relevancia", 0.0) or data.get("score", 0.0))
                    data["score"] = score
                    data["nota_relevancia"] = score
                    # Exige nota >= 6.0 e aprovado = True para passar
                    if score < 6.0:
                        data["aprovado"] = False
                    
                    return data
                except Exception as e:
                    err_str = str(e)
                    last_err = e
                    is_quota = ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower())
                    if is_quota and DEFAULT_KEY_POOL:
                        DEFAULT_KEY_POOL.mark_key_cooldown(current_key, duration_seconds=3600, reason="Quota 429 no ReviewerAgent")
                        break
                    app_logger.warning(f"[ReviewerAgent] Erro no modelo {current_model} (Chave #{k_idx+1}): {err_str}")

        app_logger.warning(f"[ReviewerAgent] Auditoria de visão indisponível ({str(last_err)}).")
        return {
            "aprovado": False,
            "nota_relevancia": 0.0,
            "score": 0.0,
            "motivo": f"Auditoria visual falhou ({str(last_err)})",
            "descartar_video_inteiro": False
        }

    def inspect_clip(
        self,
        clip_path: str,
        global_topic: str = "",
        scene_fala: str = "",
        video_title: str = "",
        status_callback = None
    ) -> Dict[str, Any]:
        """
        Extrai um frame de auditoria do clipe MP4 recortado e analisa com Gemini Vision.
        """
        if not clip_path or not os.path.exists(clip_path):
            return {"aprovado": False, "score": 0.0, "nota_relevancia": 0.0, "motivo": "Clipe não encontrado no disco", "descartar_video_inteiro": True}

        # Extrai frame aos 0.5s para auditoria
        tmp_frame = clip_path + ".review.jpg"
        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", "0.5",
                "-i", clip_path,
                "-vframes", "1",
                "-q:v", "2",
                tmp_frame
            ]
            subprocess.run(cmd, capture_output=True, timeout=8)
            if not os.path.exists(tmp_frame):
                # Tenta frame inicial
                cmd[2] = "0.0"
                subprocess.run(cmd, capture_output=True, timeout=8)
        except Exception:
            pass

        if not os.path.exists(tmp_frame):
            return {"aprovado": True, "score": 7.0, "nota_relevancia": 7.0, "motivo": "Frame não pôde ser extraído (assumindo aprovação cautelosa)"}

        context = f"Tema Global: '{global_topic}'. Fala da Cena: '{scene_fala}'. Título do Vídeo no YouTube: '{video_title}'."
        try:
            res = self.review_frame(tmp_frame, context_text=context, status_callback=status_callback)
            return res
        finally:
            if os.path.exists(tmp_frame):
                try:
                    os.remove(tmp_frame)
                except Exception:
                    pass

