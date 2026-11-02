#!/usr/bin/env python3
import inspect
import pathlib
import re
import sys
import tomllib

import purepy_conformance
from purepy_conformance import (
    CLASSIFICATION,
    ERROR_EXPECTED,
    MAIN,
    PurePyOutcome,
    PythonOutcome,
    Results,
    run,
    suite,
    tests,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
PYTHON_VERSION = (ROOT / ".python-version").read_text().strip()

RULE_NAME = re.compile(r"\\ruleName\{([a-z0-9-]+)\}")
RULE_DEF = re.compile(r"lab=\{\\ruleName\{([a-z0-9-]+)\}\}")
CITATION = re.compile(r"# rule: ([a-z0-9-]+)")
DELETED = re.compile(
    r"\\begin\{DeletedBlock\}.*?\\end\{DeletedBlock\}|\\deleted\{[^{}]*\}", re.DOTALL
)


def current(f: pathlib.Path) -> str:
    """Source with text in deleted change markup removed."""
    return DELETED.sub("", f.read_text(encoding="utf-8"))


def check_python_version(r: Results) -> None:
    with r.test("package requires the pinned Python version"):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        if project["requires-python"] != f">={PYTHON_VERSION}":
            r.fail(
                f"requires-python is {project['requires-python']}, .python-version is {PYTHON_VERSION}"
            )


def check_unique_rule_names(r: Results) -> None:
    with r.test("unique rule names"):
        where: dict[str, list[str]] = {}
        for source in ("spec", "paper"):
            for f in sorted((ROOT / source).rglob("*.tex")):
                for name in RULE_DEF.findall(current(f)):
                    where.setdefault(name, []).append(str(f.relative_to(ROOT)))
        for name, files in sorted(where.items()):
            if len(files) > 1:
                r.fail(f"{name} in {', '.join(files)}")


def check_rule_attribution(r: Results, suite_dir: pathlib.Path) -> None:
    """Every test rejected by the type checker, undefined or agreeing cites a rule of the spec on its first
    line; a test rejected by the parser or excluded from this version cites none."""
    with r.test("rule attribution"):
        spec = {
            m for f in sorted((ROOT / "spec").rglob("*.tex")) for m in RULE_NAME.findall(current(f))
        }
        for test in tests(suite_dir):
            path = test / MAIN if test.is_dir() else test
            dirs = test.relative_to(suite_dir).parts
            cites = dirs[1] not in (
                PurePyOutcome.PARSER_REJECTS,
                PurePyOutcome.EXCLUDED_FOR_NOW,
            )
            cited = CITATION.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
            if cited is None and cites:
                r.fail(f"{path.relative_to(suite_dir)} cites no rule")
            elif cited is not None and not cites:
                r.fail(f"{path.relative_to(suite_dir)} cites {cited.group(1)}")
            elif cited is not None and cited.group(1) not in spec:
                r.fail(f"{path.relative_to(suite_dir)} cites {cited.group(1)}, not in the spec")


def check_classification(r: Results, suite_dir: pathlib.Path) -> None:
    """Check which expected errors end with the classification placeholder. For a program which Python runs, the
    placeholder is required if the parser rejects the program or the program uses a feature excluded from this
    version, and optional if the type checker rejects it. No other expected error uses the placeholder."""
    with r.test("classification of excluded features"):
        for test in tests(suite_dir):
            path = test / MAIN if test.is_dir() else test
            error = path.with_suffix(ERROR_EXPECTED)
            if not error.exists():
                continue
            python, purepy = test.relative_to(suite_dir).parts[:2]
            text = error.read_text(encoding="utf-8").strip()
            ends = text.endswith(f" {CLASSIFICATION}")
            required = python != PythonOutcome.REJECTS and purepy in (
                PurePyOutcome.PARSER_REJECTS,
                PurePyOutcome.EXCLUDED_FOR_NOW,
            )
            allowed = python != PythonOutcome.REJECTS and purepy != PurePyOutcome.AGREES
            if required and not ends:
                r.fail(f"{error.relative_to(suite_dir)} does not end with {CLASSIFICATION}")
            elif CLASSIFICATION in text and not (allowed and ends):
                r.fail(f"{error.relative_to(suite_dir)} uses {CLASSIFICATION}")


def check_lint(r: Results) -> None:
    with r.test("consistency script and runner pass mypy and ruff"):
        sources = [str(TEST / "consistency.py"), inspect.getfile(purepy_conformance)]
        for tool in (
            ["mypy", "--strict", "--python-version", PYTHON_VERSION],
            ["ruff", "check"],
            ["ruff", "format", "--check"],
        ):
            proc = run([*tool, *sources])
            if proc.returncode != 0:
                r.fail((proc.stdout + proc.stderr).strip()[:400])
                break


def main() -> None:
    consistency = Results()
    check_python_version(consistency)
    check_unique_rule_names(consistency)
    with suite() as suite_dir:
        check_rule_attribution(consistency, suite_dir)
        check_classification(consistency, suite_dir)
        check_lint(consistency)
    consistency.summary()
    sys.exit(1 if consistency.failed else 0)


if __name__ == "__main__":
    main()
