"""
Módulo de Deduplicação Heurística de Contexto e Sanitização de Títulos para o Minuto Inexplicável.
Garante:
1. Títulos com teto estrito de 100 caracteres (<= 100 dígitos).
2. Remoção absoluta de sufixos clichês como '| Segredos da Engenharia' ou '| Mistérios'.
3. Detecção heurística de duplicatas contextuais (mesmo enigma + mesmo domínio investigativo/científico),
   impedindo a repetição de assuntos mesmo quando os títulos são formulados com palavras completamente distintas.
"""

import re
import difflib
from typing import Dict, Any, List, Set, Tuple, Optional, Union

# Dicionário de taxonomia de domínios investigativos, científicos e históricos do Minuto Inexplicável
TECHNICAL_DOMAINS: Dict[str, List[str]] = {
    "BASES_SUBTERRANEAS_MILITARES": [
        "base subterranea", "bunker", "cheyenne mountain", "dulce", "area 51", "s4",
        "instalacao militar", "silo nuclear", "complexo raven rock", "monte yamantau",
        "tuneis secretos", "dumbs", " abrigo antinuclear", "base secreta"
    ],
    "PROJETOS_SECRETOS_GUERRA_FRIA": [
        "projeto iceworm", "camp century", "mkultra", "projeto manhattan", "operacao starfish prime",
        "projeto blue beam", "projeto stargate", "operacao paperclip", "projeto mohole", "projeto plowshare",
        "guerra fria", "desclassificado", "documento secreto", "cia", "kgb", "pentagono", "darpa"
    ],
    "ANOMALIAS_OCEANICAS_ABISSAIS": [
        "fossa das marianas", "bloop", "julia", "upsweep", "anomalia do baltico", "triangulo das bermudas",
        "triangulo do dragao", "mar das sargacos", "sonar", "hidrofone", "noaa", "abissal", "dorsal mesoatlantica",
        "sosus", "sonar passivo", "ponto nemo"
    ],
    "ANOMALIAS_ESPACIAIS_COSMICAS": [
        "sinal wow", "estrela de tabby", "oumuamua", "fast radio burst", "frb", "transiente lunar",
        "anomalia da pioneira", "buraco negro", "esfera de dyson", "pulsar", "telescopio james webb",
        "radioastronomia", "setio", "deep space network", "voo apollo"
    ],
    "ENIGMAS_HISTORICOS_EXPEDICOES": [
        "passo dyatlov", "incidente dyatlov", "colonia de roanoke", "expedicao franklin", "mary celeste",
        "manuscrito voynich", "mecanismo de anticiterra", "gobekli tepe", "derinkuyu", "ilha de páscoa",
        "linhas de nazca", "tumba de tutancamon", "arca da alianca", "ouro de yamashita", "oak island"
    ],
    "FENOMENOS_ELETROMAGNETICOS_RADAR": [
        "haarp", "experimento filadelfia", "radar oltre-horizonte", "duga", "the woodpecker", "estacao de numeros",
        "uvb-76", "the buzzer", "pulso eletromagnetico", "emp", "tempestade solar carrington", "aurora anomala",
        "gaiola de faraday", "efeito hutchison"
    ],
    "EXPERIMENTOS_NUCLEARES_CIENTIFICOS": [
        "poco superprofundo de kola", "chernobyl", "reator de oklo", "demon core", "nucleo do demonio",
        "tokamak", "cern", "lhc", "boson de higgs", "acelerador de particulas", "bomba tsar", "fusao nuclear",
        "radioatividade", "isótopos"
    ],
    "CRIPTOZOOLOGIA_E_EXTINCAO": [
        "celacanto", "lula gigante", "megalodon", "thylacine", "tigre da tasmania", "mamute lanoso",
        "homo floresiensis", "crânio de paracas", "gigantopithecus"
    ]
}

# Stopwords em português e termos vazios para filtragem contextual
STOPWORDS_PT: Set[str] = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "da", "do", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "como", "que", "se", "seu", "sua", "seus", "suas",
    "ao", "aos", "pelo", "pela", "pelos", "pelas", "sem", "sob", "sobre",
    "e", "ou", "mas", "porque", "por que", "qual", "quais", "quem",
    "misterio", "misterios", "segredo", "segredos", "inexplicavel", "inexplicaveis",
    "desclassificado", "documentos", "arquivo", "arquivos", "revelado", "descoberta",
    "insana", "insano", "brutal", "incrivel", "chocante", "assustador",
    "tudo", "nada", "mais", "menos", "muito", "pouco", "este", "esta", "esse", "essa"
}

# Sufixos e clichês proibidos em títulos
FORBIDDEN_TITLE_PATTERNS: List[str] = [
    r"\|\s*Segredos?\s+da\s+Engenharia\b",
    r"-\s*Segredos?\s+da\s+Engenharia\b",
    r"\|\s*Minuto\s+Inexplic[aá]vel\b",
    r"-\s*Minuto\s+Inexplic[aá]vel\b",
    r"\|\s*Mist[eé]rios?\s+do\s+Mundo\b",
    r"\|\s*AI\s+Slop\b",
    r"🔮\s*",
    r"🛸\s*",
    r"🔥\s*",
    r"⚡\s*"
]

def sanitize_and_cap_title(title: str, max_length: int = 100) -> str:
    """
    Limpa sufixos de clichês (ex: '| Minuto Inexplicável', emojis prefixados)
    e garante que o título do vídeo NUNCA tenha mais de max_length caracteres (padrão 100).
    Realiza quebra elegante na última palavra para nunca cortar letras no meio.
    """
    if not title:
        return ""

    cleaned = str(title).strip()

    # 1. Remove sufixos e prefixos proibidos
    for pattern in FORBIDDEN_TITLE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Normaliza pontuações soltas e espaços múltiplos
    cleaned = re.sub(r"\s*\|\s*$", "", cleaned)
    cleaned = re.sub(r"\s*-\s*$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 3. Teto estrito de 100 caracteres com truncamento em limite de palavra
    if len(cleaned) > max_length:
        truncated = cleaned[:max_length].strip()
        last_space = truncated.rfind(" ")
        if last_space > int(max_length * 0.70):
            cleaned = truncated[:last_space].rstrip(",;:-. ")
        else:
            cleaned = truncated.rstrip(",;:-. ")

    return cleaned

def extract_canonical_entity(text: str) -> str:
    """
    Extrai e normaliza a entidade ou mistério central,
    removendo adjetivação e chamadas introdutórias.
    """
    if not text:
        return ""
    
    parts = text.split(":")
    main_part = parts[0] if len(parts) > 1 else text
    
    # Remove chamadas iniciais sensacionalistas
    cleaned = re.sub(
        r"^(O Mistério d[oa]|O Segredo d[oa]|O Que Aconteceu n[oa]|O Enigma d[oa]|O Incidente d[oa]|A Verdade Sobre [oa]|O Projeto Secreto d[oa]|A Descoberta n[oa]|O Experimento Secreto d[oa]|A Base Secreta d[oa]|O Arquivo Desclassificado d[oa]|O Fenômeno d[oa]|A Anomalia d[oa]|O Sinal d[oa])\s*",
        "", main_part, flags=re.IGNORECASE
    )
    
    cleaned = re.sub(r"[^\w\s\-\.]", " ", cleaned)
    cleaned = re.sub(r"\b(e seu|e sua|no|na|com|de|da|do|dos|das|para|sobre|o|a|os|as|que|por|ser|bom|demais)\b", " ", cleaned, flags=re.IGNORECASE)
    
    words = [w.strip() for w in cleaned.split() if w.strip()]
    return " ".join(words[:6]).strip() if words else text.strip()

def classify_technical_domains(text: str) -> List[str]:
    """
    Identifica quais domínios investigativos e científicos estão presentes no texto.
    """
    t_low = text.lower()
    matched_domains = []
    for domain, keywords in TECHNICAL_DOMAINS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", t_low):
                if domain not in matched_domains:
                    matched_domains.append(domain)
                break
    return matched_domains

def extract_semantic_stems(text: str) -> Set[str]:
    """
    Extrai o conjunto de tokens conceituais significativos (sem stopwords e com mais de 2 letras).
    """
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [w.strip() for w in clean.split() if len(w.strip()) > 2]
    return {w for w in tokens if w not in STOPWORDS_PT}

class ContextualTopicAuditor:
    """
    Motor Heurístico de Auditoria e Deduplicação Contextual.
    Compara o candidato com a base histórica de vídeos já produzidos sob 4 dimensões:
    1. Entidade / Enigma Central (mesmo caso ou variação direta).
    2. Domínio Investigativo / Científico (mesma categoria temática).
    3. Sobreposição Semântica de Fatos e Evidências (Jaccard de Stems).
    4. Proximidade Estrutural e Textual (difflib SequenceMatcher).
    """

    def __init__(self, entity_sim_threshold: float = 0.70, text_sim_threshold: float = 0.65):
        self.entity_sim_threshold = entity_sim_threshold
        self.text_sim_threshold = text_sim_threshold

    def evaluate_candidate(
        self,
        candidate_topic: Union[str, Dict[str, Any]],
        existing_items: List[Dict[str, Any]]
    ) -> Tuple[bool, float, str]:
        """
        Avalia se o tema candidato é uma repetição de assunto em relação aos itens existentes.
        
        Retorna:
        - `is_duplicate` (bool): True se for duplicata contextual, False se for inédito.
        - `confidence` (float): Nível de confiança da detecção (0.0 a 1.0).
        - `reason` (str): Justificativa técnica e detalhada para rejeição ou aprovação.
        """
        if not candidate_topic:
            return False, 0.0, "Tema vazio"

        cand_title = candidate_topic.get("tema") if isinstance(candidate_topic, dict) else str(candidate_topic)
        cand_title = sanitize_and_cap_title(cand_title)
        cand_hook = candidate_topic.get("hook", "") if isinstance(candidate_topic, dict) else ""
        cand_tech = candidate_topic.get("explicacao_tecnica", "") or candidate_topic.get("evidencias_e_fatos", "") if isinstance(candidate_topic, dict) else ""
        
        cand_full_text = f"{cand_title} {cand_hook} {cand_tech}".strip()
        cand_entity = extract_canonical_entity(cand_title)
        cand_domains = classify_technical_domains(cand_full_text)
        cand_stems = extract_semantic_stems(cand_full_text)
        cand_entity_stems = extract_semantic_stems(cand_entity)

        for existing in existing_items:
            ex_title = existing.get("tema") or existing.get("titulo") or ""
            ex_title = sanitize_and_cap_title(ex_title)
            ex_hook = existing.get("hook", "")
            ex_tech = existing.get("explicacao_tecnica") or existing.get("dissertacao_resumo") or existing.get("evidencias_e_fatos", "")
            ex_full_text = f"{ex_title} {ex_hook} {ex_tech}".strip()
            
            ex_entity = existing.get("core_entity") or extract_canonical_entity(ex_title)
            ex_domains = classify_technical_domains(ex_full_text)
            ex_stems = extract_semantic_stems(ex_full_text)
            ex_entity_stems = extract_semantic_stems(ex_entity)

            # 1. Similaridade Textual Direta (difflib)
            text_sim = difflib.SequenceMatcher(None, cand_title.lower(), ex_title.lower()).ratio()
            if text_sim >= self.text_sim_threshold:
                return (
                    True,
                    text_sim,
                    f"Título textualmente muito similar ({text_sim:.0%}) ao vídeo já gravado '{ex_title}'"
                )

            # 2. Avaliação de Entidade Central
            entity_jaccard = 0.0
            if cand_entity_stems and ex_entity_stems:
                entity_overlap = cand_entity_stems.intersection(ex_entity_stems)
                entity_union = cand_entity_stems.union(ex_entity_stems)
                entity_jaccard = len(entity_overlap) / len(entity_union) if entity_union else 0.0

            entity_str_sim = difflib.SequenceMatcher(None, cand_entity.lower(), ex_entity.lower()).ratio()
            same_entity = (
                entity_jaccard >= self.entity_sim_threshold or
                entity_str_sim >= 0.78 or
                (len(cand_entity) >= 4 and cand_entity.lower() in ex_title.lower()) or
                (len(ex_entity) >= 4 and ex_entity.lower() in cand_title.lower())
            )

            # 3. Se for a mesma entidade / mistério:
            if same_entity:
                domain_overlap = set(cand_domains).intersection(set(ex_domains))
                if domain_overlap:
                    domain_names = ", ".join(list(domain_overlap))
                    return (
                        True,
                        0.95,
                        f"O mistério/entidade '{cand_entity}' já possui vídeo abordando o domínio [{domain_names}] em '{ex_title}'"
                    )

                stem_overlap = cand_stems.intersection(ex_stems) - cand_entity_stems
                if len(stem_overlap) >= 3:
                    overlap_words = ", ".join(list(stem_overlap)[:4])
                    return (
                        True,
                        0.90,
                        f"O caso '{cand_entity}' já foi abordado com termos análogos ({overlap_words}) em '{ex_title}'"
                    )

                if len(cand_entity_stems) >= 2 and entity_jaccard >= 0.85:
                    return (
                        True,
                        0.85,
                        f"Caso '{cand_entity}' já foi protagonista do vídeo '{ex_title}'"
                    )

            # 4. Caso os títulos sejam semanticamente quase idênticos
            stems_intersection = cand_stems.intersection(ex_stems)
            stems_union = cand_stems.union(ex_stems)
            jaccard_global = len(stems_intersection) / len(stems_union) if stems_union else 0.0
            if jaccard_global >= 0.65:
                return (
                    True,
                    jaccard_global,
                    f"Alta sobreposição temática e semântica ({jaccard_global:.0%}) com o vídeo '{ex_title}'"
                )

        return False, 0.0, "Tema 100% inédito e aprovado"

DEFAULT_CONTEXTUAL_AUDITOR = ContextualTopicAuditor()
