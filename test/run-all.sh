#!/usr/bin/env bash
# Thin shim that delegates to the Python runner.
exec python3 "$(dirname "$0")/run-all.py" "$@"
