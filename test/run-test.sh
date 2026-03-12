#!/usr/bin/env bash
set -euo pipefail

interpreter="$1"
script="$2"
dir="$(dirname "$0")"
pyver=$("$interpreter" --version)

exception_expected="${script%.py}.exception.expected"
expected="${script%.py}.expected"

if [[ -f "$exception_expected" ]]; then
  expected_type=$(cat "$exception_expected")

  if "$interpreter" "$script" > "$dir/actual.txt" 2> "$dir/stderr.txt"; then
    echo "::error file=$script::Expected $expected_type but script succeeded"
    exit 1
  fi

  if ! grep -q "$expected_type" "$dir/stderr.txt"; then
    echo "::error file=$script::Expected $expected_type but got:"
    cat "$dir/stderr.txt"
    exit 1
  fi
else
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
fi
