import hashlib
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse
import httpx
from .config import DOWNLOAD_DIR, MAX_DOWNLOAD_BYTES
from .security import validate_public_url

def safe_filename(value: str) -> str:
    value = unquote(value).split("/")[-1].split("?")[0]
    value = re.sub(r"[^A-Za-z0-9._() -]", "_", value).strip(" .")
    return (value[:160] or "download.bin")

def download_media(job_id: str, url: str) -> dict:
    validate_public_url(url)
    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    filename = safe_filename(parsed.path)
    target = job_dir / filename
    temp = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    downloaded = 0

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
                with temp.open("wb") as out:
                    for chunk in response.iter_bytes(1024 * 1024):
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if MAX_DOWNLOAD_BYTES and downloaded > MAX_DOWNLOAD_BYTES:
                            raise ValueError("Download exceeds configured size limit.")
                        digest.update(chunk)
                        out.write(chunk)
                break
        else:
            raise ValueError("Too many redirects.")

    temp.replace(target)
    return {"path": str(target), "filename": target.name, "bytes": downloaded, "sha256": digest.hexdigest()}
