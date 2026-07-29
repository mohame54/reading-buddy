# Reading Buddy Frontend

Vite + React + TypeScript SPA for the Reading Buddy admin panel and user reading app. Deploys to Cloud Run as `reading-buddy-web`.

## Quick links

| Topic | Doc |
|-------|-----|
| **App code** | [`frontend/`](frontend/) |
| **Frontend architecture** | [docs/frontend/ARCHITECTURE.md](docs/frontend/ARCHITECTURE.md) |
| **API integration** | [docs/frontend/README.md](docs/frontend/README.md) |

## Routes

| Mode | URL path |
|------|----------|
| Landing | `/` |
| Admin | `/admin`, `/admin/upload`, `/admin/docs/:docId` |
| Users | `/users`, `/users/read/:docId`, `/users/score` |

## Local development

```bash
# Terminal 1 — backend API (separate repo/host)
export CORS_ORIGINS="http://localhost:5173"
uvicorn main:app --reload --port 8080

# Terminal 2 — frontend
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:5173 — use `/admin` or `/users`.

## Cloud Run deployment

Deploy from the repo root:

```bash
gcloud builds submit --config cloudbuild.yaml .
```

Before deploying, set in [`cloudbuild.yaml`](cloudbuild.yaml):

- `_VITE_API_BASE` — backend HTTPS URL
- `_VITE_WS_BASE` — backend WSS URL

Also set backend `CORS_ORIGINS` to your frontend Cloud Run origin (e.g. `https://reading-buddy-web-xxxxx.run.app`).

The root [`Dockerfile`](Dockerfile) builds `frontend/` into a static nginx image on port 8080.
