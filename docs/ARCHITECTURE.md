# Architecture

## Overview

KukuTrack is a local-first FastAPI application served as a plain JavaScript PWA. It stores farm data in one local SQLite database and optionally calls a local Ollama model for language parsing and weekly-summary wording.

```text
static PWA → FastAPI routers → service layer → SQLite / editable JSON configuration
                                ↘ local Ollama (optional)
```

## Folders and main modules

| Path | Purpose |
| --- | --- |
| `app/main.py` | FastAPI application, lifespan setup, router registration, and static-file mount. |
| `app/config.py` | Paths and environment-based settings, including the database and Ollama configuration. |
| `app/db.py` | SQLite connections, schema creation, WAL mode, and connection timeout settings. |
| `app/schemas.py` | Pydantic request and response models. |
| `app/routers/` | HTTP endpoints grouped by feature. |
| `app/services/` | Testable business logic with no HTTP response handling. |
| `app/prompts/` | Local-model prompts for parsing and weekly wording. |
| `config/` | Editable reminder schedule, target curve, and alert thresholds. |
| `static/` | HTML, CSS, JavaScript, manifest, icon, and service worker for the PWA. |
| `scripts/seed_demo.py` | Creates a deterministic fake demonstration batch. |
| `scripts/try_parse.py` | Sends one sentence to the configured local Ollama model. |
| `tests/` | Pytest coverage for services and API behavior. |

## Data model

The schema is created by `app/db.py`.

| Table | Purpose |
| --- | --- |
| `batches` | Batch name, start date, initial count, target weight, status, and creation time. |
| `daily_logs` | One daily log per batch and date: deaths, feed, and optional water/note text. |
| `weigh_ins` | Sample size and average weight for a batch/date. |
| `reminders` | Editable dated reminders with category, text, completion state, and completion time. |

## Main request flows

### Manual records

The browser sends a daily log or weigh-in to a router. The log services validate active-batch status, date range, duplicate logs, non-negative values, and mortality against birds alive before writing to SQLite.

### Assistant proposal

`app/services/assistant.py` sends a sentence to Ollama's local `/api/chat` endpoint and validates the returned JSON as `ParsedEntry`. `app/routers/assistant.py` returns that proposal without database writes. The browser displays editable fields. Only `POST /api/batches/{id}/assistant/confirm` invokes `app/services/assistant_confirmation.py`, which uses the same log and weigh-in services as manual entry.

### Dashboard, alerts, and summary

`app/services/dashboard.py` assembles stored records. `app/services/stats.py` calculates series and compares weights with `config/target_curve.json`. `app/services/alerts.py` applies the editable thresholds in `config/alert_thresholds.json`. `app/services/summary.py` builds a seven-day fact set and can ask Ollama to phrase it.

### Reliability and backup

SQLite connections use WAL mode, full synchronous writes, and a five-second busy timeout. `GET /api/backup` uses SQLite's backup API to create a consistent downloadable database copy. The service worker caches the static app shell only; API responses are always requested from the local server.

## Guardrails

1. **Local-first:** no cloud AI API is used. Ollama is local and optional.
2. **Confirmation before persistence:** AI output is a proposal only. The confirm endpoint is the only assistant route that can save data.
3. **No diagnosis or treatment advice:** prompts and fixed user-facing text do not provide diagnoses, drug names, doses, or treatment advice.
4. **Configurable farm values:** schedules, target weights, and alert thresholds live in JSON configuration, not business-logic constants.
5. **Summary validation:** an AI weekly summary is discarded when it contains a number absent from the supplied facts or forbidden medical language. The deterministic French template is then returned instead.
6. **Unavailable-model fallback:** Ollama connection, timeout, HTTP, and output errors leave manual entry available and return a friendly French message or a template summary.
7. **No stale farm data:** PWA caching excludes `/api/` responses; connectivity loss is shown to the user.
