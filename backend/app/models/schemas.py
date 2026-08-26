from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class VideoFormat(str, Enum):
    SHORTS_9_16 = "shorts_9_16"
    LONG_16_9 = "long_16_9"

class SubtitleStyle(str, Enum):
    HORMOZI = "hormozi"          # Big bold centered, bright yellow/green active word highlight
    MINIMALIST = "minimalist"    # Elegant clean subtitle at bottom
    HIGH_ENERGY = "high_energy"  # Bouncy neon cyan/yellow with box outline

class BGMTrack(str, Enum):
    CINEMATIC = "cinematic"
    EPIC = "epic"
    LOFI = "lofi"
    UPBEAT = "upbeat"
    NONE = "none"

class WordTimestamp(BaseModel):
    word: str
    start: float  # In seconds
    end: float    # In seconds

class SceneModel(BaseModel):
    id: str
    index: int
    start_time: float
    end_time: float
    duration: float
    speech_text: str
    visual_prompt: str
    image_url: Optional[str] = None
    local_image_path: Optional[str] = None
    motion_type: str = "zoom_in"  # zoom_in, zoom_out, pan_left, pan_right

class ScriptGenerationRequest(BaseModel):
    topic: str
    video_format: VideoFormat = VideoFormat.SHORTS_9_16
    tone: str = "engaging"       # engaging, dramatic, educational, humorous, mysterious
    target_duration: int = 45    # in seconds (e.g. 30-60 for shorts, 120-300 for long)
    language: str = "en"         # en for US high-conversion
    user_notes: Optional[str] = None

class ScriptResponse(BaseModel):
    topic: str
    title_concept: str
    full_script: str
    speech_blocks: List[str]    # Paragraphs/lines separated by intentional pauses
    estimated_duration: float

class TTSRequest(BaseModel):
    project_id: str
    script_text: str
    voice_id: str = "en-US-ChristopherNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"

class ScenePromptsRequest(BaseModel):
    project_id: str
    topic: str
    style_preference: str = "cinematic realistic 8k, unreal engine 5 render, dramatic lighting"

class ImageGenerationRequest(BaseModel):
    project_id: str
    scene_id: Optional[str] = None  # If none, generates for all scenes
    prompt_override: Optional[str] = None

class RenderRequest(BaseModel):
    project_id: str
    video_format: VideoFormat = VideoFormat.SHORTS_9_16
    subtitle_style: SubtitleStyle = SubtitleStyle.HORMOZI
    bgm_track: BGMTrack = BGMTrack.CINEMATIC
    bgm_volume: float = 0.15      # Ducked background music volume (0.0 to 1.0)
    voice_volume: float = 1.0

class AutoPilotRequest(BaseModel):
    topic: str
    video_format: VideoFormat = VideoFormat.SHORTS_9_16
    voice_id: str = "en-US-ChristopherNeural"
    subtitle_style: SubtitleStyle = SubtitleStyle.HORMOZI
    bgm_track: BGMTrack = BGMTrack.CINEMATIC
    art_style: str = "hyperrealistic cinematic 8k"

class MetadataResponse(BaseModel):
    titles: List[str]            # 3 High-CTR Title options
    description: str             # Structured YouTube description with timestamps & SEO keywords
    tags: List[str]              # Targeted tags
    viral_hook_analysis: str     # Why this structure works on YouTube algorithms

class ThumbnailResponse(BaseModel):
    thumbnail_prompt: str
    thumbnail_url: Optional[str] = None
    local_thumbnail_path: Optional[str] = None
    suggested_overlay_text: str

class ProjectState(BaseModel):
    id: str
    title: str
    topic: str
    video_format: VideoFormat = VideoFormat.SHORTS_9_16
    voice_id: str = "en-US-ChristopherNeural"
    subtitle_style: SubtitleStyle = SubtitleStyle.HORMOZI
    bgm_track: BGMTrack = BGMTrack.CINEMATIC
    
    # Pipeline step assets
    full_script: Optional[str] = None
    speech_blocks: List[str] = []
    
    audio_path: Optional[str] = None
    audio_duration: float = 0.0
    word_timestamps: List[WordTimestamp] = []
    
    scenes: List[SceneModel] = []
    
    subtitle_path: Optional[str] = None
    final_video_path: Optional[str] = None
    
    metadata: Optional[MetadataResponse] = None
    thumbnail: Optional[ThumbnailResponse] = None
    
    current_step: int = 1        # 1 to 9
    status: str = "idle"         # idle, generating, completed, error
    progress: int = 0            # 0 to 100
    logs: List[str] = []
