#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Parallel Middle Python Backend lane for the second HH resume.
# Permanently dry-run: it searches/scores/prepares only and must not click HH submit.
# Live sends require an explicit one-off approved lane and operator confirmation.
export HH_AUTO_APPLY_RESUME_ID="${HH_AUTO_APPLY_RESUME_ID:-45dcf0f8ff10ab20210039ed1f70384c77345a}"
export HH_PROFILE_PATH="${HH_PROFILE_PATH:-./data/profile.aleksandr.middle_python_backend.json}"
export HH_AUTO_APPLY_SEND="0"
export HH_AUTO_APPLY_ALLOW_LIVE_SEND="0"
export HH_AUTO_APPLY_HEADLESS="${HH_AUTO_APPLY_HEADLESS:-1}"
export HH_AUTO_APPLY_FETCH_DETAILS="${HH_AUTO_APPLY_FETCH_DETAILS:-1}"
export HH_AUTO_APPLY_REQUIRE_DETAILS="${HH_AUTO_APPLY_REQUIRE_DETAILS:-1}"
export HH_AUTO_APPLY_PER_QUERY="${HH_AUTO_APPLY_PER_QUERY:-20}"
export HH_AUTO_APPLY_DRAFT_THRESHOLD="${HH_AUTO_APPLY_DRAFT_THRESHOLD:-85}"
export HH_AUTO_APPLY_MIN_SCORE="${HH_AUTO_APPLY_MIN_SCORE:-85}"
export HH_AUTO_APPLY_LIMIT="${HH_AUTO_APPLY_LIMIT:-3}"
export HH_AUTO_APPLY_DAILY_LIMIT="${HH_AUTO_APPLY_DAILY_LIMIT:-5}"
export HH_AUTO_APPLY_COMPANY_GUARD="${HH_AUTO_APPLY_COMPANY_GUARD:-strict}"
export HH_AUTO_APPLY_QUERIES="${HH_AUTO_APPLY_QUERIES:-Middle Python Backend developer|Python Backend developer|Backend Python developer|Python backend разработчик|FastAPI developer|Django backend developer|Python API developer|Python REST API developer|Разработчик Python backend|Python Django разработчик}"

exec ./scripts/run_hh_auto_apply.sh "$@"
