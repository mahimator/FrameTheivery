import secrets
import uuid
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from typing import Annotated

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from rq.job import Job

from .config import API_TOKEN, CORS_ORIGINS, MAX_URLS_PER_BATCH, DOWNLOAD_DIR
from .queue import download_queue
from .security import validate_public_url, UnsafeURL

app = FastAPI(title="FrameTheivery API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

def require_auth(authorization: Annotated[str | None, Header()] = None):
    if not API_TOKEN:
        raise HTTPException(503, "API_TOKEN is not configured.")
    expected = f"Bearer {API_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, "Authentication required.")

class URLBatch(BaseModel):
    urls: list[str] = Field(min_length=1)
    concurrency: int = Field(default=3, ge=1, le=5)

def serialize_job(job: Job) -> dict:
    status = job.get_status(refresh=True)
    return {
        "id": job.id,
        "batch_id": job.meta.get("batch_id"),
        "url": job.args[1] if len(job.args) > 1 else None,
        "status": status,
        "progress": job.meta.get("progress"),
        "downloaded_bytes": job.meta.get("downloaded_bytes", 0),
        "total_bytes": job.meta.get("total_bytes"),
        "phase": job.meta.get("phase", status),
        "result": job.result if status == "finished" else None,
        "error": str(job.exc_info)[-1200:] if status == "failed" and job.exc_info else None,
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "frametheivery-api"}

@app.post("/api/v1/batches", dependencies=[Depends(require_auth)])
def create_batch(payload: URLBatch):
    if len(payload.urls) > MAX_URLS_PER_BATCH:
        raise HTTPException(413, f"Maximum {MAX_URLS_PER_BATCH} URLs per batch.")
    batch_id = str(uuid.uuid4())
    accepted, rejected = [], []
    for raw in payload.urls:
        url = raw.strip()
        if not url:
            continue
        try:
            validate_public_url(url)
            accepted.append(url)
        except (UnsafeURL, ValueError) as exc:
            rejected.append({"url": url, "error": str(exc)})
    if not accepted:
        raise HTTPException(422, detail={"message": "No valid public media URLs.", "rejected": rejected})

    redis = download_queue.connection
    jobs = []
    for url in accepted:
        job_id = str(uuid.uuid4())
        job = download_queue.enqueue(
            "app.worker.download_media", job_id, url, job_id=job_id,
            result_ttl=604800, failure_ttl=604800,
        )
        job.meta["batch_id"] = batch_id
        job.save_meta()
        redis.sadd("ft:all_jobs", job.id)
        redis.sadd(f"ft:batch:{batch_id}", job.id)
        jobs.append({"id": job.id, "batch_id": batch_id, "url": url, "status": "queued"})
    return {"batch_id": batch_id, "accepted": jobs, "rejected": rejected}

@app.get("/api/v1/jobs", dependencies=[Depends(require_auth)])
def list_jobs():
    redis = download_queue.connection
    ids = redis.smembers("ft:all_jobs")
    jobs = []
    for raw_id in ids:
        job_id = raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id)
        try:
            jobs.append(serialize_job(Job.fetch(job_id, connection=redis)))
        except Exception:
            redis.srem("ft:all_jobs", job_id)
    jobs.sort(key=lambda item: item["id"], reverse=True)
    return {"jobs": jobs}

@app.get("/api/v1/jobs/{job_id}", dependencies=[Depends(require_auth)])
def get_job(job_id: str):
    try:
        return serialize_job(Job.fetch(job_id, connection=download_queue.connection))
    except Exception:
        raise HTTPException(404, "Job not found.")

@app.post("/api/v1/jobs/{job_id}/retry", dependencies=[Depends(require_auth)])
def retry_job(job_id: str):
    redis = download_queue.connection
    try:
        original = Job.fetch(job_id, connection=redis)
    except Exception:
        raise HTTPException(404, "Job not found.")
    if not original.is_failed:
        raise HTTPException(409, "Only failed jobs can be retried.")
    original_url = original.args[1]
    validate_public_url(original_url)
    batch_id = original.meta.get("batch_id") or str(uuid.uuid4())
    new_id = str(uuid.uuid4())
    job = download_queue.enqueue(
        "app.worker.download_media", new_id, original_url, job_id=new_id,
        result_ttl=604800, failure_ttl=604800,
    )
    job.meta["batch_id"] = batch_id
    job.save_meta()
    redis.sadd("ft:all_jobs", new_id)
    redis.sadd(f"ft:batch:{batch_id}", new_id)
    return {"id": new_id, "batch_id": batch_id, "status": "queued"}

@app.get("/api/v1/jobs/{job_id}/file", dependencies=[Depends(require_auth)])
def download_job_file(job_id: str):
    try:
        job = Job.fetch(job_id, connection=download_queue.connection)
    except Exception:
        raise HTTPException(404, "Job not found.")
    if not job.is_finished or not job.result:
        raise HTTPException(409, "This transfer is not complete.")
    path = Path(job.result["path"]).resolve()
    if DOWNLOAD_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "Saved media file is unavailable.")
    return FileResponse(path, filename=job.result["filename"], media_type="application/octet-stream")

@app.get("/api/v1/batches/{batch_id}/archive", dependencies=[Depends(require_auth)])
def download_batch_archive(batch_id: str):
    redis = download_queue.connection
    ids = redis.smembers(f"ft:batch:{batch_id}")
    if not ids:
        raise HTTPException(404, "Batch not found.")
    jobs = []
    for raw_id in ids:
        job_id = raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id)
        try:
            jobs.append(Job.fetch(job_id, connection=redis))
        except Exception:
            continue
    if not jobs or any(not job.is_finished for job in jobs):
        raise HTTPException(409, "Wait until every transfer in this batch has finished.")
    export_dir = DOWNLOAD_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    archive_path = export_dir / f"{batch_id}.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for job in jobs:
            result = job.result or {}
            path = Path(result.get("path", "")).resolve()
            if DOWNLOAD_DIR.resolve() in path.parents and path.is_file():
                archive.write(path, arcname=result.get("filename", path.name))
    return FileResponse(archive_path, filename=f"frametheivery-{batch_id}.zip", media_type="application/zip")

@app.get("/api/v1/config", dependencies=[Depends(require_auth)])
def config():
    return {
        "max_urls_per_batch": MAX_URLS_PER_BATCH,
        "supported_sources": ["direct-http-media"],
        "youtube": "For your own uploads, import the export downloaded through Google Takeout or YouTube Studio.",
    }
