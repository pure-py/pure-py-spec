#!/usr/bin/env bash
# Anonymised copy of the mechanisation under <dest-dir>: CI removed, names replaced, type checked.
set -euo pipefail

SRC=isabelle-purepy
DEST="${1:?usage: anonymise-mechanisation.sh <dest-dir>}"
NAME=mechanisation
ANON_NAME="$(cat .anon-name)"
ANON_SLUG="$(tr '[:upper:]' '[:lower:]' <<< "$ANON_NAME")"

rm -rf "$DEST/$NAME"
mkdir -p "$DEST/$NAME"
git -C "$SRC" archive --format=tar HEAD | tar -x -C "$DEST/$NAME"
cd "$DEST/$NAME"

# Both name the repository or its organisation.
rm -rf .github .claude
grep -vE 'badge\.svg|\.github/workflows' README.md > README.tmp && mv README.tmp README.md

for f in $(grep -rl 'isabelle-purepy' .); do
  sed -e "s/isabelle-purepy/$NAME/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

# Language and repository names.
for f in README.md ROOT; do
  sed -e "s/pure-py/$ANON_SLUG/g" -e "s/PurePy/$ANON_NAME/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
make build
