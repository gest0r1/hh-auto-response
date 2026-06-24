#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Approved live lane for HH auto-apply after cover-letter/scoring hardening.
# Owner-approved high-volume mode:
# - details are fetched when available; missing details do not starve the high-volume queue;
# - Junior-to-Teamlead Python Backend / AI Backend / AgentOps / LLM Platform queries plus HH top-feed AI titles;
# - review lane starts from 75 so high-volume mode does not starve the queue;
# - 50 per run and 50 per day by default, matching the requested high-volume range;
# - company-wide duplicate guard is relaxed to known noisy employer families only;
# - real HH submit is still double-gated here, never via the dry-run daily wrapper.
export HH_AUTO_APPLY_SEND="${HH_AUTO_APPLY_SEND:-1}"
export HH_AUTO_APPLY_ALLOW_LIVE_SEND="${HH_AUTO_APPLY_ALLOW_LIVE_SEND:-1}"
export HH_AUTO_APPLY_RESUME_ID="${HH_AUTO_APPLY_RESUME_ID:-b2b0d680ff1065a62b0039ed1f4f426b6d6b73}"
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
export HH_AUTO_APPLY_QUERIES="${HH_AUTO_APPLY_QUERIES:-Junior Python developer|Junior Python Backend developer|Junior Backend Python developer|Младший Python разработчик|Джун Python разработчик|Python Backend developer|Python Backend Engineer|Backend Python developer|Python developer remote|Python developer удаленно|Разработчик Python удаленно|Backend developer Python|Backend developer remote|Middle Python Backend developer|Middle Python developer|Senior Python Backend developer|Senior Python developer|Lead Python Backend developer|Team Lead Python|Python Team Lead|Tech Lead Python|Ведущий Python разработчик|Тимлид Python|Руководитель backend Python|FastAPI developer|Django backend developer|Junior FastAPI developer|Senior FastAPI developer|Python API integrations engineer|Backend integrations engineer|AI Backend Engineer|LLM Backend Engineer|AI Architect|Архитектор AI|AI Solution Architect|AI automation architect|AI Product CTO|Technical Co-founder|AI Product Engineer Lead|Middle AI Engineer Fullstack|Full-stack разработчик AI агентов|Fullstack AI agents|Fullstack Python developer|AI agents developer|AgentOps engineer|LLM platform engineer|RAG engineer}"

exec ./scripts/run_hh_auto_apply.sh "$@"
