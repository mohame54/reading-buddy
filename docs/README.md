# Documentation

## For frontend developers

**[frontend/ARCHITECTURE.md](frontend/ARCHITECTURE.md)** — full architecture guide: screens, TypeScript types, API, WebSocket, grading, audio replay, checklist.

| Doc | Contents |
|-----|----------|
| [frontend/ARCHITECTURE.md](frontend/ARCHITECTURE.md) | **Main guide** — build admin + child apps end-to-end |
| [frontend/README.md](frontend/README.md) | Quick route index |
| [frontend/flows.md](frontend/flows.md) | Admin upload + child reading flows |
| [frontend/audio.md](frontend/audio.md) | Base64 WAV expectations |
| [frontend/errors.md](frontend/errors.md) | HTTP + WebSocket errors |

## API reference

Live next to the code in **[src/api/](../src/api/README.md)**.

| Doc | Contents |
|-----|----------|
| [src/api/README.md](../src/api/README.md) | Endpoint index |
| [src/api/admin.md](../src/api/admin.md) | `/admin/*` |
| [src/api/catalog.md](../src/api/catalog.md) | `/docs/*` |
| [src/api/reading.md](../src/api/reading.md) | `POST /reading/*` |
| [src/api/websocket.md](../src/api/websocket.md) | `WS /reading/session` |

## Data models

**[src/data/README.md](../src/data/README.md)** — request/response shapes and TypeScript hints.

## Backend

| Doc | Contents |
|-----|----------|
| [architecture.md](architecture.md) | System design, GCS/BQ, grading |
| [development.md](development.md) | Env vars, local run, Docker |
| [../src/bq/POOL_DOCUMENTATION.md](../src/bq/POOL_DOCUMENTATION.md) | BigQuery pool internals |

## POC & stakeholders

| Doc | Contents |
|-----|----------|
| [POC_WRITEUP.md](POC_WRITEUP.md) | POC features, decisions, success metrics |
| [STAKEHOLDER_EVAL_SUMMARY.md](STAKEHOLDER_EVAL_SUMMARY.md) | Eval results explained for leadership; roadmap (VAD, fine-tuning) |
| [../eval/README.md](../eval/README.md) | STT evaluation harness (Colab / local) |

## Root

**[../README.md](../README.md)** — project overview and doc map.
