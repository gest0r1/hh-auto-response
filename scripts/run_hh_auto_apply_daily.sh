#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Daily HH auto-apply is fail-closed after duplicate/wrong-send incidents.
# Cron must stay dry-run. Real submit clicks require a deliberate one-off override:
# HH_AUTO_APPLY_SEND=1 HH_AUTO_APPLY_ALLOW_LIVE_SEND=1 ./scripts/run_hh_auto_apply_daily.sh
export HH_AUTO_APPLY_SEND="${HH_AUTO_APPLY_SEND:-0}"
export HH_AUTO_APPLY_ALLOW_LIVE_SEND="${HH_AUTO_APPLY_ALLOW_LIVE_SEND:-0}"
export HH_AUTO_APPLY_HEADLESS="${HH_AUTO_APPLY_HEADLESS:-1}"
export HH_AUTO_APPLY_FETCH_DETAILS="${HH_AUTO_APPLY_FETCH_DETAILS:-1}"
export HH_AUTO_APPLY_REQUIRE_DETAILS="${HH_AUTO_APPLY_REQUIRE_DETAILS:-1}"
export HH_AUTO_APPLY_PER_QUERY="${HH_AUTO_APPLY_PER_QUERY:-20}"
export HH_AUTO_APPLY_DRAFT_THRESHOLD="${HH_AUTO_APPLY_DRAFT_THRESHOLD:-80}"
export HH_AUTO_APPLY_MIN_SCORE="${HH_AUTO_APPLY_MIN_SCORE:-80}"
export HH_AUTO_APPLY_LIMIT="${HH_AUTO_APPLY_LIMIT:-20}"
export HH_AUTO_APPLY_DAILY_LIMIT="${HH_AUTO_APPLY_DAILY_LIMIT:-30}"
export HH_AUTO_APPLY_QUERIES="${HH_AUTO_APPLY_QUERIES:-Python Backend developer|Python Backend Engineer|Backend Python developer|FastAPI developer|Django backend developer|Python API integrations engineer|Backend integrations engineer|AI Backend Engineer|LLM Backend Engineer|AI agents developer|AgentOps engineer|LLM platform engineer|RAG engineer}"

exec ./scripts/run_hh_auto_apply.sh "$@"
