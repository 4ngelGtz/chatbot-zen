import os, json, sys
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from src.utils import getenv_or_raise, jitter_sleep, META, save_json, is_short

load_dotenv()

def get_video_entries(channel_url: str, extract_flat: bool = True):
    ydl_opts = {
        "quiet": True,
        "extract_flat": extract_flat,
        "force_generic_extractor": False,
        "skip_download": True,
        "noplaylist": False,
        "playlistend": None,
        "concurrent_fragment_downloads": 1,
        # User-Agent para evitar bloqueos
        "http_headers": {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) yt-dlp/portfolio"},
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        # Para URLs tipo @user/videos, yt-dlp entrega una playlist con entries
        entries = info.get("entries", [])
        return entries

def main():
    channel_url = getenv_or_raise("CHANNEL_URL")
    max_videos = int(os.getenv("MAX_VIDEOS", "0"))
    exclude_shorts = os.getenv("EXCLUDE_SHORTS", "0") == "1"

    entries = get_video_entries(channel_url)
    out_path = META / "videos.jsonl"

    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for e in tqdm(entries, desc="Recolectando videos"):
            # Algunos 'entries' pueden ser playlists (ej. shorts), filtramos sólo 'video'
            if e.get("_type") and e["_type"] != "url":
                continue
            if exclude_shorts and is_short(e):
                continue

            data = {
                "id": e.get("id"),
                "title": e.get("title"),
                "url": e.get("url") or e.get("webpage_url"),
                "webpage_url": e.get("webpage_url") or e.get("url"),
                "uploader": e.get("uploader"),
            }
            if not data["id"] or not data["webpage_url"]:
                continue

            f.write(json.dumps(data, ensure_ascii=False) + "\n")
            count += 1
            if max_videos and count >= max_videos:
                break

    print(f"[OK] Guardado: {out_path} ({count} videos)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)