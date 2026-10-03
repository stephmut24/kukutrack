# KukuTrack: Prompt plan for Codex

Deadline: Monday 5 October, 08:59 (Goma time). Target: article published Sunday evening.
Rule for every prompt: plan first, then build. Afterwards I run `pytest`, `ruff check .`,
try the feature by hand, and only then commit.

## Phase A: Foundation

| # | Prompt | Depends on | Done when |
|---|--------|-----------|-----------|
| 00 | AGENTS.md at repo root | none | File committed (done) |
| 01 | Project skeleton, SQLite schema, create a batch + reminder calendar, minimal PWA page | 00 | App runs, I can create a batch and tick reminders, tests pass |

## Phase B: Core tracking (no AI yet)

| # | Prompt | Depends on | Done when |
|---|--------|-----------|-----------|
| 02 | Daily log + weigh-ins: API endpoints and mobile forms (dead count, feed kg, note; sample weight). Validation (dead cannot exceed birds alive) | 01 | I can log a day and a weigh-in from my phone |
| 03 | Stats service + dashboard: mortality rate, birds alive, feed per bird, weight curve vs target. Simple charts with plain JS/canvas, no library | 02 | Dashboard shows correct numbers on test data, unit tests cover each formula |
| 04 | Demo data command: script that seeds a realistic 45-day batch (clearly labeled fake) | 03 | One command fills the app with demo data for screenshots |

## Phase C: The AI layer (the core of the challenge)

| # | Prompt | Depends on | Done when |
|---|--------|-----------|-----------|
| 05 | Ollama client + parsing service: French sentence in, JSON out (dead, feed_kg, weight, note). Strict JSON validation, timeout, graceful failure when Ollama is down. Tests with a mocked Ollama response | 02 | Service returns valid JSON for 10 sample sentences (mocked) and a clear error when offline |
| 06 | Assistant endpoint + UI: text box (phone keyboard dictation works here), "I understood: 2 dead, 4 kg feed. Confirm?" screen, nothing saved until confirmed | 05 | Free-text entry works end to end, with manual correction before saving |
| 07 | Alerts + weekly summary: rule-based thresholds (configurable) detect problems, the model only phrases the French message. No diagnosis, vet reminder wording | 03, 05 | Summary appears on the dashboard, alerts trigger on seeded data |

## Phase D: Polish

| # | Prompt | Depends on | Done when |
|---|--------|-----------|-----------|
| 08 | Robustness and UX: friendly French errors, offline behavior, bigger touch targets, empty states, PWA install check on Android | 06 | Works fully with Ollama off (manual mode) and on a real phone |
| 09 | README and docs: install, run, phone access, architecture diagram, limitations, honest note on test duration | 08 | A stranger could run the project from the README |
| 10 (optional) | Local voice input with Whisper | 06 | Only if time remains, never at the cost of the article |

## Phase E: Not for Codex (do these yourself)

- Real test with my brother: show him the app, watch where he struggles, note his reactions (good and bad).
- Screenshots and a short demo video (use the seeded data from prompt 04).
- Write the article in simple English, publish with the DEV template and the three tags.

## Suggested schedule (Goma time)

- **Sat 12:00-17:00:** prompts 01, 02, 03
- **Sat 17:00-21:00:** prompts 04, 05 (install Ollama and the model first)
- **Sun 08:00-12:00:** prompts 06, 07
- **Sun 12:00-15:00:** test with my brother, prompt 08
- **Sun 15:00-17:00:** prompt 09, screenshots, demo
- **Sun 17:00-22:00:** write and publish the article
- **Mon morning:** buffer only (power or network cuts)

If I fall behind, cut in this order: 10, then 07, then charts in 03. Never cut 05 and 06, they are the heart of the project.

## Template for follow-up fix prompts

```
Problem: <what I saw, exact error message or behavior>
Expected: <what should happen>
Where: <file or feature>
Constraint: fix only this, keep AGENTS.md rules, do not refactor unrelated code.
Done when: <test or manual check>
```

## Honest note for the article

A real broiler batch lasts 45 to 60 days, so the field test will cover only the first days
or one early stage. Say that clearly, and show the seeded demo data as demo data.