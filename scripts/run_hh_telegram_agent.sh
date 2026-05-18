#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=hh_telegram_env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hh_telegram_env.sh"

exec "$HH_TELEGRAM_PYTHON" -m app.telegram_agent
