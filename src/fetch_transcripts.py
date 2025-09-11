# src/fetch_transcripts.py
"""
Descarga transcripts para todos los videos listados en data/video_ids.jsonl
o, si no existe, intenta construir la lista desde CHANNEL_URL con yt-dlp.

Preferencias:
- en-US, luego en (con yt-dlp)
- Si no hay, usa youtube-transcript-api para en-US/en
- Si tampoco hay, traduce a en desde cualquier idioma disponible (manual > auto)

Config vía .env (opcional):
- BROWSER_PROFILE="chrome:Profile 1"   # o
- YT_COOKIES=/ruta/cookies.txt
- CHANNEL_URL="https://www.youtube.com/@<canal>/videos"  # fallback para obtener IDs
- MAX_VIDEOS=50    # para limitar volumen en pruebas
"""

from __future__ import annotations

import json
import os
import sys
import time
import glob
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# Paths
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SUBS_DIR = RAW_DIR / "subs"
IDS_JSONL = DATA_DIR / "video_ids.jsonl"  # esperado de src.fetch_video_ids
INDEX_JSONL = DATA_DIR / "chunks" / "transcripts_index.jsonl"
(Path(DATA_DIR / "chunks")).mkdir(parents=True, exist_ok=True)
SUBS_DIR.mkdir(parents=True, exist_ok=True)

# Env
BROWSER_PROFILE = os.getenv("BROWSER_PROFILE")          # ej: "chrome:Profile 1"
YT_COOKIES = os.getenv("YT_COOKIES")                    # ej: "/path/cookies.txt"
CHANNEL_URL = os.getenv("CHANNEL_URL")
MAX_VIDEOS = int(os.getenv("MAX_VIDEOS", "0"))          # 0 = sin límite

# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------

@dataclass
class VideoItem:
    id: str
    url: str

def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)

def _supports_impersonate() -> bool:
    h = _run(["yt-dlp", "--help"])
    return "--impersonate" in (h.stdout + h.stderr)

def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _srt_out_template(out_dir: Path) -> str:
    # Salida determinista por ID
    return str(out_dir / "Transcript [%(id)s].%(ext)s")

def _sub_path(out_dir: Path, video_id: str, lang: str) -> Path:
    return out_dir / f"Transcript [{video_id}].{lang}.srt"

def _find_any_en(out_dir: Path, video_id: str) -> Optional[Path]:
    for lang in ("en-US", "en"):
        p = _sub_path(out_dir, video_id, lang)
        if p.exists() and p.stat().st_size > 100:
            return p
    return None

def _write_srt_file(out_path: Path, transcript: List[Dict]) -> None:
    def fmt_time(t: float) -> str:
        ms = int((t - int(t)) * 1000)
        h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    idx = 1
    for item in transcript:
        text = (item.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        start = float(item["start"])
        dur = float(item.get("duration", 0.0))
        end = start + dur
        lines += [str(idx), f"{fmt_time(start)} --> {fmt_time(end)}", text, ""]
        idx += 1
    content = "\n".join(lines).strip() + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

def _fallback_yta(video_id: str, out_dir: Path) -> Optional[Path]:
    """
    Fallback con youtube-transcript-api:
    - en-US -> en
    - traducir a en si no hay en/en-US
    """
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
        )
        # 1) en-US, en
        for lang in ["en-US", "en"]:
            try:
                tr = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                out = _sub_path(out_dir, video_id, lang)
                _write_srt_file(out, tr)
                if out.exists() and out.stat().st_size > 100:
                    return out
            except (NoTranscriptFound, TranscriptsDisabled):
                pass

        # 2) listar y traducir a en
        try:
            listing = YouTubeTranscriptApi.list_transcripts(video_id)
        except (NoTranscriptFound, TranscriptsDisabled):
            return None

        candidate = None
        # manual > auto
        for tr in listing:
            if not getattr(tr, "is_generated", False):
                candidate = tr; break
        if candidate is None:
            for tr in listing:
                if getattr(tr, "is_generated", False):
                    candidate = tr; break
        if candidate is None:
            return None

        try:
            translated = candidate.translate("en").fetch()
            out = _sub_path(out_dir, video_id, "en")
            _write_srt_file(out, translated)
            if out.exists() and out.stat().st_size > 100:
                return out
        except Exception:
            try:
                fetched = candidate.fetch()
                out = out_dir / f"Transcript [{video_id}].{candidate.language}.srt"
                _write_srt_file(out, fetched)
                if out.exists() and out.stat().st_size > 100:
                    return out
            except Exception:
                return None
        return None
    except Exception:
        return None

def _base_cmd(out_dir: Path) -> List[str]:
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-sub", "--write-auto-sub",
        "--sub-langs", "en-US,en",
        "--sub-format", "srt/best",
        "--convert-subs", "srt",
        "--sleep-requests", "3",
        "--sleep-interval", "3",
        "--max-sleep-interval", "8",
        "--retries", "15",
        "-N", "1",
        "--force-ipv4",
        "--geo-bypass",
        "-o", _srt_out_template(out_dir),
    ]
    if BROWSER_PROFILE:
        cmd += ["--cookies-from-browser", BROWSER_PROFILE]
    elif YT_COOKIES and Path(YT_COOKIES).exists():
        cmd += ["--cookies", YT_COOKIES]
    return cmd

def _download_subs_for_video(video: VideoItem) -> Dict:
    """
    Retorna un dict con {id, url, status, lang, paths} para index.
    """
    vid = video.id
    url = video.url
    out_dir = SUBS_DIR / vid
    _safe_mkdir(out_dir)

    # Limpia archivos previos del mismo id
    for f in out_dir.glob(f"Transcript [{vid}].*"):
        try:
            f.unlink()
        except IsADirectoryError:
            shutil.rmtree(f, ignore_errors=True)

    base = _base_cmd(out_dir)

    # 1) yt-dlp normal
    p1 = _run(base + [url])
    sub = _find_any_en(out_dir, vid)

    # 2) impersonate si está disponible
    if not sub and _supports_impersonate():
        for client in ["chrome", "safari15_3", "edge"]:
            p_imp = _run(base + ["--impersonate", client, url])
            sub = _find_any_en(out_dir, vid)
            if sub:
                break

    # 3) player_client alternativos si no hay --impersonate
    if not sub and not _supports_impersonate():
        for pc in ["ios", "android", "web_creator"]:
            p_pc = _run(base + ["--extractor-args", f"youtube:player_client={pc}", url])
            sub = _find_any_en(out_dir, vid)
            if sub:
                break

    # 4) Fallback API
    if not sub:
        sub_path = _fallback_yta(vid, out_dir)
        if sub_path:
            sub = str(sub_path)

    status = "ok" if sub else "missing"
    lang = None
    paths = []
    if sub:
        p = Path(sub)
        lang = p.suffix.replace(".","")  # .srt -> "srt", not ideal; get lang from filename:
        # Mejor: parsear idioma del nombre:
        # Transcript [<id>].<lang>.srt
        name = p.name
        try:
            lang = name.split("].", 1)[1].rsplit(".", 1)[0]
        except Exception:
            pass
        # agrega todos los .srt del id para registro
        for f in sorted(out_dir.glob(f"Transcript [{vid}].*.srt")):
            paths.append(str(f))

    return {
        "id": vid,
        "url": url,
        "status": status,
        "lang": lang,
        "paths": paths,
        "dir": str(out_dir),
    }

def _load_video_list() -> List[VideoItem]:
    items: List[VideoItem] = []
    if IDS_JSONL.exists():
        with open(IDS_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                vid = rec.get("id") or rec.get("video_id")
                url = rec.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else None)
                if vid and url:
                    items.append(VideoItem(id=vid, url=url))

    if items:
        return items[:MAX_VIDEOS] if MAX_VIDEOS > 0 else items

    # Fallback: intentar obtener IDs desde CHANNEL_URL (flat-playlist, sin descargar)
    if CHANNEL_URL:
        print(f"[info] IDs no encontrados en {IDS_JSONL}. Extrayendo desde CHANNEL_URL...")
        proc = _run([
            "yt-dlp",
            "--skip-download",
            "--flat-playlist",
            "--print", "%(id)s\t%(webpage_url)s",
            CHANNEL_URL
        ])
        if proc.returncode == 0 and proc.stdout:
            for line in proc.stdout.splitlines():
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    vid, url = parts
                    items.append(VideoItem(id=vid, url=url))

    return items[:MAX_VIDEOS] if (MAX_VIDEOS > 0 and items) else items

def main() -> int:
    videos = _load_video_list()
    if not videos:
        print(f"[error] No hay listado de videos. Asegúrate de correr `make ids` o definir CHANNEL_URL en .env", file=sys.stderr)
        return 1

    index_recs: List[Dict] = []
    print(f"[info] Descargando transcripts para {len(videos)} videos...")
    for v in tqdm(videos, desc="Transcripts", unit="vid"):
        try:
            rec = _download_subs_for_video(v)
            index_recs.append(rec)
            # Pequeña pausa para ser amables con YT y reducir 429:
            time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[warn] Interrumpido por usuario.")
            break
        except Exception as e:
            print(f"[warn] Error en video {v.id}: {e}", file=sys.stderr)
            index_recs.append({
                "id": v.id, "url": v.url, "status": "error", "error": str(e),
                "paths": [], "dir": str(SUBS_DIR / v.id)
            })

    # Grabar índice JSONL
    _safe_mkdir(INDEX_JSONL.parent)
    with open(INDEX_JSONL, "w", encoding="utf-8") as f:
        for rec in index_recs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Resumen
    ok = sum(1 for r in index_recs if r.get("status") == "ok")
    missing = sum(1 for r in index_recs if r.get("status") == "missing")
    errors = sum(1 for r in index_recs if r.get("status") == "error")
    print(f"[done] OK: {ok} | Missing: {missing} | Errors: {errors} | Total: {len(index_recs)}")
    return 0 if ok > 0 and errors == 0 else 0  # no fallar el proceso por algunos missing

if __name__ == "__main__":
    # Recomendación de versión de Python
    if sys.version_info < (3, 10):
        print("[warn] Se recomienda Python 3.10+ para yt-dlp moderno.", file=sys.stderr)
    sys.exit(main())
