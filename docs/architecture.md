# Architecture

## Goal

Build a safe HH.ru job-search operating system: search vacancies, rank them, draft relevant responses, store everything in CRM, learn from Aleksandr's feedback, and show the funnel visually.

## Runtime flow

1. `HHClient.search_vacancies()` loads public HH vacancies with a compliant User-Agent.
2. `score_vacancy()` gives each vacancy a deterministic score and decision: `hot`, `review`, `maybe`, `archive`.
3. `CRMRepository.upsert_vacancy()` deduplicates by `external_id` and stores raw/context fields in SQLite.
4. If score is high enough, `generate_cover_letter()` creates a draft response.
5. Draft goes to `applications` with status `draft`.
6. User reaction is stored in `feedback_events`.
7. `LearningEngine` adjusts `learning_signals` weights.
8. Dashboard reads `/api/dashboard` and displays metrics, pipeline, cards, drafts, feedback, and learning weights.

## Safety boundaries

- No external response sending in MVP.
- No CAPTCHA bypassing.
- No paid actions.
- No identical spam.
- OAuth sending must require explicit user confirmation and daily limits.

## Database

SQLite tables:

- `vacancies` — source vacancy data, score, decision, reasons.
- `applications` — draft/sent/reply/interview/offer pipeline.
- `feedback_events` — user reaction and edited texts.
- `learning_signals` — weights for preferred/negative terms.
- `run_logs` — future agent execution audit.

## API

- `GET /health`
- `GET /api/dashboard`
- `GET /api/vacancies`
- `POST /api/agent/run`
- `POST /api/feedback`

## Dashboard design

Industrial/data-dense dark interface: score rings, pipeline bars, learning signals, draft previews, and animated agent orbit. The UI has a demo fallback, so it is usable even before backend/API is running.
