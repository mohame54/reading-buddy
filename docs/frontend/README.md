# Frontend integration

**Start here:** [ARCHITECTURE.md](ARCHITECTURE.md) — complete guide to build the admin panel and child reading app (screens, API contracts, WebSocket, grading, audio replay).

Supplementary docs: [flows](flows.md) · [audio](audio.md) · [errors](errors.md)

## Base URL & CORS

| Environment | HTTP | WebSocket |
|-------------|------|-----------|
| Local | `http://localhost:8080` | `ws://localhost:8080/reading/session` |
| Production | `https://your-host` | `wss://your-host/reading/session` |

CORS is enabled (`CORS_ORIGINS` env, default `*`). Set your frontend origin in development:

```bash
export CORS_ORIGINS="http://localhost:3000"
```

## Which routes for which app?

### Admin panel

| Action | Method | Endpoint | Docs |
|--------|--------|----------|------|
| Upload document | `POST` | `/admin/docs` | [admin.md](../../src/api/admin.md) |
| List documents (paginated) | `GET` | `/admin/docs/{offset}/{limit}` | [admin.md](../../src/api/admin.md) |
| Get document | `GET` | `/admin/docs/{doc_id}` | [admin.md](../../src/api/admin.md) |
| Get page | `GET` | `/admin/docs/{doc_id}/pages/{page_number}` | [admin.md](../../src/api/admin.md) |
| Delete document | `DELETE` | `/admin/docs/{doc_id}` | [admin.md](../../src/api/admin.md) |

### Parent / child app

| Action | Method | Endpoint | Docs |
|--------|--------|----------|------|
| Library (paginated) | `GET` | `/docs/{offset}/{limit}` | [catalog.md](../../src/api/catalog.md) |
| Prepare book (pages + audio URLs) | `GET` | `/docs/{doc_id}` | [catalog.md](../../src/api/catalog.md) |
| Single page (optional) | `GET` | `/docs/{doc_id}/pages/{page_number}` | [catalog.md](../../src/api/catalog.md) |
| Check utterance | `POST` | `/reading/check` | [reading.md](../../src/api/reading.md) |
| Final score (POST flow) | `POST` | `/reading/finish` | [reading.md](../../src/api/reading.md) |
| Live session (Record/Stop) | `WebSocket` | `/reading/session` | [websocket.md](../../src/api/websocket.md) |
| Health | `GET` | `/health` | — |

## Data you need on the client

| Field | Where | Use |
|-------|-------|-----|
| `items` + `total` / `offset` / `limit` | `GET /docs/{offset}/{limit}` | Library pager; card = image beside text |
| `pages[].content` | Doc detail | Reader text per page |
| `pages[].audio_url` | Doc detail | Prefetch; mistake replay via `start`/`end` |
| `content_url` | Doc detail | Optional PDF download/embed |
| `start` / `end` | Reading feedback | Seek into page audio |
| `cursor` | Reading responses | Next utterance check (POST flow) |
| `page_complete` | Reading responses | Enable **Next page** |
| `accuracy` | Score response | Final score screen |

`content_aligned` is optional on the client — the server resolves it into mismatch `start` / `end`.

## Recommended screens

1. **Library** — browse docs with first-page image beside first-page text.
2. **Prepare** — on select, `GET /docs/{id}` and cache pages + audio.
3. **Reader** — Record / Stop; next page only after `page_complete`.
4. **Score** — show accuracy when the book finishes.

Use **WebSocket** (`/reading/session`) for the reader. Use **POST** (`/reading/check`) as a simpler fallback.

## Further reading

- [UI flows](flows.md) — step-by-step admin and child flows
- [Audio format](audio.md) — encoding expectations
- [Errors](errors.md) — HTTP and WebSocket error handling
- [Data models](../../src/data/README.md) — TypeScript-friendly shapes
- [Architecture](../architecture.md) — storage and grading internals

## OpenAPI

Run the server and open http://localhost:8080/docs for interactive request/response schemas.
