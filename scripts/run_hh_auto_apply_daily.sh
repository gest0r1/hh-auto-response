#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Daily HH auto-apply is fail-closed after duplicate/wrong-send incidents.
# This daily/cron wrapper is permanently dry-run: it must never click HH submit.
# Manual live sends, if ever needed, must use scripts/run_hh_auto_apply.sh directly
# with an explicit one-off operator decision, not this scheduled wrapper.
export HH_AUTO_APPLY_SEND="0"
export HH_AUTO_APPLY_ALLOW_LIVE_SEND="0"
export HH_AUTO_APPLY_HEADLESS="${HH_AUTO_APPLY_HEADLESS:-1}"
export HH_AUTO_APPLY_FETCH_DETAILS="${HH_AUTO_APPLY_FETCH_DETAILS:-1}"
export HH_AUTO_APPLY_REQUIRE_DETAILS="${HH_AUTO_APPLY_REQUIRE_DETAILS:-1}"
export HH_AUTO_APPLY_PER_QUERY="${HH_AUTO_APPLY_PER_QUERY:-20}"
export HH_AUTO_APPLY_DRAFT_THRESHOLD="${HH_AUTO_APPLY_DRAFT_THRESHOLD:-90}"
export HH_AUTO_APPLY_MIN_SCORE="${HH_AUTO_APPLY_MIN_SCORE:-90}"
export HH_AUTO_APPLY_LIMIT="${HH_AUTO_APPLY_LIMIT:-3}"
export HH_AUTO_APPLY_DAILY_LIMIT="${HH_AUTO_APPLY_DAILY_LIMIT:-5}"
export HH_AUTO_APPLY_QUERIES="${HH_AUTO_APPLY_QUERIES:-Junior Python developer|Junior Python Backend developer|Младший Python разработчик|Джун Python разработчик|Python Backend developer|Python Backend Engineer|Backend Python developer|Middle Python Backend developer|Senior Python Backend developer|Lead Python Backend developer|Team Lead Python|Python Team Lead|Tech Lead Python|Ведущий Python разработчик|Тимлид Python|Руководитель backend Python|FastAPI developer|Django backend developer|Python API integrations engineer|Backend integrations engineer|AI Backend Engineer|LLM Backend Engineer|AI agents developer|AgentOps engineer|LLM platform engineer|RAG engineer}"

exec ./scripts/run_hh_auto_apply.sh "$@"
