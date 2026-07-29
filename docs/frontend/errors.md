# Errors

## HTTP

| Status | When | Response shape |
|--------|------|----------------|
| `200` | Success | Endpoint-specific JSON |
| `400` | Validation failed (e.g. `pages_number` ≠ `pages.length`) | `{ "detail": "..." }` |
| `404` | Document or page not found | `{ "detail": "..." }` |

### Health check

`GET /health` always returns `200`:

```json
{ "status": "ok" }
```

Use this for load balancers and startup probes.

## WebSocket

Errors are sent as JSON messages without closing the connection (unless the client sends `end` or disconnects):

```json
{ "type": "error", "message": "Document not found" }
```

Common cases:

| Message | Cause |
|---------|-------|
| `Session not started` | Sent `audio` / `next_page` before `start` |
| `Document not found` | Invalid `doc_id` in `start` |
| `Page not found` | Invalid `page_number` |
| `Unknown message type: ...` | Unrecognized `type` field |

## Upload failures

`POST /admin/docs` returns `400` with `detail` on validation or processing errors. Partial GCS uploads are cleaned up server-side on failure.

## Signed URL failures

If `content_url` or `audio_url` is `null` or requests fail, verify the service account has a **private key** (required for GCS signed URLs).
