#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH=backend
export HH_CRM_DB_PATH="${HH_CRM_DB_PATH:-./data/hh_crm.sqlite3}"

if [[ -z "${HH_AUTO_APPLY_PYTHON:-}" ]]; then
  if [[ -x /usr/local/lib/hermes-agent/venv/bin/python3 ]]; then
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
  --draft-threshold "${HH_AUTO_APPLY_DRAFT_THRESHOLD:-80}"
  --min-score "${HH_AUTO_APPLY_MIN_SCORE:-80}"
  --limit "${HH_AUTO_APPLY_LIMIT:-5}"
  --daily-limit "${HH_AUTO_APPLY_DAILY_LIMIT:-5}"
)

if [[ "${HH_AUTO_APPLY_HEADLESS:-0}" == "1" ]]; then
  cmd+=(--headless)
fi

if [[ "${HH_AUTO_APPLY_INCLUDE_DEMO:-0}" == "1" ]]; then
  cmd+=(--include-demo)
fi

# Real HH submit clicks are opt-in. Keep this 0 for dry-run/form-fill checks.
if [[ "${HH_AUTO_APPLY_SEND:-0}" == "1" ]]; then
  cmd+=(--send)
fi

cmd+=("$@")
exec "${cmd[@]}"
