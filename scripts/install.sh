#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "ERROR: Python 3.11+ is required." >&2
    exit 127
  fi
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"ERROR: Python 3.11+ is required, found {sys.version.split()[0]}")
PY

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -e '.[dev,browser]'
"$VENV_PYTHON" -m playwright install chromium

mkdir -p data logs .secrets

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
else
  echo "Keeping existing .env"
fi

if [[ ! -f data/profile.local.json ]]; then
  cp data/profile.template.json data/profile.local.json
  echo "Created data/profile.local.json from template"
else
  echo "Keeping existing data/profile.local.json"
fi

if command -v npm >/dev/null 2>&1; then
  (
    cd dashboard
    npm ci
  )
else
  echo "WARNING: npm was not found; dashboard dependencies were not installed." >&2
  echo "Install Node.js 22+ and run: cd dashboard && npm ci" >&2
fi

cat <<'EOF'

HH Auto Response installation completed.

Next steps:
  1. Edit .env
  2. Edit data/profile.local.json
  3. source .venv/bin/activate
  4. export PYTHONPATH=backend
  5. python -m app.cli init-db
  6. Run a dry-run search before enabling any live actions.

Repository: https://github.com/gest0r1/hh-auto-response
EOF
