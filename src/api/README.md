# API reference

All paths are relative to the API base URL (e.g. `http://localhost:8080`).

## Routers

| Prefix | Module | Documentation |
|--------|--------|---------------|
| `/admin` | [`admin.py`](admin.py) | [admin.md](admin.md) |
| `/docs` | [`docs.py`](docs.py) | [catalog.md](catalog.md) |
| `/reading` | [`reading.py`](reading.py) | [reading.md](reading.md) · [websocket.md](websocket.md) |
| `/health` | [`main.py`](../../main.py) | Returns `{ "status": "ok" }` |

## Endpoint index

### Admin (`/admin`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/docs` | Upload document + pages |
| `GET` | `/admin/docs/{offset}/{limit}` | Paginated document list |
| `GET` | `/admin/docs/{doc_id}` | Document detail + signed URL |
| `GET` | `/admin/docs/{doc_id}/pages/{page_number}` | Page detail |
| `DELETE` | `/admin/docs/{doc_id}` | Delete document + GCS assets |

### Catalog (`/docs`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/docs/{offset}/{limit}` | Paginated public document list |
| `GET` | `/docs/{doc_id}` | Document detail + signed URLs |
| `GET` | `/docs/{doc_id}/pages/{page_number}` | Single page (optional) |

> Exact `GET /docs` is FastAPI Swagger UI, not the catalog list.

### Reading (`/reading`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reading/check` | Check one utterance |
| `POST` | `/reading/finish` | Submit final score (POST flow) |
| `WebSocket` | `/reading/session` | Live reading session |

## Request/response types

Pydantic models live in [`src/data/reqs.py`](../data/reqs.py). See [data README](../data/README.md).

## Interactive docs

Run the server and open `/docs` (Swagger UI) for schemas and try-it-out.

## Frontend guides

- [Frontend architecture](../../docs/frontend/ARCHITECTURE.md)
- [Frontend integration](../../docs/frontend/README.md)
- [UI flows](../../docs/frontend/flows.md)
