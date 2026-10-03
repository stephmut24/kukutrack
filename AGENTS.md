# AGENTS.md

## Project
**KukuTrack** ("kuku" = chicken in Swahili): a small offline-first app that helps
a broiler farmer track a batch of chicks from day 1 to sale (45–60 days, target
weight about 3 kg).

It tracks: mortality, feed consumption, weight, and reminders (heating, vaccines,
vitamins, protein, boosters). A local open-weight AI model lets the farmer log
things in plain language ("2 dead chicks this morning, gave 4 kg of feed").

Built for one real person (my younger brother). He is busy, has dirty hands,
uses an Android phone, speaks French, and internet is unreliable and expensive.
Simplicity beats features.

## Hard constraints (never break these)
1. **Local-first.** The core app must run with no internet. No cloud AI APIs in
   the core. The AI runs through Ollama (open-weight model, Gemma).
2. **The AI never writes to the database on its own.** It proposes a structured
   result; the user sees it and confirms before anything is saved.
3. **The AI never gives veterinary diagnoses or medical advice.** Alerts may say
   "mortality is higher than usual, check temperature, water and feed, and ask a
   vet if it continues". Nothing more specific.
4. **No hard-coded medical values.** Vaccine days, doses, vitamin schedules and
   target weights live in an editable config/database, never in code logic.
   Default values are placeholders to be confirmed with the farmer's vet.
5. **No new dependency without asking me first.**
6. **No secrets, API keys or promo codes** in any file in the repo.
7. **Do not run git commands.** I commit myself.

## Stack
- Python 3.11+, FastAPI, Uvicorn
- SQLite via the standard `sqlite3` module (no ORM)
- Pydantic for request/response schemas
- `httpx` to call the local Ollama HTTP API
- Frontend: plain HTML, CSS and vanilla JS served by FastAPI as a PWA
  (mobile-first, large touch targets). No frontend framework, no build step.
- Tests: pytest. Lint: ruff.

## Commands
- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Test: `pytest`
- Lint: `ruff check .`

## Layout
```
app/
  main.py          # FastAPI app, mounts routers and static files
  config.py        # settings (db path, Ollama URL, model name)
  db.py            # connection helper and schema creation
  schemas.py       # Pydantic models
  routers/         # one file per feature (batches, logs, reminders, assistant, dashboard)
  services/        # business logic, no HTTP code (calendar, stats, assistant)
config/
  default_schedule.json   # editable default reminder template
static/            # PWA files (index.html, app.js, style.css, manifest, service worker)
tests/             # pytest tests mirroring app/services
docs/              # notes, screenshots, decisions
data/              # SQLite file lives here, gitignored
```
Keep business logic in `services/` so it can be tested without HTTP.

## Code style
- Type hints on all functions. Small functions with one job.
- Clear names in English. Comments only where the reason is not obvious.
- All **user-facing text is in French** (UI, reminders, alerts). Code, comments,
  docs and commit-style notes are in English.
- Dates are stored as ISO strings (UTC date, no time needed unless required).
- Return clear error messages; never swallow exceptions silently.
- If Ollama is unreachable, the app still works: manual entry stays available and
  the assistant feature shows a friendly French message.

## Testing rules
- Every service function with logic (calendar generation, mortality rate,
  feed per bird, weight vs target) needs at least one pytest test.
- Test the AI parsing with a fake/mocked Ollama response. Do not require a
  running model for the test suite.
- Do not edit a test just to make it pass. Fix the code, or tell me why the test
  is wrong.

## Working style
- For any task bigger than one file, **propose a short plan first** and wait for
  my approval.
- Do one task at a time. Stay inside the scope I gave you; mention ideas for
  later instead of building them.
- When finished, report: what changed, how to run it, what is still missing, and
  any assumption you made.
- If something is unclear or risky, ask me instead of guessing.

## Definition of done (every task)
- `pytest` passes and `ruff check .` reports no errors.
- The feature works when I run the app and try it.
- No unrelated files were changed.