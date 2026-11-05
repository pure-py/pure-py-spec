#!/usr/bin/env python3
"""Copy the generated modules into the package with relative imports; delete with #12, Relative imports between
generated modules, https://github.com/ourlang/isabelle-python-codegen/issues/12"""

import pathlib
import re
import shutil
import sys


def main() -> None:
    source, package = map(pathlib.Path, sys.argv[1:])
    modules = sorted(p.stem for p in source.glob("*.py"))
    shutil.rmtree(package, ignore_errors=True)
    package.mkdir()
    (package / "__init__.py").write_text("")
    for module in modules:
        text = (source / f"{module}.py").read_text()
        text = re.sub(
            r"^import (\w+)$",
            lambda m: f"from . import {m.group(1)}" if m.group(1) in modules else m.group(0),
            text,
            flags=re.MULTILINE,
        )
        (package / f"{module}.py").write_text(text)


if __name__ == "__main__":
    main()
