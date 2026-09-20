import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"

def load_env():
    """Simple parser for .env without requiring third-party libraries."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())

load_env()

API_KEY = os.getenv("HEVY_API_KEY", "")
API_BASE_URL = os.getenv("HEVY_API_BASE_URL", "https://api.hevyapp.com/v1")

DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKOUTS_CACHE_FILE = DATA_DIR / "workouts.json"
ROUTINES_CACHE_FILE = DATA_DIR / "routines.json"
TEMPLATES_CACHE_FILE = DATA_DIR / "exercise_templates.json"
