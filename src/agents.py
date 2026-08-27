import os
import re
import time
import json
import random
import subprocess
import tempfile
import threading
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

try:
    from .logger import app_logger, LogSpan, record_throttling
except ImportError:
    from logger import app_logger, LogSpan, record_throttling

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lista de modelos rápidos e comprovadamente ativos
DEFAULT_FALLBACK_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite"
]

def resolve_gemini_api_key(explicit_key: Optional[str] = None) -> str:
    """
    Resolve a chave de API do Gemini a partir de múltiplas fontes com prioridade:
    1. Chave explícita informada como argumento
    2. Arquivo 'gemini-api.txt' (extraindo de comando curl/header ou chave pura)
    3. Arquivos alternativos 'key.txt', 'gemini_api.txt', 'api_key.txt'
    4. Arquivo '.env'
    5. Variável de ambiente 'GEMINI_API_KEY'
    """
    if explicit_key and explicit_key.strip():
        k = explicit_key.strip()
        if k != "sua_chave_gemini_aqui":
            return k

    # 1. Checa arquivos .txt conhecidos de chave no diretório do projeto e cwd
    txt_candidates = [
        "gemini-api.txt",
        "gemini_api.txt",
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
                        content = f.read().strip()
                    # Tenta extrair de header curl (-H 'X-goog-api-key: ...')
                    match_header = re.search(r"X-goog-api-key:\s*['\"]?([A-Za-z0-9_\-\.]+)['\"]?", content, re.IGNORECASE)
                    if match_header:
                        found_key = match_header.group(1).strip()
                        if found_key and found_key != "sua_chave_gemini_aqui":
                            return found_key
                    # Tenta extrair de padrão GEMINI_API_KEY=...
                    match_kv = re.search(r"GEMINI_API_KEY\s*=\s*['\"]?([A-Za-z0-9_\-\.]+)['\"]?", content, re.IGNORECASE)
                    if match_kv:
                        found_key = match_kv.group(1).strip()
                        if found_key and found_key != "sua_chave_gemini_aqui":
                            return found_key
                    # Se for texto em linha única sem espaços
                    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
                    if len(lines) == 1 and " " not in lines[0] and len(lines[0]) >= 20:
                        return lines[0]
                except Exception as e:
                    app_logger.warning(f"[Agents] Erro ao ler chave de '{full_fn}': {str(e)}")

    # 2. Checa variável de ambiente
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key and env_key != "sua_chave_gemini_aqui":
        return env_key

    # 3. Checa arquivo .env
    for sdir in search_dirs:
        env_file = os.path.join(sdir, ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    env_content = f.read()
                match_env = re.search(r"GEMINI_API_KEY\s*=\s*['\"]?([A-Za-z0-9_\-\.]+)['\"]?", env_content, re.IGNORECASE)
                if match_env:
                    found_key = match_env.group(1).strip()
                    if found_key and found_key != "sua_chave_gemini_aqui":
                        return found_key
            except Exception:
                pass

    return ""

def get_genai_client(api_key: Optional[str] = None) -> genai.Client:
    """Cria e retorna uma instância do cliente oficial google-genai."""
    key = api_key.strip() if (api_key and api_key.strip()) else resolve_gemini_api_key()
    if key and key != "sua_chave_gemini_aqui":
        return genai.Client(api_key=key)
    return genai.Client()

def validate_gemini_api_connection(api_key: Optional[str] = None, model_name: str = "gemini-flash-lite-latest") -> Tuple[bool, str]:
    """
    Valida a conectividade e autenticação com a API Gemini antes de iniciar o pipeline.
    Retorna (sucesso: bool, mensagem: str).
    """
    if api_key is not None:
        key = api_key.strip()
    else:
        key = resolve_gemini_api_key()

    if not key or key == "sua_chave_gemini_aqui":
        return False, "Chave de API do Gemini não configurada. Defina GEMINI_API_KEY no arquivo .env ou nas variáveis de ambiente."
    try:
        client = genai.Client(api_key=key)
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
            return True, f"Conexão com a API Gemini validada com sucesso (modelo: {model_name})."
        return False, "Resposta vazia retornada pela API Gemini durante o teste de pré-voo."
    except Exception as e:
        err_msg = str(e)
        return False, f"Falha na validação da API Gemini: {err_msg}"



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
    model_name: str = "gemini-flash-lite-latest",
    fallback_models: list = None,
    auto_fallback: bool = True,
    auto_cooldown: bool = True,
    response_mime_type: str = None,
    cooldown_callback = None,
    status_callback = None,
    timeout_seconds: float = 60.0,
    max_cooldown_retries: int = 3,
    api_key: Optional[str] = None
) -> str:
    """
    Executa chamada com streaming em tempo real, timeout de 60s+ e fallback automático (google-genai SDK).
    """
    GLOBAL_RATE_LIMITER.acquire()
    
    if fallback_models is None:
        fallback_models = list(DEFAULT_FALLBACK_MODELS)
        
    models_to_try = [model_name]
    if auto_fallback:
        for m in fallback_models:
            if m not in models_to_try:
                models_to_try.append(m)

    client = get_genai_client(api_key=api_key)

    for m_idx, current_model in enumerate(models_to_try):
        retries_left = max_cooldown_retries
        while retries_left > 0:
            start_time = time.time()
            try:
                if status_callback:
                    status_callback(f"Conectando ao modelo **{current_model}**...")

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type=response_mime_type,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
                )
                
                response_stream = client.models.generate_content_stream(
                    model=current_model,
                    contents=prompt,
                    config=config
                )
                
                full_text = []
                chunk_count = 0
                for chunk in response_stream:
                    chunk_text = chunk.text or ""
                    full_text.append(chunk_text)
                    chunk_count += 1
                    elapsed = round(time.time() - start_time, 1)
                    if status_callback and chunk_count % 3 == 1:
                        total_len = sum(len(c) for c in full_text)
                        status_callback(f"Gerando via **{current_model}**... (⏱️ {elapsed}s • {total_len} carac.)")

                final_text = "".join(full_text).strip()
                if final_text:
                    elapsed = round(time.time() - start_time, 1)
                    if status_callback:
                        status_callback(f"✅ Concluído via **{current_model}** em {elapsed}s ({len(final_text)} caracteres).")
                    return final_text
                else:
                    raise Exception("Resposta vazia do modelo.")
                
            except Exception as e:
                err_text = str(e)
                elapsed = round(time.time() - start_time, 1)
                is_quota = "ResourceExhausted" in type(e).__name__ or "RESOURCE_EXHAUSTED" in err_text or "Quota exceeded" in err_text or "429" in err_text
                is_timeout = "DeadlineExceeded" in type(e).__name__ or "DEADLINE_EXCEEDED" in err_text or "timeout" in err_text.lower() or "504" in err_text
                
                if is_timeout:
                    app_logger.warning(f"[Gemini API] Timeout (> {timeout_seconds}s) no modelo {current_model}")
                    if auto_fallback and m_idx < len(models_to_try) - 1:
                        next_model = models_to_try[m_idx + 1]
                        if status_callback:
                            status_callback(f"⏱️ Timeout em **{current_model}**. Alternando para **{next_model}**...")
                        break
                    else:
                        raise e
                
                if not is_quota:
                    if auto_fallback and m_idx < len(models_to_try) - 1:
                        next_model = models_to_try[m_idx + 1]
                        if status_callback:
                            status_callback(f"⚠️ Erro em **{current_model}**. Fallback para **{next_model}**...")
                        break
                    raise e
                
                wait_sec = extract_retry_seconds(err_text)
                record_throttling("API_GEMINI", "HTTP_429_QUOTA", f"Cota esgotada no modelo {current_model}: {err_text[:180]}", retry_after=wait_sec)
                
                if auto_fallback and m_idx < len(models_to_try) - 1:
                    next_model = models_to_try[m_idx + 1]
                    if status_callback:
                        status_callback(f"⚠️ Cota atingida em **{current_model}**. Alternando para **{next_model}**...")
                    break
                
                if auto_cooldown:
                    if status_callback:
                        status_callback(f"⏳ Cota atingida em **{current_model}**. Cooldown de {wait_sec}s...")
                    for remaining in range(wait_sec, 0, -1):
                        if cooldown_callback:
                            cooldown_callback(remaining, wait_sec, current_model)
                        time.sleep(1)
                    if cooldown_callback:
                        cooldown_callback(0, wait_sec, current_model)
                    retries_left -= 1
                    continue
                else:
                    raise e
                    
    raise Exception(f"Todos os modelos falharam. Último modelo: {models_to_try[-1]}")

def generate_multimodal_with_resilience(
    contents: list,
    system_instruction: str,
    model_name: str = "gemini-flash-lite-latest",
    fallback_models: list = None,
    auto_fallback: bool = True,
    auto_cooldown: bool = True,
    response_mime_type: str = "application/json",
    cooldown_callback = None,
    status_callback = None,
    timeout_seconds: float = 60.0,
    api_key: Optional[str] = None
) -> str:
    """
    Executa chamada multimodal (imagens + texto) com rate limiter, timeout 60s+ e fallback.
    """
    GLOBAL_RATE_LIMITER.acquire()

    if fallback_models is None:
        fallback_models = list(DEFAULT_FALLBACK_MODELS)
        
    models_to_try = [model_name]
    if auto_fallback:
        for m in fallback_models:
            if m not in models_to_try:
                models_to_try.append(m)

    client = get_genai_client(api_key=api_key)

    for m_idx, current_model in enumerate(models_to_try):
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type=response_mime_type,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
            )
            response = client.models.generate_content(
                model=current_model,
                contents=contents,
                config=config
            )
            if response and response.text:
                return response.text.strip()
            raise Exception("Resposta multimodal vazia.")
        except Exception as e:
            err_text = str(e)
            is_quota = "ResourceExhausted" in type(e).__name__ or "RESOURCE_EXHAUSTED" in err_text or "429" in err_text
            if is_quota:
                wait_sec = extract_retry_seconds(err_text)
                record_throttling("API_GEMINI", "HTTP_429_MULTIMODAL_QUOTA", f"Cota esgotada em visão ({current_model}): {err_text[:180]}", retry_after=wait_sec)
            app_logger.warning(f"[MultimodalVision] Erro no modelo {current_model}: {err_text}")
            if auto_fallback and m_idx < len(models_to_try) - 1:
                continue
            raise e
    raise Exception("Todos os modelos de visão multimodal falharam.")

POPULAR_INEXPLICABLE_ANGLES = [
    "Bases Militares Secretas e Instalações Subterrâneas Desclassificadas (ex: Camp Century Groenlândia, Cheyenne Mountain, Diefenbunker, Mount Weather, Base Submarina de Balaklava, Complexo Riese)",
    "Mistérios e Expedições Árticas e Antárticas (ex: Incidente Dyatlov, Operação Highjump Antártida, Navios Perdidos HMS Erebus e Terror, Anomalia Magnética de Wilkes Land)",
    "Perfurações Profundas, Cavernas e Anomalias Geológicas da Terra (ex: Poço Superprofundo de Kola 12km, Mina de Mirny Sibéria, Cavernas Subterrâneas de Derinkuyu, Caverna Isolada de Movile)",
    "Sinais Misteriosos e Anomalias do Espaço Profundo (ex: Sinal Wow! 1977 telescópio Big Ear, Estrela de Tabby KIC 8462852, Objeto Interestelar Oumuamua, Misterioso Sinal BLC1 Proxima Centauri)",
    "Mistérios Abissais e Estruturas Ocultas dos Oceanos (ex: Fossa das Marianas Challenger Deep, Anomalia do Mar Báltico, Som Subaquático Bloop, Mar dos Sargaços, Estrada Submersa de Bimini)",
    "Projetos Científicos e Militares Ultrassecretos da Guerra Fria (ex: Projeto MKUltra CIA, Projeto Habbakuk porta-aviões de gelo, Projeto Montauk, Radar Duga Chernobyl Pica-Pau Russo, Experimento Filadélfia)",
    "Arqueologia Impossível e Estruturas Megalíticas Enigmáticas (ex: Göbekli Tepe 11000 anos, Cidade Flutuante de Nan Madol, Linhas Gigantes de Nazca, Pirâmides Submersas de Yonaguni, Mecanismo de Anticítera)",
    "Fenômenos Atmosféricos e Luzes Misteriosas Registradas (ex: Luzes Noturnas de Hessdalen Noruega, Explosão do Meteoro de Tunguska 1908, Relâmpago Eterno de Catatumbo, Luzes de Marfa Texas)",
    "Desaparecimentos em Massa e Ilhas Fantasmas (ex: Desaparecimento de Roanoke 1590, Navio Fantasma Mary Celeste 1872, Mistério do Farol das Ilhas Flannan 1900, Ilha Fantasma Sandy Island)",
    "Artefatos Fora de Lugar (OOPArts) e Tecnologia Antiga Inexplicável (ex: Bateria Antiga de Bagdá, Pilares de Ferro Inoxidável de Déli, Esferas Perfeitas de Pedra da Costa Rica, Manuscrito Voynich)"
]

FALLBACK_INEXPLICABLE_TOPICS = [
    {
        "tema": "A Base Nuclear Secreta Enterrada Sob o Gelo ❄️☢️",
        "descricao": "Em plena Guerra Fria, o exército americano construiu o Projeto Camp Century: uma cidade militar nuclear inteira escavada dentro da calota de gelo da Groenlândia.\n\n🔔 Inscreva-se no @MinutoInexplicavel para mais arquivos desclassificados!\n💬 Você sabia que reatores nucleares funcionaram sob o gelo polar?",
        "tags": ["#Shorts", "#MinutoInexplicavel", "#ProjetosSecretos", "#CampCentury", "#GuerraFria", "#Misterios", "#HistoriaOculta", "#Documentario", "#Curiosidades", "#FatosReais"],
        "hook": "Em plena Guerra Fria, uma cidade militar inteira com reator nuclear foi enterrada sob o gelo polar.",
        "explicacao_tecnica": "O Projeto Camp Century foi uma base ultrassecreta escavada na calota de gelo da Groenlândia com túneis para mísseis balísticos nucleares."
    },
    {
        "tema": "O Poço Mais Fundo da Terra e os Sons de Kola 🕳️🇷🇺",
        "descricao": "Cientistas soviéticos perfuraram mais de doze mil metros na crosta terrestre no Poço Superprofundo de Kola, descobrindo anomalias térmicas e geológicas inexplicáveis.\n\n🔔 Siga o @MinutoInexplicavel!\n💬 O que você acha que existe nas camadas mais profundas da crosta terrestre?",
        "tags": ["#Shorts", "#MinutoInexplicavel", "#PocoDeKola", "#Ciencia", "#Geologia", "#Misterios", "#URSS", "#HistoriaReal", "#Documentario", "#Curiosidades"],
        "hook": "Eles cavaram doze quilômetros em direção ao centro da Terra e o que encontraram desafiou a física.",
        "explicacao_tecnica": "O Poço Superprofundo de Kola atingiu 12.262 metros de profundidade, revelando rochas fraturadas saturadas de água e temperaturas muito superiores ao previsto."
    },
    {
        "tema": "O Enigma do Passo Dyatlov nos Montes Urais 🏔️❄️",
        "descricao": "Em 1959, nove esquiadores experientes rasgaram sua barraca de dentro para fora e fugiram descalços na neve mortal dos Montes Urais sob circunstâncias enigmáticas.\n\n🔔 Inscreva-se no canal @MinutoInexplicavel para não perder nenhum mistério!\n💬 Qual a sua teoria sobre o Incidente de Dyatlov?",
        "tags": ["#Shorts", "#MinutoInexplicavel", "#PassoDyatlov", "#MisteriosReais", "#MontesUrais", "#Sobrenatural", "#HistoriaOculta", "#Documentario", "#FatosReais", "#Curiosidades"],
        "hook": "Nove montanhistas rasgaram a própria barraca por dentro e fugiram descalços na neve a menos trinta graus.",
        "explicacao_tecnica": "O Incidente do Passo Dyatlov em 1959 resultou na morte inexplicada de nove expedicionários soviéticos com traumas severos e radiação nas roupas."
    },
    {
        "tema": "O Abismo da Fossa das Marianas: O Fundo do Oceano 🌊👁️",
        "descricao": "Com quase onze mil metros de profundidade, o Challenger Deep abriga pressões esmagadoras e formas de vida bioluminescentes nunca antes catalogadas pela ciência.\n\n🔔 Inscreva-se no canal @MinutoInexplicavel!\n💬 Você teria coragem de descer ao ponto mais profundo da Terra?",
        "tags": ["#Shorts", "#MinutoInexplicavel", "#FossaDasMarianas", "#OceanoProfundo", "#Abismo", "#CriaturasAbissais", "#Ciencia", "#Documentario", "#Exploracao", "#Curiosidades"],
        "hook": "A quase onze quilômetros de profundidade, a pressão esmagadora guarda criaturas que nunca viram a luz.",
        "explicacao_tecnica": "A Depressão Challenger na Fossa das Marianas atinge mais de mil atmosferas de pressão, sustentando ecossistemas baseados em quimiossíntese."
    },
    {
        "tema": "O Sinal Wow! de 1977: A Mensagem Interestelar 📡🌌",
        "descricao": "O radiotelescópio Big Ear captou um sinal de rádio de banda estreita com 72 segundos de duração vindo da constelação de Sagitário que nunca mais se repetiu.\n\n🔔 Inscreva-se no canal @MinutoInexplicavel!\n💬 Você acredita que o Sinal Wow foi emitido por inteligência extraterrestre?",
        "tags": ["#Shorts", "#MinutoInexplicavel", "#SinalWow", "#Espaco", "#Astronomia", "#SinaisEspaciais", "#SETI", "#Documentario", "#Curiosidades", "#Cosmos"],
        "hook": "Em 1977, um telescópio registrou uma transmissão espacial tão intensa que o astrônomo circulou a folha e escreveu 'Uau!'.",
        "explicacao_tecnica": "O Sinal Wow foi uma emissão de rádio anômala na frequência da linha de hidrogênio (1420 MHz) detectada pelo projeto SETI com características de origem artificial."
    },
    {
        "tema": "Derinkuyu: A Cidade Subterrânea de 18 Andares ⛏️🏛️",
        "descricao": "Escavada na rocha vulcânica da Capadócia, a cidade subterrânea de Derinkuyu comportava mais de vinte mil pessoas com poços de ventilação e portas de pedra colossais.\n\n🔔 Inscreva-se no canal @MinutoInexplicavel!\n💬 O que levou uma civilização inteira a viver debaixo da terra?",
        "tags": ["#Shorts", "#MinutoInexplicavel", "#Derinkuyu", "#Arqueologia", "#HistoriaAntiga", "#Capadocia", "#Subterraneo", "#Documentario", "#Misterios", "#Curiosidades"],
        "hook": "Debaixo do solo da Turquia, uma cidade inteira de dezoito andares foi esculpida na rocha sólida.",
        "explicacao_tecnica": "Derinkuyu possui túneis com até 85 metros de profundidade, equipados com dutos de ar, prensas de óleo, refeitórios e portas circulares de pedra maciça."
    },
    {
        "tema": "O Bloop: O Rugido Submarino do Pacífico Sul 🔊🐋",
        "descricao": "Em 1997, hidrofones militares captaram um som subaquático de frequência ultra-baixa detectado a mais de cinco mil quilômetros de distância no oceano Pacífico.\n\n🔔 Inscreva-se no canal @MinutoInexplicavel!\n💬 O que você acha que produziu um som tão colossal no fundo do mar?",
        "tags": ["#Shorts", "#MinutoInexplicavel", "#TheBloop", "#MisteriosDoOceano", "#Criptozoologia", "#Ciencia", "#Profundezas", "#Documentario", "#Curiosidades", "#FatosReais"],
        "hook": "Sensores militares no oceano captaram um ruído tão colossal que nenhum animal conhecido na Terra poderia ter produzido.",
        "explicacao_tecnica": "O som apelidado de Bloop foi registrado pela NOAA por hidrofones da Guerra Fria a milhares de quilômetros de distância no Pacífico Sul."
    },
    {
        "tema": "O Radar Duga de Chernobyl: O Pica-Pau Russo 📻☢️",
        "descricao": "Uma antena colossal soviética de 150 metros de altura emitia um sinal pulsante misterioso de 10 Hz que interferia em transmissões de rádio do mundo inteiro.\n\n🔔 Inscreva-se no @MinutoInexplicavel!\n💬 Você sabia que essa antena gigante ficava escondida perto de Chernobyl?",
        "tags": ["#Shorts", "#MinutoInexplicavel", "#RadarDuga", "#Chernobyl", "#URSS", "#GuerraFria", "#PicaPauRusso", "#HistoriaOculta", "#Documentario", "#Curiosidades"],
        "hook": "Uma muralha metálica de 150 metros de altura perto de Chernobyl transmitia um sinal secreto que intrigou o planeta.",
        "explicacao_tecnica": "O sistema de radar além-do-horizonte Duga operava na faixa de ondas curtas para detecção precoce de mísseis balísticos intercontinentais."
    }
]

class ProposerAgent:
    """
    Agente Propositor de Temas para o canal 'Minuto Inexplicável'.
    Gera o PACOTE COMPLETO DE PUBLICAÇÃO: Título, Descrição estruturada, Hashtags virais, Hook de 3s e Contexto Factual.
    Respeita estritamente a Blacklist de temas já gravados.
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_key = (api_key or kwargs.get("api_key") or kwargs.get("key") or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.system_instruction = (
            "Você é o estrategista chefe de conteúdo viral e roteirista sênior do canal 'Minuto Inexplicável' (Shorts 9:16).\n"
            "Sua missão é conceber ideias completas de vídeos sobre mistérios reais, documentos desclassificados, projetos militares secretos e anomalias científicas da Terra e do Espaço.\n"
            "Gere O PACOTE COMPLETO DE PUBLICAÇÃO: Título Magnético com emojis, Descrição Completa para YouTube Shorts/TikTok, Hashtags Estratégicas, Hook inicial de suspense (3 segundos) e Contexto Factual/Histórico.\n"
            "FOCO ESTRITO EM MISTÉRIOS REAIS COM VASTA DISPONIBILIDADE DE FILMAGENS DE ARQUIVO, SATÉLITE, EXPEDIÇÕES E DOCUMENTÁRIOS NO YOUTUBE.\n\n"
            "Responda SEMPRE em formato JSON com uma lista de objetos contendo exatamente:\n"
            "- 'tema': Título do vídeo otimizado para clique e alta retenção (ex: 'A Base Nuclear Secreta Enterrada Sob o Gelo ❄️☢️')\n"
            "- 'descricao': Descrição completa e formatada para publicação no YouTube Shorts (incluindo hook, resumo do mistério desclassificado, chamada para inscrição no 'Minuto Inexplicável' e pergunta provocativa para engajamento nos comentários)\n"
            "- 'tags': Lista de 8 a 15 hashtags virais pertinentes (ex: ['#Shorts', '#MinutoInexplicavel', '#Misterios', '#ProjetosSecretos', '#HistoriaOculta', '#Documentario', '#Curiosidades', '#GuerraFria', ...])\n"
            "- 'hook': Frase inicial de altíssimo impacto e suspense para os primeiros 3 segundos da narração\n"
            "- 'explicacao_tecnica': Resumo factual, instigante e documentado do mistério."
        )

    def generate_topics(self, count=10, blacklist: Optional[List[Any]] = None, seed=None, cooldown_callback=None, status_callback=None):
        seed_val = seed if seed is not None else random.randint(100000, 999999)
        time_salt = int(time.time() * 1000) % 100000
        angles_sample = random.sample(POPULAR_INEXPLICABLE_ANGLES, min(4, len(POPULAR_INEXPLICABLE_ANGLES)))
        angles_str = "\n".join([f"- {a}" for a in angles_sample])

        blacklist_str = ""
        if blacklist:
            formatted_items = []
            for b in blacklist[-60:]:
                if isinstance(b, dict):
                    t = b.get("tema") or b.get("core_entity") or str(b)
                else:
                    t = str(b).strip()
                if t:
                    formatted_items.append(f"- {t}")
            if formatted_items:
                blacklist_str = (
                    f"\n\n[BLACKLIST DE MISTÉRIOS JÁ GRAVADOS - ESTRITAMENTE PROIBIDO REPETIR]:\n"
                    f"{chr(10).join(formatted_items)}\n"
                    f"ATENÇÃO MÁXIMA: É TERMINANTEMENTE PROIBIDO repetir qualquer um dos mistérios, locais ou eventos listados na Blacklist acima. "
                    f"Gere temas 100% INÉDITOS com outros segredos, projetos desclassificados e anomalias."
                )

        prompt = (
            f"Gere {count} ideias COMPLETAS e INÉDITAS sobre mistérios reais do mundo para o canal 'Minuto Inexplicável' (vídeos de 60 a 90 segundos).\n\n"
            f"[ENTROPIA & SEED DE DIVERSIDADE]: #{seed_val}-{time_salt}\n"
            f"DIRETRIZES OBRIGATÓRIAS:\n"
            f"1. PACOTE COMPLETO: Cada ideia DEVE conter 'tema' (Título), 'descricao' (Descrição completa para o YouTube), 'tags' (Hashtags virais), 'hook' (Primeiros 3 segundos) e 'explicacao_tecnica' (Contexto documental).\n"
            f"2. BASE EM FATOS REAIS E ARQUIVOS: Escolha mistérios que possuam vasto acervo de imagens reais, fotos de arquivo, filmagens de satélite, expedições e documentários no YouTube (ex: Projeto Camp Century Groenlândia, Poço de Kola, Incidente Dyatlov, Fossa das Marianas, Sinal Wow, Cavernas de Derinkuyu, Mar dos Sargaços, Ilha Bouvet, Experimentos da Guerra Fria).\n"
            f"3. VARIEDADE MÁXIMA: Garanta que as {count} ideias cubram diferentes categorias (bases secretas, anomalias espaciais, expedições árticas, fenômenos oceânicos, arqueologia impossível).\n"
            f"4. ÂNGULOS DESTAQUE SORTEADOS PARA ESTA RODADA:\n{angles_str}"
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
                api_key=self.api_key
            )
            parsed = json.loads(raw_text)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
            elif isinstance(parsed, dict) and "temas" in parsed and isinstance(parsed["temas"], list):
                return parsed["temas"]
            raise Exception("Resposta da IA não continha uma lista válida de temas.")
        except Exception as e:
            app_logger.error(f"[ProposerAgent] Falha na geração de temas via IA: {str(e)}")
            raise e


class EvaluatorAgent:
    """
    Agente Avaliador de Retenção e Fator Mistério.
    Julga o potencial viral, a força do hook inicial e a credibilidade factual do roteiro.
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_key = (api_key or kwargs.get("api_key") or kwargs.get("key") or os.environ.get("GEMINI_API_KEY", "")).strip()
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
    """
    Gera o conteúdo textual completo para o arquivo metadata.txt de cada vídeo:
    - TÍTULO
    - DESCRIÇÃO (estruturada com Hook, Contexto, CTA e Pergunta)
    - HASHTAGS (10 a 15 hashtags virais)
    """
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
    Agente Diretor de Produção do 'Minuto Inexplicável'.
    Gera roteiro investigativo em formato aprofundado (60 a 90 segundos, 150 a 220 palavras faladas)
    e divide em 12 a 18 cenas dinâmicas com queries de YouTube em INGLÊS focadas em filmagens históricas, satélite, arquivo e CGI.
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_key = (api_key or kwargs.get("api_key") or kwargs.get("key") or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.system_instruction = (
            "Você é o Diretor de Produção Audiovisual e Roteirista Investigativo de elite do canal 'Minuto Inexplicável'. "
            "Sua missão é criar o roteiro aprofundado de 60 a 90 segundos (entre 150 e 220 palavras faladas, 60s a 90s) "
            "com tom hipnótico de suspense documental (estilo Discovery/History Channel / Arquivo Confidencial) "
            "e selecionar as filmagens REAIS DE ARQUIVO, SATÉLITE E DOCUMENTÁRIOS mais puras do YouTube para cada cena.\n\n"
            "REGRAS CRÍTICAS DE BUSCA NO YOUTUBE ('youtube_query'):\n"
            "1. Todas as queries DEVEM ser em INGLÊS, CURTAS (3 a 6 palavras) e com CONEXÃO PARTICULAR OBRIGATÓRIA ao evento/local/mistério de estudo.\n"
            "2. OBRIGATÓRIO: TODA query DEVE conter o [NOME EXATO DO LOCAL/PROJETO/EVENTO] + [TERMO DE ARQUIVO/DOCUMENTÁRIO] (ex: 'Camp Century Greenland nuclear ice documentary', 'Kola Superdeep borehole USSR real footage', 'Mariana trench deep sea exploration 4k', 'Dyatlov Pass incident historical photos').\n"
            "3. Prefira termos que puxem filmagens autênticas: 'real archival footage', 'documentary 4k', 'satellite drone view', 'historical expedition', 'underground bunker 4k', 'ocean depth exploration 4k'.\n"
            "4. 'fala': a frase falada exata da narração nesta cena (narração fluida, sem introduções robóticas).\n"
            "Responda SEMPRE em JSON com a chave raiz 'cenas' (lista de 12 a 18 objetos contendo 'scene_id', 'fala', 'youtube_query', 'duracao_estimada')."
        )

    def generate_storyboard(self, tema: Dict[str, Any], cooldown_callback=None, status_callback=None) -> List[Dict[str, Any]]:
        raw_topic = tema.get('tema', 'Mistério Desclassificado')
        core_entity = extract_core_entity(raw_topic)
        prompt = (
            f"Crie o roteiro investigativo aprofundado de 60 a 90 segundos com plano de cortes detalhado.\n"
            f"TEMA CENTRAL: '{raw_topic}'\n"
            f"ENTIDADE/LOCAL/PROJETO: '{core_entity}'\n"
            f"Hook Inicial: {tema.get('hook')}\n"
            f"Base Factual/Histórica: {tema.get('explicacao_tecnica')}\n\n"
            f"Gere entre 12 e 18 cenas dinâmicas (150 a 220 palavras totais) com queries CURTAS em INGLÊS sobre as filmagens reais e documentários de '{core_entity}'."
        )
        cenas = []
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
            if isinstance(data, dict) and "cenas" in data and isinstance(data["cenas"], list):
                cenas = data["cenas"]
            elif isinstance(data, list):
                cenas = data
        except Exception as e:
            app_logger.error(f"[DirectorAgent] Erro ao obter/decodificar storyboard por IA: {str(e)}")
            raise e

        if not cenas or len(cenas) < 4:
            raise Exception(f"Storyboard retornado por IA inválido ou com menos de 4 cenas (cenas={len(cenas) if cenas else 0}).")


        core_words = [w.lower() for w in core_entity.split() if len(w) > 2]
        sanitized_cenas = []
        for c in cenas:
            q = c.get("youtube_query", "").strip()
            q_lower = q.lower()
            has_anchor = any(w in q_lower for w in core_words) if core_words else False
            if not has_anchor and q:
                q = f"{core_entity} {q}".strip()
            c["youtube_query"] = q
            sanitized_cenas.append(c)

        return sanitized_cenas

FORBIDDEN_TITLE_KEYWORDS = [
    "gopro", "insta360", "dji osmo", "action cam", "action camera",
    "telemetry overlay", "gps telemetry", "gps stats", "telemetry app",
    "tutorial", "how to", "how-to", "how to add", "how to install", "como fazer", "passo a passo",
    "install", "installation", "setup", "diy", "guia", "guide", "review", "unboxing",
    "windows", "macos", "mac os", "macbook", "pc build", "software", "plugin",
    "obs studio", "premiere pro", "after effects", "davinci", "photoshop", "apk",
    "gameplay", "walkthrough", "playthrough", "forza", "minecraft", "roblox", "gta 5", "gta v",
    "hot wheels", "diecast", "lego", "toy", "brinquedo", "fortnite",
    "podcast", "react", "reaction", "reacting", "interview", "entrevista", "bate papo",
    "daily vlog", "vlog", "meu dia", "comprei", "compramos", "minha casa", "child", "kid", "kids",
    "humor", "pegadinha", "prank", "desafio"
]

def find_ffmpeg_binary() -> str:
    """Busca o executável do FFmpeg em múltiplos locais conhecidos (static-ffmpeg, imageio-ffmpeg, WinGet, PATH)."""
    try:
        import static_ffmpeg
        ffmpeg_exe, _ = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        if os.path.exists(ffmpeg_exe):
            return ffmpeg_exe
    except Exception:
        pass
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    return "ffmpeg"

class ReviewerAgent:
    """
    Agente Revisor e Auditor de Qualidade Visual Multimodal (Gemini Vision) para 'Minuto Inexplicável'.
    Inspeciona frames com POLÍTICA ZERO ROSTOS (sem apresentadores/vlogs) e EARLY-DISCARD para descartar gameplays e lixo.
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_key=None, *args, **kwargs):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_key = (api_key or kwargs.get("api_key") or kwargs.get("key") or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.system_instruction = (
            "Você é o Auditor Chefe de Qualidade Visual de Documentários (POLÍTICA ZERO ROSTOS & EARLY-DISCARD RIGOROSA).\n"
            "Sua missão é inspecionar o quadro (frame) de um recorte do YouTube e julgar a pertinência para o canal 'Minuto Inexplicável'.\n\n"
            "DIRETRIZES CRÍTICAS:\n"
            "1. POLÍTICA ZERO ROSTOS: Qualquer pessoa, rosto humano em primeiro plano, apresentador, youtuber conversando ou talking head DEVE SER REPROVADO IMEDIATAMENTE (aprovado = false, score = 1.0).\n"
            "2. POLÍTICA DE EARLY-DISCARD ('descartar_video_inteiro'):\n"
            "   - Defina 'descartar_video_inteiro: true' se o vídeo for FUNDAMENTALMENTE IRRELEVANTE, GAMEPLAY, TUTORIAL, VLOG PESSOAL, DESENHO OU FOFOCA.\n"
            "   - Defina 'descartar_video_inteiro: false' APENAS SE o vídeo for de fato documental sobre o tema, mas este trecho específico continha uma pessoa secundária que pode não estar em outro ponto.\n"
            "3. REGRAS DE APROVAÇÃO (aprovado = true, descartar_video_inteiro = false, score >= 7.0):\n"
            "   - Filmagem de arquivo histórico, mapa com coordenadas, imagens de satélite, bases secretas, gelo/oceano/espaço, documentos, telescópios ou reconstituicão 3D limpa (SEM APRESENTADOR VISÍVEL).\n\n"
            "Responda SEMPRE em JSON:\n"
            "{\n"
            "  \"aprovado\": true | false,\n"
            "  \"descartar_video_inteiro\": true | false,\n"
            "  \"score\": 0.0 a 10.0,\n"
            "  \"motivo\": \"justificativa concisa\",\n"
            "  \"elementos_detectados\": \"elementos visíveis\"\n"
            "}"
        )

    def pre_filter_title(self, video_title: str, global_topic: str) -> Tuple[bool, str]:
        """Pré-filtro de título em 0.001s antes de qualquer download."""
        t_low = video_title.lower()
        for b in FORBIDDEN_TITLE_KEYWORDS:
            if b in t_low:
                return False, f"Título contém termo proibido/irrelevante: '{b}'"
        return True, "Título pré-aprovado"

    def extract_clip_frame(self, clip_path: str) -> Optional[Image.Image]:
        """Extrai 1 frame representativo do trecho e redimensiona para 384px para envio ultra-rápido."""
        try:
            ffmpeg_bin = find_ffmpeg_binary()
            temp_frame = os.path.join(tempfile.gettempdir(), f"frame_rev_{int(time.time()*1000)}_{threading.get_ident()}.jpg")
            cmd = [ffmpeg_bin, "-y", "-ss", "1.5", "-i", clip_path, "-vframes", "1", "-q:v", "3", temp_frame]
            subprocess.run(cmd, capture_output=True, check=True)
            if os.path.exists(temp_frame):
                img = Image.open(temp_frame).convert("RGB")
                img.thumbnail((384, 384))
                try:
                    os.remove(temp_frame)
                except:
                    pass
                return img
        except Exception as e:
            app_logger.warning(f"[ReviewerAgent] Erro ao extrair frame: {str(e)}")
        return None

    def inspect_clip(
        self,
        clip_path: str,
        global_topic: str,
        scene_fala: str,
        video_title: str,
        status_callback = None
    ) -> Dict[str, Any]:
        """Inspeciona o recorte de vídeo com Gemini Vision (1 frame 384px, timeout 60s)."""
        with LogSpan("ReviewerAgent.inspect_clip", extra={"clip": clip_path, "topic": global_topic, "title": video_title}):
            ok_title, reason = self.pre_filter_title(video_title, global_topic)
            if not ok_title:
                app_logger.info(f"[ReviewerAgent] Pré-filtro reprovou '{video_title}': {reason}")
                return {
                    "aprovado": False,
                    "descartar_video_inteiro": True,
                    "score": 1.0,
                    "motivo": reason,
                    "elementos_detectados": "Título incompatível"
                }

            frame = self.extract_clip_frame(clip_path)
            if not frame:
                return {
                    "aprovado": True,
                    "descartar_video_inteiro": False,
                    "score": 7.0,
                    "motivo": "Aprovado por pré-filtro de título",
                    "elementos_detectados": "Vídeo"
                }

            prompt_text = (
                f"Avalie a qualidade e pertinência deste recorte para o documentário (POLÍTICA ZERO ROSTOS & EARLY-DISCARD).\n"
                f"TEMA GLOBAL DO MISTÉRIO: '{global_topic}'\n"
                f"TÍTULO DO VÍDEO NO YOUTUBE: '{video_title}'\n"
                f"FALA DA CENA: '{scene_fala}'\n\n"
                f"SE HOUVER QUALQUER ROSTO HUMANO/APRESENTADOR EM PRIMEIRO PLANO, REPROVE IMEDIATAMENTE (score 1.0). "
                f"Se o vídeo for fora do tema (tutorial de software/GoPro, gameplay de jogo, vlog pessoal, desenho animado), marque 'descartar_video_inteiro: true'. "
                f"O clipe mostra com boa qualidade filmagem de arquivo, satélite, mapa, natureza extrema, documento ou reconstituição de '{global_topic}' sem apresentadores visíveis?"
            )

            contents = [prompt_text, frame]

            try:
                raw_json = generate_multimodal_with_resilience(
                    contents=contents,
                    system_instruction=self.system_instruction,
                    model_name=self.model_name,
                    fallback_models=self.fallback_models,
                    auto_fallback=self.auto_fallback,
                    auto_cooldown=self.auto_cooldown,
                    response_mime_type="application/json",
                    timeout_seconds=60.0,
                    api_key=self.api_key
                )
                result = json.loads(raw_json)
                
                if "descartar_video_inteiro" not in result:
                    motivo_low = result.get("motivo", "").lower()
                    is_irrelevant = any(kw in motivo_low for kw in [
                        "desalinhado", "irrelevante", "gameplay", "vlog", "fofoca",
                        "desconectad", "drone", "gopro", "tutorial", "estático",
                        "gráfico", "software", "sem relação", "incompatível"
                    ])
                    result["descartar_video_inteiro"] = (not result.get("aprovado", False)) and (result.get("score", 10.0) <= 3.0 or is_irrelevant)

                app_logger.info(
                    f"[ReviewerAgent] Parecer do trecho '{video_title}': "
                    f"Aprovado={result.get('aprovado')} (Descartar={result.get('descartar_video_inteiro')}, "
                    f"Nota {result.get('score')}/10) - {result.get('motivo')}"
                )
                return result
            except Exception as e:
                app_logger.warning(f"[ReviewerAgent] Timeout/Erro na visão ({str(e)}). Usando aprovação por pré-filtro.")
                return {
                    "aprovado": True,
                    "descartar_video_inteiro": False,
                    "score": 7.5,
                    "motivo": "Aprovado por título e contingência",
                    "elementos_detectados": "Arquivo / Documentário"
                }

CoderAgent = DirectorAgent
