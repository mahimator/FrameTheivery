# FrameTheivery

Self-hosted bulk media downloader and archive manager.

## Current capabilities
- Paste up to 200 public YouTube watch-page URLs or direct HTTP(S) media URLs per batch.
- Extract public YouTube video streams with yt-dlp, including separate video/audio streams merged with FFmpeg when available.
- Persistent Redis/RQ job queue with parallel workers.
- Per-file transfer progress, status and error reporting.
- Retry failed transfers.
- SHA-256 checksums and file sizes.
- Individual file downloads and batch ZIP exports.
- URL validation and private-network destination rejection for submitted URLs.
- Docker Compose deployment and Netlify-compatible frontend.

## YouTube source support
YouTube watch-page URLs are handled by yt-dlp without signing into the old channel. The video must be publicly playable to the server. Private, deleted, members-only, age-restricted or otherwise restricted videos may fail. The downloaded file is the best stream YouTube makes available to the public extractor, not necessarily the original upload master.

Only use this feature for videos you own or have permission to download. Third-party downloading can conflict with YouTube's terms, so account recovery and official YouTube export tools remain the preferred recovery route when available. This project does not attempt to defeat DRM, paywalls, private-video restrictions or other access controls.

## Stack
- React + Vite frontend
- FastAPI API
- Redis + RQ persistent job queue
- Python workers using yt-dlp and HTTPX
- FFmpeg for merging separate audio/video streams
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

## Important operational notes
- Keep yt-dlp updated because YouTube changes its player and extraction behaviour.
- Configure sensible storage quotas. Video files can be large.
- Do not expose Redis or the worker service publicly.
- Use HTTPS and keep the API token secret.
