#!/usr/bin/env bash
# Anonymised copy of the mechanisation under <dest-dir>: renamed, scrubbed, type checked.
set -euo pipefail

SRC=isabelle-purepy
DEST="${1:?usage: anonymise-mechanisation.sh <dest-dir>}"
NAME=mechanisation

rm -rf "$DEST/$NAME"
mkdir -p "$DEST/$NAME"
git -C "$SRC" archive --format=tar HEAD | tar -x -C "$DEST/$NAME"
cd "$DEST/$NAME"

# CI configuration and references to it have no place in a submission.
rm -rf .github
grep -vE 'badge\.svg|\.github/workflows' README.md > README.tmp && mv README.tmp README.md

# Language and repository names, as in the anonymised paper and specification.
for f in README.md ROOT document/root.tex; do
  sed -e "s/isabelle-purepy/$NAME/g" -e 's/pure-py/ourlang/g' -e 's/PurePy/OurLang/g' \
    "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
sed -e 's/\\author{nhuber}/\\author{Anonymous}/' \
    -e "s/\\\\title{$NAME}/\\\\title{OurLang mechanisation in Isabelle\\/HOL}/" \
  document/root.tex > root.tmp && mv root.tmp document/root.tex

# The anonymised copy must still type check.
make build
