#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
if [ "${1:-}" = "--demo" ]; then .venv/bin/python -m backend.seed; fi
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
