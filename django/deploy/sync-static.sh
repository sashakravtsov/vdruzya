#!/usr/bin/env bash
# Rebuild Manifest hashed static after rsync. Without this, browsers keep old
# realtime.*.js / classic.*.css and compose toolbar buttons appear dead.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
else
  PY=python3
fi
"$PY" manage.py collectstatic --noinput -v0
echo "OK   collectstatic (manifest hashed assets)"
