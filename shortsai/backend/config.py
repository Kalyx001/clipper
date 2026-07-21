import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
DB_PATH = STORAGE_DIR / "jobs.db"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Required
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Whisper
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")  # tiny/base/small/medium/large-v3
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # cpu or cuda
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# YouTube OAuth (from Google Cloud Console -> OAuth client, "Desktop app" or "Web application")
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:8000/api/youtube/oauth2callback")

# App
MAX_CLIP_SECONDS = int(os.getenv("MAX_CLIP_SECONDS", "30"))
MIN_CLIP_SECONDS = int(os.getenv("MIN_CLIP_SECONDS", "8"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
