# Data models

Pydantic models for API request/response bodies. Source: [`reqs.py`](reqs.py) (API DTOs) and [`models.py`](models.py) (BigQuery records).

BigQuery column definitions: [`schemas.json`](../schemas.json)

## Upload (admin)

### `InsertDocReq`

| Field | Type | Description |
|-------|------|-------------|
| `title` | `string` | Document title |
| `ext` | `string` | File extension without dot |
| `pages_number` | `int` | Must match `pages.length` |
| `content` | `string` | Base64 document file |
| `pages` | `InsertPageReq[]` | Per-page text + audio |

### `InsertPageReq`

| Field | Type | Description |
|-------|------|-------------|
| `text` | `string` | Expected reading text |
| `audio` | `string` | Base64 reference WAV |

### `StatusResponse`

| Field | Type | Description |
|-------|------|-------------|
| `status` | `"success" \| "error"` | Result |
| `message` | `string?` | Human-readable message |
| `doc_id` | `string?` | Set on successful upload |

## Catalog

### `DocSummary`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Document id |
| `title` | `string` | Card title |
| `ext` | `string` | File extension |
| `pages_number` | `int` | Page count |
| `first_page_content` | `string?` | Page 1 text beside the preview image |
| `first_page_image_url` | `string?` | Signed URL for page 1 PNG preview |

### `DocListResponse`

| Field | Type | Description |
|-------|------|-------------|
| `items` | `DocSummary[]` | Page of documents |
| `total` | `int` | Total docs in the dataset |
| `offset` | `int` | Skip count |
| `limit` | `int` | Page size (max 100) |

### `DocDetailResponse`

`id`, `title`, `ext`, `pages_number`, `gcs_uri`, `content_url?`, `pages: PageSummary[]`

### `PageSummary`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Page id |
| `page_number` | `int` | 1-based |
| `content` | `string` | Reading text |
| `audio_url` | `string?` | Signed URL for reference audio (set on prepare) |

### `PageDetailResponse`

`id`, `doc_id`, `page_number`, `content`, `content_aligned?`, `audio_gcs_uri`, `audio_url?`

## Reading

### `CheckReadingReq`

| Field | Type | Default |
|-------|------|---------|
| `doc_id` | `string` | — |
| `page_number` | `int` | — |
| `audio` | `string` | base64 utterance |
| `cursor` | `int` | `0` |

### `CheckReadingResponse`

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | No mismatches |
| `cursor` | `int` | Updated position |
| `mismatches` | `WordMismatch[]` | First mistake details |
| `page_complete` | `bool` | Page fully read |

### `WordMismatch`

| Field | Type | Description |
|-------|------|-------------|
| `index` | `int` | Word index in page content |
| `expected` | `string` | Correct word |
| `heard` | `string?` | What STT detected |
| `start` | `float?` | Word start (seconds) in page reference audio |
| `end` | `float?` | Word end (seconds) in page reference audio |

### `FinishReadingReq`

`doc_id`, `words_total`, `words_correct`, `pages_completed`, `words_skipped` (default `0`), `words_retried_correct` (default `0`)

### `SkipReadingReq`

`doc_id`, `page_number`, `cursor`

### `FinalScoreResponse`

`doc_id`, `words_total`, `words_correct`, `words_skipped`, `words_retried_correct`, `pages_completed`, `pages_total`, `accuracy`

## BigQuery records

### `Doc` ([`models.py`](models.py))

`id`, `title`, `ext`, `pages_number`, `gcs_uri`

### `Page`

`id`, `doc_id`, `page_number`, `content`, `audio_gcs_uri`, `content_aligned?`

### `content_aligned` JSON shape

Array of word segments stored as a string:

```json
[
  { "word": "مرحبا", "start": 0.0, "end": 0.48 },
  { "word": "بكم", "start": 0.48, "end": 0.72 }
]
```

## TypeScript reference

```typescript
interface InsertDocReq {
  title: string;
  ext: string;
  pages_number: number;
  content: string; // base64
  pages: { text: string; audio: string }[];
}

interface CheckReadingResponse {
  ok: boolean;
  cursor: number;
  page_complete: boolean;
  mismatches: {
    index: number;
    expected: string;
    heard?: string;
    start?: number;
    end?: number;
  }[];
}

interface FinalScoreResponse {
  doc_id: string;
  words_total: number;
  words_correct: number;
  words_skipped: number;
  words_retried_correct: number;
  pages_completed: number;
  pages_total: number;
  accuracy: number;
}
```

## Related

- [Admin API](../api/admin.md)
- [Catalog API](../api/catalog.md)
- [Reading API](../api/reading.md)
