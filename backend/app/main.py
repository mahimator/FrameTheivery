import secrets
import uuid
from typing import Annotated
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field
from .config import API_TOKEN, CORS_ORIGINS, MAX_URLS_PER_BATCH
from .queue import download_queue
from .security import validate_public_url, UnsafeURL

app = FastAPI(title="FrameTheivery API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False, allow_methods=["GET","POST","DELETE"], allow_headers=["Authorization","Content-Type"])

def require_auth(authorization: Annotated[str | None, Header()] = None):
    if not API_TOKEN:
        raise HTTPException(503, "API_TOKEN is not configured.")
    expected = f"Bearer {API_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, "Authentication required.")

class URLBatch(BaseModel):
    urls: list[str] = Field(min_length=1)
    concurrency: int = Field(default=3, ge=1, le=5)

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
    jobs = []
    for url in accepted:
        job_id = str(uuid.uuid4())
        job = download_queue.enqueue("app.worker.download_media", job_id, url, job_id=job_id, result_ttl=86400, failure_ttl=604800)
        jobs.append({"id": job.id, "batch_id": batch_id, "url": url, "status": "queued"})
    return {"batch_id": batch_id, "accepted": jobs, "rejected": rejected}

@app.get("/api/v1/jobs", dependencies=[Depends(require_auth)])
def list_jobs():
    queued = []
    for job in download_queue.get_jobs():
        queued.append({"id": job.id, "status": job.get_status(), "result": job.result if job.is_finished else None, "error": str(job.exc_info)[-1000:] if job.is_failed else None})
    return {"jobs": queued}

@app.get("/api/v1/jobs/{job_id}", dependencies=[Depends(require_auth)])
def get_job(job_id: str):
    from rq.job import Job
    try:
        job = Job.fetch(job_id, connection=download_queue.connection)
    except Exception:
        raise HTTPException(404, "Job not found.")
    return {"id": job.id, "status": job.get_status(), "result": job.result if job.is_finished else None, "error": str(job.exc_info)[-1000:] if job.is_failed else None}

@app.get("/api/v1/config", dependencies=[Depends(require_auth)])
def config():
    return {"max_urls_per_batch": MAX_URLS_PER_BATCH, "supported_sources": ["direct-http-media"], "youtube": "Import your own uploads through Google Takeout or YouTube Studio exports."}
