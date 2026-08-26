import os
import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.app.config import settings, STORAGE_DIR, FRONTEND_STATIC_DIR
from backend.app.models.schemas import (
    ProjectState,
    ScriptGenerationRequest,
    ScriptResponse,
    TTSRequest,
    ScenePromptsRequest,
    ImageGenerationRequest,
    RenderRequest,
    AutoPilotRequest,
    VideoFormat,
    SubtitleStyle,
    BGMTrack,
    MetadataResponse,
    ThumbnailResponse
)
from backend.app.utils.file_manager import (
    get_project_dir,
    save_project_state,
    load_project_state,
    list_all_projects
)
from backend.app.services.llm_service import llm_service
from backend.app.services.tts_service import tts_service
from backend.app.services.aligner_service import aligner_service
from backend.app.services.prompt_service import prompt_service
from backend.app.services.image_service import image_service
from backend.app.services.subtitle_service import subtitle_service
from backend.app.services.video_engine import video_engine
from backend.app.services.metadata_service import metadata_service
from backend.app.services.thumbnail_service import thumbnail_service
from backend.app.services.youtube_service import youtube_service

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- MEDIA SERVING -----------------
@app.get("/media/projects/{project_id}/{folder}/{filename}")
async def serve_project_media(project_id: str, folder: str, filename: str):
    file_path = STORAGE_DIR / project_id / folder / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(file_path)

# ----------------- CONFIG, GENRES & API KEYS -----------------
@app.get("/api/genres")
async def get_genres():
    return {"genres": settings.GENRES}

@app.post("/api/topics/generate")
async def generate_topics(data: Dict[str, Any]):
    genre_id = data.get("genre_id", "mysteries")
    video_format = data.get("video_format", VideoFormat.SHORTS_9_16)
    topics = await llm_service.generate_topics_by_genre(genre_id, video_format)
    return {"topics": topics}

@app.get("/api/settings/keys")
async def get_api_keys_status():
    return {
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "elevenlabs_configured": bool(settings.ELEVENLABS_API_KEY),
        "fal_configured": bool(settings.FAL_KEY)
    }

@app.post("/api/settings/keys")
async def update_api_keys(data: Dict[str, Any]):
    test_provider = data.get("test_provider")
    
    # If testing a single key
    if test_provider and test_provider in data:
        key_val = data.get(test_provider, "")
        result = await llm_service.test_api_key(test_provider, key_val)
        if not result["valid"]:
            return JSONResponse(status_code=200, content=result)  # Return 200 with valid: False for clean UI display
        
        # If valid, save it
        settings_dict = {}
        if test_provider == "gemini":
            settings_dict["gemini_api_key"] = key_val
        elif test_provider == "groq":
            settings_dict["groq_api_key"] = key_val
        elif test_provider == "openai":
            settings_dict["openai_api_key"] = key_val
        settings.save_to_file(settings_dict)
        return {"valid": True, "message": result["message"]}

    # Bulk save
    to_save = {}
    if "gemini_api_key" in data:
        to_save["gemini_api_key"] = data["gemini_api_key"].strip()
    if "groq_api_key" in data:
        to_save["groq_api_key"] = data["groq_api_key"].strip()
    if "openai_api_key" in data:
        to_save["openai_api_key"] = data["openai_api_key"].strip()
    if "elevenlabs_api_key" in data:
        to_save["elevenlabs_api_key"] = data["elevenlabs_api_key"].strip()
    if "fal_key" in data:
        to_save["fal_key"] = data["fal_key"].strip()

    settings.save_to_file(to_save)
    return {"valid": True, "message": "Chaves salvas com sucesso!"}

# ----------------- YOUTUBE DATA API V3 -----------------
@app.get("/api/youtube/status")
async def get_youtube_status():
    info = youtube_service.get_channel_info()
    return info

@app.post("/api/youtube/client-secrets")
async def upload_client_secrets(file: UploadFile = File(...)):
    import json
    content = await file.read()
    secrets_dict = json.loads(content.decode("utf-8"))
    res = youtube_service.save_client_secrets(secrets_dict)
    return res

@app.post("/api/youtube/auth/desktop")
async def auth_youtube_desktop():
    try:
        info = youtube_service.authenticate_with_desktop_flow()
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"YouTube OAuth error: {str(e)}")

@app.post("/api/projects/{project_id}/youtube/upload")
async def upload_project_to_youtube(project_id: str, data: Dict[str, Any]):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = get_project_dir(project_id)
    video_path = project_dir / "video" / "final_video.mp4"
    thumbnail_path = project_dir / "thumbnail" / "thumbnail.jpg"

    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Vídeo final ainda não foi renderizado.")

    title = data.get("title", project.title or project.topic)
    description = data.get("description", project.metadata.description if project.metadata else "")
    tags = data.get("tags", project.metadata.tags if project.metadata else [])
    privacy = data.get("privacy_status", "private")
    category = data.get("category_id", "27")

    try:
        res = await youtube_service.upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy,
            category_id=category,
            thumbnail_path=thumbnail_path if thumbnail_path.exists() else None
        )
        project.logs.append(f"🚀 Vídeo publicado no YouTube com sucesso: {res['video_url']}")
        save_project_state(project)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha no upload para o YouTube: {str(e)}")

@app.get("/api/voices")
async def get_voices():
    return {"voices": settings.DEFAULT_VOICES}

@app.get("/api/formats")
async def get_formats():
    return {
        "formats": [
            {"id": "shorts_9_16", "name": "YouTube Shorts (9:16 Vertical, 1080x1920)", "aspect": "9:16"},
            {"id": "long_16_9", "name": "YouTube Long-form (16:9 Horizontal, 1920x1080)", "aspect": "16:9"}
        ],
        "subtitle_styles": [
            {"id": "hormozi", "name": "Hormozi / Viral TikTok (Big Bold Center, Neon Yellow Highlight)"},
            {"id": "high_energy", "name": "High Energy (Impact Font, Neon Green Highlight)"},
            {"id": "minimalist", "name": "Documentary Minimalist (Clean Bottom Bar)"}
        ],
        "bgm_tracks": [
            {"id": "cinematic", "name": "Cinematic Ambient (Tension & Mystery)"},
            {"id": "epic", "name": "Epic & Inspiring"},
            {"id": "lofi", "name": "Lo-Fi Chill"},
            {"id": "upbeat", "name": "Fast & Energetic"},
            {"id": "none", "name": "No Background Music (Voice Only)"}
        ]
    }

# ----------------- PROJECT MANAGEMENT -----------------
@app.get("/api/projects")
async def get_projects():
    return {"projects": list_all_projects()}

@app.post("/api/projects/create")
async def create_project(data: Dict[str, Any]):
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    topic = data.get("topic", "The Mysterious Wow! Signal")
    video_format = data.get("video_format", VideoFormat.SHORTS_9_16)
    
    project = ProjectState(
        id=project_id,
        title=f"Video: {topic}",
        topic=topic,
        video_format=video_format,
        current_step=1,
        status="idle",
        progress=0,
        logs=["Project created."]
    )
    save_project_state(project)
    return project

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# ----------------- STEP 1: SCRIPT GENERATION -----------------
@app.post("/api/projects/{project_id}/script")
async def generate_script(project_id: str, req: ScriptGenerationRequest):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "generating_script"
    project.topic = req.topic
    project.video_format = req.video_format
    save_project_state(project)

    script_data = await llm_service.generate_script(
        topic=req.topic,
        video_format=req.video_format,
        tone=req.tone,
        target_duration=req.target_duration,
        user_notes=req.user_notes
    )

    project.title = script_data.get("title_concept", project.title)
    project.full_script = script_data.get("full_script", "")
    project.speech_blocks = script_data.get("speech_blocks", [])
    project.current_step = 2
    project.status = "idle"
    project.progress = 20
    word_count = len(project.full_script.split())
    project.logs.append(f"Step 1 Complete: Script generated ({word_count} words in {len(project.speech_blocks)} speech blocks).")
    save_project_state(project)

    return project

# ----------------- STEP 2 & 3: AUDIO & TIMESTAMPS -----------------
@app.post("/api/projects/{project_id}/audio")
async def generate_audio_and_align(project_id: str, req: TTSRequest):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = get_project_dir(project_id)
    audio_path = project_dir / "audio" / "narration.mp3"

    project.status = "generating_audio"
    project.voice_id = req.voice_id
    project.full_script = req.script_text
    save_project_state(project)

    # 1. Synthesize audio + extract boundaries & word timestamps
    boundaries, word_ts, total_duration = await tts_service.generate_speech(
        text=req.script_text,
        output_audio_path=audio_path,
        voice_id=req.voice_id,
        rate=req.rate,
        pitch=req.pitch
    )

    # 2. Segment into visual scene intervals
    scenes = aligner_service.segment_into_scenes(
        speech_blocks=project.speech_blocks or [req.script_text],
        sentence_boundaries=boundaries,
        total_duration=total_duration
    )

    project.audio_path = f"/media/projects/{project_id}/audio/narration.mp3"
    project.audio_duration = total_duration
    project.word_timestamps = word_ts
    project.scenes = scenes
    project.current_step = 4
    project.status = "idle"
    project.progress = 40
    project.logs.append(f"Step 2 & 3 Complete: Audio synthesized ({total_duration:.1f}s) and {len(scenes)} scenes aligned.")
    save_project_state(project)

    return project

# ----------------- STEP 4: SCENE PROMPTS -----------------
@app.post("/api/projects/{project_id}/prompts")
async def generate_prompts(project_id: str, req: ScenePromptsRequest):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "generating_prompts"
    save_project_state(project)

    updated_scenes = await prompt_service.generate_prompts_for_scenes(
        topic=req.topic or project.topic,
        scenes=project.scenes,
        style_preference=req.style_preference
    )

    project.scenes = updated_scenes
    project.current_step = 5
    project.status = "idle"
    project.progress = 55
    project.logs.append(f"Step 4 Complete: Bespoke visual prompts created for {len(updated_scenes)} scenes.")
    save_project_state(project)

    return project

# ----------------- STEP 5: IMAGES / ILLUSTRATIONS -----------------
@app.post("/api/projects/{project_id}/images")
async def generate_images(project_id: str, req: ImageGenerationRequest):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = get_project_dir(project_id)
    images_dir = project_dir / "images"

    project.status = "generating_images"
    save_project_state(project)

    if req.scene_id:
        # Regenerate specific scene
        for scene in project.scenes:
            if scene.id == req.scene_id:
                if req.prompt_override:
                    scene.visual_prompt = req.prompt_override
                local_p = await image_service.generate_scene_image(
                    scene=scene,
                    output_dir=images_dir,
                    video_format=project.video_format,
                    force_regenerate=True
                )
                scene.image_url = f"/media/projects/{project_id}/images/{Path(local_p).name}"
                break
    else:
        # Generate for all scenes
        await image_service.generate_all_scene_images(
            scenes=project.scenes,
            output_dir=images_dir,
            video_format=project.video_format
        )
        for scene in project.scenes:
            if scene.local_image_path:
                scene.image_url = f"/media/projects/{project_id}/images/{Path(scene.local_image_path).name}"

    project.current_step = 6
    project.status = "idle"
    project.progress = 70
    project.logs.append("Step 5 Complete: All scene illustrations ready.")
    save_project_state(project)

    return project

# ----------------- STEP 6: SUBTITLES -----------------
@app.post("/api/projects/{project_id}/subtitles")
async def generate_subtitles(project_id: str, style: SubtitleStyle = SubtitleStyle.HORMOZI):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = get_project_dir(project_id)
    ass_path = project_dir / "subtitles" / "karaoke.ass"

    project.subtitle_style = style
    subtitle_service.generate_ass_subtitles(
        word_timestamps=project.word_timestamps,
        output_ass_path=ass_path,
        style=style,
        video_format=project.video_format
    )

    project.subtitle_path = f"/media/projects/{project_id}/subtitles/karaoke.ass"
    project.current_step = 7
    project.logs.append(f"Step 6 Complete: Interactive karaoke subtitles generated ({style.value} style).")
    save_project_state(project)

    return project

# ----------------- STEP 7: RENDER VIDEO -----------------
@app.post("/api/projects/{project_id}/render")
async def render_video(project_id: str, req: RenderRequest):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = get_project_dir(project_id)
    output_video_path = project_dir / "video" / "final_video.mp4"
    voice_path = project_dir / "audio" / "narration.mp3"
    ass_path = project_dir / "subtitles" / "karaoke.ass"

    project.status = "rendering_video"
    project.subtitle_style = req.subtitle_style
    project.bgm_track = req.bgm_track
    project.video_format = req.video_format
    save_project_state(project)

    # Ensure subtitles exist with requested style
    subtitle_service.generate_ass_subtitles(
        word_timestamps=project.word_timestamps,
        output_ass_path=ass_path,
        style=req.subtitle_style,
        video_format=req.video_format
    )

    # Ensure all scenes have local images
    for s in project.scenes:
        if not s.local_image_path or not Path(s.local_image_path).exists():
            s.local_image_path = str(project_dir / "images" / f"{s.id}.jpg")

    success = video_engine.render_complete_video(
        project_dir=project_dir,
        scenes=project.scenes,
        voice_audio_path=voice_path,
        ass_subtitle_path=ass_path,
        output_video_path=output_video_path,
        video_format=req.video_format,
        bgm_track=req.bgm_track,
        bgm_volume=req.bgm_volume
    )

    if not success:
        project.status = "error"
        project.logs.append("Video rendering encountered an issue.")
        save_project_state(project)
        raise HTTPException(status_code=500, detail="Video rendering failed")

    project.final_video_path = f"/media/projects/{project_id}/video/final_video.mp4"
    project.current_step = 8
    project.status = "idle"
    project.progress = 85
    project.logs.append("Step 7 Complete: Final video rendered with Ken Burns motion, audio ducking and karaoke subtitles!")
    save_project_state(project)

    return project

# ----------------- STEP 8: METADATA -----------------
@app.post("/api/projects/{project_id}/metadata")
async def generate_metadata(project_id: str):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    meta = await metadata_service.generate_package(
        topic=project.topic,
        full_script=project.full_script or project.topic
    )
    project.metadata = meta
    project.current_step = 9
    project.logs.append("Step 8 Complete: High-CTR Titles, SEO Description and Tags generated.")
    save_project_state(project)
    return project

# ----------------- STEP 9: THUMBNAIL -----------------
@app.post("/api/projects/{project_id}/thumbnail")
async def generate_thumbnail(project_id: str, custom_text: Optional[str] = None):
    project = load_project_state(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = get_project_dir(project_id)
    thumb_dir = project_dir / "thumbnail"

    title_text = project.metadata.titles[0] if (project.metadata and project.metadata.titles) else project.topic
    thumb = await thumbnail_service.generate_thumbnail(
        topic=project.topic,
        title=title_text,
        output_dir=thumb_dir,
        custom_overlay_text=custom_text
    )

    thumb.thumbnail_url = f"/media/projects/{project_id}/thumbnail/thumbnail.jpg"
    project.thumbnail = thumb
    project.progress = 100
    project.status = "completed"
    project.logs.append("Step 9 Complete: High-impact YouTube Thumbnail generated!")
    save_project_state(project)
    return project

from backend.app.services.agents.multi_agent_orchestrator import multi_agent_orchestrator
from backend.app.services.routine_service import routine_service

# ----------------- CONFIG, GENRES & API KEYS -----------------
@app.get("/api/genres")
async def get_genres():
    return {"genres": settings.GENRES}

@app.post("/api/topics/generate")
async def generate_topics(data: Dict[str, Any]):
    count = int(data.get("count", 3))
    topics = await multi_agent_orchestrator.generate_dynamic_topics(count=count)
    return {"topics": topics}

# ----------------- BATCH ROUTINES ENDPOINTS -----------------
@app.post("/api/routines/batch")
async def start_batch_routine(data: Dict[str, Any], background_tasks: BackgroundTasks):
    count = int(data.get("count", 3))
    voice_id = data.get("voice_id", "en-US-ChristopherNeural")
    subtitle_style = SubtitleStyle(data.get("subtitle_style", SubtitleStyle.HORMOZI))
    bgm_track = BGMTrack(data.get("bgm_track", BGMTrack.CINEMATIC))

    if routine_service._is_running:
        return JSONResponse(status_code=400, content={"error": "Uma rotina já está em execução."})

    background_tasks.add_task(
        routine_service.execute_batch_routine,
        count=count,
        voice_id=voice_id,
        subtitle_style=subtitle_style,
        bgm_track=bgm_track
    )

    return {"message": f"Rotina iniciada para {count} Shorts!", "status": "started"}

@app.get("/api/routines/status")
async def get_routine_status():
    return routine_service.get_routine_status()

# ----------------- 1-CLICK MULTI-AGENT AUTO-PILOT PIPELINE -----------------
async def run_autopilot_pipeline(project_id: str, req: AutoPilotRequest):
    try:
        project = load_project_state(project_id)
        if not project:
            return

        project.status = "generating"
        project.progress = 5
        project.logs.append("🚀 Multi-Agentes Ativados: Executando pipeline para Minuto Inexplicável...")
        save_project_state(project)

        # 1. Multi-Agent Scriptwriting & 3s Hook Audit
        script_res = await multi_agent_orchestrator.execute_script_phase(
            topic=req.topic
        )
        project.title = script_res.get("title_concept", project.title)
        project.full_script = script_res.get("full_script", "")
        project.speech_blocks = script_res.get("speech_blocks", [])
        project.progress = 20
        word_count = len(project.full_script.split())
        project.logs.append(f"✓ Agente Roteirista & Auditor: Roteiro otimizado ({word_count} palavras) com gancho de 3s.")
        save_project_state(project)

        # 2 & 3. Neural Voice Narration & Word Boundaries
        project_dir = get_project_dir(project_id)
        audio_path = project_dir / "audio" / "narration.mp3"
        boundaries, word_ts, total_duration = await tts_service.generate_speech(
            text=project.full_script,
            output_audio_path=audio_path,
            voice_id=req.voice_id
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
        project.logs.append(f"✓ Agente Sonoplasta: Narração gerada ({total_duration:.1f}s) e {len(scenes)} cenas sincronizadas.")
        save_project_state(project)

        # 4. Multi-Agent Visual Director (Cinematographic Prompts & Motion)
        updated_scenes = await multi_agent_orchestrator.execute_visual_direction_phase(
            topic=req.topic,
            scenes=scenes,
            style_theme=req.art_style
        )
        project.scenes = updated_scenes
        project.progress = 55
        project.logs.append(f"✓ Agente Diretor Visual: Prompts cinematográficos 9:16 e movimentos Ken Burns definidos.")
        save_project_state(project)

        # 5. AI Image Illustrations
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
        project.logs.append("✓ Ilustrador: Imagens hiper-realistas 9:16 renderizadas.")
        save_project_state(project)

        # 6. Interactive Karaoke Subtitles
        ass_path = project_dir / "subtitles" / "karaoke.ass"
        subtitle_service.generate_ass_subtitles(
            word_timestamps=project.word_timestamps,
            output_ass_path=ass_path,
            style=req.subtitle_style,
            video_format=VideoFormat.SHORTS_9_16
        )
        project.subtitle_path = f"/media/projects/{project_id}/subtitles/karaoke.ass"
        project.progress = 80
        project.logs.append("✓ Agente de Legendas: Karaoke dinâmico sincronizado.")
        save_project_state(project)

        # 7. Sound Design SFX & Video Render
        sfx_timeline = multi_agent_orchestrator.execute_sound_design_phase(
            scenes=project.scenes,
            word_timestamps=project.word_timestamps,
            total_duration=total_duration
        )
        project.logs.append(f"✓ Agente Sonoplasta: {len(sfx_timeline)} efeitos sonoros (SFX whooshes, sinos e impactos) mixados.")

        out_video = project_dir / "video" / "final_video.mp4"
        video_engine.render_complete_video(
            project_dir=project_dir,
            scenes=project.scenes,
            voice_audio_path=audio_path,
            ass_subtitle_path=ass_path,
            output_video_path=out_video,
            video_format=VideoFormat.SHORTS_9_16,
            bgm_track=req.bgm_track,
            bgm_volume=0.14,
            sfx_timeline=sfx_timeline
        )
        project.final_video_path = f"/media/projects/{project_id}/video/final_video.mp4"
        project.progress = 90
        project.logs.append("✓ Renderizador: Vídeo final compilado com Ken Burns + SFX + BGM.")
        save_project_state(project)

        # 8. YouTube SEO Package
        meta = await multi_agent_orchestrator.execute_seo_phase(
            topic=project.topic,
            full_script=project.full_script
        )
        project.metadata = meta
        project.logs.append("✓ Agente Estrategista SEO: Título viral, descrição e tags para o Minuto Inexplicável.")
        save_project_state(project)

        # 9. High-CTR Thumbnail
        thumb_dir = project_dir / "thumbnail"
        thumb = await thumbnail_service.generate_thumbnail(
            topic=project.topic,
            title=meta.titles[0] if meta.titles else project.topic,
            output_dir=thumb_dir
        )
        thumb.thumbnail_url = f"/media/projects/{project_id}/thumbnail/thumbnail.jpg"
        project.thumbnail = thumb
        project.progress = 100
        project.status = "completed"
        project.logs.append("🎉 Produção Multi-Agente Concluída! Vídeo pronto para publicação!")
        save_project_state(project)

    except Exception as e:
        print(f"AutoPilot Error: {e}")
        project = load_project_state(project_id)
        if project:
            project.status = "error"
            project.logs.append(f"❌ Erro durante a execução Multi-Agente: {e}")
            save_project_state(project)

@app.post("/api/autopilot")
async def trigger_autopilot(req: AutoPilotRequest, background_tasks: BackgroundTasks):
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    project = ProjectState(
        id=project_id,
        title=f"Minuto: {req.topic}",
        topic=req.topic,
        video_format=VideoFormat.SHORTS_9_16,
        voice_id=req.voice_id,
        subtitle_style=req.subtitle_style,
        bgm_track=req.bgm_track,
        current_step=1,
        status="queued",
        progress=0,
        logs=["Projeto Multi-Agente inicializado."]
    )
    save_project_state(project)

    # Launch pipeline asynchronously in background
    background_tasks.add_task(run_autopilot_pipeline, project_id, req)
    return project

# Mount frontend static directory
if FRONTEND_STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_STATIC_DIR), html=True), name="static")

