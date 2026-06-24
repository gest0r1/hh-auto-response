#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hh_telegram_env.sh
source "$SCRIPT_DIR/hh_telegram_env.sh"

export HH_CRM_DB_PATH="${HH_CRM_DB_PATH:-./data/hh_crm.sqlite3}"

# Emergency fail-closed lock: after a wrong-answer incident, block all live HH chat sends
# even if --send/HH_CHAT_REPLY_ALLOW_LIVE_SEND are provided. Dry-runs still work.
HH_CHAT_LIVE_SEND_DISABLED_FLAG="${HH_CHAT_LIVE_SEND_DISABLED_FLAG:-./data/hh_chat_live_send_disabled.flag}"
if [[ -f "$HH_CHAT_LIVE_SEND_DISABLED_FLAG" ]]; then
  export HH_CHAT_REPLY_SEND=0
  export HH_CHAT_REPLY_ALLOW_LIVE_SEND=0
fi

if [[ -z "${HH_CHAT_REPLY_PYTHON:-}" ]]; then
  if [[ -x ./.venv/bin/python3 ]]; then
    HH_CHAT_REPLY_PYTHON=./.venv/bin/python3
  elif [[ -n "${HH_TELEGRAM_PYTHON:-}" ]]; then
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

caller_args=()
blocked_live_send=0
blocked_external_submit=0
caller_external_submit=0
live_send_allowed=0
if [[ "${HH_CHAT_REPLY_SEND:-0}" == "1" && "${HH_CHAT_REPLY_ALLOW_LIVE_SEND:-0}" == "1" ]]; then
  live_send_allowed=1
fi

for arg in "$@"; do
  case "$arg" in
    --send|--send=*)
      if [[ "$live_send_allowed" != "1" ]]; then
        blocked_live_send=1
      fi
      ;;
    --external-submit|--external-submit=*)
      if [[ "$live_send_allowed" != "1" ]]; then
        blocked_external_submit=1
      else
        caller_external_submit=1
      fi
      ;;
    *)
      caller_args+=("$arg")
      ;;
  esac
done

# Real HH chat messages are double-gated. SEND=0 only drafts and logs candidates.
# HH_CHAT_REPLY_ALLOW_LIVE_SEND must be set for the specific run; cron must stay dry-run.
if [[ "$live_send_allowed" == "1" ]]; then
  cmd+=(--send)
elif [[ "${HH_CHAT_REPLY_SEND:-0}" == "1" ]]; then
  blocked_live_send=1
fi

if [[ "${HH_CHAT_EXTERNAL_SUBMIT:-0}" == "1" || "$caller_external_submit" == "1" ]]; then
  if [[ "$live_send_allowed" != "1" ]]; then
    blocked_external_submit=1
  else
    cmd+=(--external-submit)
  fi
fi

if [[ "$blocked_live_send" == "1" ]]; then
  echo "HH chat replies: live send blocked (--send); set HH_CHAT_REPLY_SEND=1 and HH_CHAT_REPLY_ALLOW_LIVE_SEND=1" >&2
fi
if [[ "$blocked_external_submit" == "1" ]]; then
  echo "HH chat replies: external submit blocked (--external-submit); set HH_CHAT_REPLY_SEND=1 and HH_CHAT_REPLY_ALLOW_LIVE_SEND=1" >&2
fi

cmd+=("${caller_args[@]}")
exec "${cmd[@]}"
