#!/usr/bin/env python3
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
README = HERE / "README.md"
BEGIN, END = "<!-- theories -->\n", "\n<!-- /theories -->"


def theories() -> list[pathlib.Path]:
    paths = []
    for session in re.split(r"^session ", (HERE / "ROOT").read_text(), flags=re.MULTILINE)[1:]:
        directory = re.match(r'"[^"]+"(?: in "([^"]+)")?', session).group(1) or "."
        for line in session.split("theories\n", 1)[1].splitlines():
            if not re.fullmatch(r"\s+\w+", line):
                break
            paths.append(pathlib.Path(directory) / f"{line.strip()}.thy")
    return paths


def description(path: pathlib.Path) -> str:
    header = re.match(r"\(\* (.*) \*\)\n", (HERE / path).read_text())
    if header is None:
        sys.exit(f"{path}: no header comment")
    return header.group(1)


def table() -> str:
    rows = [("File", "Content")] + [(f"`{path}`", description(path)) for path in theories()]
    widths = [max(len(row[i]) for row in rows) for i in range(2)]
    lines = [f"| {a.ljust(widths[0])} | {b.ljust(widths[1])} |" for a, b in rows]
    return "\n".join([lines[0], f"|{'-' * (widths[0] + 2)}|{'-' * (widths[1] + 2)}|", *lines[1:]])


def main() -> None:
    text = README.read_text()
    before, rest = text.split(BEGIN, 1)
    after = rest.split(END, 1)[1]
    updated = before + BEGIN + table() + END + after
    if sys.argv[1:] == ["--check"]:
        if updated != text:
            sys.exit("README.md theories out of date: run ./theories.py")
    else:
        README.write_text(updated)


if __name__ == "__main__":
    main()
