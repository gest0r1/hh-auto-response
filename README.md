# HeadHunter CRM Agent

Human-in-the-loop job search automation for HeadHunter and similar job boards. The project collects vacancies, scores them against a candidate profile, prepares personalized response drafts and routes risky external actions through a review workflow.

This repository is published as a portfolio-safe version. Real resumes, tokens, browser profiles and local CRM state are intentionally not stored in git.

## What it does

- imports vacancies into a lightweight CRM
- scores opportunities against a configurable candidate profile
- prepares tailored cover-letter drafts
- keeps a review queue before any external action
- supports Telegram notifications and operator review
- uses a browser profile for gated actions when explicit sending is enabled
- keeps runtime state in local files or a database, not in source control

## Architecture

```text
Job board pages / API
  -> collector
  -> SQLite CRM
  -> scoring engine
  -> response generator
  -> review queue
  -> Telegram/operator approval
  -> optional gated browser send
```

Main modules:

- `backend/app/config.py` - environment-based settings and profile loading
- `backend/app/scoring.py` - vacancy scoring logic
- `backend/app/responses.py` - response draft generation
- `backend/app/hh_browser.py` - browser automation layer for gated actions
- `backend/app/hh_chat.py` - chat and reply workflow
- `scripts/` - operator scripts and scheduled jobs
- `tests/` - regression tests for scoring, config, CLI and Telegram flow

## Safety model

The default mode is draft-first. The agent can prepare text, rank vacancies and notify the operator, but external sends must be explicitly enabled and reviewed.

Production-only files that must stay outside git:

- `.secrets/hh_telegram.env`
- `.env`
- `data/hh_crm.sqlite3`
- `data/hh-browser-profile/`
- logs, offsets, lock files and review queues
- real candidate profiles and resumes

Use `data/profile.example.json` as a public demo profile. For real use, set `HH_PROFILE_PATH` to a server-local private profile file.

## Quick start

```bash
git clone https://github.com/Glour/headhunter-crm-agent.git
cd headhunter-crm-agent
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

Create local config from examples and keep real values outside git:

```bash
cp .env.example .env
# edit .env locally
export HH_PROFILE_PATH=/secure/server/path/profile.private.json
```

## Configuration

Common variables:

- `HH_CRM_DB_PATH` - local CRM database path
- `HH_PROFILE_PATH` - private candidate profile JSON
- `HH_USER_AGENT` - job-board user agent
- `HH_ACCESS_TOKEN` - optional API token
- `HH_RESUME_ID` - optional resume ID
- `HH_BROWSER_USER_DATA_DIR` - private browser profile path

## Tests

```bash
python -m pytest -q
```

## Repository status

Portfolio/public-safe branch. Production secrets and personal data are not part of this repository.

## License

Proprietary. See `LICENSE`.
