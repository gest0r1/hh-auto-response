#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Hourly autonomous HH chat follow-up. User explicitly asked the agent to reply in HH chats.
export HH_CHAT_REPLY_SEND="${HH_CHAT_REPLY_SEND:-1}"
export HH_CHAT_EXTERNAL_SUBMIT="${HH_CHAT_EXTERNAL_SUBMIT:-1}"
export HH_CHAT_REPLY_HEADLESS="${HH_CHAT_REPLY_HEADLESS:-1}"
export HH_CHAT_REPLY_LIMIT="${HH_CHAT_REPLY_LIMIT:-8}"
export HH_CHAT_REPLY_MAX_CHATS="${HH_CHAT_REPLY_MAX_CHATS:-120}"

exec ./scripts/run_hh_chat_replies.sh "$@"
