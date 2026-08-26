import uuid
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from backend.app.models.schemas import (
    ProjectState,
    VideoFormat,
    SubtitleStyle,
    BGMTrack
)
from backend.app.utils.file_manager import get_project_dir, save_project_state, load_project_state
from backend.app.services.topic_memory_service import topic_memory
from backend.app.services.agents.multi_agent_orchestrator import multi_agent_orchestrator
from backend.app.services.tts_service import tts_service
from backend.app.services.aligner_service import aligner_service
from backend.app.services.image_service import image_service
from backend.app.services.subtitle_service import subtitle_service
from backend.app.services.video_engine import video_engine
from backend.app.services.thumbnail_service import thumbnail_service

class RoutineService:
    def __init__(self):
        self.active_routine: Optional[Dict[str, Any]] = None
        self._is_running = False

    def get_routine_status(self) -> Dict[str, Any]:
        if not self.active_routine:
            return {"is_running": False, "message": "Nenhuma rotina em execução no momento."}
        return self.active_routine

    async def execute_batch_routine(
        self,
        count: int = 3,
        voice_id: str = "en-US-ChristopherNeural",
        subtitle_style: SubtitleStyle = SubtitleStyle.HORMOZI,
        bgm_track: BGMTrack = BGMTrack.CINEMATIC
    ):
        """
        Executes a batch routine of N Shorts sequentially using Multi-Agent generation.
        """
        if self._is_running:
            return {"error": "Uma rotina já está em execução."}

        self._is_running = True
        routine_id = f"rot_{uuid.uuid4().hex[:6]}"
        
        self.active_routine = {
            "routine_id": routine_id,
            "is_running": True,
            "total_videos": count,
            "completed_videos": 0,
            "current_index": 1,
            "current_topic": "Gerando tópicos dinâmicos com Gemini...",
            "created_projects": [],
            "logs": [f"⚡ Rotina [{routine_id}] iniciada para {count} Shorts de Curiosidades."]
        }

        try:
            # 1. Generate unique curiosity topics via Multi-Agent Gemini
            topics_list = await multi_agent_orchestrator.generate_dynamic_topics(count=count)
            while len(topics_list) < count:
                more = await multi_agent_orchestrator.generate_dynamic_topics(count=count - len(topics_list))
                topics_list.extend(more)

            for idx, item in enumerate(topics_list[:count], 1):
                topic = item.get("topic", f"Unexplained Phenomenon #{idx}")
                topic_memory.ban_topic(topic, source=f"batch_routine_{routine_id}")
                self.active_routine["current_index"] = idx
                self.active_routine["current_topic"] = topic
                self.active_routine["logs"].append(f"🎬 [{idx}/{count}] Iniciando produção: '{topic}'")

                project_id = f"proj_{uuid.uuid4().hex[:8]}"
                project = ProjectState(
                    id=project_id,
                    title=f"Minuto: {topic}",
                    topic=topic,
                    video_format=VideoFormat.SHORTS_9_16,
                    voice_id=voice_id,
                    subtitle_style=subtitle_style,
                    bgm_track=bgm_track,
                    current_step=1,
                    status="generating",
                    progress=5,
                    logs=[f"Rotina [{routine_id}] iniciou Short {idx}/{count}."]
                )
                save_project_state(project)
                project_dir = get_project_dir(project_id)

                # Step 1: Script & 3s Hook Audit via Multi-Agent
                script_res = await multi_agent_orchestrator.execute_script_phase(topic=topic)
                project.title = script_res.get("title_concept", project.title)
                project.full_script = script_res.get("full_script", "")
                project.speech_blocks = script_res.get("speech_blocks", [])
                project.progress = 20
                project.logs.append(f"✓ Roteirista & Auditor: Roteiro otimizado com gancho 3s ({len(project.full_script.split())} palavras).")
                save_project_state(project)

                # Step 2 & 3: Neural Voice Narration & Timestamps
                audio_path = project_dir / "audio" / "narration.mp3"
                boundaries, word_ts, total_duration = await tts_service.generate_speech(
                    text=project.full_script,
                    output_audio_path=audio_path,
                    voice_id=voice_id
                )
                scenes = aligner_service.segment_into_scenes(
                    speech_blocks=project.speech_blocks,
                    sentence_boundaries=boundaries,
                    total_duration=total_duration
                )
                project.audio_path = f"/media/projects/{project_id}/audio/narration.mp3"
                project.audio_duration = total_duration
                project.word_timestamps = word_ts
                project.scenes = scenes
                project.progress = 40
                project.logs.append(f"✓ Sonoplasta: Narração gerada ({total_duration:.1f}s) e {len(scenes)} cenas sincronizadas.")
                save_project_state(project)

                # Step 4: Visual Director (Cinematographic Prompts & Motion)
                updated_scenes = await multi_agent_orchestrator.execute_visual_direction_phase(
                    topic=topic,
                    scenes=scenes,
                    style_theme="Cinematic 8k, dark mystery atmosphere, photorealistic, volumetric mist"
                )
                project.scenes = updated_scenes
                project.progress = 55
                project.logs.append(f"✓ Diretor Visual: Prompts cinematográficos 9:16 e movimentos Ken Burns definidos.")
                save_project_state(project)

                # Step 5: AI Illustrations
                images_dir = project_dir / "images"
                await image_service.generate_all_scene_images(
                    scenes=updated_scenes,
                    output_dir=images_dir,
                    video_format=VideoFormat.SHORTS_9_16
                )
                for s in project.scenes:
                    if s.local_image_path:
                        s.image_url = f"/media/projects/{project_id}/images/{Path(s.local_image_path).name}"
                project.progress = 70
                project.logs.append("✓ Ilustrador: Imagens hiper-realistas geradas.")
                save_project_state(project)

                # Step 6: Interactive Karaoke Subtitles
                ass_path = project_dir / "subtitles" / "karaoke.ass"
                subtitle_service.generate_ass_subtitles(
                    word_timestamps=project.word_timestamps,
                    output_ass_path=ass_path,
                    style=subtitle_style,
                    video_format=VideoFormat.SHORTS_9_16
                )
                project.subtitle_path = f"/media/projects/{project_id}/subtitles/karaoke.ass"
                project.progress = 80
                project.logs.append("✓ Legendas: Karaoke dinâmico sincronizado.")
                save_project_state(project)

                # Step 7: Sound Design SFX & Video Render
                sfx_timeline = multi_agent_orchestrator.execute_sound_design_phase(
                    scenes=project.scenes,
                    word_timestamps=project.word_timestamps,
                    total_duration=total_duration
                )
                project.logs.append(f"✓ Sonoplasta: {len(sfx_timeline)} efeitos sonoros (SFX whooshes, sinos e impactos) mapeados.")

                out_video = project_dir / "video" / "final_video.mp4"
                video_engine.render_complete_video(
                    project_dir=project_dir,
                    scenes=project.scenes,
                    voice_audio_path=audio_path,
                    ass_subtitle_path=ass_path,
                    output_video_path=out_video,
                    video_format=VideoFormat.SHORTS_9_16,
                    bgm_track=bgm_track,
                    bgm_volume=0.14,
                    sfx_timeline=sfx_timeline
                )
                project.final_video_path = f"/media/projects/{project_id}/video/final_video.mp4"
                project.progress = 90
                project.logs.append("✓ Renderizador: Vídeo final compilado com Ken Burns + SFX + BGM.")
                save_project_state(project)

                # Step 8: YouTube SEO Package
                meta = await multi_agent_orchestrator.execute_seo_phase(
                    topic=topic,
                    full_script=project.full_script
                )
                project.metadata = meta
                project.logs.append("✓ Estrategista SEO: Título viral, descrição e tags prontos.")
                save_project_state(project)

                # Step 9: High-CTR Thumbnail
                thumb_dir = project_dir / "thumbnail"
                thumb = await thumbnail_service.generate_thumbnail(
                    topic=topic,
                    title=meta.titles[0] if meta.titles else topic,
                    output_dir=thumb_dir
                )
                thumb.thumbnail_url = f"/media/projects/{project_id}/thumbnail/thumbnail.jpg"
                project.thumbnail = thumb
                project.progress = 100
                project.status = "completed"
                project.logs.append("🎉 Vídeo 100% pronto para publicação no canal!")
                save_project_state(project)

                self.active_routine["completed_videos"] += 1
                self.active_routine["created_projects"].append({
                    "id": project.id,
                    "title": project.title,
                    "final_video_path": project.final_video_path
                })
                self.active_routine["logs"].append(f"✅ Short {idx}/{count} concluído com sucesso!")

            self.active_routine["logs"].append("🏆 Todos os vídeos da rotina foram finalizados com sucesso!")
            self.active_routine["is_running"] = False

        except Exception as e:
            print(f"Routine Error: {e}")
            if self.active_routine:
                self.active_routine["is_running"] = False
                self.active_routine["logs"].append(f"❌ Erro na rotina: {str(e)}")
        finally:
            self._is_running = False

routine_service = RoutineService()
