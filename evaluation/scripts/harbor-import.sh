#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
venv=.cache/harbor-venv
if [ ! -x "$venv/bin/python" ]; then
  uv venv --python 3.12 "$venv"
fi
uv pip sync --python "$venv/bin/python" harbor/requirements.lock
"$venv/bin/python" harbor_runner.py migrate --recorded-only "$@"
