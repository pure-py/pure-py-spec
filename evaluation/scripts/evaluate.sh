#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-.venv}"
uv sync --locked
uv run --locked python evaluation.py run "$@"
