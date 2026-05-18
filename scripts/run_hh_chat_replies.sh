#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hh_telegram_env.sh
source "$SCRIPT_DIR/hh_telegram_env.sh"

export HH_CRM_DB_PATH="${HH_CRM_DB_PATH:-./data/hh_crm.sqlite3}"

if [[ -z "${HH_CHAT_REPLY_PYTHON:-}" ]]; then
  if [[ -n "${HH_TELEGRAM_PYTHON:-}" ]]; then
    HH_CHAT_REPLY_PYTHON="$HH_TELEGRAM_PYTHON"
  elif [[ -x /usr/local/lib/hermes-agent/venv/bin/python3 ]]; then
    HH_CHAT_REPLY_PYTHON=/usr/local/lib/hermes-agent/venv/bin/python3
  elif command -v python3 >/dev/null 2>&1; then
    HH_CHAT_REPLY_PYTHON="$(command -v python3)"
  elif [[ -x /usr/bin/python3 ]]; then
    HH_CHAT_REPLY_PYTHON=/usr/bin/python3
  elif command -v python >/dev/null 2>&1; then
    HH_CHAT_REPLY_PYTHON="$(command -v python)"
  else
    echo "HH chat replies: no Python interpreter found" >&2
    exit 127
  fi
fi

"$HH_CHAT_REPLY_PYTHON" -m app.cli init-db >/tmp/hh-crm-chat-replies-init.json

cmd=(
  "$HH_CHAT_REPLY_PYTHON" -m app.cli reply-hh-chats
  --limit "${HH_CHAT_REPLY_LIMIT:-5}"
  --max-chats "${HH_CHAT_REPLY_MAX_CHATS:-80}"
  --state-file "${HH_CHAT_REPLY_STATE_FILE:-./data/hh_chat_reply_state.json}"
)

if [[ "${HH_CHAT_REPLY_HEADLESS:-0}" == "1" ]]; then
  cmd+=(--headless)
fi

# Real HH chat messages are opt-in. SEND=0 only drafts and logs candidates.
if [[ "${HH_CHAT_REPLY_SEND:-0}" == "1" ]]; then
  cmd+=(--send)
fi

if [[ "${HH_CHAT_EXTERNAL_SUBMIT:-0}" == "1" ]]; then
  cmd+=(--external-submit)
fi

cmd+=("$@")
exec "${cmd[@]}"
