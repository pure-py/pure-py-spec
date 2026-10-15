#!/usr/bin/env bash
# Write index.html listing the released specification PDFs, newest first, in the current directory
set -euo pipefail
versions=$(ls -d v*/ | tr -d / | sort -V -r)
latest=$(echo "$versions" | head -1)
{
  echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>PurePy specification</title></head><body>'
  echo '<h1>PurePy language specification</h1>'
  echo "<p><a href=\"latest/PurePy-spec.pdf\">Latest ($latest)</a></p><ul>"
  for v in $versions; do echo "<li><a href=\"$v/PurePy-spec.pdf\">$v</a></li>"; done
  echo '</ul></body></html>'
} > index.html
