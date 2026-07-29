# Admin API

Prefix: `/admin`  
Implementation: [`admin.py`](admin.py)

Used by the **admin panel** to upload, list, inspect, and delete documents.

## Upload document

`POST /admin/docs`  
`Content-Type: application/json`

### Request body

```json
{
  "title": "My Story",
  "ext": "pdf",
  "pages_number": 2,
  "content": "<base64-encoded document file>",
  "pages": [
    {
      "text": "مرحبا بكم في قصتنا",
      "audio": "<base64-encoded WAV for page 1>"
    },
    {
      "text": "هذه الصفحة الثانية",
      "audio": "<base64-encoded WAV for page 2>"
    }
  ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `title` | yes | Display name |
| `ext` | yes | File extension without dot (`pdf`, `epub`, …) |
| `pages_number` | yes | Must equal `pages.length` |
| `content` | yes | Full document file as base64 |
| `pages[].text` | yes | Expected reading text for that page |
| `pages[].audio` | yes | Reference narration as base64 WAV |

### Success (200)

```json
{
  "status": "success",
  "message": "Document inserted successfully",
  "doc_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Error (400)

```json
{ "detail": "Expected 2 pages, got 1" }
```

On upload the server:

1. Stores the document at `docs/{doc_id}.{ext}` in GCS
2. Renders page 1 to PNG → `previews/{doc_id}.png` (PDF or image uploads)
3. Stores each page audio at `audios/{doc_id}/{page_number}.wav`
4. Runs STT on reference audio → saves word alignments to `content_aligned`
5. Inserts rows into BigQuery `docs` and `pages`

## List documents

`GET /admin/docs/{offset}/{limit}`

Example: `GET /admin/docs/0/10` → first 10 docs; `GET /admin/docs/10/10` → docs 11–20.

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
  "offset": 0,
  "limit": 10
}
```

Type: `DocListResponse` — same shape as the public [catalog list](catalog.md#list-documents-library).

## Get document

`GET /admin/docs/{doc_id}`

Same shape as [catalog document detail](catalog.md#get-document) (`DocDetailResponse`).

## Get page

`GET /admin/docs/{doc_id}/pages/{page_number}`

Same shape as [catalog page detail](catalog.md#get-page) (`PageDetailResponse`), including `content_aligned` for debugging.

## Delete document

`DELETE /admin/docs/{doc_id}`

```json
{
  "status": "success",
  "message": "Document deleted"
}
```

Deletes BigQuery rows and GCS objects under `docs/` and `audios/{doc_id}/`.

## Re-align document

`POST /admin/docs/{doc_id}/realign`

Re-runs STT on every page that has reading text and reference audio, and updates `content_aligned` in BigQuery. Use after changing `STT_FRAME_DURATION` or fixing alignment bugs on existing uploads.

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "pages_aligned": 6,
  "pages_skipped": 2
}
```

Picture-only pages and pages without audio are skipped (`pages_skipped`).

## Re-align single page

`POST /admin/docs/{doc_id}/pages/{page_number}/realign`

Re-aligns one page and returns updated `PageDetailResponse` (including `content_aligned`).

## Related

- [Audio format](../../docs/frontend/audio.md)
- [Admin upload flow](../../docs/frontend/flows.md#admin-upload-flow)
- [Data models](../data/README.md)
