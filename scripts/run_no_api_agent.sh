#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=backend
export HH_CRM_DB_PATH="${HH_CRM_DB_PATH:-./data/hh_crm.sqlite3}"

python -m app.cli init-db >/tmp/hh-crm-no-api-init.json

if [[ $# -eq 0 ]]; then
  set -- \
    --query 'React Python CRM' \
    --query 'Telegram bot Python' \
    --query 'AI automation developer' \
    --query 'Full-stack developer удалённо' \
    --per-query 20 \
    --draft-threshold 80
fi

python -m app.cli run-public-once "$@" --export-review-queue ./data/review_queue.md
