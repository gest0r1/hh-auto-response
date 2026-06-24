#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Approved live lane for the Middle Python Backend HH resume.
# Owner-approved high-volume mode:
# - explicit middle resume id, never HH default selection;
# - middle profile/positioning source;
# - details are fetched when available; missing details do not starve the high-volume queue;
# - 50 per run and 50 per day for this resume lane;
# - real HH submit is double-gated by scripts/run_hh_auto_apply.sh and the repo stop flag.
export HH_AUTO_APPLY_SEND="${HH_AUTO_APPLY_SEND:-1}"
export HH_AUTO_APPLY_ALLOW_LIVE_SEND="${HH_AUTO_APPLY_ALLOW_LIVE_SEND:-1}"
export HH_AUTO_APPLY_RESUME_ID="${HH_AUTO_APPLY_RESUME_ID:-45dcf0f8ff10ab20210039ed1f70384c77345a}"
export HH_PROFILE_PATH="${HH_PROFILE_PATH:-./data/profile.aleksandr.middle_python_backend.json}"
export HH_AUTO_APPLY_HEADLESS="${HH_AUTO_APPLY_HEADLESS:-1}"
export HH_AUTO_APPLY_FETCH_DETAILS="${HH_AUTO_APPLY_FETCH_DETAILS:-1}"
export HH_AUTO_APPLY_REQUIRE_DETAILS="${HH_AUTO_APPLY_REQUIRE_DETAILS:-0}"
export HH_AUTO_APPLY_PER_QUERY="${HH_AUTO_APPLY_PER_QUERY:-50}"
export HH_AUTO_APPLY_PAGES="${HH_AUTO_APPLY_PAGES:-5}"
export HH_AUTO_APPLY_DRAFT_THRESHOLD="${HH_AUTO_APPLY_DRAFT_THRESHOLD:-75}"
export HH_AUTO_APPLY_MIN_SCORE="${HH_AUTO_APPLY_MIN_SCORE:-75}"
export HH_AUTO_APPLY_LIMIT="${HH_AUTO_APPLY_LIMIT:-50}"
export HH_AUTO_APPLY_DAILY_LIMIT="${HH_AUTO_APPLY_DAILY_LIMIT:-50}"
export HH_AUTO_APPLY_COMPANY_GUARD="${HH_AUTO_APPLY_COMPANY_GUARD:-family}"
export HH_AUTO_APPLY_QUERIES="${HH_AUTO_APPLY_QUERIES:-Middle Python Backend developer|Middle Python developer|Python Backend developer|Python Backend Engineer|Backend Python developer|Python developer remote|Python developer удаленно|Разработчик Python удаленно|Backend developer Python|Backend developer remote|Python backend разработчик|FastAPI developer|Django backend developer|Python API developer|Python REST API developer|Разработчик Python backend|Python Django разработчик|Python API integrations engineer|Backend integrations engineer|AI Backend Engineer|LLM Backend Engineer|AI agents developer|AgentOps engineer|RAG engineer}"

exec ./scripts/run_hh_auto_apply.sh "$@"
