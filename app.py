"""CONVERT. v1: Spotify-to-YouTube matching and authorized audio conversion.

FastAPI server serves its own static frontend. All uploaded/downloaded media are
short-lived temporary files. Not a Spotify audio downloader.
"""
from __future__ import annotations

import asyncio
import html
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask
from fastapi.middleware.cors import CORSMiddleware

HERE = Path(__file__).resolve().parent
WORK = Path(tempfile.gettempdir()) / "convert_jobs"
WORK.mkdir(exist_ok=True)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "90")) * 1024 * 1024
MAX_DURATION = 12 * 60  # seconds; protects the free server
JOB_TTL = 30 * 60
MAX_ACTIVE = 1
JOBS: dict[str, dict] = {}
MUTEX = threading.RLock()

app = FastAPI(title="CONVERT. Audio", docs_url=None, redoc_url=None)
# Allows optional static frontend hosted on Cloudflare Pages. Public demo backend:
# do not use for large, untrusted production traffic without auth/rate-limiting.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

class LinkInput(BaseModel):
    url: str

class SearchInput(BaseModel):
    query: str

class JobInput(BaseModel):
    url: str
    format: str
    authorized: bool


def clean_temp():
    now = time.time()
    with MUTEX:
        for ident, job in list(JOBS.items()):
            if job.get("status") == "processing":
                continue
            if now - job.get("ended", job["created"]) > JOB_TTL:
                shutil.rmtree(job["dir"], ignore_errors=True)
                del JOBS[ident]


def spotify_id(text: str) -> str | None:
    try:
        u = urlparse(text.strip())
        if u.scheme not in ("https", "http") or u.hostname not in ("open.spotify.com", "play.spotify.com"):
            return None
        m = re.fullmatch(r"/track/([A-Za-z0-9]{22})/?", u.path)
        return m.group(1) if m else None
    except Exception:
        return None


def spotify_short(text: str) -> bool:
    try:
        u = urlparse(text.strip())
        return u.scheme in ("http", "https") and u.hostname == "spotify.link" and 1 < len(u.path) < 120
    except Exception:
        return False


async def expand_spotify_short(url: str) -> str:
    # Redirect to Spotify only; do not turn this into a general-purpose URL fetcher.
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        current = url
        for _ in range(5):
            parsed = urlparse(current)
            if parsed.scheme != "https" or parsed.hostname not in ("spotify.link", "open.spotify.com"):
                break
            if spotify_id(current):
                return current
            response = await client.get(current)
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            target = response.headers.get("location", "")
            if target.startswith("/") and not target.startswith("//"):
                target = f"https://{parsed.hostname}{target}"
            current = target
    raise ValueError("Deze korte Spotify-link kon niet naar een track worden omgezet")


def youtube_id(text: str) -> str | None:
    try:
        u = urlparse(text.strip())
        if u.scheme not in ("https", "http"):
            return None
        host = (u.hostname or "").lower()
        if host == "youtu.be":
            ident = u.path.strip("/").split("/")[0]
        elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            if u.path in ("/watch", "/watch/"):
                ident = parse_qs(u.query).get("v", [""])[0]
            elif u.path.startswith(("/shorts/", "/live/")):
                ident = u.path.split("/")[2]
            else:
                return None
        else:
            return None
        return ident if re.fullmatch(r"[A-Za-z0-9_-]{11}", ident) else None
    except Exception:
        return None


def ytdlp_options() -> dict:
    return {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 22, "retries": 2,
            "fragment_retries": 2, "skip_unavailable_fragments": False, "ignoreerrors": False, "nocheckcertificate": False}


def format_seconds(seconds: float | None) -> str:
    if not seconds:
        return ""
    n = int(seconds)
    return f"{n//60}:{n%60:02d}"


def public_video(info: dict) -> dict | None:
    ident = info.get("id") or ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", ident):
        return None
    dur = info.get("duration")
    return {
        "id": ident,
        "title": str(info.get("title") or "YouTube-video")[:180],
        "channel": str(info.get("channel") or info.get("uploader") or "YouTube")[:100],
        "duration": int(dur) if dur else None,
        "time": format_seconds(dur),
        "thumbnail": f"https://i.ytimg.com/vi/{ident}/mqdefault.jpg",
        "url": f"https://www.youtube.com/watch?v={ident}",
    }


def search_videos(query: str) -> list[dict]:
    from yt_dlp import YoutubeDL
    with YoutubeDL({**ytdlp_options(), "extract_flat": "in_playlist", "skip_download": True}) as ydl:
        result = ydl.extract_info("ytsearch7:" + query, download=False)
    choices = [public_video(x) for x in (result.get("entries") or []) if isinstance(x, dict)]
    videos = [x for x in choices if x is not None]
    # Choose official/audio first over covers, karaoke, sped-up or live recordings.
    terms = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
    undesired = {"cover", "karaoke", "slowed", "nightcore", "sped", "reaction", "instrumental", "live", "remix"}
    def score(v):
        title = v["title"].lower()
        found = {t for t in re.findall(r"[a-z0-9]+", title) if len(t) > 2}
        covered = len(terms & found)
        unwanted = sum(1 for t in undesired if t in found and t not in terms)
        official = int("official" in found or "topic" in v["channel"].lower())
        return covered * 7 + official * 2 - unwanted * 9
    return sorted(videos, key=score, reverse=True)[:5]


@app.get("/")
def index():
    return FileResponse(HERE / "index.html", media_type="text/html")


@app.get("/api/health")
def health():
    return {"ok": True, "name": "CONVERT.", "version": "1.0", "max_minutes": MAX_DURATION // 60}


@app.post("/api/resolve")
async def resolve(body: LinkInput):
    sid = spotify_id(body.url)
    if not sid and spotify_short(body.url):
        try:
            sid = spotify_id(await expand_spotify_short(body.url))
        except Exception as exc:
            raise HTTPException(400, "Deze korte Spotify-link werkt niet. Kopieer de volledige tracklink uit Spotify.") from exc
    vid = youtube_id(body.url)
    if sid:
        # Public oEmbed endpoint returns track title/cover, NOT Spotify audio.
        url = f"https://open.spotify.com/track/{sid}"
        try:
            async with httpx.AsyncClient(timeout=16, follow_redirects=False) as client:
                r = await client.get("https://open.spotify.com/oembed", params={"url": url})
                r.raise_for_status()
                data = r.json()
            title = str(data.get("title") or "")[:200].strip()
            # Embedded title sometimes includes the artist while the plain oEmbed title doesn't.
            match = re.search(r'title=["\']Spotify Embed: ([^"\']+)', str(data.get("html") or ""))
            query_text = html.unescape(match.group(1))[:180].strip() if match else title
            if not title:
                raise ValueError("Geen titel ontvangen")
            return {"source": "spotify", "title": title, "artwork": data.get("thumbnail_url"),
                    "query": query_text + " official audio", "spotify_url": url}
        except Exception as exc:
            raise HTTPException(502, "Spotify kan het nummer momenteel niet herkennen. Probeer later opnieuw of zoek handmatig op titel en artiest.") from exc
    if vid:
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({**ytdlp_options(), "skip_download": True}) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, f"https://www.youtube.com/watch?v={vid}", False)
            if not info:
                raise ValueError("Geen video gevonden")
            result = public_video(info)
            if not result:
                raise ValueError("Geen geldige video gevonden")
            return {"source": "youtube", "video": result}
        except Exception as exc:
            raise HTTPException(502, "YouTube laat deze video niet ophalen vanaf de server. Probeer een ander nummer of upload je eigen bestand.") from exc
    raise HTTPException(400, "Gebruik een Spotify-tracklink of YouTube-videolink.")


@app.post("/api/search")
async def search(body: SearchInput):
    q = body.query.strip()
    if not (2 <= len(q) <= 160):
        raise HTTPException(400, "Vul een zoekopdracht van 2–160 tekens in.")
    try:
        videos = await asyncio.wait_for(asyncio.to_thread(search_videos, q), timeout=42)
        if not videos:
            raise HTTPException(404, "Geen YouTube-resultaten gevonden. Je kunt ook een videolink plakken.")
        return {"videos": videos}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, "YouTube-zoekopdracht mislukt op deze gratis server. Open de zoekresultaten rechtstreeks op YouTube of probeer het later.") from exc


def reserve_job() -> dict:
    clean_temp()
    with MUTEX:
        if sum(j.get("status") == "processing" for j in JOBS.values()) >= MAX_ACTIVE:
            raise HTTPException(429, "Er wordt al een nummer verwerkt. Probeer het over een minuut opnieuw.")
        key = uuid.uuid4().hex
        workdir = WORK / key
        workdir.mkdir(mode=0o700)
        job = {"id": key, "created": time.time(), "dir": workdir, "status": "processing", "phase": "In wachtrij...", "kind": "", "result": ""}
        JOBS[key] = job
    return job


def update(job: dict, phase: str):
    with MUTEX:
        job["phase"] = phase


def finish(job: dict, *, result: Path | None = None, message: str = ""):
    with MUTEX:
        if result:
            job["status"] = "complete"
            job["result"] = str(result)
            job["phase"] = "Klaar om te downloaden"
        else:
            job["status"] = "error"
            job["phase"] = message[:320] if message else "Conversie mislukt"
        job["ended"] = time.time()


def safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\- .()]+", "", name, flags=re.UNICODE)
    name = name.strip(" ._- ")[:85]
    return name or "CONVERT-audio"


def ffmpeg_convert(source: Path, target: Path, fmt: str):
    if fmt == "mp3":
        flags = ["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100", "-ac", "2"]
    elif fmt == "flac":
        flags = ["-c:a", "flac", "-sample_fmt", "s32", "-bits_per_raw_sample", "24", "-ar", "44100", "-ac", "2"]
    else:
        raise ValueError("Ongeldig formaat")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(source), "-map", "0:a:0", "-vn", *flags, str(target)]
    try:
        subprocess.run(cmd, timeout=300, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("FFmpeg is niet geïnstalleerd op de server.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Conversie duurt te lang voor deze gratis server.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("FFmpeg kan dit audioformaat niet converteren. " + (exc.stderr or "").strip()[-120:])
    if not target.exists() or target.stat().st_size < 1000:
        raise RuntimeError("De converter heeft geen geldig audiobestand gemaakt.")


def ffprobe_duration(path: Path) -> float | None:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
        duration = float(p.stdout.strip())
        return duration if duration > 0 else None
    except Exception:
        return None


def run_upload(job: dict, path: Path, name: str, fmt: str):
    try:
        update(job, "Audiobestand controleren...")
        duration = ffprobe_duration(path)
        if duration is not None and duration > MAX_DURATION:
            raise RuntimeError("Dit bestand is langer dan 12 minuten. Kies een kortere opname.")
        update(job, f"Audio omzetten naar {fmt.upper()}...")
        target = job["dir"] / f"{safe_filename(Path(name).stem)}.{fmt}"
        ffmpeg_convert(path, target, fmt)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        finish(job, result=target)
    except Exception as exc:
        finish(job, message=str(exc))


def run_youtube(job: dict, url: str, fmt: str):
    try:
        from yt_dlp import YoutubeDL
        update(job, "YouTube-video controleren...")
        options = {**ytdlp_options(), "format": "bestaudio[ext=m4a]/bestaudio/best", "outtmpl": str(job["dir"] / "source.%(ext)s"),
                   "max_filesize": MAX_UPLOAD_BYTES, "restrictfilenames": True}
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise RuntimeError("Deze video is niet beschikbaar.")
            duration = info.get("duration")
            if duration and duration > MAX_DURATION:
                raise RuntimeError("YouTube-video is langer dan 12 minuten. Kies een kortere video.")
            title = str(info.get("title") or "YouTube-audio")
            update(job, "Audio ophalen van YouTube...")
            ydl.download([url])
        sources = [f for f in job["dir"].iterdir() if f.is_file() and f.name.startswith("source.")]
        if not sources:
            raise RuntimeError("YouTube leverde geen downloadbaar audiobestand op.")
        src = max(sources, key=lambda f: f.stat().st_size)
        if src.stat().st_size > MAX_UPLOAD_BYTES:
            raise RuntimeError("YouTube-bestand is te groot voor de gratis server.")
        update(job, f"Audio omzetten naar {fmt.upper()}...")
        out = job["dir"] / f"{safe_filename(title)}.{fmt}"
        ffmpeg_convert(src, out, fmt)
        src.unlink(missing_ok=True)
        finish(job, result=out)
    except Exception:
        # Avoid echoing potentially sensitive network details and shell errors to visitors.
        finish(job, message="YouTube blokkeert deze server of de download/conversie is mislukt. Probeer een ander nummer of upload een eigen videobestand.")


@app.post("/api/jobs/url")
async def create_from_url(body: JobInput):
    if body.format not in ("mp3", "flac"):
        raise HTTPException(400, "Kies MP3 of FLAC.")
    if not body.authorized:
        raise HTTPException(400, "Bevestig dat je deze video mag downloaden en converteren.")
    ident = youtube_id(body.url)
    if not ident:
        raise HTTPException(400, "Kies eerst een geldige YouTube-video. Spotify-audio wordt niet gedownload.")
    job = reserve_job()
    canonical = f"https://www.youtube.com/watch?v={ident}"
    threading.Thread(target=run_youtube, args=(job, canonical, body.format), daemon=True).start()
    return {"id": job["id"]}


@app.post("/api/jobs/upload")
async def create_from_upload(file: UploadFile = File(...), format: str = Form(...), authorized: str = Form(...)):
    if format not in ("mp3", "flac"):
        raise HTTPException(400, "Kies MP3 of FLAC.")
    if authorized != "true":
        raise HTTPException(400, "Bevestig dat je dit bestand mag converteren.")
    if not file.filename:
        raise HTTPException(400, "Geen bestand gekozen.")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".mp3", ".mp4", ".mov", ".wav", ".m4a", ".flac", ".aac", ".webm", ".ogg", ".opus", ".mkv"):
        raise HTTPException(400, "Dit bestandstype wordt niet ondersteund.")
    job = reserve_job()
    uploaded = job["dir"] / ("upload" + ext)
    total = 0
    try:
        with open(uploaded, "wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Bestand is groter dan de limiet van 90 MB.")
                output.write(chunk)
        if total < 100:
            raise HTTPException(400, "Bestand is leeg of ongeldig.")
        threading.Thread(target=run_upload, args=(job, uploaded, file.filename, format), daemon=True).start()
        return {"id": job["id"]}
    except Exception:
        with MUTEX:
            JOBS.pop(job["id"], None)
        shutil.rmtree(job["dir"], ignore_errors=True)
        raise
    finally:
        await file.close()


@app.get("/api/jobs/{ident}")
def job_status(ident: str):
    clean_temp()
    with MUTEX:
        job = JOBS.get(ident)
        if not job:
            raise HTTPException(404, "Taak niet gevonden. Probeer opnieuw.")
        return {"id": ident, "status": job["status"], "phase": job["phase"], "download": f"/api/jobs/{ident}/download" if job["status"] == "complete" else None}


@app.get("/api/jobs/{ident}/download")
def download(ident: str):
    clean_temp()
    with MUTEX:
        job = JOBS.get(ident)
        if not job or job["status"] != "complete":
            raise HTTPException(404, "Dit bestand is nog niet klaar of is verlopen.")
        file = Path(job["result"])
    if not file.is_file() or file.parent != job["dir"]:
        raise HTTPException(404, "Bestand niet meer beschikbaar.")
    media = "audio/flac" if file.suffix == ".flac" else "audio/mpeg"
    return FileResponse(file, media_type=media, filename=file.name)
