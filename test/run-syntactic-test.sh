#!/usr/bin/env bash
set -euo pipefail

# Usage: run-syntactic-test.sh <expected-exit-code> <file.py>
#   exit 0: well-formed (accepted)
#   exit 1: unsupported (permanently excluded)
#   exit 2: not yet supported (pending)

expected="$1"
script="$2"

actual=$(python3 src/purepy_parse.py "$script" 2>&1; echo $?)
exit_code="${actual##*$'\n'}"

if [ "$exit_code" != "$expected" ]; then
  echo "::error file=$script::Expected exit code $expected but got $exit_code"
  echo "$actual"
  exit 1
fi
