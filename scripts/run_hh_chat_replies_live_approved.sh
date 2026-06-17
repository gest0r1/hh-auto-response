#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Fail-closed lane for HH chat follow-ups after wrong/looped reply incident.
# This is intentionally separate from run_hh_chat_replies_hourly.sh, which stays dry-run by default.
# Live sends require explicit one-off env override after dry-run inspection:
# - only HH in-chat replies are sent;
# - owner-approved all-title mode: QA/MLOps/DevOps titles are answered honestly instead of silently blocked;
# - external handoffs are treated as terminal/no-reply in HH by default;
# - manual-required answers, duplicates and closed chats are still blocked/skipped;
# - external Google/Telegram/interview tasks are not submitted automatically.
export HH_CHAT_REPLY_SEND="${HH_CHAT_REPLY_SEND:-0}"
export HH_CHAT_REPLY_ALLOW_LIVE_SEND="${HH_CHAT_REPLY_ALLOW_LIVE_SEND:-0}"
export HH_CHAT_REPLY_ANSWER_LOW_FIT="${HH_CHAT_REPLY_ANSWER_LOW_FIT:-1}"
export HH_CHAT_REPLY_ACK_EXTERNAL_HANDOFF="${HH_CHAT_REPLY_ACK_EXTERNAL_HANDOFF:-0}"
export HH_CHAT_EXTERNAL_SUBMIT=0
export HH_CHAT_REPLY_HEADLESS="${HH_CHAT_REPLY_HEADLESS:-1}"
export HH_CHAT_REPLY_LIMIT="${HH_CHAT_REPLY_LIMIT:-8}"
export HH_CHAT_REPLY_MAX_CHATS="${HH_CHAT_REPLY_MAX_CHATS:-140}"

exec ./scripts/run_hh_chat_replies.sh "$@"
