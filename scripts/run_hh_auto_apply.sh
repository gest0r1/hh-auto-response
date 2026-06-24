#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=load_project_env.sh
source ./scripts/load_project_env.sh

export PYTHONPATH="${PYTHONPATH:-backend}"
export HH_CRM_DB_PATH="${HH_CRM_DB_PATH:-./data/hh_crm.sqlite3}"
export HH_USER_AGENT="${HH_USER_AGENT:-Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36}"

# Emergency fail-closed lock: after a wrong-resume incident, block all live HH
# auto-apply sends even if --send/HH_AUTO_APPLY_ALLOW_LIVE_SEND are provided.
# Dry-runs still work. Remove the flag only after the resume is verified.
HH_AUTO_APPLY_LIVE_SEND_DISABLED_FLAG="${HH_AUTO_APPLY_LIVE_SEND_DISABLED_FLAG:-./data/hh_auto_apply_live_send_disabled.flag}"
HH_AUTO_APPLY_LIVE_SEND_DISABLED=0
if [[ -f "$HH_AUTO_APPLY_LIVE_SEND_DISABLED_FLAG" ]]; then
  if [[ "${HH_AUTO_APPLY_SEND:-0}" == "1" || "${HH_AUTO_APPLY_ALLOW_LIVE_SEND:-0}" == "1" ]]; then
    HH_AUTO_APPLY_LIVE_SEND_DISABLED=1
  fi
  export HH_AUTO_APPLY_SEND=0
  export HH_AUTO_APPLY_ALLOW_LIVE_SEND=0
fi

if [[ -z "${HH_AUTO_APPLY_PYTHON:-}" ]]; then
  if [[ -x ./.venv/bin/python3 ]]; then
    HH_AUTO_APPLY_PYTHON=./.venv/bin/python3
  elif [[ -x /usr/local/lib/hermes-agent/venv/bin/python3 ]]; then
    HH_AUTO_APPLY_PYTHON=/usr/local/lib/hermes-agent/venv/bin/python3
  elif command -v python3 >/dev/null 2>&1; then
    HH_AUTO_APPLY_PYTHON="$(command -v python3)"
  elif [[ -x /usr/bin/python3 ]]; then
    HH_AUTO_APPLY_PYTHON=/usr/bin/python3
  elif command -v python >/dev/null 2>&1; then
    HH_AUTO_APPLY_PYTHON="$(command -v python)"
  else
    echo "HH auto-apply: no Python interpreter found" >&2
    exit 127
  fi
fi

"$HH_AUTO_APPLY_PYTHON" -m app.cli init-db >/tmp/hh-crm-auto-apply-init.json

query_args=()
if [[ -n "${HH_AUTO_APPLY_QUERIES:-}" ]]; then
  IFS='|' read -r -a __hh_auto_apply_queries <<< "$HH_AUTO_APPLY_QUERIES"
  for __hh_query in "${__hh_auto_apply_queries[@]}"; do
    __hh_query="${__hh_query#${__hh_query%%[![:space:]]*}}"
    __hh_query="${__hh_query%${__hh_query##*[![:space:]]}}"
    if [[ -n "$__hh_query" ]]; then
      query_args+=(--query "$__hh_query")
    fi
  done
  unset __hh_query __hh_auto_apply_queries
fi

if [[ ${#query_args[@]} -eq 0 ]]; then
  query_args=(
    --query "${HH_AUTO_APPLY_QUERY_1:-React Python CRM}"
    --query "${HH_AUTO_APPLY_QUERY_2:-Telegram bot Python}"
    --query "${HH_AUTO_APPLY_QUERY_3:-AI automation developer}"
    --query "${HH_AUTO_APPLY_QUERY_4:-Full-stack developer удалённо}"
  )
fi

cmd=(
  "$HH_AUTO_APPLY_PYTHON" -m app.cli auto-apply
  "${query_args[@]}"
  --per-query "${HH_AUTO_APPLY_PER_QUERY:-20}"
  --pages "${HH_AUTO_APPLY_PAGES:-1}"
  --draft-threshold "${HH_AUTO_APPLY_DRAFT_THRESHOLD:-80}"
  --min-score "${HH_AUTO_APPLY_MIN_SCORE:-80}"
  --limit "${HH_AUTO_APPLY_LIMIT:-5}"
  --daily-limit "${HH_AUTO_APPLY_DAILY_LIMIT:-5}"
  --company-guard "${HH_AUTO_APPLY_COMPANY_GUARD:-strict}"
)

if [[ -n "${HH_AUTO_APPLY_RESUME_ID:-}" ]]; then
  cmd+=(--resume-id "$HH_AUTO_APPLY_RESUME_ID")
fi

if [[ "${HH_AUTO_APPLY_HEADLESS:-0}" == "1" ]]; then
  cmd+=(--headless)
fi

if [[ "${HH_AUTO_APPLY_INCLUDE_DEMO:-0}" == "1" ]]; then
  cmd+=(--include-demo)
fi

caller_args=()
blocked_live_send=0
if [[ "${HH_AUTO_APPLY_LIVE_SEND_DISABLED:-0}" == "1" ]]; then
  blocked_live_send=1
fi
for arg in "$@"; do
  case "$arg" in
    --send|--send=*)
      if [[ "${HH_AUTO_APPLY_SEND:-0}" != "1" || "${HH_AUTO_APPLY_ALLOW_LIVE_SEND:-0}" != "1" ]]; then
        blocked_live_send=1
      fi
      ;;
    *)
      caller_args+=("$arg")
      ;;
  esac
done

# Real HH submit clicks are double-gated. Default cron/daily runs must only dry-run/fill.
if [[ "${HH_AUTO_APPLY_SEND:-0}" == "1" && "${HH_AUTO_APPLY_ALLOW_LIVE_SEND:-0}" == "1" ]]; then
  cmd+=(--send)
elif [[ "${HH_AUTO_APPLY_SEND:-0}" == "1" ]]; then
  blocked_live_send=1
fi

if [[ "$blocked_live_send" == "1" ]]; then
  echo "HH auto-apply: live send blocked (--send); set HH_AUTO_APPLY_SEND=1 and HH_AUTO_APPLY_ALLOW_LIVE_SEND=1" >&2
fi

cmd+=("${caller_args[@]}")
exec "${cmd[@]}"
