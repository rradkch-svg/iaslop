from typing import List
from backend.app.models.schemas import SceneModel
from backend.app.services.llm_service import llm_service

class PromptService:
    async def generate_prompts_for_scenes(
        self,
        topic: str,
        scenes: List[SceneModel],
        style_preference: str = "hyperrealistic cinematic 8k, volumetric lighting, photorealistic, dramatic composition"
    ) -> List[SceneModel]:
        """
        Step 4: Generates timestamped visual prompts for all scenes in the project.
        Example output per scene: [0:07] cinematic underwater bioluminescent creature in deep ocean...
        """
        scenes_data = [
            {
                "start": s.start_time,
                "end": s.end_time,
                "text": s.speech_text
            }
            for s in scenes
        ]
        
        prompts = await llm_service.generate_scene_prompts(topic, scenes_data, style_preference)
        
        for i, scene in enumerate(scenes):
            if i < len(prompts):
                scene.visual_prompt = prompts[i]
            else:
                scene.visual_prompt = f"cinematic scene representing {scene.speech_text}, 8k, {style_preference}"

        return scenes

prompt_service = PromptService()
