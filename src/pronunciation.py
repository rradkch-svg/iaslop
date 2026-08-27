"""
Módulo de Pronúncia e Léxico Fonético Especializado para o Minuto Inexplicável.
Converte termos em inglês, nomes próprios estrangeiros, projetos militares, locais remotos,
anomalias científicas e jargões para grafias fonéticas adaptadas ao Edge-TTS (pt-BR)
para uma narração 100% fluida e natural, enquanto preserva a grafia original para as legendas ASS.
"""

import re
from typing import Dict, List, Tuple, Any, Optional

# Dicionário mestre de substituição fonética para TTS em Português Brasileiro (pt-BR)
# Mapeia termos estrangeiros, nomes de mistérios, projetos e siglas para grafia fonética pt-BR
MYSTERY_PHONETIC_LEXICON: Dict[str, str] = {
    # -------------------------------------------------------------------------
    # Projetos Secretos, Expedições e Mistérios Históricos
    # -------------------------------------------------------------------------
    "camp century": "Kemp Sênturi",
    "century": "Sênturi",
    "dyatlov": "Di-át-lov",
    "passo dyatlov": "Passo Di-át-lov",
    "derinkuyu": "De-rin-cú-iu",
    "kola": "Có-la",
    "poço de kola": "Poço de Có-la",
    "bloop": "Blúp",
    "the bloop": "Dâ Blúp",
    "duga": "Dú-ga",
    "duga-3": "Dú-ga Três",
    "woodpecker": "Uud-pé-quer",
    "russian woodpecker": "Râshian Uud-pé-quer",
    "wow!": "Uáu",
    "sinal wow": "Sinal Uáu",
    "sinal wow!": "Sinal Uáu",
    "tunguska": "Tun-gús-ka",
    "voynich": "Vói-nitch",
    "manuscrito voynich": "Manuscrito Vói-nitch",
    "mkultra": "Eme-Ká-Ultra",
    "mk ultra": "Eme-Ká-Ultra",
    "mk-ultra": "Eme-Ká-Ultra",
    "project mkultra": "Projeto Eme-Ká-Ultra",
    "gobekli tepe": "Gue-béc-li Tê-pê",
    "göbekli tepe": "Gue-béc-li Tê-pê",
    "gobekli": "Gue-béc-li",
    "tepe": "Tê-pê",
    "yonaguni": "Iô-na-gú-ni",
    "roanoke": "Rô-a-nôuc",
    "flannan": "Flá-nan",
    "bouvet": "Bu-vê",
    "ilha bouvet": "Ilha Bu-vê",
    "sargasso": "Sar-gás-so",
    "habbakuk": "Ha-bá-kuk",
    "projeto habbakuk": "Projeto Ha-bá-kuk",
    "pykrete": "Pái-crit",
    "montauk": "Mon-tóck",
    "filadelfia": "Fila-délfia",
    "philadelphia": "Fila-délfia",
    "nan madol": "Nan Ma-dól",
    "antikythera": "An-ti-ki-tê-ra",
    "anticitera": "An-ti-ci-tê-ra",
    "oumuamua": "Ou-mua-múa",
    "'oumuamua": "Ou-mua-múa",
    "1i/'oumuamua": "Um I Ou-mua-múa",
    "kic 8462852": "Ká-I-Cê Oito Quatro Meia Dois Oito Cinco Dois",
    "tabby": "Té-bi",
    "estrela de tabby": "Estrela de Té-bi",
    "proxima centauri": "Próxima Sen-táu-ri",
    "movile": "Mo-ví-le",
    "caverna de movile": "Caverna de Mo-ví-le",
    "cicada 3301": "Si-cêi-da Trinta e Três Zero Um",
    "cicada": "Si-cêi-da",
    "shugborough": "Chág-bo-ro",
    "inscricao de shugborough": "Inscrição de Chág-bo-ro",
    "taos": "Tá-os",
    "taos hum": "Tá-os Râm",
    "hum": "Râm",
    "the hum": "Dâ Râm",
    "skinwalker": "Iskin-uól-quer",
    "skinwalker ranch": "Rancho Iskin-uól-quer",
    "rendlesham": "Rên-del-cham",
    "area 51": "Área Cinquenta e Um",
    "dulce": "Dúl-ce",
    "cheyenne": "Xái-en",
    "cheyenne mountain": "Montanha Xái-en",
    "diefenbunker": "Dí-fen-bân-quer",
    "balaklava": "Ba-la-clá-va",
    "riese": "Rí-ze",
    "complexo riese": "Complexo Rí-ze",
    "erebus": "É-re-bus",
    "hms erebus": "Aga-Eme-Esse É-re-bus",
    "hms terror": "Aga-Eme-Esse Té-rror",
    "wilkes": "Uíl-kes",
    "terra de wilkes": "Terra de Uíl-kes",
    "mirny": "Mír-ni",
    "mina de mirny": "Mina de Mír-ni",
    "challenger deep": "Tchá-len-djer Díp",
    "marianas": "Ma-ri-a-nas",
    "fossa das marianas": "Fossa das Ma-ri-a-nas",
    "mary celeste": "Méri Se-lést",

    # -------------------------------------------------------------------------
    # Termos Científicos, Geopolíticos e Astronômicos em Inglês
    # -------------------------------------------------------------------------
    "deep web": "Díp Uéb",
    "dark web": "Dárk Uéb",
    "black project": "Blék Pródjéct",
    "black projects": "Blék Pródjécts",
    "black budget": "Blék Bâ-djet",
    "top secret": "Tóp Sí-cret",
    "classified": "Clas-si-fáid",
    "declassified": "De-clas-si-fáid",
    "b-roll": "Bi-Rôul",
    "broll": "Bi-Rôul",
    "found footage": "Fáund Fú-tedj",
    "sonar": "So-nár",
    "radar": "Ra-dár",
    "hydrophone": "Raidro-fôun",
    "hydrophones": "Raidro-fôuns",
    "black box": "Blék Bóks",
    "unidentified": "An-aidenti-fáid",
    "ufo": "U-Éfe-Ó",
    "uap": "U-A-Pê",
    "usaf": "U-Esse-A-Éfe",
    "cia": "Cê-I-Á",
    "fbi": "Éfe-Bê-I",
    "kgb": "Ká-Gê-Bê",
    "nasa": "Nása",
    "darpa": "Dár-pa",
    "pentagon": "Pên-ta-gon",
    "pentagono": "Pen-tá-gono",
    "lockheed": "Lók-rid",
    "skunk works": "Iscânc Uôrks",
    "boeing": "Bô-ing",
    "northrop": "Nór-trop",
    "blackbird": "Blék-bârd",
    "sr-71": "Esse-Érre Setenta e Um",
    "u-2": "U-Dois",
    "b-2": "Bê-Dois",
    "b-52": "Bê Cinquenta e Dois",
    "f-117": "Éfe Cento e Dezessete",
    "f-22": "Éfe Vinte e Dois",
    "f-35": "Éfe Trinta e Cinco",

    # -------------------------------------------------------------------------
    # Termos Técnicos, Físicos e Militares
    # -------------------------------------------------------------------------
    "cockpit": "Cók-pit",
    "payload": "Pêi-lôud",
    "thrust": "Trâst",
    "mach": "Mác",
    "mach 1": "Mác Um",
    "mach 2": "Mác Dois",
    "mach 3": "Mác Três",
    "hypersonic": "Raiper-sônic",
    "stealth": "Istélf",
    "fallout": "Fó-laut",
    "bunker": "Bân-quer",
    "bunkers": "Bân-quers",
    "silo": "Sí-lo",
    "silos": "Sí-los",
    "icbm": "I-Cê-Bê-Eme",
    "megaton": "Mé-ga-ton",
    "megatons": "Mé-ga-tons",
    "kiloton": "Quí-lo-ton",
    "kilotons": "Quí-lo-tons",
    "geiger": "Gái-guer",
    "contador geiger": "Contador Gái-guer",
    "half-life": "Rélf-Láif",
    "iceberg": "Áis-bêrg",
    "permafrost": "Pêr-ma-fróst",
    "drill": "Dríl",
    "borehole": "Bór-rôul",
    "deep sea": "Díp Sí",
    "abyss": "A-bís",
    "frequency": "Fri-quên-si",
    "infrasound": "Infra-saund",
    "infrasom": "Infra-som",
    "hertz": "Rérts",
    "gigahertz": "Giga-rérts",
    "megahertz": "Mega-rérts",
    "kilohertz": "Quilo-rérts"
}

class PronunciationEngine:
    """
    Motor de Pronúncia Fonética Adaptada para Narração Neural Edge-TTS (pt-BR).
    Aplica substituições fonéticas no texto falado (TTS) sem alterar o texto original exibido nas legendas ASS.
    """

    def __init__(self, custom_lexicon: Optional[Dict[str, str]] = None):
        self.lexicon: Dict[str, str] = dict(MYSTERY_PHONETIC_LEXICON)
        if custom_lexicon:
            self.lexicon.update(custom_lexicon)
        self._compile_regexes()

    def _compile_regexes(self):
        """Compila expressões regulares ordenadas pelo tamanho decrescente das chaves para substituição segura."""
        sorted_keys = sorted(self.lexicon.keys(), key=lambda k: len(k), reverse=True)
        self.compiled_rules: List[Tuple[re.Pattern, str]] = []
        for term in sorted_keys:
            replacement = self.lexicon[term]
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            self.compiled_rules.append((pattern, replacement))

    def add_custom_rule(self, term: str, phonetic_spelling: str):
        """Adiciona ou substitui dinamicamente uma regra no léxico fonético."""
        self.lexicon[term.strip().lower()] = phonetic_spelling.strip()
        self._compile_regexes()

    def get_lexicon(self) -> Dict[str, str]:
        """Retorna uma cópia do léxico fonético ativo."""
        return dict(self.lexicon)

    def apply_pronunciation_to_text(self, text: str) -> str:
        """
        Aplica o léxico fonético a uma string de texto para preparar a síntese por voz.
        Preserva a pontuação, pausas e caixa alta contextual.
        """
        if not text or not text.strip():
            return text

        result = text

        # 1. Substituição pelo léxico compilado
        for pattern, replacement in self.compiled_rules:
            def _replace_match(match):
                matched_str = match.group(0)
                if matched_str.isupper() and len(matched_str) > 1:
                    return replacement.upper()
                elif matched_str[0].isupper():
                    return replacement[0].upper() + replacement[1:] if len(replacement) > 1 else replacement.upper()
                return replacement

            result = pattern.sub(_replace_match, result)

        # 2. Ajustes fonéticos de unidades científicas e anos
        result = re.sub(r"\b(\d+)\s*km\b", r"\1 quilômetros", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(\d+)\s*m\b", r"\1 metros", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(\d+)\s*hz\b", r"\1 hérts", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(\d+)\s*khz\b", r"\1 quilo-hérts", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(\d+)\s*mhz\b", r"\1 mega-hérts", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(\d+)\s*ghz\b", r"\1 giga-hérts", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(\d+)\s*rpm\b", r"\1 érre-pê-eme", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(\d+)\s*psi\b", r"\1 pê-esse-i", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(\d+)\s*bar\b", r"\1 bar", result, flags=re.IGNORECASE)

        return result

# Instância padrão global para reutilização
DEFAULT_PRONUNCIATION_ENGINE = PronunciationEngine()
