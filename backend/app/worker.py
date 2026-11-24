import hashlib
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
import yt_dlp
from rq import get_current_job

from .config import DOWNLOAD_DIR, MAX_DOWNLOAD_BYTES
from .security import validate_public_url

YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be", "www.youtube-nocookie.com",
}

def is_youtube_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host in YOUTUBE_HOSTS

def safe_filename(value: str) -> str:
    value = unquote(value).split("/")[-1].split("?")[0]
    value = re.sub(r"[^A-Za-z0-9._() -]", "_", value).strip(" .")
    return (value[:160] or "download.bin")

def set_progress(downloaded: int, total: int | None, phase: str = "downloading") -> None:
    job = get_current_job()
    if job is None:
        return
    job.meta.update({
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "progress": round(downloaded / total * 100, 1) if total else None,
        "phase": phase,
    })
    job.save_meta()

def file_result(path: Path, content_type: str | None = None) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    size = path.stat().st_size
    set_progress(size, size, "complete")
    return {
        "path": str(path),
        "filename": path.name,
        "bytes": size,
        "sha256": digest.hexdigest(),
        "content_type": content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    }

def download_youtube(job_dir: Path, url: str) -> dict:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if host not in YOUTUBE_HOSTS:
        raise ValueError("Only public YouTube watch-page URLs are accepted by the YouTube extractor.")

    set_progress(0, None, "extracting")
    def progress_hook(data: dict) -> None:
        status = data.get("status")
        if status == "downloading":
            downloaded = int(data.get("downloaded_bytes") or 0)
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            total = int(total) if total else None
            if MAX_DOWNLOAD_BYTES and downloaded > MAX_DOWNLOAD_BYTES:
                raise yt_dlp.utils.DownloadError("Download exceeds configured size limit.")
            set_progress(downloaded, total, "downloading")
        elif status == "finished":
            set_progress(int(data.get("downloaded_bytes") or 0), None, "processing")

    options = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(job_dir / "%(title).160B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "trim_file_name": 180,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "continuedl": True,
        "overwrites": False,
        "progress_hooks": [progress_hook],
    }
    if MAX_DOWNLOAD_BYTES:
        options["max_filesize"] = MAX_DOWNLOAD_BYTES

    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)

    candidates = [
        item for item in job_dir.iterdir()
        if item.is_file() and not item.name.endswith((".part", ".ytdl", ".temp"))
    ]
    if not candidates:
        raise RuntimeError("YouTube reported completion but no media file was produced.")
    output = max(candidates, key=lambda item: item.stat().st_mtime)
    return file_result(output)

def download_direct(job_dir: Path, url: str) -> dict:
    filename = safe_filename(urlparse(url).path)
    target = job_dir / filename
    temp = target.with_suffix(target.suffix + ".part")
    downloaded = 0
    total = None
    content_type = "application/octet-stream"
    set_progress(0, None, "connecting")

    try:
        with httpx.Client(follow_redirects=False, timeout=httpx.Timeout(30.0, read=120.0)) as client:
            current = url
            for _ in range(6):
                validate_public_url(current)
                with client.stream("GET", current, headers={"User-Agent": "FrameTheivery/1.0"}) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            response.raise_for_status()
                        current = str(response.url.join(location))
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "application/octet-stream")
                    if "text/html" in content_type.lower():
                        raise ValueError("URL returned an HTML page, not a direct media file.")
                    raw_length = response.headers.get("content-length")
                    total = int(raw_length) if raw_length and raw_length.isdigit() else None
                    if MAX_DOWNLOAD_BYTES and total and total > MAX_DOWNLOAD_BYTES:
                        raise ValueError("Download exceeds configured size limit.")
                    with temp.open("wb") as out:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if not chunk:
                                continue
                            downloaded += len(chunk)
                            if MAX_DOWNLOAD_BYTES and downloaded > MAX_DOWNLOAD_BYTES:
                                raise ValueError("Download exceeds configured size limit.")
                            out.write(chunk)
                            set_progress(downloaded, total)
                    break
            else:
                raise ValueError("Too many redirects.")

        temp.replace(target)
        return file_result(target, content_type)
    except Exception:
        temp.unlink(missing_ok=True)
        raise

def download_media(job_id: str, url: str) -> dict:
    validate_public_url(url)
    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    if is_youtube_url(url):
        return download_youtube(job_dir, url)
    return download_direct(job_dir, url)
