import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
COLAB_API_URL = os.getenv("COLAB_API_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "8000"))

# Directories
ASSETS_DIR = BASE_DIR / "assets"
CHARACTERS_DIR = ASSETS_DIR / "characters"
AUDIO_DIR = ASSETS_DIR / "audio"
OUTPUT_DIR = BASE_DIR / "outputs"

CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CHARACTER_PATH = CHARACTERS_DIR / "default_comedian.png"
PUNCHLINE_BEAT_PATH = AUDIO_DIR / "punchline_beat.mp3"

# Edge-TTS Neural Voices Map
VOICE_MAP = {
    "bn": {
        "female": "bn-BD-NabanitaNeural",
        "male": "bn-BD-PradeepNeural",
        "default": "bn-BD-NabanitaNeural"
    },
    "hi": {
        "female": "hi-IN-SwaraNeural",
        "male": "hi-IN-MadhurNeural",
        "default": "hi-IN-SwaraNeural"
    },
    "en": {
        "female": "en-US-JennyNeural",
        "male": "en-US-GuyNeural",
        "default": "en-US-JennyNeural"
    }
}

