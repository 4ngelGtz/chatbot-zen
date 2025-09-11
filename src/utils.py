import os, time, json, random, re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Carga .env desde raíz del repo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
META = DATA / "meta"

for p in (DATA, RAW, PROCESSED, META):
    p.mkdir(parents=True, exist_ok=True)

def getenv_or_raise(key: str, default=None):
    val = os.getenv(key, default)
    if val is None:
        raise EnvironmentError(f"{key} no está definido en .env")
    return val

def jitter_sleep(base: float):
    # Pequeño jitter para evitar patrones (anti-429)
    time.sleep(base + random.uniform(0.1, 0.6))

def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def load_json(path: Path, default=None):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default

def is_short(video_dict):
    # Heurística: Shorts suelen venir con duración muy corta o path /shorts/
    url = video_dict.get("url", "") or video_dict.get("webpage_url", "")
    title = video_dict.get("title", "") or ""
    if "/shorts/" in url:
        return True
    # Si duration aparece y es < 60s, lo consideramos short opcionalmente
    dur = video_dict.get("duration") or video_dict.get("duration_string")
    # yt-dlp extract_flat no siempre trae duration; lo filtramos por URL mayormente
    return False

def clean_filename(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s).strip("_")