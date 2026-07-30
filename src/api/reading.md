# Reading API (POST)

Prefix: `/reading`  
Implementation: [`reading.py`](reading.py) · Service: [`stt_service.py`](../services/stt_service.py)

HTTP fallback for reading checks and final score. For live sessions prefer [WebSocket](websocket.md).

## How grading works

1. Client sends **one complete utterance** as base64 audio.
2. Server transcribes with Arabic ONNX STT.
3. Words are compared to page `content` starting at **`cursor`**.
4. On mismatch → returns `start` / `end` (seconds in the page reference audio).
5. Cursor advances only over consecutive correct words before the first mistake; all mismatches in the utterance are returned.
6. Client may **retry** (`POST /reading/check` with same cursor) or **skip** (`POST /reading/skip`) to advance past each unresolved word.
7. When all words on the page are resolved → `page_complete: true`.

Grading uses **`content`** (admin text). Timestamps in `content_aligned` are resolved server-side into `start` / `end` on mismatches.

### Scoring (POST flow)

Track on the client when using POST-only mode:

| Outcome | `words_total` | `words_correct` | Extra |
|---------|---------------|-----------------|-------|
| Correct first try | +1 | +1 | — |
| Wrong, then correct on retry | +1 | +1 | `words_retried_correct` +1 |
| Skip after feedback | +1 | +0 | `words_skipped` +1 |

`accuracy = words_correct / words_total`. Retries that succeed get full credit; skipping hurts accuracy.

## Check utterance

`POST /reading/check`

### Request

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "page_number": 1,
  "audio": "<base64 WAV of child's utterance>",
  "cursor": 0
}
```

Type: `CheckReadingReq`

### Response

```json
{
  "ok": false,
  "cursor": 0,
  "page_complete": false,
  "mismatches": [
    {
      "index": 0,
      "expected": "مرحبا",
      "heard": "مرحب",
      "start": 0.0,
      "end": 0.48
    }
  ]
}
```

Type: `CheckReadingResponse`

| Field | Meaning |
|-------|---------|
| `ok` | `true` if no mismatches in this utterance |
| `cursor` | Send this value on the next check |
| `page_complete` | All words on the page resolved |
| `mismatches[].start` / `end` | Seconds in page `audio_url` — seek to replay the word (or play the full page audio) |

## Skip word

`POST /reading/skip`

Advance past the current word without awarding `words_correct`. Use after a mismatch when the child chooses to continue.

### Request

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "page_number": 1,
  "cursor": 0
}
```

Type: `SkipReadingReq`

### Response

Same shape as `CheckReadingResponse` — `cursor` is incremented by one, `mismatches` is empty, `page_complete` when the page is finished.

Client should increment `words_total` and `words_skipped` (not `words_correct`).

## Loop

```
cursor = 0
repeat:
  record utterance
  POST /reading/check { ..., cursor }
  if mismatches:
    seek page audio to start/end (or play full)
    retry with same cursor OR POST /reading/skip → cursor + 1, words_skipped++
  else:
    cursor = response.cursor
    update words_total / words_correct (and words_retried_correct if recovering from mismatch)
until page_complete
→ next page
```

## Final score

`POST /reading/finish`

Use when tracking score on the **client** (POST-only flow). WebSocket sessions emit score automatically — see [websocket.md](websocket.md).

### Request

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "words_total": 42,
  "words_correct": 38,
  "words_skipped": 4,
  "words_retried_correct": 6,
  "pages_completed": 2
}
```

Type: `FinishReadingReq`

### Response

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "words_total": 42,
  "words_correct": 38,
  "words_skipped": 4,
  "words_retried_correct": 6,
  "pages_completed": 2,
  "pages_total": 2,
  "accuracy": 0.9048
}
```

Type: `FinalScoreResponse` — `accuracy = words_correct / words_total` (0 if total is 0).

## Related

- [WebSocket session](websocket.md)
- [Audio format](../../docs/frontend/audio.md)
- [POST reading flow](../../docs/frontend/flows.md#child-reading-flow-post-only)
