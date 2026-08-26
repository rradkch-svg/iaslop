import os
from pathlib import Path
import imageio_ffmpeg

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
STORAGE_DIR = BASE_DIR / "storage" / "projects"
ASSETS_DIR = BACKEND_DIR / "assets"
BGM_DIR = ASSETS_DIR / "bgm"
FONTS_DIR = ASSETS_DIR / "fonts"
FRONTEND_STATIC_DIR = BASE_DIR / "frontend" / "static"

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
BGM_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR.mkdir(parents=True, exist_ok=True)

class Settings:
    # App Config
    APP_NAME: str = "YouTube AI Video Studio"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    # FFmpeg Binary Path (auto-detected from imageio_ffmpeg)
    try:
        FFMPEG_EXE: str = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_EXE: str = "ffmpeg"
        
    # AI API Keys (Optional - fallbacks available for 100% free usage)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    FAL_KEY: str = os.getenv("FAL_KEY", "")
    
    # Available English TTS Voices (Edge-TTS)
    DEFAULT_VOICES = [
        {"id": "en-US-ChristopherNeural", "name": "Christopher (US - Deep, Storyteller, Viral)", "gender": "Male"},
        {"id": "en-US-EricNeural", "name": "Eric (US - Energetic, High Retention, Shorts)", "gender": "Male"},
        {"id": "en-US-GuyNeural", "name": "Guy (US - Casual, Engaging, Documentary)", "gender": "Male"},
        {"id": "en-US-JennyNeural", "name": "Jenny (US - Warm, Expressive, Narrative)", "gender": "Female"},
        {"id": "en-US-AriaNeural", "name": "Aria (US - Crisp, Professional, Informative)", "gender": "Female"},
        {"id": "en-GB-RyanNeural", "name": "Ryan (UK - Sophisticated, Deep Voice)", "gender": "Male"},
        {"id": "en-GB-SoniaNeural", "name": "Sonia (UK - Elegant, Storytelling)", "gender": "Female"}
    ]
    
    # Video Format Resolutions
    RESOLUTIONS = {
        "shorts_9_16": {"width": 1080, "height": 1920, "fps": 30, "aspect": "9:16"},
        "long_16_9": {"width": 1920, "height": 1080, "fps": 30, "aspect": "16:9"}
    }

settings = Settings()
