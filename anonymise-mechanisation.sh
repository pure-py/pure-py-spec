#!/usr/bin/env bash
# Anonymised copy of the mechanisation checked out at <src-dir>, under <dest-dir>, with the conformance suite as a wheel
set -euo pipefail

SRC="${1:?usage: anonymise-mechanisation.sh <src-dir> <dest-dir>}"
DEST="${2:?usage: anonymise-mechanisation.sh <src-dir> <dest-dir>}"
ROOT="$(pwd)"
REPO=isabelle-purepy
NAME=mechanisation
ANON_NAME="$(cat .anon-name)"
ANON_SLUG="$(tr '[:upper:]' '[:lower:]' <<< "$ANON_NAME")"

anonymise() {
  for f in $(grep -rl "$REPO" .); do
    sed -e "s/$REPO/$NAME/g" "$f" > "$f.tmp" && cat "$f.tmp" > "$f" && rm "$f.tmp"
  done
  for f in $(grep -rlE 'pure-py|PurePy|purepy' .); do
    sed -e "s/pure-py/$ANON_SLUG/g" -e "s/PurePy/$ANON_NAME/g" -e "s/purepy/$ANON_SLUG/g" "$f" > "$f.tmp" && cat "$f.tmp" > "$f" && rm "$f.tmp"
  done
  for f in $(find . -depth -name '*purepy*'); do
    mv "$f" "${f%purepy*}$ANON_SLUG${f##*purepy}"
  done
}

rm -rf "$DEST/$NAME" "$DEST/suite"
mkdir -p "$DEST/suite"
make -C "$SRC" -s dist DEST="$(cd "$DEST" && pwd)/$NAME"

git -C "$ROOT" archive --format=tar HEAD pyproject.toml src | tar -x -C "$DEST/suite"
(cd "$DEST/suite" && anonymise && uv build -q --wheel --out-dir "../$NAME")
rm -rf "$DEST/suite"

cd "$DEST/$NAME"
grep -vE 'badge\.svg|\.github/workflows' README.md > README.tmp && mv README.tmp README.md
anonymise
WHEEL="$(basename "$ANON_SLUG"_conformance-*.whl)"
sed -e "s|\"$ANON_SLUG-conformance @ [^\"]*\"|\"$ANON_SLUG-conformance\"|" pyproject.toml > pyproject.tmp && mv pyproject.tmp pyproject.toml
printf '\n[tool.uv.sources]\n%s-conformance = { path = "%s" }\n' "$ANON_SLUG" "$WHEEL" >> pyproject.toml
uv lock -q
