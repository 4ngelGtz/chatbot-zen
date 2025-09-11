# tests/test_transcripts_enus.py
import os
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

VIDEO_ID = os.getenv("TEST_VIDEO_ID", "YRmc0-dlDgM")
VIDEO_URL = os.getenv("TEST_VIDEO_URL", f"https://www.youtube.com/watch?v={VIDEO_ID}")
OUT_DIR = Path("data/tests/enus")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_TEMPLATE = str(OUT_DIR / "Transcript [%(id)s].%(ext)s")

def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)

def _supports_impersonate() -> bool:
    h = _run(["yt-dlp", "--help"])
    return "--impersonate" in (h.stdout + h.stderr)

def _base_cmd():
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
        "-o", OUTPUT_TEMPLATE,
    ]
    browser_profile = os.getenv("BROWSER_PROFILE")  # ej. chrome:Profile 1
    cookies_file = os.getenv("YT_COOKIES")
    if browser_profile:
        cmd += ["--cookies-from-browser", browser_profile]
    elif cookies_file and os.path.exists(cookies_file):
        cmd += ["--cookies", cookies_file]
    return cmd

def _sub_path(lang: str) -> Path:
    return OUT_DIR / f"Transcript [{VIDEO_ID}].{lang}.srt"

def _find_sub() -> str | None:
    for lang in ("en-US", "en"):
        p = _sub_path(lang)
        if p.exists() and p.stat().st_size > 100:
            return str(p)
    return None

def _write_srt_file(out_path: Path, transcript: list[dict]) -> None:
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

def _fallback_yta() -> str | None:
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
        )
        # en-US -> en
        for lang in ["en-US", "en"]:
            try:
                tr = YouTubeTranscriptApi.get_transcript(VIDEO_ID, languages=[lang])
                out = _sub_path(lang)
                _write_srt_file(out, tr)
                if out.exists() and out.stat().st_size > 100:
                    return str(out)
            except (NoTranscriptFound, TranscriptsDisabled):
                pass

        # traducir a 'en'
        try:
            listing = YouTubeTranscriptApi.list_transcripts(VIDEO_ID)
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
            out = _sub_path("en")
            _write_srt_file(out, translated)
            if out.exists() and out.stat().st_size > 100:
                return str(out)
        except Exception:
            try:
                fetched = candidate.fetch()
                out = OUT_DIR / f"Transcript [{VIDEO_ID}].{candidate.language}.srt"
                _write_srt_file(out, fetched)
                if out.exists() and out.stat().st_size > 100:
                    return str(out)
            except Exception:
                return None
        return None
    except Exception:
        return None

def test_download_transcript_enus():
    # limpiar salidas previas del mismo ID
    for f in OUT_DIR.glob(f"Transcript [{VIDEO_ID}].*"):
        try: f.unlink()
        except IsADirectoryError: shutil.rmtree(f, ignore_errors=True)

    base = _base_cmd()

    # (0) Diagnóstico: listar subtítulos
    ls = _run(["yt-dlp", "--list-subs", VIDEO_URL])
    print("---- LIST SUBS ----\n", ls.stdout or ls.stderr)

    # (1) yt-dlp normal (web)
    p1 = _run(base + [VIDEO_URL])
    sub_file = _find_sub()

    # (2) probar impersonations si están disponibles
    if (not sub_file) and _supports_impersonate():
        for client in ["chrome", "safari15_3", "edge"]:
            p_imp = _run(base + ["--impersonate", client, VIDEO_URL])
            sub_file = _find_sub()
            if sub_file:
                break

    # (3) probar player_client alternativos si no hay --impersonate
    if not sub_file and not _supports_impersonate():
        for pc in ["ios", "android", "web_creator"]:
            p_pc = _run(base + ["--extractor-args", f"youtube:player_client={pc}", VIDEO_URL])
            sub_file = _find_sub()
            if sub_file:
                break

    # (4) Fallback API
    if not sub_file:
        sub_file = _fallback_yta()

    if not sub_file:
        print("\n---- YT-DLP WEB STDOUT ----\n", p1.stdout)
        print("\n---- YT-DLP WEB STDERR ----\n", p1.stderr)
        print("\n---- LIST SUBS (again) ----\n", ls.stdout or ls.stderr)

    assert sub_file is not None, "No se descargó ni pudo reconstruirse el transcript en-US/en"
    assert Path(sub_file).stat().st_size > 100, "El transcript está vacío o muy pequeño"