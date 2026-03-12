#!/usr/bin/env bash
set -euo pipefail

interpreter="$1"
script="$2"
expected="${script%.py}.expected"
pyver=$("$interpreter" --version)

"$interpreter" "$script" > actual.txt

if ! diff -u "$expected" actual.txt > diff.txt; then
  echo "::error file=$script::Test failed for $script using $pyver"
  echo "----- Expected output -----"
  cat "$expected"
  echo "----- Actual output -----"
  cat actual.txt
  echo "----- Diff -----"
  cat diff.txt
  exit 1
fi
