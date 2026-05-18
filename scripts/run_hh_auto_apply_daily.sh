#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Daily autonomous HH sending. User explicitly approved real submit clicks.
export HH_AUTO_APPLY_SEND="${HH_AUTO_APPLY_SEND:-1}"
export HH_AUTO_APPLY_HEADLESS="${HH_AUTO_APPLY_HEADLESS:-1}"
export HH_AUTO_APPLY_FETCH_DETAILS="${HH_AUTO_APPLY_FETCH_DETAILS:-1}"
export HH_AUTO_APPLY_REQUIRE_DETAILS="${HH_AUTO_APPLY_REQUIRE_DETAILS:-1}"
export HH_AUTO_APPLY_PER_QUERY="${HH_AUTO_APPLY_PER_QUERY:-20}"
export HH_AUTO_APPLY_DRAFT_THRESHOLD="${HH_AUTO_APPLY_DRAFT_THRESHOLD:-85}"
export HH_AUTO_APPLY_MIN_SCORE="${HH_AUTO_APPLY_MIN_SCORE:-85}"
export HH_AUTO_APPLY_LIMIT="${HH_AUTO_APPLY_LIMIT:-20}"
export HH_AUTO_APPLY_DAILY_LIMIT="${HH_AUTO_APPLY_DAILY_LIMIT:-30}"
export HH_AUTO_APPLY_QUERIES="${HH_AUTO_APPLY_QUERIES:-AI agents developer|AI Agent Systems Engineer|AgentOps engineer|LLM platform engineer|MLOps AI platform engineer|AI automation architect|AI implementation engineer|Multi-agent systems engineer|Prompt engineer AI agents|MCP developer|RAG engineer|Full-stack AI engineer|Backend AI platform engineer|Telegram bot AI developer}"

exec ./scripts/run_hh_auto_apply.sh "$@"
