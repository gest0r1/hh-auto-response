# HH CRM Agent Implementation Plan

> For Hermes: continue with TDD and keep external sending disabled until explicit confirmation.

**Goal:** build a full-stack HH.ru CRM agent with search, scoring, drafts, feedback learning, and dashboard.

**Architecture:** Python/FastAPI backend with SQLite CRM and deterministic core modules; React/Vite dashboard reads backend summaries; HH sending remains gated behind future OAuth-confirmed flow.

**Tech stack:** Python 3.11, FastAPI, SQLite, pytest, React, TypeScript, Vite.

## Completed MVP slices

1. Core scoring tests and implementation.
2. Cover-letter generator tests and implementation.
3. Learning engine tests and implementation.
4. SQLite repository tests and implementation.
5. Agent orchestration test and implementation.
6. FastAPI endpoints.
7. React/Vite visual dashboard.
8. Demo seed data and smoke checks.

## Next bite-sized tasks

### Task 1: Profile import

- Add `profiles` table.
- Add `ProfileRepository` methods.
- Add CLI `import-profile data/profile.json`.
- Add API `GET/PUT /api/profile`.
- Test: import template and verify generator uses real cases/portfolio.

### Task 2: Telegram review queue

- Add endpoint for pending drafts.
- Add message formatter for Telegram.
- Add button actions: approve, edit, reject, archive.
- Test: feedback updates application state and learning weights.

### Task 3: HH browser auto-apply with safe limits

- Add one-shot `auto-apply` CLI: public search → score → draft → browser runner.
- Keep real submit behind explicit `--send`; dry-run fills forms only.
- Add daily limit and duplicate guard through draft/sent statuses.
- Store `sent_at`, feedback event, and run log for audit.
- Test: mocked browser send success, dry-run, and daily-limit stop.

### Task 4: HH OAuth and safe send

- Add OAuth token storage without printing secrets.
- Add resume list endpoint.
- Implement send action via negotiations only for approved application.
- Add daily limit and duplicate guard.
- Test: mocked HH send success/failure.

### Task 5: Follow-up agent

- Add follow-up due calculation.
- Generate follow-up draft after 2–4 days without reply.
- Dashboard section for due follow-ups.

### Task 6: Conversion analytics

- Track phrase/features per draft.
- Link positive outcomes to text patterns.
- Show best-performing angles in dashboard.
