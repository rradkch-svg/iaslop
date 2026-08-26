from typing import List, Dict, Any
from backend.app.models.schemas import SceneModel
from backend.app.services.agents.base_agent import BaseAgent

class VisualDirectorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="VisualDirector",
            role_description="Cinematographic director for Minuto Inexplicável. Generates photorealistic, dark atmospheric visual prompts and Ken Burns motion cues."
        )

    async def direct_scene_visuals(self, topic: str, scenes: List[SceneModel], style_theme: str = "") -> List[SceneModel]:
        """
        Directs visual prompts and camera motions for each scene to ensure continuous visual engagement,
        eliminating static frames and boosting watch-time retention.
        """
        scenes_data = [
            {
                "index": s.index,
                "duration": s.duration,
                "text": s.speech_text
            }
            for s in scenes
        ]

        system_prompt = (
            "You are the Cinematographic Visual Director for 'Minuto Inexplicável' YouTube Shorts. "
            "Your job is to generate rich, vivid, photorealistic image prompts (9:16 vertical aspect ratio) "
            "and assign dynamic camera motion types for each scene.\n"
            "MOTION OPTIONS: 'zoom_in' (escalating tension), 'zoom_out' (revealing scale), 'pan_left', 'pan_right' (investigative scan).\n"
            "VISUAL STYLE: Dark atmospheric lighting, photorealistic 8k, volumetric mist, anamorphic lens flare, eerie mystery, ultra-detailed textures."
        )

        user_prompt = f"""
Topic: {topic}
Base Style: {style_theme or 'Cinematic photorealism, eerie mystery atmosphere, 8k unreal engine 5, dramatic volumetric lighting'}

Scenes to direct:
{scenes_data}

Return a JSON array where each item corresponds to a scene in order:
[
  {{
    "index": 1,
    "visual_prompt": "Ultra-detailed visual prompt describing subject, environment, lighting, and camera angle...",
    "motion_type": "zoom_in"
  }},
  ...
]
"""
        result = await self.call_llm_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.75
        )

        motion_cycle = ["zoom_in", "pan_left", "zoom_out", "pan_right"]

        if isinstance(result, list) and len(result) > 0:
            prompt_map = {item.get("index", idx + 1): item for idx, item in enumerate(result)}
            for scene in scenes:
                director_data = prompt_map.get(scene.index)
                if director_data:
                    prompt = director_data.get("visual_prompt", "")
                    if prompt:
                        scene.visual_prompt = f"{prompt}, 9:16 vertical framing, photorealistic, cinematic atmospheric lighting, 8k resolution"
                    scene.motion_type = director_data.get("motion_type", motion_cycle[(scene.index - 1) % len(motion_cycle)])
        else:
            # Fallback direct assignment
            for idx, scene in enumerate(scenes):
                scene.visual_prompt = f"Cinematic scene representing '{scene.speech_text}', {topic}, dark atmospheric mystery, photorealistic 8k, 9:16 vertical ratio"
                scene.motion_type = motion_cycle[idx % len(motion_cycle)]

        return scenes

visual_director_agent = VisualDirectorAgent()
