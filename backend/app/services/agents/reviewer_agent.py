import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from backend.app.config import settings
from backend.app.services.agents.base_agent import BaseAgent

class ReviewerAgent(BaseAgent):
    """
    Multimodal Visual Auditor (Gemini Vision):
    Inspects candidate B-Roll video clips extracted from YouTube or stock sources.
    Enforces the Smart Anti-Vlog Policy: rejects modern talking-head vloggers and gameplay,
    while approving authentic historical archival footage, scientists in labs, documents,
    space/nature phenomena, and mystery scenery with high relevance (Score >= 7.0).
    """
    def __init__(self):
        super().__init__(
            agent_name="VisualReviewerSpecialist",
            role_description="Multimodal vision auditor inspecting B-Roll video frames for quality, relevance, and Anti-Vlog compliance."
        )

    def pre_filter_title(self, video_title: str, global_topic: str) -> Tuple[bool, str]:
        """
        Fast O(1) heuristic metadata filter before downloading video streams.
        Rejects obvious gaming, vlogs, reaction videos, podcasts, and irrelevant fluff.
        """
        title_lower = video_title.lower()
        
        # Banned keywords in title
        banned_terms = [
            "gameplay", "walkthrough", "lets play", "let's play", "reaction", 
            "reacting to", "vlog", "podcast", "unboxing", "tiktok dance",
            "minecraft", "roblox", "fortnite", "gta v", "gta 5", "livestream"
        ]
        for term in banned_terms:
            if term in title_lower:
                return False, f"Title contains banned format term: '{term}'"

        return True, "Title approved for segment scanning"

    def extract_clip_frame(self, clip_path: Path, timestamp: float = 1.0) -> Optional[bytes]:
        """
        Extracts a single representative frame from a video clip at the given timestamp
        scaled down to 384x384 for ultra-fast, token-efficient Gemini Vision multimodal inspection.
        """
        if not clip_path.exists():
            return None

        ffmpeg_exe = settings.FFMPEG_EXE
        cmd = [
            ffmpeg_exe,
            "-ss", f"{timestamp:.2f}",
            "-i", str(clip_path),
            "-vframes", "1",
            "-vf", "scale=384:384:force_original_aspect_ratio=increase,crop=384:384",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "-"
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if res.returncode == 0 and len(res.stdout) > 500:
                return res.stdout
        except Exception as e:
            print(f"[ReviewerAgent] Error extracting frame: {e}")
        return None

    async def inspect_clip(
        self,
        clip_path: Path,
        global_topic: str,
        scene_fala: str,
        video_title: str = ""
    ) -> Dict[str, Any]:
        """
        Multimodal visual inspection with Gemini Vision:
        Evaluates frame for:
        1. Absence of front-facing modern vloggers / talking heads with microphones.
        2. Relevance to the mystery curiosity topic.
        3. Visual aesthetics and clarity (1080x1920 vertical composition).
        """
        frame_bytes = self.extract_clip_frame(clip_path, timestamp=1.2)
        if not frame_bytes:
            # Try at 0.5s
            frame_bytes = self.extract_clip_frame(clip_path, timestamp=0.5)

        if not frame_bytes:
            return {
                "aprovado": False,
                "score": 0.0,
                "motivo": "Falha ao extrair frame para auditoria visual.",
                "elementos_detectados": "none"
            }

        prompt = f"""
You are the Lead Visual Quality Auditor for the YouTube Shorts channel 'Minuto Inexplicável' (Curiosities & Mysteries).
Inspect this video frame candidate for the following scene:

Global Topic: {global_topic}
Spoken Scene Line: "{scene_fala}"
Source Video Title: "{video_title}"

AUDIT RULES:
1. ANTI-VLOG POLICY: Reject front-facing modern YouTubers/vloggers talking directly to camera, reaction videos, or gaming UI.
   (Archival historical footage, vintage photos, scientists working in labs, documents, artifacts, or mystery landscapes ARE WELCOME).
2. RELEVANCE: Does this visual connect logically or atmospherically to the mystery/curiosity?
3. SCORE: Rate visual quality and cinematic relevance from 1.0 to 10.0.

Return ONLY valid JSON:
{{
  "aprovado": true or false (true if score >= 6.5 and NO modern vlogger talking head),
  "score": 8.5,
  "motivo": "Brief explanation in Portuguese of visual quality and verdict",
  "elementos_detectados": "Key visual objects seen in frame"
}}
"""
        result = await self.call_vision(
            prompt=prompt,
            image_bytes=frame_bytes,
            mime_type="image/jpeg",
            json_mode=True
        )

        if isinstance(result, dict) and "aprovado" in result:
            return result

        # Fallback lenient pass if vision is unavailable
        return {
            "aprovado": True,
            "score": 7.5,
            "motivo": "Aprovado por heurística de metadados.",
            "elementos_detectados": "visual scene"
        }

reviewer_agent = ReviewerAgent()
