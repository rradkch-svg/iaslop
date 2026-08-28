"""
Motor de Síntese Vocal Neural, Prosódia Dinâmica e Tratamento Fonético.
Utiliza Edge-TTS neural (pt-BR) com suporte a presets de prosódia, redundância de vozes
e integração com o Dicionário Fonético para o Minuto Inexplicável.
"""

import os
import re
import asyncio
from typing import List, Dict, Any, Tuple, Optional
import edge_tts

try:
    from .logger import app_logger, LogSpan
    from .pronunciation import PronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE
except ImportError:
    from logger import app_logger, LogSpan
    from pronunciation import PronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE

FALLBACK_VOICES = [
    "pt-BR-AntonioNeural",
    "pt-BR-FranciscaNeural",
    "pt-BR-ThalitaNeural"
]

# Estilos e perfis de dinamismo vocal para o Minuto Inexplicável
VOICE_PROSODY_PRESETS: Dict[str, Dict[str, str]] = {
    "MISTERIO_ENERGICO": {
        "rate": "+25%",
        "pitch": "+3Hz",
        "volume": "+0%",
        "description": "Ritmo acelerado 1.25x com entonação enérgica para retenção máxima em Shorts."
    },
    "SUSPENSE_DOCUMENTARIO": {
        "rate": "+18%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "description": "Cadência firme, analítica e de suspense investigativo para fatos documentados."
    },
    "INVESTIGACAO_URGENTE": {
        "rate": "+30%",
        "pitch": "+5Hz",
        "volume": "+5%",
        "description": "Velocidade máxima e tom vibrante para projetos secretos e desclassificações."
    }
}

class AudioEngine:
    """
    Motor de Síntese Vocal Neural e Dinâmica com Dicionário Fonético Especializado.
    Garante pronúncia correta de termos estrangeiros, nomes de projetos e locais via pt-BR Neural TTS,
    enquanto preserva o texto original para as legendas ASS exibidas na tela.
    """
    def __init__(
        self,
        voice: str = "pt-BR-AntonioNeural",
        rate: str = "+25%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        pronunciation_engine: Optional[PronunciationEngine] = None
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.fallback_voices = [v for v in FALLBACK_VOICES if v != voice]
        self.pronunciation_engine = pronunciation_engine or DEFAULT_PRONUNCIATION_ENGINE

    def _sanitize_text_for_pacing(self, text: str) -> str:
        """
        Limpa marcações markdown e remove pontuações excessivas (ex: reticências longas,
        travessões e quebras duplas) para eliminar pausas mortas e garantir dinâmica ágil.
        """
        clean = text.replace("**", "").replace("*", "").replace("#", "")
        clean = re.sub(r"\.{2,}", ".", clean)
        clean = re.sub(r"\s*—\s*|\s*--\s*", ", ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    async def _generate_async_for_voice(
        self,
        text: str,
        output_mp3: str,
        voice_name: str,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        volume: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        clean_text = self._sanitize_text_for_pacing(text)
        
        # Aplica a adaptação fonética para a fala (TTS)
        spoken_text = self.pronunciation_engine.apply_pronunciation_to_text(clean_text) if self.pronunciation_engine else clean_text

        rate_to_use = rate if rate is not None else self.rate
        pitch_to_use = pitch if pitch is not None else self.pitch
        volume_to_use = volume if volume is not None else self.volume

        communicate = edge_tts.Communicate(
            spoken_text,
            voice_name,
            rate=rate_to_use,
            pitch=pitch_to_use,
            volume=volume_to_use
        )
        
        sentence_boundaries = []
        word_boundaries = []
        raw_audio = bytearray()
        
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                raw_audio.extend(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                start_sec = chunk["offset"] / 10_000_000.0
                duration_sec = chunk["duration"] / 10_000_000.0
                sentence_boundaries.append({
                    "text": chunk["text"],
                    "start": start_sec,
                    "end": start_sec + duration_sec,
                    "duration": duration_sec
                })
            elif chunk["type"] == "WordBoundary":
                start_sec = chunk["offset"] / 10_000_000.0
                duration_sec = chunk["duration"] / 10_000_000.0
                word_boundaries.append({
                    "word": chunk["text"],
                    "start": start_sec,
                    "end": start_sec + duration_sec
                })

        if not raw_audio:
            raise Exception(f"Nenhum byte de áudio retornado pelo serviço Edge-TTS para a voz {voice_name}")

        with open(output_mp3, "wb") as f:
            f.write(raw_audio)

        orig_words = [w.strip() for w in clean_text.split() if w.strip()]

        # Mapeia as palavras do texto original limpo para os tempos capturados via alinhamento fonético
        if word_boundaries:
            if self.pronunciation_engine and hasattr(self.pronunciation_engine, "align_phonetic_timing_to_original"):
                return self.pronunciation_engine.align_phonetic_timing_to_original(clean_text, word_boundaries)
            if len(word_boundaries) == len(orig_words):
                for idx, ow in enumerate(orig_words):
                    word_boundaries[idx]["word"] = ow
            return word_boundaries

        if sentence_boundaries:
            words_timing = []
            for sent in sentence_boundaries:
                s_text = sent["text"]
                s_start = sent["start"]
                s_duration = sent["duration"]
                raw_words = s_text.split()
                if not raw_words:
                    continue

                weights = []
                for w in raw_words:
                    w_len = len(w)
                    if w.endswith((".", "!", "?", ",", ";", ":")):
                        w_len += 2
                    weights.append(max(w_len, 1))

                total_weight = sum(weights)
                current_time = s_start

                for w, weight in zip(raw_words, weights):
                    w_dur = (weight / total_weight) * s_duration
                    w_start = current_time
                    w_end = min(current_time + w_dur, sent["end"])
                    words_timing.append({
                        "word": w.strip(),
                        "start": round(w_start, 3),
                        "end": round(w_end, 3)
                    })
                    current_time = w_end
            
            if self.pronunciation_engine and hasattr(self.pronunciation_engine, "align_phonetic_timing_to_original"):
                return self.pronunciation_engine.align_phonetic_timing_to_original(clean_text, words_timing)

            # Se a quantidade de palavras bater com o texto original, preserva as palavras originais
            if len(words_timing) == len(orig_words):
                for idx, ow in enumerate(orig_words):
                    words_timing[idx]["word"] = ow
            return words_timing

        # Fallback de temporização proporcional
        raw_words = orig_words
        words_timing = []
        curr = 0.0
        for w in raw_words:
            dur = max(len(w) * 0.045, 0.20)
            words_timing.append({
                "word": w,
                "start": round(curr, 3),
                "end": round(curr + dur, 3)
            })
            curr += dur
        return words_timing

    def generate_audio(
        self,
        text: str,
        output_mp3: str,
        output_vtt: str = "",
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        volume: Optional[str] = None
    ) -> Tuple[bool, Any]:
        """
        Gera áudio MP3 com redundância e failover de vozes em caso de queda do servidor,
        aplicando a taxa de aceleração e prosódia configuradas (padrão +25%).
        """
        voices_to_try = [self.voice] + self.fallback_voices
        rate_to_use = rate if rate is not None else self.rate
        pitch_to_use = pitch if pitch is not None else self.pitch
        volume_to_use = volume if volume is not None else self.volume
        
        with LogSpan("AudioEngine.generate_audio", extra={"text_len": len(text), "output": output_mp3, "rate": rate_to_use}):
            for v_name in voices_to_try:
                try:
                    app_logger.info(f"[AudioEngine] Tentando síntese com a voz: {v_name} (taxa: {rate_to_use}, pitch: {pitch_to_use})")
                    words_timing = asyncio.run(
                        self._generate_async_for_voice(
                            text,
                            output_mp3,
                            v_name,
                            rate=rate_to_use,
                            pitch=pitch_to_use,
                            volume=volume_to_use
                        )
                    )
                    app_logger.info(f"[AudioEngine] Síntese concluída com sucesso usando {v_name} ({len(words_timing)} palavras, taxa {rate_to_use}).")
                    return True, words_timing
                except Exception as e:
                    app_logger.warning(f"[AudioEngine] Falha na voz {v_name}: {str(e)}. Tentando próxima voz de fallback...")
            
            err_msg = f"Todas as vozes de TTS ({voices_to_try}) falharam."
            app_logger.error(err_msg)
            return False, err_msg
