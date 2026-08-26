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
        with word-by-word Alex Hormozi Pill Box karaoke highlight.
        """
        output_ass_path.parent.mkdir(parents=True, exist_ok=True)
        is_short = video_format == VideoFormat.SHORTS_9_16
        
        play_res_x = 1080 if is_short else 1920
        play_res_y = 1920 if is_short else 1080
        
        # Style configuration (Pill Box Hormozi with 280px Safe Area from bottom)
        if style == SubtitleStyle.HORMOZI:
            font_name = "Arial Black"
            font_size = 68 if is_short else 54
            primary_color = "&H00FFFFFF&"      # Crisp White
            highlight_color = "&H0000E5FF&"    # Golden Yellow (&HAABBGGRR&)
            outline_color = "&H00000000&"      # Deep Black Box Outline
            back_color = "&HA0111111&"         # Dark Pill Box container
            alignment = 2                      # Bottom Center
            margin_v = 280 if is_short else 60 # Safe Area: 280px from bottom on Shorts
            border_style = 1                   # 1 = Outline + Drop shadow box
            outline = 6
            shadow = 3
            words_per_chunk = 3 if is_short else 5
        elif style == SubtitleStyle.HIGH_ENERGY:
            font_name = "Impact"
            font_size = 72 if is_short else 58
            primary_color = "&H00FFFFFF&"
            highlight_color = "&H0000FF66&"    # Bright Neon Green
            outline_color = "&H00000000&"
            back_color = "&HB0000000&"
            alignment = 2
            margin_v = 280 if is_short else 60
            border_style = 1
            outline = 7
            shadow = 4
            words_per_chunk = 2 if is_short else 4
        else:  # MINIMALIST
            font_name = "Montserrat"
            font_size = 46 if is_short else 38
            primary_color = "&H00E2E8F0&"      # Soft Silver
            highlight_color = "&H00FACC15&"    # Warm Gold
            outline_color = "&H001E293B&"
            back_color = "&H00000000&"
            alignment = 2
            margin_v = 200 if is_short else 60
            border_style = 1
            outline = 3
            shadow = 1
            words_per_chunk = 4 if is_short else 6

        ass_header = f"""[Script Info]
Title: Minuto Inexplicavel Pill Box Subtitles
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,1,0,{border_style},{outline},{shadow},{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []
        
        # Group words into rapid-fire micro-chunks (2-3 words)
        chunks = []
        for i in range(0, len(word_timestamps), words_per_chunk):
            chunk = word_timestamps[i:i + words_per_chunk]
            if chunk:
                chunks.append(chunk)

        for chunk in chunks:
            for active_idx, active_word_ts in enumerate(chunk):
                start_time_str = self.format_ass_time(active_word_ts.start)
                end_time_str = self.format_ass_time(active_word_ts.end)
                
                # Build formatted chunk text with active word highlighted
                chunk_parts = []
                for idx, w_ts in enumerate(chunk):
                    clean_word = w_ts.word.strip().upper()
                    if idx == active_idx:
                        # Highlight active word with glow & scale pop
                        chunk_parts.append(r"{\c" + highlight_color + r"\fscx108\fscy108}" + clean_word + r"{\r}")
                    else:
                        # Inactive word in white
                        chunk_parts.append(r"{\c" + primary_color + r"\fscx100\fscy100}" + clean_word + r"{\r}")
                
                line_text = " ".join(chunk_parts)
                events.append(f"Dialogue: 0,{start_time_str},{end_time_str},Default,,0,0,0,,{line_text}")

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header)
            f.write("\n".join(events))
            f.write("\n")

        return output_ass_path

subtitle_service = SubtitleService()
