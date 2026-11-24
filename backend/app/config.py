import os
from pathlib import Path

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "/data/downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
API_TOKEN = os.getenv("API_TOKEN", "")
MAX_URLS_PER_BATCH = int(os.getenv("MAX_URLS_PER_BATCH", "200"))
MAX_DOWNLOAD_BYTES = int(os.getenv("MAX_DOWNLOAD_BYTES", "0"))
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
