#!/usr/bin/env bash
set -euo pipefail
file="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
cd "$(dirname "$file")"
printf '\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}\n\\input{%s}\n\\end{document}\n' "$(basename "$file")" > figure-check.tex
pdflatex -interaction=nonstopmode -halt-on-error figure-check.tex
