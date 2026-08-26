from pathlib import Path
from typing import List
from backend.app.models.schemas import WordTimestamp, SubtitleStyle, VideoFormat

class SubtitleService:
    def format_ass_time(self, seconds: float) -> str:
        """Formats seconds into ASS timestamp format: H:MM:SS.cc"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int(round((seconds - int(seconds)) * 100))
        if centis >= 100:
            secs += 1
            centis = 0
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

    def generate_ass_subtitles(
        self,
        word_timestamps: List[WordTimestamp],
        output_ass_path: Path,
        style: SubtitleStyle = SubtitleStyle.HORMOZI,
        video_format: VideoFormat = VideoFormat.SHORTS_9_16
    ) -> Path:
        """
        Step 6: Generates an Advanced SubStation Alpha (.ass) subtitle file
        with word-by-word active karaoke highlight.
        """
        output_ass_path.parent.mkdir(parents=True, exist_ok=True)
        is_short = video_format == VideoFormat.SHORTS_9_16
        
        # Determine canvas resolution for ASS
        play_res_x = 1080 if is_short else 1920
        play_res_y = 1920 if is_short else 1080
        
        # Style configuration
        if style == SubtitleStyle.HORMOZI:
            # High impact: Bold uppercase, centered, thick black border, bright yellow active highlight
            font_name = "Arial Black"
            font_size = 72 if is_short else 56
            primary_color = "&H00FFFFFF&"      # White for inactive words
            highlight_color = "&H0000E6FF&"    # Neon Yellow for active word (&HAABBGGRR&)
            outline_color = "&H00000000&"      # Pure Black
            back_color = "&H64000000&"         # Shadow
            alignment = 5 if is_short else 2   # 5 = Mid-center (Shorts), 2 = Bottom-center (Long)
            margin_v = 0 if is_short else 70
            outline = 6
            shadow = 3
            words_per_chunk = 3 if is_short else 5
        elif style == SubtitleStyle.HIGH_ENERGY:
            font_name = "Impact"
            font_size = 76 if is_short else 60
            primary_color = "&H00FFFFFF&"
            highlight_color = "&H0000FF66&"    # Bright Neon Green
            outline_color = "&H00000000&"
            back_color = "&H80000000&"
            alignment = 5 if is_short else 2
            margin_v = 0 if is_short else 65
            outline = 7
            shadow = 4
            words_per_chunk = 2 if is_short else 4
        else:  # MINIMALIST
            font_name = "Montserrat"
            font_size = 46 if is_short else 38
            primary_color = "&H00E2E8F0&"      # Soft silver
            highlight_color = "&H00FACC15&"    # Warm gold
            outline_color = "&H001E293B&"
            back_color = "&H00000000&"
            alignment = 2                      # Bottom-center
            margin_v = 110 if is_short else 60
            outline = 2
            shadow = 1
            words_per_chunk = 4 if is_short else 7

        ass_header = f"""[Script Info]
Title: YouTube AI Studio Subtitles
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,1,0,1,{outline},{shadow},{alignment},30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []
        
        # Group words into small chunks (e.g. 2-4 words)
        chunks = []
        for i in range(0, len(word_timestamps), words_per_chunk):
            chunk = word_timestamps[i:i + words_per_chunk]
            if chunk:
                chunks.append(chunk)

        for chunk in chunks:
            # For each word in this chunk, create a dialogue line spanning that word's duration
            for active_idx, active_word_ts in enumerate(chunk):
                start_time_str = self.format_ass_time(active_word_ts.start)
                end_time_str = self.format_ass_time(active_word_ts.end)
                
                # Build the chunk text where active word has highlight_color
                styled_words = []
                for idx, w_ts in enumerate(chunk):
                    word_clean = w_ts.word.upper() if (style == SubtitleStyle.HORMOZI or style == SubtitleStyle.HIGH_ENERGY) else w_ts.word
                    if idx == active_idx:
                        styled_words.append(f"{{\\c{highlight_color}\\t(0,80,\\fscx108\\fscy108)}}{word_clean}{{\\c{primary_color}\\fscx100\\fscy100}}")
                    else:
                        styled_words.append(f"{{\\c{primary_color}}}{word_clean}")

                line_text = " ".join(styled_words)
                events.append(f"Dialogue: 0,{start_time_str},{end_time_str},Default,,0,0,0,,{line_text}")

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header + "\n".join(events) + "\n")

        return output_ass_path

subtitle_service = SubtitleService()
