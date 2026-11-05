#!/usr/bin/env python3
"""Copy exit codes of pinned conformance suite into type checker, which is installed without the suite"""

import pathlib
import sys

from ourlang_conformance import Exit


def main() -> None:
    (path,) = map(pathlib.Path, sys.argv[1:])
    members = "".join(f"    {code.name} = {code.value}\n" for code in Exit)
    path.write_text(f"from enum import IntEnum\n\n\nclass Exit(IntEnum):\n{members}")


if __name__ == "__main__":
    main()
