"""
Módulo de Música de Fundo (BGM) Sem Copyright e Ambiência de Suspense.
Fornece banco de trilhas sonoras de suspense, dark ambient, drones investigativos e tensão documental.
Permite seleção randômica, correspondência temática por palavras-chave e download dinâmico de trilhas royalty-free.
"""

import os
import re
import glob
import random
import wave
import subprocess
import numpy as np
from typing import Optional, List, Dict, Tuple, Any

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BGM_DIR = os.path.join(PROJECT_ROOT, "assets", "audio", "bgm")
os.makedirs(BGM_DIR, exist_ok=True)

# Mapeamento de perfis sonoros de suspense por categoria temática
BGM_THEME_PROFILES: Dict[str, Dict[str, Any]] = {
    "abyss_oceanic": {
        "filename": "suspense_abyss_oceanic.wav",
        "description": "Sub-drone profundo e pulso subaquático (estilo Fossa das Marianas, Bloop e Mar dos Sargaços).",
        "base_freq": 48.0,
        "detune_freq": 47.6,
        "harmonic_freq": 57.08, # Eb1
        "keywords": ["oceano", "mar", "marianas", "bloop", "agua", "submarino", "fossa", "profundo", "sargaco", "abismo"]
    },
    "cold_war_classified": {
        "filename": "suspense_cold_war_classified.wav",
        "description": "Tensão documental militar e bunker subterrâneo (estilo Camp Century, Guerra Fria e Duga).",
        "base_freq": 55.0, # A1
        "detune_freq": 54.4,
        "harmonic_freq": 65.41, # C2
        "keywords": ["nuclear", "militar", "gelo", "groenlandia", "urss", "soviético", "duga", "bunker", "guerra", "century", "secreto", "icbm"]
    },
    "cosmic_space_anomaly": {
        "filename": "suspense_cosmic_space_anomaly.wav",
        "description": "Ambiência etérea, ressonância e mistério astronômico (estilo Sinal Wow, Oumuamua e KIC).",
        "base_freq": 65.41, # C2
        "detune_freq": 65.0,
        "harmonic_freq": 77.78, # Eb2
        "keywords": ["espaco", "sinal", "wow", "estrela", "universo", "oumuamua", "astronomia", "radio", "telescopio", "planeta", "alien"]
    },
    "ancient_underground": {
        "filename": "suspense_ancient_underground.wav",
        "description": "Atmosfera sombria de arqueologia proibida e catacumbas (estilo Derinkuyu, Voynich e Göbekli Tepe).",
        "base_freq": 43.65, # F1
        "detune_freq": 43.2,
        "harmonic_freq": 51.91, # Ab1
        "keywords": ["derinkuyu", "caverna", "subterraneo", "turquia", "antigo", "arqueologia", "voynich", "gobekli", "manuscrito", "piramide"]
    },
    "arctic_isolation_dyatlov": {
        "filename": "suspense_arctic_isolation_dyatlov.wav",
        "description": "Vento gélido, isolamento polar e mistério insolúvel (estilo Passo Dyatlov e Expedições Árticas).",
        "base_freq": 58.27, # Bb1
        "detune_freq": 57.8,
        "harmonic_freq": 69.30, # Db2
        "keywords": ["dyatlov", "neve", "ural", "montanha", "alpinistas", "frio", "artico", "expedicao", "flannan", "bouvet"]
    }
}

class BGMEngine:
    """
    Motor de Gerenciamento e Síntese de Música de Fundo (BGM) Royalty-Free para o Minuto Inexplicável.
    Garante trilhas de alta qualidade de suspense com volume reduzido (ducking) e sem risco de copyright.
    """

    def __init__(self, bgm_dir: Optional[str] = None):
        self.bgm_dir = os.path.abspath(bgm_dir or BGM_DIR)
        os.makedirs(self.bgm_dir, exist_ok=True)
        self._ensure_soundbank()

    def _ensure_soundbank(self):
        """Inicializa e sintetiza os arquivos de áudio padrão do soundbank de suspense caso não existam."""
        for key, profile in BGM_THEME_PROFILES.items():
            track_path = os.path.join(self.bgm_dir, profile["filename"])
            if not os.path.exists(track_path) or os.path.getsize(track_path) < 1000:
                self._synthesize_suspense_drone(
                    output_wav=track_path,
                    base_freq=profile["base_freq"],
                    detune_freq=profile["detune_freq"],
                    harmonic_freq=profile["harmonic_freq"],
                    duration_sec=120.0
                )

    def _synthesize_suspense_drone(
        self,
        output_wav: str,
        base_freq: float = 55.0,
        detune_freq: float = 54.5,
        harmonic_freq: float = 65.41,
        duration_sec: float = 120.0,
        sample_rate: int = 44100
    ) -> str:
        """
        Sintetiza proceduralmente uma trilha de suspense/dark ambient cinematográfico de 120s
        utilizando osciladores de sub-grave, batimento de fase (detuning), harmônicos menores e ruído textural.
        Garante 100% royalty-free sem risco de ContentID ou copyright do YouTube.
        """
        total_samples = int(sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, total_samples, False)

        # 1. Sub-grave primário (oscilador senoidal puro)
        sub_osc = 0.50 * np.sin(2 * np.pi * base_freq * t)

        # 2. Batimento de fase / pulso binaural lento (detuning sutil para criar tensão)
        detune_osc = 0.35 * np.sin(2 * np.pi * detune_freq * t)

        # 3. Harmônico menor de suspense com modulação LFO lenta de amplitude
        lfo_speed = 0.08 # ciclo de 12.5s
        lfo_amp = 0.5 * (1.0 + np.sin(2 * np.pi * lfo_speed * t))
        harmonic_osc = 0.25 * np.sin(2 * np.pi * harmonic_freq * t) * lfo_amp

        # 4. Quinto grau diminuto (trítono / tensão instigante)
        tritone_freq = base_freq * 1.4142
        tritone_osc = 0.12 * np.sin(2 * np.pi * tritone_freq * t) * (1.0 - lfo_amp)

        # 5. Textura de ruído rosa filtrado (ambiência de fita analógica e reverberação escura)
        noise = np.random.normal(0, 0.04, total_samples)
        # Filtro passa-baixas simples (moving average)
        filter_window = 60
        noise_filtered = np.convolve(noise, np.ones(filter_window)/filter_window, mode='same')

        # 6. Mixagem e normalização
        combined = sub_osc + detune_osc + harmonic_osc + tritone_osc + noise_filtered
        max_val = np.max(np.abs(combined))
        if max_val > 0:
            combined = combined / max_val * 0.85

        # 7. Fade-in e Fade-out suaves
        fade_samples = int(sample_rate * 3.0)
        fade_in = np.linspace(0.0, 1.0, fade_samples)
        fade_out = np.linspace(1.0, 0.0, fade_samples)
        combined[:fade_samples] *= fade_in
        combined[-fade_samples:] *= fade_out

        # Conversão para PCM 16-bit
        audio_int16 = (combined * 32767).astype(np.int16)

        # Gravação do arquivo WAV
        with wave.open(output_wav, 'wb') as wf:
            wf.setnchannels(1) # Mono
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())

        app_logger.info(f"[BGMEngine] Trilha de suspense sintetizada: {output_wav} ({duration_sec}s)")
        return output_wav

    def list_available_tracks(self) -> List[Dict[str, Any]]:
        """Retorna todas as faixas de BGM disponíveis no soundbank local."""
        tracks = []
        for file in glob.glob(os.path.join(self.bgm_dir, "*.wav")) + glob.glob(os.path.join(self.bgm_dir, "*.mp3")):
            fn = os.path.basename(file)
            tracks.append({
                "filename": fn,
                "path": file,
                "size_kb": os.path.getsize(file) // 1024
            })
        return tracks

    def get_bgm_for_topic(self, topic_title: str = "", topic_context: str = "") -> str:
        """
        Seleciona de forma inteligente a melhor trilha de BGM de suspense com base nas palavras-chave do tema,
        ou escolhe aleatoriamente se nenhuma categoria específica for detectada.
        """
        full_text = f"{topic_title} {topic_context}".lower()

        # Verifica pontuação de relevância em cada perfil temático
        best_profile = None
        highest_score = 0

        for key, profile in BGM_THEME_PROFILES.items():
            score = 0
            for kw in profile.get("keywords", []):
                if kw in full_text:
                    score += 1
            if score > highest_score:
                highest_score = score
                best_profile = profile

        if best_profile and highest_score > 0:
            track_path = os.path.join(self.bgm_dir, best_profile["filename"])
            if os.path.exists(track_path):
                app_logger.info(f"[BGMEngine] BGM selecionada por afinidade temática: {best_profile['filename']}")
                return track_path

        # Fallback randômico entre todas as faixas disponíveis
        return self.get_random_bgm()

    def get_random_bgm(self) -> str:
        """Retorna aleatoriamente uma trilha de BGM do soundbank."""
        available = glob.glob(os.path.join(self.bgm_dir, "*.wav")) + glob.glob(os.path.join(self.bgm_dir, "*.mp3"))
        if available:
            chosen = random.choice(available)
            app_logger.info(f"[BGMEngine] BGM selecionada aleatoriamente: {os.path.basename(chosen)}")
            return chosen
        
        # Se nenhuma existir, gera a padrão
        default_path = os.path.join(self.bgm_dir, "suspense_cold_war_classified.wav")
        return self._synthesize_suspense_drone(default_path)

    def fetch_online_royalty_free_bgm(self, query: str = "dark ambient suspense investigation background music no copyright") -> Optional[str]:
        """
        Busca e baixa do YouTube uma faixa de áudio royalty-free via yt-dlp, salvando no soundbank local.
        """
        out_template = os.path.join(self.bgm_dir, "online_bgm_%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "192k",
            "--max-downloads", "1",
            "--default-search", f"ytsearch1:{query}",
            "-o", out_template
        ]
        try:
            app_logger.info(f"[BGMEngine] Buscando BGM royalty-free online: '{query}'...")
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=90)
            
            # Localiza o arquivo baixado
            recent_files = glob.glob(os.path.join(self.bgm_dir, "online_bgm_*.mp3"))
            if recent_files:
                latest = max(recent_files, key=os.path.getctime)
                app_logger.info(f"[BGMEngine] BGM online baixada com sucesso: {latest}")
                return latest
        except Exception as e:
            app_logger.warning(f"[BGMEngine] Falha ao baixar BGM online ({str(e)}). Mantendo trilha do soundbank local.")

        return self.get_random_bgm()

# Instância padrão global
DEFAULT_BGM_ENGINE = BGMEngine()
