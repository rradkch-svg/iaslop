"""
Módulo de Efeitos Sonoros (Sound FX / SFX) e Sincronização Temporal.
Gera e gerencia transições dinâmicas (Whooshes), sinos de mistério/revelação (Bells/Chimes),
clicks de documento/fotografia (Tactile Clicks) e impactos sub-graves (Sub-Hits)
alinhados aos cortes de cena e palavras-chave da narração.
"""

import os
import re
import glob
import wave
import random
import numpy as np
from typing import List, Dict, Any, Optional, Tuple


try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SFX_DIR = os.path.join(PROJECT_ROOT, "assets", "audio", "sfx")
os.makedirs(SFX_DIR, exist_ok=True)

# Palavras-chave que ativam Sound FX especiais de revelação e documento
MYSTERY_TRIGGER_WORDS = {
    "bells": [
        "mistério", "misterioso", "inexplicável", "segredo", "oculto", "revelado",
        "nunca", "desapareceu", "ninguém", "anomalia", "impossível", "descoberta",
        "enigma", "estranho", "bizarro", "sinal", "abismo"
    ],
    "clicks": [
        "documento", "desclassificado", "relatório", "arquivos", "foto", "registro",
        "satélite", "coordenadas", "ano", "militares", "evidência", "dados",
        "oficial", "confidencial", "metros", "quilômetros", "projeto"
    ]
}

class SFXEngine:
    """
    Motor de Gerenciamento, Síntese e Sincronização de Efeitos Sonoros (SFX).
    """

    def __init__(self, sfx_dir: Optional[str] = None):
        self.sfx_dir = os.path.abspath(sfx_dir or SFX_DIR)
        os.makedirs(self.sfx_dir, exist_ok=True)
        self._ensure_soundbank()

    def _ensure_soundbank(self):
        """Inicializa e sintetiza os arquivos de SFX essenciais no soundbank local."""
        sfx_definitions = {
            "whoosh_fast.wav": lambda p: self._synthesize_whoosh(p, duration_sec=0.50, sweep_type="fast"),
            "whoosh_deep.wav": lambda p: self._synthesize_whoosh(p, duration_sec=0.70, sweep_type="deep"),
            "whoosh_riser.wav": lambda p: self._synthesize_whoosh(p, duration_sec=0.85, sweep_type="riser"),
            "bell_mystery_chime.wav": lambda p: self._synthesize_mystery_bell(p, duration_sec=1.8, f0=987.77), # B5
            "bell_deep_toll.wav": lambda p: self._synthesize_mystery_bell(p, duration_sec=2.4, f0=329.63, deep=True), # E4
            "click_mechanical.wav": lambda p: self._synthesize_click(p, duration_sec=0.07, click_type="mechanical"),
            "click_camera_shutter.wav": lambda p: self._synthesize_click(p, duration_sec=0.12, click_type="shutter"),
            "sub_impact_hit.wav": lambda p: self._synthesize_sub_impact(p, duration_sec=1.4)
        }

        for filename, synth_fn in sfx_definitions.items():
            full_path = os.path.join(self.sfx_dir, filename)
            if not os.path.exists(full_path) or os.path.getsize(full_path) < 500:
                try:
                    synth_fn(full_path)
                except Exception as e:
                    app_logger.warning(f"[SFXEngine] Falha ao sintetizar {filename}: {str(e)}")

    def _synthesize_whoosh(self, output_wav: str, duration_sec: float = 0.55, sweep_type: str = "fast", sample_rate: int = 44100) -> str:
        """Sintetiza um efeito de Whoosh/Transição dinâmico com modulação de ruído e sweep de frequência."""
        num_samples = int(sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, num_samples, False)

        noise = np.random.normal(0, 1.0, num_samples)
        
        if sweep_type == "deep":
            env = np.sin(np.pi * (t / duration_sec)) ** 2.5
            freq_sweep = 120 + 600 * np.sin(np.pi * (t / duration_sec))
        elif sweep_type == "riser":
            env = (t / duration_sec) ** 2.0
            freq_sweep = 200 + 1400 * (t / duration_sec)
        else: # fast
            env = np.sin(np.pi * (t / duration_sec)) ** 3.0
            freq_sweep = 250 + 1100 * np.sin(np.pi * (t / duration_sec))

        sine_sweep = np.sin(2 * np.pi * freq_sweep * t) * env
        combined = (noise * env * 0.45) + (sine_sweep * 0.55)
        
        max_val = np.max(np.abs(combined))
        if max_val > 0:
            combined = combined / max_val * 0.85

        self._save_pcm_wav(output_wav, combined, sample_rate)
        return output_wav

    def _synthesize_mystery_bell(self, output_wav: str, duration_sec: float = 1.8, f0: float = 880.0, deep: bool = False, sample_rate: int = 44100) -> str:
        """Sintetiza um sino etéreo/harmônico de mistério com decaimento exponencial."""
        num_samples = int(sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, num_samples, False)

        partials = [
            (f0 * 1.0, 1.0, 3.5 if deep else 4.0),
            (f0 * 1.503, 0.65, 4.5 if deep else 5.5),
            (f0 * 1.998, 0.45, 6.0 if deep else 7.0),
            (f0 * 2.742, 0.30, 7.5 if deep else 8.5),
            (f0 * 3.001, 0.20, 9.0 if deep else 10.0)
        ]

        bell = np.zeros(num_samples)
        for freq, amp, decay in partials:
            bell += amp * np.sin(2 * np.pi * freq * t) * np.exp(-decay * t)

        max_val = np.max(np.abs(bell))
        if max_val > 0:
            bell = bell / max_val * 0.85

        self._save_pcm_wav(output_wav, bell, sample_rate)
        return output_wav

    def _synthesize_click(self, output_wav: str, duration_sec: float = 0.08, click_type: str = "mechanical", sample_rate: int = 44100) -> str:
        """Sintetiza um click mecânico nítido para passagens de documentos ou transições sutis."""
        num_samples = int(sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, num_samples, False)

        if click_type == "shutter":
            click1 = np.sin(2 * np.pi * 3200 * t) * np.exp(-80 * t)
            # Segundo pulso ligeiramente defasado
            offset_s = 0.03
            t_off = np.maximum(0, t - offset_s)
            click2 = np.sin(2 * np.pi * 1800 * t_off) * np.exp(-60 * t_off) * (t >= offset_s)
            click = click1 + 0.7 * click2
        else:
            click = np.sin(2 * np.pi * 2600 * t) * np.exp(-90 * t) + np.random.normal(0, 0.4, num_samples) * np.exp(-110 * t)

        max_val = np.max(np.abs(click))
        if max_val > 0:
            click = click / max_val * 0.85

        self._save_pcm_wav(output_wav, click, sample_rate)
        return output_wav

    def _synthesize_sub_impact(self, output_wav: str, duration_sec: float = 1.4, sample_rate: int = 44100) -> str:
        """Sintetiza um impacto sub-grave pesado para o gancho inicial e momentos de clímax."""
        num_samples = int(sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, num_samples, False)

        # Pitch drop exponencial: 160 Hz descendo para 38 Hz
        pitch_env = 38.0 + 120.0 * np.exp(-8.0 * t)
        phase = 2 * np.pi * np.cumsum(pitch_env) / sample_rate
        sub = np.sin(phase) * np.exp(-3.5 * t)

        # Transiente inicial nítido
        transient = np.sin(2 * np.pi * 800 * t) * np.exp(-40 * t)

        combined = sub * 0.80 + transient * 0.20
        max_val = np.max(np.abs(combined))
        if max_val > 0:
            combined = combined / max_val * 0.85

        self._save_pcm_wav(output_wav, combined, sample_rate)
        return output_wav

    def _save_pcm_wav(self, output_wav: str, audio_data: np.ndarray, sample_rate: int = 44100):
        """Salva array float32/float64 como WAV PCM 16-bit Mono."""
        audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        with wave.open(output_wav, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())

    def detect_sfx_cues(
        self,
        storyboard: List[Dict[str, Any]],
        words_timing: List[Dict[str, Any]],
        total_duration: float,
        enable_whoosh: bool = True,
        enable_bells: bool = True,
        enable_clicks: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Analisa o storyboard e o timing da narração para calcular com precisão de milissegundos
        todos os pontos onde Whooshes, Sinos, Clicks e Sub-Impacts devem ser disparados.
        """
        cues: List[Dict[str, Any]] = []

        # 1. Sub-Impact no primeiro segundo do gancho (t = 0.05s)
        cues.append({
            "type": "sub_impact",
            "file": os.path.join(self.sfx_dir, "sub_impact_hit.wav"),
            "timestamp": 0.05,
            "volume": 0.50
        })

        # 2. Whooshes automáticos nas transições entre cenas
        if enable_whoosh and storyboard and len(storyboard) > 1:
            cum_time = 0.0
            whoosh_files = [
                os.path.join(self.sfx_dir, "whoosh_fast.wav"),
                os.path.join(self.sfx_dir, "whoosh_deep.wav"),
                os.path.join(self.sfx_dir, "whoosh_riser.wav")
            ]
            for idx, sc in enumerate(storyboard):
                sc_dur = float(sc.get("duracao_estimada", 5.0))
                cum_time += sc_dur
                if idx < len(storyboard) - 1 and cum_time < (total_duration - 1.0):
                    # Dispara o whoosh 0.2s antes do corte para criar antecipação cinematográfica
                    t_cue = max(0.0, round(cum_time - 0.20, 2))
                    w_choice = random.choice(whoosh_files)
                    cues.append({
                        "type": "whoosh",
                        "file": w_choice,
                        "timestamp": t_cue,
                        "volume": 0.35
                    })

        # 3. Sinos e Clicks baseados em palavras de mistério e documentos
        if (enable_bells or enable_clicks) and words_timing:
            bell_files = [
                os.path.join(self.sfx_dir, "bell_mystery_chime.wav"),
                os.path.join(self.sfx_dir, "bell_deep_toll.wav")
            ]
            click_files = [
                os.path.join(self.sfx_dir, "click_mechanical.wav"),
                os.path.join(self.sfx_dir, "click_camera_shutter.wav")
            ]

            last_sfx_time = -5.0 # Impede disparos colados

            for w_data in words_timing:
                raw_w = re.sub(r"[^\w]", "", w_data.get("word", "")).lower()
                w_start = float(w_data.get("start", 0.0))

                if (w_start - last_sfx_time) < 4.0:
                    continue # Intervalo mínimo de 4s entre SFX contextuais

                if enable_bells and any(kw in raw_w for kw in MYSTERY_TRIGGER_WORDS["bells"]):
                    cues.append({
                        "type": "bell",
                        "file": random.choice(bell_files),
                        "timestamp": round(w_start, 2),
                        "volume": 0.30
                    })
                    last_sfx_time = w_start

                elif enable_clicks and any(kw in raw_w for kw in MYSTERY_TRIGGER_WORDS["clicks"]):
                    cues.append({
                        "type": "click",
                        "file": random.choice(click_files),
                        "timestamp": round(w_start, 2),
                        "volume": 0.25
                    })
                    last_sfx_time = w_start

        cues.sort(key=lambda x: x["timestamp"])
        app_logger.info(f"[SFXEngine] {len(cues)} pontos de SFX calculados na linha do tempo.")
        return cues

    def build_sfx_audio_track(
        self,
        sfx_cues: List[Dict[str, Any]],
        output_wav: str,
        total_duration: float,
        master_sfx_volume: float = 0.35,
        sample_rate: int = 44100
    ) -> str:
        """
        Monta uma trilha de áudio única contendo todos os efeitos sonoros posicionados
        exatamente nos milissegundos correspondentes da linha do tempo.
        """
        total_samples = int(sample_rate * (total_duration + 2.0))
        timeline = np.zeros(total_samples, dtype=np.float32)

        for cue in sfx_cues:
            f_path = cue.get("file")
            t_sec = float(cue.get("timestamp", 0.0))
            vol = float(cue.get("volume", 0.35)) * master_sfx_volume

            if not f_path or not os.path.exists(f_path):
                continue

            try:
                with wave.open(f_path, 'rb') as wf:
                    n_channels = wf.getnchannels()
                    s_width = wf.getsampwidth()
                    f_rate = wf.getframerate()
                    raw_bytes = wf.readframes(wf.getnframes())

                if s_width == 2:
                    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32767.0
                else:
                    continue

                if n_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)

                start_idx = int(t_sec * sample_rate)
                end_idx = min(start_idx + len(samples), total_samples)
                sample_slice = samples[:(end_idx - start_idx)] * vol

                timeline[start_idx:end_idx] += sample_slice

            except Exception as e:
                app_logger.warning(f"[SFXEngine] Erro ao carregar SFX '{f_path}': {str(e)}")

        # Soft peak limiter para prevenir distorções
        max_peak = np.max(np.abs(timeline))
        if max_peak > 0.95:
            timeline = timeline / max_peak * 0.95

        self._save_pcm_wav(output_wav, timeline, sample_rate)
        app_logger.info(f"[SFXEngine] Trilha de SFX montada: {output_wav} ({total_duration:.1f}s, {len(sfx_cues)} cues)")
        return output_wav

    def list_available_sfx(self) -> List[Dict[str, Any]]:
        """Retorna a lista de todos os efeitos sonoros disponíveis no soundbank."""
        files = glob.glob(os.path.join(self.sfx_dir, "*.wav"))
        res = []
        for fp in files:
            res.append({
                "filename": os.path.basename(fp),
                "path": fp,
                "size_kb": os.path.getsize(fp) // 1024
            })
        return res

# Instância padrão global
DEFAULT_SFX_ENGINE = SFXEngine()
