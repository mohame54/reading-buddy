# Reading Buddy Frontend

Vite + React + TypeScript SPA for the Reading Buddy admin panel and user reading app.

## Routes

| Path | Mode |
|------|------|
| `/` | Landing page |
| `/admin` | Admin dashboard |
| `/admin/upload` | Upload wizard |
| `/admin/docs/:docId` | Document detail |
| `/users` | Library |
| `/users/read/:docId` | Reader |
| `/users/score` | Score screen |

## Local development

1. Copy environment file:

```bash
cp .env.example .env
```

2. Start the backend API on port 8080 with CORS enabled:

```bash
export CORS_ORIGINS=http://localhost:5173
uvicorn main:app --host 0.0.0.0 --port 8080
```

3. Install and run the frontend:

```bash
npm install
npm run dev
```

Open http://localhost:5173 — use `/admin` for admin mode and `/users` for the reading app.

## Build

```bash
npm run build
npm run preview
```

## Cloud Run deployment

The frontend deploys as Cloud Run service `reading-buddy-web` using nginx.

1. Update `_VITE_API_BASE` and `_VITE_WS_BASE` in the repo root [`cloudbuild.yaml`](../cloudbuild.yaml) to point at your backend API URL.
2. Set the backend `CORS_ORIGINS` to your frontend Cloud Run origin (e.g. `https://reading-buddy-web-xxxxx.run.app`).
3. Deploy from the repo root:

```bash
gcloud builds submit --config cloudbuild.yaml .
```

The root [`Dockerfile`](../Dockerfile) builds `frontend/` and serves the static SPA on port 8080.

## Environment variables

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE` | Backend HTTP URL (e.g. `http://localhost:8080`) |
| `VITE_WS_BASE` | Backend WebSocket URL (e.g. `ws://localhost:8080`) |

These are baked in at build time for production.
