from typing import List, Dict, Any
from pathlib import Path
from backend.app.models.schemas import SceneModel, WordTimestamp

class SoundDesignerAgent:
    def __init__(self):
        self.agent_name = "SoundDesigner"
        self.role_description = "Sound designer & audio mixer orchestrator. Places whooshes, bell dings, and sub-bass impacts to maximize viewer retention."

    def build_sfx_timeline(
        self,
        scenes: List[SceneModel],
        word_timestamps: List[WordTimestamp],
        total_duration: float
    ) -> List[Dict[str, Any]]:
        """
        Calculates an exact timeline of sound effect cues across the Short.
        - 0.0s: Opening Hook Sub-Bass Drop (instant visceral impact).
        - 0.3s - 1.2s: Mystery Bell / Tension Chime during opening hook.
        - Scene Cut Points: Whoosh transition sweeps aligned with Ken Burns camera changes.
        - Keyword Reveal Points: Bell / Suspense hits on dramatic words (e.g. 'anomaly', 'vanished', 'secret', 'alien', 'classified', 'never').
        """
        timeline: List[Dict[str, Any]] = []

        # 1. Opening Hook Impact (0.0s)
        timeline.append({
            "time": 0.0,
            "sfx_type": "sub_boom",
            "volume": 0.95,
            "reason": "Opening Hook 3-Second Impact"
        })

        # 2. Opening Tension Bell (0.6s)
        timeline.append({
            "time": 0.6,
            "sfx_type": "bell",
            "volume": 0.80,
            "reason": "Hook Mystery Accent"
        })

        # 3. Scene Transition Whooshes (on scene cut timestamps)
        for scene in scenes:
            if scene.index > 1 and scene.start_time > 1.5:
                # Place whoosh 0.2s before scene start so the sweep peaks exactly on the cut
                whoosh_time = max(0.0, scene.start_time - 0.2)
                timeline.append({
                    "time": round(whoosh_time, 2),
                    "sfx_type": "whoosh",
                    "volume": 0.75,
                    "reason": f"Scene {scene.index} Transition Cut"
                })

        # 4. Keyword Reveal Dings / Bell Accents
        mystery_keywords = {
            "mystery", "anomaly", "vanished", "secret", "never", "bizarre",
            "impossible", "unexplained", "died", "classified", "disappeared",
            "terrifying", "warning", "hidden", "found", "shocking"
        }

        placed_reveals = 0
        for wt in word_timestamps:
            clean_word = wt.word.lower().strip(".,!?:;\"'()")
            if clean_word in mystery_keywords and wt.start > 3.0 and wt.start < (total_duration - 2.0):
                # Ensure at least 4.0s gap between bell hits
                recent_bells = [t for t in timeline if t["sfx_type"] in ("bell", "reveal_hit") and abs(t["time"] - wt.start) < 4.0]
                if not recent_bells and placed_reveals < 3:
                    timeline.append({
                        "time": round(wt.start, 2),
                        "sfx_type": "bell" if placed_reveals % 2 == 0 else "reveal_hit",
                        "volume": 0.70,
                        "reason": f"Keyword Impact: '{clean_word}'"
                    })
                    placed_reveals += 1

        # Sort timeline by time
        timeline.sort(key=lambda x: x["time"])
        return timeline

sound_designer_agent = SoundDesignerAgent()
