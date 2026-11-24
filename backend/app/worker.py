import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from rq import get_current_job

from .config import DOWNLOAD_DIR, MAX_DOWNLOAD_BYTES
from .security import validate_public_url

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

def download_media(job_id: str, url: str) -> dict:
    validate_public_url(url)
    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(urlparse(url).path)
    target = job_dir / filename
    temp = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    downloaded = 0
    total = None
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
                    content_type = response.headers.get("content-type", "")
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
                            digest.update(chunk)
                            out.write(chunk)
                            set_progress(downloaded, total)
                    break
            else:
                raise ValueError("Too many redirects.")

        temp.replace(target)
        set_progress(downloaded, total or downloaded, "complete")
        return {
            "path": str(target),
            "filename": target.name,
            "bytes": downloaded,
            "sha256": digest.hexdigest(),
            "content_type": content_type,
        }
    except Exception:
        temp.unlink(missing_ok=True)
        raise
