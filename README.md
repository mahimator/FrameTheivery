# FrameTheivery

Self-hosted bulk media URL downloader and archive manager.

## Product scope
- Bulk ingestion of direct media URLs that the operator is authorized to download.
- Persistent job queue with configurable concurrency, retries, per-file progress and batch status.
- Safe URL validation, redirect validation and SSRF protections.
- Local persistent storage, metadata extraction, checksums and batch ZIP export.
- YouTube uploads: use Google Takeout / YouTube Studio exports for content you own. This application does not extract protected YouTube streams or bypass YouTube download controls. Import the exported archive through the archive-import workflow (planned in the ingestion service).

## Stack
- React + Vite frontend (Netlify-compatible)
- FastAPI API
- PostgreSQL + Redis
- RQ workers
- Docker Compose
- Caddy reverse proxy (deployment host)

## Development
1. Copy `.env.example` to `.env` and set strong secrets.
2. `docker compose up --build`
3. API docs: `http://localhost:8000/docs`
4. Frontend: `http://localhost:5173`

The frontend uses `VITE_API_BASE_URL`. Never expose the API, database or Redis without authentication and TLS.

## Deployment
Netlify can host the frontend only. Run the API, Redis, PostgreSQL and workers on a VPS or other persistent server. Configure the Netlify environment variable `VITE_API_BASE_URL` to the public HTTPS API origin.

## Security
Only download URLs you own or are authorized to retrieve. The downloader rejects localhost/private-network targets and validates redirects to reduce SSRF risk. Put the service behind HTTPS and authentication before exposing it publicly.
