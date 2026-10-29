#!/usr/bin/env bash
# Anonymised copy of the mechanisation checked out at <src-dir>, under <dest-dir>.
set -euo pipefail

SRC="${1:?usage: anonymise-mechanisation.sh <src-dir> <dest-dir>}"
DEST="${2:?usage: anonymise-mechanisation.sh <src-dir> <dest-dir>}"
REPO=isabelle-purepy
NAME=mechanisation
ANON_NAME="$(cat .anon-name)"
ANON_SLUG="$(tr '[:upper:]' '[:lower:]' <<< "$ANON_NAME")"

rm -rf "$DEST/$NAME"
mkdir -p "$DEST"
make -C "$SRC" -s dist DEST="$(cd "$DEST" && pwd)/$NAME"
cd "$DEST/$NAME"

grep -vE 'badge\.svg|\.github/workflows' README.md > README.tmp && mv README.tmp README.md

for f in $(grep -rl "$REPO" .); do
  sed -e "s/$REPO/$NAME/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

# Language and repository names.
for f in $(grep -rlE 'pure-py|PurePy' .); do
  sed -e "s/pure-py/$ANON_SLUG/g" -e "s/PurePy/$ANON_NAME/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
make build
