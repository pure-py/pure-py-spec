#!/usr/bin/env bash
set -uo pipefail

cd "$(dirname "$0")/.."

# Set up venv if not already active
if [ -z "${VIRTUAL_ENV:-}" ] && [ -z "${CI:-}" ]; then
  if [ ! -d .venv ]; then
    python3 -m venv .venv
  fi
  source .venv/bin/activate
fi

# Check Python version (PurePy targets 3.12+)
py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
  : # ok
else
  echo "Warning: Python $py_version detected; PurePy targets 3.12+" >&2
fi

interpreter="${1:-python3}"
failed=0
passed=0

green=$'\033[32m'
red=$'\033[31m'
reset=$'\033[0m'

pass() {
  echo "  ${green}✓${reset} $1"
  passed=$((passed + 1))
}

fail() {
  echo "  ${red}✗${reset} $1"
  failed=$((failed + 1))
}

run() {
  local label="$1"
  shift
  if "$@" > /dev/null 2>&1; then
    pass "$label"
  else
    fail "$label"
  fi
}

expect_exit() {
  local expected="$1"
  local label="$2"
  local file="$3"
  python3 src/purepy_parse.py "$file" > /dev/null 2>&1
  code=$?
  if [ "$code" -eq "$expected" ]; then
    pass "$label"
  else
    fail "$label (expected exit $expected, got $code)"
  fi
}

# --- Well-formed: must be accepted by purepy_parse.py and run correctly under Python ---

echo "well-formed"
for f in test/well-formed/*.py test/well-formed/conditionals/*.py test/well-formed/functions/*.py test/well-formed/scopes/*.py; do
  [ -f "$f" ] || continue
  run "$f (parse)" python3 src/purepy_parse.py "$f"
  run "$f (check)" python3 src/purepy_check.py "$f"
  run "$f (run)"   test/run-test.sh "$interpreter" "$f"
done

# --- Pending: must be rejected by purepy_parse.py with exit 2 ---

echo "well-formed/pending"
for f in test/well-formed/pending/*.py; do
  [ -f "$f" ] || continue
  expect_exit 2 "$f" "$f"
done

# --- Ill-formed/semantic: must be accepted by purepy_parse.py, and run correctly under Python ---

echo "ill-formed/semantic"
for f in test/ill-formed/semantic/*.py; do
  [ -f "$f" ] || continue
  run "$f (parse)" python3 src/purepy_parse.py "$f"
  run "$f (run)"   test/run-test.sh "$interpreter" "$f"
done

# --- Ill-formed/unsupported: must be rejected by purepy_parse.py with exit 1 ---

echo "ill-formed/unsupported"
for f in test/ill-formed/unsupported/*.py; do
  [ -f "$f" ] || continue
  expect_exit 1 "$f" "$f"
done

# --- Summary ---

total=$((passed + failed))
echo ""
if [ "$failed" -gt 0 ]; then
  echo "${red}✗ $passed/$total passed, $failed failed${reset}"
  exit 1
else
  echo "${green}✓ $total/$total passed${reset}"
fi
