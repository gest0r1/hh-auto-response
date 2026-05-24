#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=backend
export HH_CRM_DB_PATH="./data/hh_crm.sqlite3"
python -m app.cli init-db
python -m app.cli seed-demo >/tmp/hh-crm-seed.json
pytest -q
(cd dashboard && npm run build)
python - <<'PY'
from fastapi.testclient import TestClient
from app.api import app
client = TestClient(app)
assert client.get('/health').status_code == 200
summary = client.get('/api/dashboard').json()
assert summary['metrics']['vacancies_total'] >= 2
assert summary['metrics']['drafts_total'] >= 2
print('smoke ok', summary['metrics'])
PY
