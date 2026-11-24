# FrameTheivery

Self-hosted bulk media URL downloader and archive manager.

## Current capabilities
- Paste up to 200 direct HTTP(S) media URLs per batch.
- Persistent Redis/RQ job queue with parallel workers.
- Per-file transfer progress, status and error reporting.
- Retry failed transfers.
- SHA-256 checksums and file sizes.
- Individual file downloads and batch ZIP exports.
- URL and redirect validation, private-network destination rejection.
- Docker Compose deployment and Netlify-compatible frontend.

## Source support
The downloader accepts direct media-file URLs, not ordinary YouTube watch-page URLs. For your own YouTube uploads, obtain an export through [Google Takeout](https://takeout.google.com/) or YouTube Studio. YouTube page URL extraction is intentionally not implemented because this service must not bypass YouTube's download controls or platform restrictions. A dedicated Takeout archive importer is a separate integration.

## Stack
- React + Vite frontend
- FastAPI API
- Redis + RQ persistent job queue
- Python workers using HTTPX streaming
- Docker Compose

## Local development
1. Copy `.env.example` to `.env`.
2. Replace `API_TOKEN` with a long random secret.
3. Set `CORS_ORIGINS` to the frontend origin.
4. Run `docker compose up --build`.
5. Open `http://localhost:5173`.

API health: `http://localhost:8000/health`  
API docs: `http://localhost:8000/docs`

## Server deployment
Run the API, Redis and workers on a persistent VPS with Docker Compose. The compose worker service starts the number of processes configured by `MAX_CONCURRENT_DOWNLOADS` (default 3). Mount persistent storage for `/data`. Put the API behind HTTPS and configure a strong `API_TOKEN`.

Netlify hosts the frontend only. Connect this repository to a Netlify site with:
- Base directory: `frontend`
- Build command: `npm run build`
- Publish directory: `dist`
- Environment variable: `VITE_API_BASE_URL=https://YOUR-API-HOST`

Also set `CORS_ORIGINS` on the API server to the exact Netlify origin.

## Important security notes
Only download content you own or are authorized to retrieve. The service rejects localhost, private and reserved IP destinations and revalidates redirect targets. Do not expose Redis or the worker service publicly. Use HTTPS, keep the API token secret, and configure sensible storage quotas before opening the service to the internet.
