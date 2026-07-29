# Catalog API

Prefix: `/docs`  
Implementation: [`docs.py`](docs.py)

Public endpoints for the **parent/child app** to browse documents, prepare a session, and drive the interactive reader.

## Screens this API supports

```
[ Library ]  →  [ Prepare ]  →  [ Reader ]
 list docs       download         pages +
 title+preview   + cache audio    Record/Stop
```

| Screen | Endpoint | What you get |
|--------|----------|--------------|
| Library | `GET /docs/{offset}/{limit}` | Paginated title + first-page image + text |
| Prepare | `GET /docs/{doc_id}` | All page texts, per-page `audio_url` and cached `image_url`, optional file `content_url` |
| Reader | WebSocket `/reading/session` (or POST `/reading/check`) | Grading; advance page only after `page_complete` |

## List documents (library)

`GET /docs/{offset}/{limit}`

Example: `GET /docs/10/10` returns documents **11–20** (skip 10, take 10). `limit` is capped at 100.

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "My Story",
      "ext": "pdf",
      "pages_number": 2,
      "first_page_content": "مرحبا بكم في قصتنا",
      "first_page_image_url": "https://storage.googleapis.com/..."
    }
  ],
  "total": 42,
  "offset": 10,
  "limit": 10
}
```

Type: `DocListResponse`

| Field | Use on frontend |
|-------|-----------------|
| `items[].title` | Card heading |
| `items[].first_page_image_url` | First-page preview image (beside the text) |
| `items[].first_page_content` | Text overview next to the image |
| `items[].pages_number` | “2 pages” badge |
| `total` | Build pager / infinite scroll |
| `offset` / `limit` | Echo of the request |

Each library card shows the **first page image** beside the **first page text**. Tapping a card opens prepare.

## Get document (prepare)

`GET /docs/{doc_id}`

Call once when the user picks a book. Cache the response before opening the reader.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "My Story",
  "ext": "pdf",
  "pages_number": 2,
  "gcs_uri": "gs://bucket/docs/550e8400-e29b-41d4-a716-446655440000.pdf",
  "content_url": "https://storage.googleapis.com/...",
  "pages": [
    {
      "id": "...",
      "page_number": 1,
      "content": "مرحبا بكم في قصتنا",
      "audio_url": "https://storage.googleapis.com/...",
      "image_url": "https://storage.googleapis.com/..."
    },
    {
      "id": "...",
      "page_number": 2,
      "content": "هذه الصفحة الثانية",
      "audio_url": "https://storage.googleapis.com/...",
      "image_url": null
    }
  ]
}
```

| Field | Use on frontend |
|-------|-----------------|
| `content_url` | Optional: download/embed the original file (PDF) |
| `pages[].content` | Reading text for each page (grading + word progress) |
| `pages[].audio_url` | Prefetch reference audio; seek with mismatch `start`/`end` |
| `pages[].image_url` | Signed URL to cached page PNG when already rendered; `null` until first request renders it |

Type: `DocDetailResponse`

## Get page

`GET /docs/{doc_id}/pages/{page_number}`

Optional — prefer prepare (`GET /docs/{doc_id}`) which already includes every page. Use this for a single-page refresh or admin debugging.

```json
{
  "id": "...",
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "page_number": 1,
  "content": "مرحبا بكم في قصتنا",
  "content_aligned": "[{\"word\":\"مرحبا\",\"start\":0.0,\"end\":0.5}]",
  "audio_gcs_uri": "gs://bucket/audios/550e8400.../1.wav",
  "audio_url": "https://storage.googleapis.com/...",
  "image_url": "https://storage.googleapis.com/..."
}
```

Type: `PageDetailResponse`

On first request, the server renders the PDF page to PNG, uploads to `page_images/{doc_id}/{page_number}.png`, stores `image_gcs_uri` in BigQuery, and returns a signed `image_url`. Subsequent requests reuse the cached object.

## Reader UX (client)

After prepare:

1. Show page `N` text from cached `pages`.
2. **Record** → capture utterance → send to WebSocket / `POST /reading/check`.
3. **Stop** → end capture and submit that utterance.
4. On mismatch → seek `audio_url` to `start`/`end` (or play full page); keep same page; child retries.
5. On `page_complete` → enable **Next page** (do not skip ahead earlier).
6. Last page → show score.

See [flows.md](../../docs/frontend/flows.md) and [websocket.md](websocket.md).

## Errors

`404` if `doc_id` or `page_number` does not exist.

## Related

- [Child reading flow](../../docs/frontend/flows.md#child-reading-flow-websocket--recommended)
- [Reading API](reading.md)
