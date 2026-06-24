# HH CRM Agent — текущий handoff по совместной работе

Snapshot: 2026-06-24 10:15 UTC
Repo: `/root/home/headhunter-crm-agent`
Branch: `main`
Final commit/push: recorded in git history; see `git log -1 --oneline` and the final chat summary for the pushed commit hash.

Этот файл — рабочий handoff для следующего захода в проект. Он описывает, что уже сделано, какие последние нововведения добавлены, какие safety-гейты активны, где лежит источник правды и как продолжать работу без повторения прошлых ошибок.

## 1. Коротко: что сейчас построено

HH CRM Agent сейчас ведёт локальную CRM по HH-откликам, вакансиям, чатам и внешним формам. Основной режим — безопасная автоматизация: поиск/скоринг/черновики/очередь, а любые реальные отправки должны быть привязаны к конкретной строке CRM и защищены несколькими гейтами.

Ключевые направления текущей работы:

1. **Source-of-truth hardening**: перед любой формой, чатом или отправкой смотреть точную строку `applications`/`vacancies` в `data/hh_crm.sqlite3`, включая `application_id`, `vacancy_id`, `resume_id`, статус и историю.
2. **Две HH-резюмные линии**:
   - main 300k Python Backend / AI Backend: `b2b0d680ff1065a62b0039ed1f4f426b6d6b73`;
   - middle 200k Python Backend: `45dcf0f8ff10ab20210039ed1f70384c77345a`.
3. **Fail-closed отправки**: dry-run wrappers остаются dry-run; live wrappers требуют явных env-гейтов и/или owner approval.
4. **Chat reply hardening**: больше нельзя автоотправлять generic/context-focus ответы на конкретные вопросы; такие ответы блокируются как `blocked_unsafe_auto_reply`.
5. **External handoff**: Google Forms/Telegram/external links распознаются, готовятся ответы и handoff, но external submit по умолчанию отключён.
6. **Middle profile corrected**: middle profile — это **полная копия текущего main 300k профиля**, меняются только middle-позиционирование и зарплата 200k; не lean/short версия.

## 2. Source of truth / строгие правила перед действиями

Перед любым live-действием:

```bash
cd /root/home/headhunter-crm-agent
PYTHONPATH=backend .venv/bin/python3 -m app.cli list-applications --limit 20
PYTHONPATH=backend .venv/bin/python3 -m app.cli list-external-interactions --limit 20
```

Нельзя выводить/отправлять ответ из памяти или только из текста вакансии. Нужно привязаться к CRM:

- `applications.id` / `application_id`;
- `vacancy_id`;
- `resume_id`;
- `status`;
- `cover_letter` / `feedback_events` / chat state;
- external interactions, если форма/внешний чат уже обрабатывались.

Особенно важно из-за двух резюме: не выбирать resume по догадке из названия вакансии/зарплаты/уровня. Resume id берётся из CRM application row.

## 3. Текущее состояние runtime/CRM

Команда-снимок выполнялась 2026-06-24:

```bash
PYTHONPATH=backend .venv/bin/python3 - <<'PY'
import sqlite3, json
con=sqlite3.connect('data/hh_crm.sqlite3'); con.row_factory=sqlite3.Row
for table in ['applications','vacancies','feedback_events','run_logs','external_interactions']:
    print(table, con.execute(f'select count(*) from {table}').fetchone()[0])
PY
```

Сводка на момент handoff:

| Таблица | Count |
|---|---:|
| `applications` | 1017 |
| `vacancies` | 5858 |
| `feedback_events` | 967 |
| `run_logs` | 1051 |
| `external_interactions` | 2 |

Статусы applications по `resume_id`:

| resume_id | status | count | last_updated |
|---|---|---:|---|
| `45dcf0f8ff10ab20210039ed1f70384c77345a` | archived | 12 | 2026-06-21 16:43:47 |
| `45dcf0f8ff10ab20210039ed1f70384c77345a` | blocked | 14 | 2026-06-24 09:57:18 |
| `45dcf0f8ff10ab20210039ed1f70384c77345a` | reply | 1 | 2026-06-22 13:32:22 |
| `45dcf0f8ff10ab20210039ed1f70384c77345a` | sent | 35 | 2026-06-24 09:57:18 |
| `NULL` legacy rows | archived | 76 | 2026-06-19 21:26:21 |
| `NULL` legacy rows | blocked | 111 | 2026-06-18 18:47:53 |
| `NULL` legacy rows | rejected | 1 | 2026-05-25 16:19:29 |
| `NULL` legacy rows | sent | 619 | 2026-06-19 09:34:50 |
| `b2b0d680ff1065a62b0039ed1f4f426b6d6b73` | archived | 76 | 2026-06-24 09:53:16 |
| `b2b0d680ff1065a62b0039ed1f4f426b6d6b73` | blocked | 24 | 2026-06-23 15:52:44 |
| `b2b0d680ff1065a62b0039ed1f4f426b6d6b73` | sent | 48 | 2026-06-24 10:01:52 |

External interactions:

| kind | status | count | last_updated |
|---|---|---:|---|
| `google_form` | `dry_run_prepared_not_submitted` | 1 | 2026-06-21 10:06:46 |
| `google_form` | `submitted` | 1 | 2026-06-21 11:38:04 |

Flags:

| Flag | State | Meaning |
|---|---|---|
| `data/hh_auto_apply_live_send_disabled.flag` | absent | auto-apply live lane is not globally stopped by repo flag |
| `data/hh_chat_live_send_disabled.flag` | present | live HH chat sends are globally stopped until explicit removal/review |
| `data/hh_auto_apply_live_send_enabled.audit` | present locally | local audit marker only; ignored from git |

Recent run logs showed live auto-apply activity by resume lane:

| run_id | at | resume_id | sent | queued | blocked | notes |
|---:|---|---|---:|---:|---:|---|
| 1051 | 2026-06-24 10:01:52 | main 300k | 9 | 9 | 0 | daily remaining 41; 1693 seen/saved |
| 1050 | 2026-06-24 09:57:18 | middle 200k | 4 | 5 | 1 | one `submit_unverified`; daily remaining 46 |
| 1049 | 2026-06-24 06:52:03 | middle 200k | 0 | 0 | 0 | search only |
| 1048 | 2026-06-24 06:52:03 | main 300k | 0 | 0 | 0 | search only |

## 4. Cron / scheduled automation

Current relevant crontab entries:

```cron
@reboot /root/home/headhunter-crm-agent/scripts/ensure_hh_telegram_agent.sh >> /root/home/headhunter-crm-agent/logs/hh_telegram_watchdog.log 2>&1
*/5 * * * * /root/home/headhunter-crm-agent/scripts/ensure_hh_telegram_agent.sh >> /root/home/headhunter-crm-agent/logs/hh_telegram_watchdog.log 2>&1
10 6 * * * /root/home/headhunter-crm-agent/scripts/run_hh_telegram_daily.sh >> /root/home/headhunter-crm-agent/logs/hh_telegram_daily.log 2>&1
25 6,9,12,15,18 * * * /root/home/headhunter-crm-agent/scripts/run_hh_auto_apply_live_approved.sh >> /root/home/headhunter-crm-agent/logs/hh_auto_apply.log 2>&1
35 6,9,12,15,18 * * * /root/home/headhunter-crm-agent/scripts/run_hh_auto_apply_middle_live_approved.sh >> /root/home/headhunter-crm-agent/logs/hh_auto_apply_middle.log 2>&1
# HH chat replies live cron is disabled after wrong/looped reply incident.
```

Important: chat live cron is commented out/disabled. `data/hh_chat_live_send_disabled.flag` also exists, so even accidental live chat wrapper invocation is fail-closed unless reviewed.

## 5. Recent code/features added

### 5.1 DB/schema/repository

Files:

- `backend/app/db.py`
- `backend/app/repository.py`
- `backend/app/cli.py`
- `tests/test_crm_external_interactions.py`
- `tests/test_cli.py`

Changes:

- Added `external_interactions` table with `application_id`, `vacancy_id`, `kind`, `target_url`, `status`, `resume_id`, `payload_json`, `notes`, timestamps.
- `CRMRepository.record_external_interaction(...)` now requires a real `application_id`; it snapshots `application.resume_id` into the external event.
- Added listing/filtering external interactions.
- Daily sent count can be scoped by `resume_id`, so main and middle lanes have separate daily caps.
- Queue/review logic can work per resume lane and preserve application `resume_id`.
- CLI gained external interaction operations and resume-aware apply/browser queue behavior.

Operational consequence: external forms and chat handoffs are auditably attached to a CRM application, not to an inferred vacancy/context.

### 5.2 HH browser apply runner

Files:

- `backend/app/hh_browser.py`
- `tests/test_hh_browser.py`

Changes:

- `ApplyDraft` now carries `resume_id`.
- Apply URL is augmented with `?resume=<resume_id>` when available.
- Runner tries to select the requested resume on the HH apply form.
- If requested resume is missing, result is `resume_not_found` instead of silently sending via default HH resume.
- Submit confirmation is verified by HH page markers; if click happened but confirmation is absent, status is `submit_unverified`.
- Login and navigation failures are explicit statuses.

Why it matters: this was added after wrong-resume/duplicate-send risk. Never let HH default resume choice decide live send.

### 5.3 Auto-apply lanes and high-volume mode

Files:

- `backend/app/auto_apply.py`
- `backend/app/agent.py`
- `backend/app/scoring.py`
- `scripts/run_hh_auto_apply.sh`
- `scripts/run_hh_auto_apply_daily.sh`
- `scripts/run_hh_auto_apply_live_approved.sh`
- `scripts/run_hh_auto_apply_middle_daily.sh`
- `scripts/run_hh_auto_apply_middle_live_approved.sh`
- `tests/test_auto_apply.py`
- `tests/test_profile_positioning.py`
- `tests/test_scoring.py`
- `tests/test_shell_live_gates.py`

Changes:

- Main live lane defaults to 50/run and 50/day for main resume.
- Middle live lane added with middle resume id and `HH_PROFILE_PATH=./data/profile.aleksandr.middle_python_backend.json`, also 50/run and 50/day.
- Dry-run daily wrappers stay permanently dry-run.
- `run_hh_auto_apply.sh` has an emergency repo flag: `data/hh_auto_apply_live_send_disabled.flag`; if present, it forces `HH_AUTO_APPLY_SEND=0` and `HH_AUTO_APPLY_ALLOW_LIVE_SEND=0`.
- Live wrappers still require `HH_AUTO_APPLY_SEND=1` and `HH_AUTO_APPLY_ALLOW_LIVE_SEND=1`.
- High-volume live search uses broader Python Backend / AI Backend / AgentOps / LLM / RAG / AI Product queries and a `family` company guard for noisy duplicate employer families.
- Scoring/cover letters adjusted toward Python Backend / AI Backend and stronger proof cases.

### 5.4 Middle resume/profile correction

Files:

- `data/profile.aleksandr.middle_python_backend.json`
- `docs/hh_middle_python_backend_resume_draft_2026-06-19.md`
- `tests/test_profile_positioning.py`

Final decision:

- Middle lane must be a **full copy of main profile**, not shortened.
- Only middle positioning/title and 200k salary expectation differ.
- Strong cases remain available in the same full case set; do not strip senior-looking proof out of the profile.

Current middle profile key values:

```json
{
  "headline": "Middle Python Backend Developer / AI Backend Developer",
  "min_monthly_salary": 200000,
  "salary_positioning": {
    "active_hh_resume": "Middle Python Backend Developer",
    "active_hh_resume_salary_rub": 200000
  }
}
```

### 5.5 HH chat replies hardening

Files:

- `backend/app/hh_chat.py`
- `scripts/run_hh_chat_replies.sh`
- `scripts/run_hh_chat_replies_hourly.sh`
- `scripts/run_hh_chat_replies_live_approved.sh`
- `scripts/manual_hh_chat_send_approved.py`
- `tests/test_hh_chat.py`
- `tests/test_shell_live_gates.py`

Changes:

- Generic/context-focus replies to concrete recruiter questions are blocked as `blocked_unsafe_auto_reply`.
- Manual-required answers are blocked as `blocked_manual_review`.
- Repeated greetings are stripped on follow-ups (`followup_no_greeting`).
- State prevents duplicate answers and duplicate external alerts.
- External links are routed to handoff, not blind HH replies.
- Google Forms can be prepared/filled through handler but external submit remains off by default.
- `run_hh_chat_replies.sh` respects `data/hh_chat_live_send_disabled.flag` and forces dry-run if the flag exists.
- Live chat wrapper is intentionally fail-closed: by default `HH_CHAT_REPLY_SEND=0`, `HH_CHAT_REPLY_ALLOW_LIVE_SEND=0`, `HH_CHAT_EXTERNAL_SUBMIT=0`.
- Manual approved chat sender was refactored to load approvals from a local JSON file via `HH_CHAT_MANUAL_APPROVED_JSON`, so chat ids/recruiter text/approved replies are not committed.

Do not re-enable chat live cron without dry-run review and exact question→answer audit.

### 5.6 Chat/question answer coverage

`backend/app/hh_chat.py` now includes deterministic templates/guards for:

- concrete stack/database experience;
- Flask/SQLAlchemy/Node/Python+Vue honesty;
- algorithms/data structures examples;
- autotest/CI/metrics and network/logs diagnostics honesty;
- Django/FastAPI screening with salary/logistics;
- office-first-year/full-time office readiness;
- no-more-questions prompts;
- contract/location/B2B logistics;
- external handoff and Google Form answer prep.

Safety pattern: if a prompt is concrete but no precise template matches, the runner returns manual-review/block instead of a generic positive answer.

### 5.7 Candidate profile and cover letters

Files:

- `data/profile.aleksandr.json`
- `docs/cover-letter-methodology.md`
- `backend/app/responses.py`
- `tests/test_responses.py`

Changes:

- Candidate positioning remains Python Backend / AI Backend / AgentOps.
- Stronger post-Viably cases are preferred when relevant: Crypto Arbitrage Platform, Transoff, WhyNotAI Telegram Agents.
- Salary wording stays flexible: can discuss 100k–200k for quick/remote/stable roles; 300k+ is comfort target, not hard blocker.
- Current employment answer: no formal permanent employment, ready to start as soon as possible.

## 6. Files changed in this batch

Source/runtime-safe files intended for commit:

```text
.gitignore
backend/app/agent.py
backend/app/auto_apply.py
backend/app/cli.py
backend/app/db.py
backend/app/hh_browser.py
backend/app/hh_chat.py
backend/app/repository.py
backend/app/responses.py
backend/app/scoring.py
data/profile.aleksandr.json
data/profile.aleksandr.middle_python_backend.json
docs/cover-letter-methodology.md
docs/hh_middle_python_backend_resume_draft_2026-06-19.md
docs/handoff-current-hh-crm-agent-2026-06-24.md
scripts/manual_hh_chat_send_approved.py
scripts/run_hh_auto_apply.sh
scripts/run_hh_auto_apply_daily.sh
scripts/run_hh_auto_apply_live_approved.sh
scripts/run_hh_auto_apply_middle_daily.sh
scripts/run_hh_auto_apply_middle_live_approved.sh
scripts/run_hh_chat_replies.sh
tests/test_auto_apply.py
tests/test_cli.py
tests/test_crm_external_interactions.py
tests/test_hh_browser.py
tests/test_hh_chat.py
tests/test_profile_positioning.py
tests/test_responses.py
tests/test_scoring.py
tests/test_shell_live_gates.py
```

Local/runtime artifacts intentionally ignored from git:

```text
data/hh_*_disabled.flag*
data/hh_*_enabled.audit
data/hh_*_audit_*.md
data/hh_*_audit_*.json
data/hh_corrective_reply_drafts_*.md
data/hh_chat_manual_approved*.json
tmp/
```

Reason: these can contain recruiter messages, local state, screenshots, approval plans, audit trails, and other sensitive/session-specific data.

## 7. Verification performed

Commands run successfully before handoff commit:

```bash
cd /root/home/headhunter-crm-agent
PYTHONPATH=backend .venv/bin/python3 -m pytest tests/test_profile_positioning.py tests/test_auto_apply.py tests/test_hh_browser.py tests/test_hh_chat.py tests/test_crm_external_interactions.py tests/test_cli.py tests/test_responses.py tests/test_scoring.py tests/test_shell_live_gates.py -q
PYTHONPATH=backend .venv/bin/python3 -m pytest -q
PYTHONPATH=backend .venv/bin/python3 -m pytest --collect-only -q | awk -F': ' '/^tests\// {sum += $2} END {print sum " tests collected"}'
git diff --check
python3 -m json.tool data/profile.aleksandr.json >/dev/null
python3 -m json.tool data/profile.aleksandr.middle_python_backend.json >/dev/null
```

Results:

- targeted test subset: passed;
- full test suite: passed;
- collected tests: 197;
- `git diff --check`: passed;
- both profile JSON files valid.

## 8. Operational playbook

### Dry-run main auto-apply

```bash
cd /root/home/headhunter-crm-agent
HH_AUTO_APPLY_SEND=0 HH_AUTO_APPLY_ALLOW_LIVE_SEND=0 ./scripts/run_hh_auto_apply_daily.sh
```

### Dry-run middle auto-apply

```bash
cd /root/home/headhunter-crm-agent
HH_AUTO_APPLY_SEND=0 HH_AUTO_APPLY_ALLOW_LIVE_SEND=0 ./scripts/run_hh_auto_apply_middle_daily.sh
```

### Approved live main lane

Only after review/approval:

```bash
cd /root/home/headhunter-crm-agent
HH_AUTO_APPLY_SEND=1 HH_AUTO_APPLY_ALLOW_LIVE_SEND=1 ./scripts/run_hh_auto_apply_live_approved.sh
```

### Approved live middle lane

Only after review/approval:

```bash
cd /root/home/headhunter-crm-agent
HH_AUTO_APPLY_SEND=1 HH_AUTO_APPLY_ALLOW_LIVE_SEND=1 ./scripts/run_hh_auto_apply_middle_live_approved.sh
```

### Emergency stop auto-apply live sends

```bash
cd /root/home/headhunter-crm-agent
touch data/hh_auto_apply_live_send_disabled.flag
```

Remove only after verifying current HH resume selection and queue.

### HH chat dry-run

```bash
cd /root/home/headhunter-crm-agent
HH_CHAT_REPLY_SEND=0 HH_CHAT_REPLY_ALLOW_LIVE_SEND=0 ./scripts/run_hh_chat_replies_hourly.sh
```

### HH chat live send

Currently should be treated as disabled. If ever re-enabled:

1. remove/inspect `data/hh_chat_live_send_disabled.flag` only after explicit owner approval;
2. run dry-run;
3. review exact question→answer pairs;
4. run one-off with explicit gates, not cron.

```bash
HH_CHAT_REPLY_SEND=1 HH_CHAT_REPLY_ALLOW_LIVE_SEND=1 ./scripts/run_hh_chat_replies_live_approved.sh
```

### Manual approved chat send

Keep approval data local:

```bash
cat > data/hh_chat_manual_approved.local.json <<'JSON'
{
  "items": [
    {
      "key": "example",
      "chat_id": "...",
      "title": "...",
      "url": "https://hh.ru/chat/...",
      "expected_phrases": ["phrase that must be present"],
      "reply": "Exact owner-approved reply"
    }
  ]
}
JSON
HH_CHAT_MANUAL_APPROVED_JSON=data/hh_chat_manual_approved.local.json \
  PYTHONPATH=backend .venv/bin/python3 scripts/manual_hh_chat_send_approved.py
```

The JSON path is ignored by git.

## 9. Known risks / follow-ups

1. **Chat live replies remain risky**. The system is much safer now, but the correct default is still dry-run/manual review for HH chats.
2. **`submit_unverified` requires manual audit**. It means HH submit button was clicked but no delivered/answered confirmation marker was detected. Check the HH application row before retrying.
3. **Legacy `applications.resume_id IS NULL` rows exist**. They are historical and should not be used for new live decisions without reconstructing exact resume context.
4. **External submit stays off by default**. For Google Forms, review every generated answer and exact application row first.
5. **Middle profile must stay full-copy**. Do not reintroduce a shortened middle-only profile.
6. **Cron live auto-apply is active for both lanes**. If unexpected sends happen, first use the repo flag `data/hh_auto_apply_live_send_disabled.flag`, then inspect `logs/hh_auto_apply*.log` and `run_logs`.

## 10. Next-agent checklist

- [ ] Start with `git status --short --branch` and confirm repo matches pushed commit.
- [ ] Query CRM before any send/form/chat action.
- [ ] Check `data/hh_chat_live_send_disabled.flag` before any chat work.
- [ ] For middle lane, verify `HH_PROFILE_PATH=./data/profile.aleksandr.middle_python_backend.json` and resume id `45dcf0f8ff10ab20210039ed1f70384c77345a`.
- [ ] For main lane, verify resume id `b2b0d680ff1065a62b0039ed1f4f426b6d6b73`.
- [ ] Treat external forms as handoff/manual unless there is explicit owner approval and exact answer review.
- [ ] Run `PYTHONPATH=backend .venv/bin/python3 -m pytest -q` after code changes.

## 11. Git state at handoff creation

Before committing this handoff, branch was `main...origin/main` with local modifications/untracked source files. Recent commits before this batch:

```text
7f77c34 feat: expand HH auto apply volume and targeting
80ad6f4 fix: harden HH CRM server automation gates
c7dc1d2 fix: block incomplete HH checklist replies
d212bed fix: gate HH chat sends and route screening replies
5c28783 fix: restore Python backend positioning
bb4d48b feat: harden HH CRM automation
d3a6612 chore: publish safe portfolio snapshot
```

The final commit hash/push URL should be added to this section after commit/push.
