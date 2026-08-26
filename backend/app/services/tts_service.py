import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Tuple
import edge_tts
from backend.app.config import settings
from backend.app.models.schemas import WordTimestamp
from backend.app.utils.ffmpeg_helper import get_media_duration

class TTSService:
    def __init__(self):
        self.elevenlabs_key = settings.ELEVENLABS_API_KEY
        self.openai_key = settings.OPENAI_API_KEY

    async def generate_speech(
        self,
        text: str,
        output_audio_path: Path,
        voice_id: str = "en-US-ChristopherNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ) -> Tuple[List[Dict[str, Any]], List[WordTimestamp], float]:
        """
        Synthesizes English audio using Edge-TTS (or ElevenLabs if configured).
        Returns:
          - sentence_boundaries: List of {'text': str, 'start': float, 'end': float}
          - word_timestamps: List of WordTimestamp(word, start, end)
          - total_duration: float in seconds
        """
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Clean text of markdown or extra artifacts
        clean_text = text.replace("**", "").replace("*", "").replace("#", "").strip()
        
        communicate = edge_tts.Communicate(clean_text, voice_id, rate=rate, pitch=pitch)
        
        sentence_boundaries = []
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

        with open(output_audio_path, "wb") as f:
            f.write(raw_audio)

        # Probe exact audio duration via FFmpeg
        total_duration = get_media_duration(output_audio_path)
        if total_duration <= 0 and sentence_boundaries:
            total_duration = sentence_boundaries[-1]["end"]

        # Calculate high-precision word timestamps
        word_timestamps = self._calculate_word_timestamps(sentence_boundaries, total_duration)

        return sentence_boundaries, word_timestamps, total_duration

    def _calculate_word_timestamps(
        self,
        sentence_boundaries: List[Dict[str, Any]],
        total_duration: float
    ) -> List[WordTimestamp]:
        """
        Maps words within each sentence to precise fractional timestamp intervals
        proportional to character length and punctuation pauses.
        """
        word_timestamps: List[WordTimestamp] = []
        
        for sent in sentence_boundaries:
            s_text = sent["text"]
            s_start = sent["start"]
            s_duration = sent["duration"]
            
            raw_words = s_text.split()
            if not raw_words:
                continue

            # Weight words by character count (+ bonus for trailing punctuation)
            weights = []
            for w in raw_words:
                w_len = len(w)
                if w.endswith((".", "!", "?", ",", ";", ":")):
                    w_len += 2  # Punctuation pause weight
                weights.append(max(w_len, 1))

            total_weight = sum(weights)
            current_time = s_start

            for w, weight in zip(raw_words, weights):
                w_dur = (weight / total_weight) * s_duration
                w_start = current_time
                w_end = min(current_time + w_dur, sent["end"])
                
                # Strip trailing punctuation for clean display if needed, but keep readable
                clean_word = w.strip()
                word_timestamps.append(WordTimestamp(
                    word=clean_word,
                    start=round(w_start, 3),
                    end=round(w_end, 3)
                ))
                current_time = w_end

        return word_timestamps

tts_service = TTSService()
