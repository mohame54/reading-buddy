# Development

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- GCP project with BigQuery dataset and GCS bucket
- Service account with BigQuery + Storage permissions (private key for signed URLs)
- STT model files in `models/` (`stt_ar_ctc.onnx`, `tokens.txt`)

Download model (requires `FOLDER_DRIVE_ID`):

```bash
export FOLDER_DRIVE_ID="your-google-drive-folder-id"
uv run python download_model.py
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PROJECT_ID` | yes | BigQuery `project_id.dataset_id` |
| `GOOGLE_CREDENTIALS` | yes | Base64-encoded service account JSON |
| `GCS_BUCKET` | yes | Bucket name for docs and audios |
| `MODEL_DIR` | no | Path to STT model (default: `models`) |
| `STT_NUM_THREADS` | no | ONNX threads (default: `2`) |
| `STT_ALIGN_BATCH_SIZE` | no | Pages per `decode_streams` batch on upload (default: `4`) |
| `CORS_ORIGINS` | no | Comma-separated origins (default: `*`) |
| `FOLDER_DRIVE_ID` | no | For `download_model.py` only |

## Run locally

```bash
export PROJECT_ID="your-gcp-project.your_dataset"
export GOOGLE_CREDENTIALS="<base64 service account JSON>"
export GCS_BUCKET="your-bucket-name"
export MODEL_DIR="models"
export CORS_ORIGINS="http://localhost:5173"  # Vite dev server (see frontend/)

uv sync
uv run uvicorn main:app --reload --port 8080
```

- Swagger UI: http://localhost:8080/docs
- Health: http://localhost:8080/health

## Docker

```bash
docker build -f Dockerfile -t reading-buddy .
docker run -p 8080:8080 \
  -e PROJECT_ID=... \
  -e GOOGLE_CREDENTIALS=... \
  -e GCS_BUCKET=... \
  -e FOLDER_DRIVE_ID=... \
  reading-buddy
```

The entrypoint downloads the model at container start when `FOLDER_DRIVE_ID` is set and `models/stt_ar_ctc.onnx` is missing.

## Notes

- Signed URLs (`content_url`, `audio_url`) require a service account **with a private key**.
- BigQuery tables `docs` and `pages` are created automatically on first startup if missing.
- Interactive OpenAPI docs are always available at `/docs` when the server is running.

## Frontend

The React SPA is in [`frontend/`](../frontend/). Deploy it separately to Cloud Run (`reading-buddy-web`).

For production, set `CORS_ORIGINS` on the API to the frontend origin instead of `*`:

```bash
export CORS_ORIGINS="https://reading-buddy-web-xxxxx.run.app"
```

Update `VITE_API_BASE` and `VITE_WS_BASE` in `frontend/cloudbuild.yaml` before deploying the frontend.
