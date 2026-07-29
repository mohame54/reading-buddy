# Frontend UI flows

## Admin upload flow

1. User selects a document file → read as base64 → `content`.
2. For each page:
   - Capture or upload reference WAV → base64 → `pages[].audio`
   - Enter expected reading text → `pages[].text`
3. `POST /admin/docs` with `pages_number === pages.length`.
4. Store returned `doc_id` for list/detail views.

See [Admin API](../../src/api/admin.md) for the full request body.

## Child app: library → prepare → reader

```mermaid
flowchart LR
  library["Library\nGET /docs/offset/limit"]
  prepare["Prepare\nGET /docs/id"]
  reader["Reader\nWS + Record/Stop"]
  score["Score"]

  library -->|"pick book"| prepare
  prepare -->|"cache pages + audio"| reader
  reader -->|"all pages done"| score
```

### 1. Library

`GET /docs/{offset}/{limit}` (e.g. `/docs/0/10`, then `/docs/10/10`) → cards with **title**, **first_page_image_url**, and **first_page_content**. Use `total` for pagination.

### 2. Prepare (on book select)

`GET /docs/{doc_id}` once:

- Prefetch / cache each `pages[].audio_url` (for mistake replay).
- Optionally download `content_url` if you show the original PDF.
- Keep `pages[].content` in memory for the reader.

### 3. Interactive reader

Controls: **Record**, **Stop**, and **Next page** (enabled only after the current page is finished).

```mermaid
sequenceDiagram
  participant UI as Child UI
  participant API as GET /docs
  participant WS as WS /reading/session

  UI->>API: GET /docs/0/10 (library)
  API-->>UI: items + total
  UI->>API: GET /docs/{doc_id} (prepare)
  API-->>UI: pages content + audio_url
  UI->>WS: start doc_id page 1
  WS-->>UI: page
  loop until page complete
    Note over UI: Record → Stop → send utterance
    UI->>WS: audio
    alt mismatch
      WS-->>UI: feedback + start/end
      Note over UI: seek page audio; retry
    else ok
      WS-->>UI: ok cursor
    end
  end
  WS-->>UI: page_complete
  Note over UI: enable Next page
  UI->>WS: next_page
  WS-->>UI: page
  Note over UI: repeat per page
  WS-->>UI: score
```

1. Connect `WS /reading/session` → `{ "type": "start", "doc_id", "page_number": 1 }`.
2. Show cached page text; wire **Record** / **Stop**.
3. On Stop → `{ "type": "audio", "data": "<base64 WAV>" }`.
4. On `feedback` → seek that page’s `audio_url` to `start`/`end` (or play full); retry (cursor unchanged).
5. On `page_complete` → enable **Next page** → `{ "type": "next_page" }` (last page auto-emits `score`).
6. On `score` → results screen.

Client example: [websocket.md](../../src/api/websocket.md#minimal-browser-example).

## Child reading flow (POST only)

Same library + prepare steps, then:

1. Loop per page with **Record** / **Stop**.
2. `POST /reading/check` with current `cursor`.
3. On mismatch → seek page audio; retry.
4. Until `page_complete` → allow next page.
5. Track score on the client; after last page → `POST /reading/finish`.

## When to use which mode

| Mode | Pros | Cons |
|------|------|------|
| WebSocket | Server tracks score; fewer round-trips; live UX | Connection management |
| POST | Simple HTTP; easy to debug | Client tracks score; more requests |
