from typing import List, Dict, Any
from backend.app.models.schemas import SceneModel, WordTimestamp

class AlignerService:
    def segment_into_scenes(
        self,
        speech_blocks: List[str],
        sentence_boundaries: List[Dict[str, Any]],
        total_duration: float,
        target_scene_duration: float = 4.5
    ) -> List[SceneModel]:
        """
        Step 3: Groups speech blocks and sentence boundaries into optimal scene intervals (3-6s).
        Calculates exact start and end times for each visual illustration.
        """
        scenes: List[SceneModel] = []
        
        # Motions cycle for dynamic Ken Burns variety
        motion_types = ["zoom_in", "pan_left", "zoom_out", "pan_right"]

        if not sentence_boundaries:
            # Fallback if no boundaries detected: evenly partition total duration
            count = max(len(speech_blocks), 1)
            duration_per_scene = total_duration / count
            for i, block in enumerate(speech_blocks or ["Scene"]):
                start = i * duration_per_scene
                end = min((i + 1) * duration_per_scene, total_duration)
                scenes.append(SceneModel(
                    id=f"scene_{i+1}",
                    index=i + 1,
                    start_time=round(start, 2),
                    end_time=round(end, 2),
                    duration=round(end - start, 2),
                    speech_text=block,
                    visual_prompt="",
                    motion_type=motion_types[i % len(motion_types)]
                ))
            return scenes

        # Build scenes from sentence boundaries
        current_scene_sentences = []
        current_start = sentence_boundaries[0]["start"]
        
        for idx, sent in enumerate(sentence_boundaries):
            current_scene_sentences.append(sent)
            current_duration = sent["end"] - current_start
            
            # Check if we should close this scene:
            # 1. We reached target duration (~4-6s)
            # 2. Or this is the last sentence
            # 3. Or significant pause after this sentence
            is_last = (idx == len(sentence_boundaries) - 1)
            pause_after = 0.0
            if not is_last:
                pause_after = sentence_boundaries[idx + 1]["start"] - sent["end"]

            if is_last or current_duration >= target_scene_duration or pause_after > 0.4:
                scene_text = " ".join([s["text"] for s in current_scene_sentences])
                scene_end = sent["end"]
                if is_last:
                    scene_end = max(scene_end, total_duration)
                    
                scene_index = len(scenes) + 1
                scenes.append(SceneModel(
                    id=f"scene_{scene_index}",
                    index=scene_index,
                    start_time=round(current_start, 2),
                    end_time=round(scene_end, 2),
                    duration=round(scene_end - current_start, 2),
                    speech_text=scene_text,
                    visual_prompt="",
                    motion_type=motion_types[(scene_index - 1) % len(motion_types)]
                ))
                
                # Reset for next scene
                if not is_last:
                    current_start = sentence_boundaries[idx + 1]["start"]
                    current_scene_sentences = []

        return scenes

aligner_service = AlignerService()
