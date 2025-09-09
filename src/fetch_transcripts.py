\
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from tqdm import tqdm
from datetime import datetime
import yt_dlp

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw_transcripts"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PREF_LANGS = ["en", "en-US", "en-GB"]
FALLBACK_LANGS = ["es", "es-419", "auto"]  # in case there are Spanish or auto-generated

def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    return v

def _extract_channel_entries(channel_url: str, max_videos: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Use yt-dlp (no API key required) to list videos from a channel or playlist.
    Returns a list with basic metadata for each video.
    """
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "nocheckcertificate": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    entries = []
    # The extractor may return a dict with 'entries' (playlist/channel) or a single video dict
    if isinstance(info, dict) and "entries" in info:
        for e in info["entries"]:
            if not e: 
                continue
            # Some entries might be 'url' like "https://www.youtube.com/watch?v=VIDEO_ID"
            video_id = e.get("id")
            title = e.get("title")
            url = e.get("url") or e.get("webpage_url")
            if url and "watch?v=" not in url and video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
            # upload_date sometimes appears as YYYYMMDD
            upload_date_raw = e.get("upload_date")
            published_at = None
            if upload_date_raw and len(upload_date_raw) == 8:
                published_at = datetime.strptime(upload_date_raw, "%Y%m%d").isoformat()
            entries.append({
                "video_id": video_id,
                "title": title,
                "url": url,
                "published_at": published_at
            })
    else:
        # Single video object
        video_id = info.get("id")
        title = info.get("title")
        url = info.get("webpage_url")
        upload_date_raw = info.get("upload_date")
        published_at = None
        if upload_date_raw and len(upload_date_raw) == 8:
            published_at = datetime.strptime(upload_date_raw, "%Y%m%d").isoformat()
        entries.append({
            "video_id": video_id,
            "title": title,
            "url": url,
            "published_at": published_at
        })

    # De-dup & clip
    seen = set()
    out = []
    for e in entries:
        vid = e.get("video_id")
        if vid and vid not in seen:
            seen.add(vid)
            out.append(e)
        if max_videos and len(out) >= int(max_videos):
            break
    return out

def _fetch_transcript(video_id: str) -> Dict[str, Any]:
    """
    Fetch transcript segments for a given video_id with language preference & fallbacks.
    Returns dict with 'language', 'segments' and 'text_full'.
    """
    # Try preferred langs
    try_order = [PREF_LANGS, FALLBACK_LANGS]
    for lang_list in try_order:
        try:
            # list_transcripts allows detecting available transcripts and picking 'generated' vs 'manually created'
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # Try languages in order
            for lang in lang_list:
                try:
                    if lang == "auto":
                        # auto-generated English if exists
                        tr = transcript_list.find_generated_transcript(PREF_LANGS)
                    else:
                        tr = transcript_list.find_transcript([lang])
                    segs = tr.fetch()
                    text_full = " ".join(seg.get("text", "") for seg in segs if seg.get("text"))
                    return {
                        "language": tr.language_code,
                        "is_generated": tr.is_generated,
                        "segments": segs,
                        "text_full": text_full,
                    }
                except Exception:
                    continue
        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
            break
    # If everything fails
    return {
        "language": None,
        "is_generated": None,
        "segments": [],
        "text_full": "",
    }

def main():
    load_dotenv()
    channel_url = get_env("CHANNEL_URL")
    if not channel_url:
        raise SystemExit("CHANNEL_URL is required in .env (e.g., https://www.youtube.com/@BuddhasWizdom/videos)")
    max_videos = get_env("MAX_VIDEOS")

    print(f"[INFO] Listing videos from: {channel_url}")
    videos = _extract_channel_entries(channel_url, max_videos=max_videos)
    if not videos:
        raise SystemExit("No videos found. Check CHANNEL_URL or try removing MAX_VIDEOS.")

    (DATA_DIR / "videos.json").write_text(json.dumps(videos, indent=2), encoding="utf-8")
    print(f"[OK] Found {len(videos)} videos. Saved metadata to data/videos.json")

    # Fetch transcripts
    combined_path = DATA_DIR / "transcripts.jsonl"
    n_ok, n_fail = 0, 0
    with combined_path.open("w", encoding="utf-8") as w:
        for v in tqdm(videos, desc="Fetching transcripts"):
            vid = v["video_id"]
            if not vid:
                n_fail += 1
                continue
            tdata = _fetch_transcript(vid)
            # Save per-video raw JSON
            (RAW_DIR / f"{vid}.json").write_text(json.dumps({
                "video": v,
                "transcript": tdata
            }, ensure_ascii=False, indent=2), encoding="utf-8")

            # Write to combined JSONL (flat)
            record = {
                "video_id": vid,
                "title": v.get("title"),
                "url": v.get("url"),
                "published_at": v.get("published_at"),
                "language": tdata.get("language"),
                "is_generated": tdata.get("is_generated"),
                "segments": tdata.get("segments", []),
                "text_full": tdata.get("text_full", ""),
            }
            w.write(json.dumps(record, ensure_ascii=False) + "\n")
            # count
            if record["text_full"]:
                n_ok += 1
            else:
                n_fail += 1
    print(f"[DONE] Transcripts written to {combined_path}. OK: {n_ok}, Fail/Empty: {n_fail}")

if __name__ == "__main__":
    main()
