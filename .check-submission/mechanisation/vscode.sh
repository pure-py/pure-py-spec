#!/usr/bin/env bash
# Session directory in Isabelle/VSCode, with the pinned code generator.
set -euo pipefail

make -s codegen
isabelle vscode -d . -d python/isabelle-python-codegen -R mechanisation .
