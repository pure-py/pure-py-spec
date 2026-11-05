#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_PYTHON="$(cat ../.python-version)"
venv=.cache/harbor-venv
if [ ! -x "$venv/bin/python" ]; then
  uv venv "$venv"
fi
uv pip sync --python "$venv/bin/python" harbor/requirements.lock
"$venv/bin/python" harbor_runner.py import "$@"
