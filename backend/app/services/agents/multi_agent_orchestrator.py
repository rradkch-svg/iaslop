from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.app.models.schemas import SceneModel, WordTimestamp, MetadataResponse
from backend.app.services.agents.hook_script_agent import hook_script_agent
from backend.app.services.agents.visual_director_agent import visual_director_agent
from backend.app.services.agents.sound_designer_agent import sound_designer_agent
from backend.app.services.agents.retention_auditor_agent import retention_auditor_agent
from backend.app.services.agents.reviewer_agent import reviewer_agent
from backend.app.services.agents.youtube_seo_agent import youtube_seo_agent
from backend.app.services.broll_engine import broll_engine

class MultiAgentOrchestrator:
    """
    Coordinates the 6 specialized AI agents for Minuto Inexplicável:
    1. HookScriptAgent (Scriptwriting & 3s Hook)
    2. RetentionAuditorAgent (3s Hook & Pacing Quality Audit)
    3. VisualDirectorAgent (Cinematographic Prompts & B-Roll Query Direction)
    4. ReviewerAgent (Gemini Vision Multimodal Quality & Anti-Vlog Auditor)
    5. SoundDesignerAgent (SFX Cues & Transition Sweeps)
    6. YoutubeSEOAgent (High-CTR Titles, SEO Description & Tags)
    """

    async def generate_dynamic_topics(self, count: int = 3) -> List[Dict[str, str]]:
        return await hook_script_agent.generate_curiosity_topics(count=count)

    async def execute_script_phase(self, topic: str, user_notes: Optional[str] = None) -> Dict[str, Any]:
        # 1. Draft initial high-retention script
        script_data = await hook_script_agent.write_shorts_script(topic=topic, user_notes=user_notes)
        
        # 2. Audit and optimize the opening 3-second hook
        audit_result = await retention_auditor_agent.audit_and_optimize_hook(
            topic=topic,
            current_hook=script_data.get("opening_hook", ""),
            full_script=script_data.get("full_script", "")
        )

        optimized_hook = audit_result.get("optimized_hook")
        if optimized_hook and optimized_hook != script_data.get("opening_hook"):
            # Update first speech block with optimized hook
            if script_data.get("speech_blocks") and len(script_data["speech_blocks"]) > 0:
                script_data["speech_blocks"][0] = f"[SFX:SUB_BOOM] {optimized_hook}"
            script_data["opening_hook"] = optimized_hook

        return script_data

    async def execute_visual_direction_phase(self, topic: str, scenes: List[SceneModel], style_theme: str = "") -> List[SceneModel]:
        return await visual_director_agent.direct_scene_visuals(topic=topic, scenes=scenes, style_theme=style_theme)

    async def execute_broll_and_visual_phase(self, scenes: List[SceneModel], topic: str, project_dir: Path) -> List[Path]:
        """
        Executes parallel B-Roll scraping + segment scanning + Gemini Vision multimodal auditing
        with automatic AI illustration + Ken Burns fallback.
        """
        return await broll_engine.process_all_scenes_hybrid(
            scenes=scenes,
            global_topic=topic,
            project_dir=project_dir
        )

    def execute_sound_design_phase(self, scenes: List[SceneModel], word_timestamps: List[WordTimestamp], total_duration: float) -> List[Dict[str, Any]]:
        return sound_designer_agent.build_sfx_timeline(scenes=scenes, word_timestamps=word_timestamps, total_duration=total_duration)

    async def execute_seo_phase(self, topic: str, full_script: str) -> MetadataResponse:
        return await youtube_seo_agent.generate_seo_package(topic=topic, full_script=full_script)

multi_agent_orchestrator = MultiAgentOrchestrator()
