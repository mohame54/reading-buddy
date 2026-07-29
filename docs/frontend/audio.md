# Audio format

## Summary

| Usage | Format | Notes |
|-------|--------|-------|
| Upload `pages[].audio` | Base64-encoded WAV | Or any format `soundfile` can decode |
| Child utterance (`audio` / `data`) | Base64-encoded WAV | Recommended |
| Mistake replay | Page `audio_url` + `start` / `end` | Seek client-side; or play the full page audio |

Sample rate is normalized server-side to **16 kHz** for STT.

## Upload (admin)

Each page's reference narration is sent as base64 in `InsertPageReq.audio`:

```json
{
  "text": "مرحبا بكم في قصتنا",
  "audio": "<base64 WAV>"
}
```

The server stores the decoded file at `audios/{doc_id}/{page_number}.wav` in GCS.

## Child utterances

Send **complete utterances** (a phrase or sentence), not raw PCM stream chunks. The STT model is offline/batch — it expects a full audio buffer per request.

WebSocket:

```json
{ "type": "audio", "data": "<base64 WAV>" }
```

POST:

```json
{ "doc_id": "...", "page_number": 1, "audio": "<base64 WAV>", "cursor": 0 }
```

## Playing mistake clips (browser)

Fetch page `audio_url` once (from `GET /docs/{doc_id}/pages/{n}`). On mismatch, use returned `start` / `end` (seconds):

```javascript
function playWordClip(audioEl, start, end) {
  audioEl.currentTime = start;
  audioEl.play();
  const stop = () => {
    if (audioEl.currentTime >= end) {
      audioEl.pause();
      audioEl.removeEventListener("timeupdate", stop);
    }
  };
  audioEl.addEventListener("timeupdate", stop);
}

// Or let the user choose: play the full page narration instead
function playFullPage(audioEl) {
  audioEl.currentTime = 0;
  audioEl.play();
}
```

## Recording tips

- Prefer mono WAV from `MediaRecorder` or encode mic capture to WAV before base64.
- Browser WebM/Opus may fail unless the server can decode it — WAV is the safe choice.
