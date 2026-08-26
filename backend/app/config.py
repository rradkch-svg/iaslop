import os
import json
from pathlib import Path
import imageio_ffmpeg

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
STORAGE_DIR = BASE_DIR / "storage" / "projects"
SETTINGS_FILE = BASE_DIR / "storage" / "settings.json"
ASSETS_DIR = BACKEND_DIR / "assets"
BGM_DIR = ASSETS_DIR / "bgm"
SFX_DIR = ASSETS_DIR / "sfx"
FONTS_DIR = ASSETS_DIR / "fonts"
FRONTEND_STATIC_DIR = BASE_DIR / "frontend" / "static"

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
BGM_DIR.mkdir(parents=True, exist_ok=True)
SFX_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR.mkdir(parents=True, exist_ok=True)

class Settings:
    # App Config
    APP_NAME: str = "Minuto Inexplicável AI Studio"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    # FFmpeg Binary Path (auto-detected from imageio_ffmpeg)
    try:
        FFMPEG_EXE: str = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_EXE: str = "ffmpeg"
        
    # AI API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    FAL_KEY: str = os.getenv("FAL_KEY", "")
    
    def __init__(self):
        self.load_from_file()

    def load_from_file(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.GEMINI_API_KEY = data.get("gemini_api_key", self.GEMINI_API_KEY)
                    self.GROQ_API_KEY = data.get("groq_api_key", self.GROQ_API_KEY)
                    self.OPENAI_API_KEY = data.get("openai_api_key", self.OPENAI_API_KEY)
                    self.ANTHROPIC_API_KEY = data.get("anthropic_api_key", self.ANTHROPIC_API_KEY)
                    self.ELEVENLABS_API_KEY = data.get("elevenlabs_api_key", self.ELEVENLABS_API_KEY)
                    self.FAL_KEY = data.get("fal_key", self.FAL_KEY)
            except Exception as e:
                print(f"Error loading settings.json: {e}")

    def save_to_file(self, data: dict):
        current = {}
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except Exception:
                pass
        current.update(data)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        self.load_from_file()

    # Exclusive Genre: Curiosidades & Fatos Fascinantes
    GENRES = [
        {
            "id": "curiosidades",
            "name": "🧠 Curiosidades & Fatos Fascinantes",
            "desc": "Fatos bizarros, mistérios intrigantes, anomalias científicas e segredos históricos explicados de forma rápida, hipnótica e irresistível."
        }
    ]

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
