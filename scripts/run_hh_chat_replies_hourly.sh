#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Hourly HH chat follow-up. Fail-closed after wrong-template incidents:
# by default this job only drafts/logs candidates. Real sends require an explicit
# one-run override: HH_CHAT_REPLY_SEND=1 HH_CHAT_REPLY_ALLOW_LIVE_SEND=1.
export HH_CHAT_REPLY_SEND="${HH_CHAT_REPLY_SEND:-0}"
export HH_CHAT_REPLY_ALLOW_LIVE_SEND="${HH_CHAT_REPLY_ALLOW_LIVE_SEND:-0}"
export HH_CHAT_EXTERNAL_SUBMIT="${HH_CHAT_EXTERNAL_SUBMIT:-0}"
export HH_CHAT_REPLY_HEADLESS="${HH_CHAT_REPLY_HEADLESS:-1}"
export HH_CHAT_REPLY_LIMIT="${HH_CHAT_REPLY_LIMIT:-8}"
export HH_CHAT_REPLY_MAX_CHATS="${HH_CHAT_REPLY_MAX_CHATS:-120}"

exec ./scripts/run_hh_chat_replies.sh "$@"
