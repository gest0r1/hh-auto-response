#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=hh_telegram_env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hh_telegram_env.sh"

# Daily refresh sends its own result/queue; do not also send startup messages.
export HH_TELEGRAM_SEND_ON_START=0

exec "$HH_TELEGRAM_PYTHON" -m app.telegram_daily "$@"
