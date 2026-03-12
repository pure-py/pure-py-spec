#!/usr/bin/env bash
set -euo pipefail

interpreter="$1"
script="$2"
expected="${script%.py}.expected"
pyver=$("$interpreter" --version)
dir="$(dirname "$0")"

"$interpreter" "$script" > "$dir/actual.txt"

if ! diff -u "$expected" "$dir/actual.txt" > "$dir/diff.txt"; then
  echo "::error file=$script::Test failed for $script using $pyver"
  echo "----- Expected output -----"
  cat "$expected"
  echo "----- Actual output -----"
  cat "$dir/actual.txt"
  echo "----- Diff -----"
  cat "$dir/diff.txt"
  exit 1
fi
