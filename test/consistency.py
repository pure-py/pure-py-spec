#!/usr/bin/env python3
import pathlib
import re
import sys

from purepy_conformance import (
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
MYPY_INI = "mypy.ini"
MYPY_BUG = "mypy-bug"
PYTHON_VERSION = (ROOT / ".python-version").read_text().strip()

RULE_NAME = re.compile(r"\\ruleName\{([a-z0-9-]+)\}")
RULE_DEF = re.compile(r"lab=\{\\ruleName\{([a-z0-9-]+)\}\}")
CITATION = re.compile(r"# rule: ([a-z0-9-]+)")


def check_unique_rule_names(r: Results) -> None:
    with r.test("unique rule names"):
        where: dict[str, list[str]] = {}
        for source in ("spec", "paper"):
            for f in sorted((ROOT / source).rglob("*.tex")):
                for name in RULE_DEF.findall(f.read_text(encoding="utf-8")):
                    where.setdefault(name, []).append(str(f.relative_to(ROOT)))
        for name, files in sorted(where.items()):
            if len(files) > 1:
                r.fail(f"{name} in {', '.join(files)}")


def check_rule_attribution(r: Results, suite_dir: pathlib.Path) -> None:
    """Every test rejected by the type checker, undefined or agreeing cites a rule of the spec on its first
    line; a test rejected by the parser cites none."""
    with r.test("rule attribution"):
        spec = {
            m
            for f in sorted((ROOT / "spec").rglob("*.tex"))
            for m in RULE_NAME.findall(f.read_text(encoding="utf-8"))
        }
        for test in tests(suite_dir):
            path = test / MAIN if test.is_dir() else test
            dirs = test.relative_to(suite_dir).parts
            cites = dirs[1] != PurePyOutcome.PARSER_REJECTS
            cited = CITATION.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
            if cited is None and cites:
                r.fail(f"{path.relative_to(suite_dir)} cites no rule")
            elif cited is not None and not cites:
                r.fail(f"{path.relative_to(suite_dir)} cites {cited.group(1)}")
            elif cited is not None and cited.group(1) not in spec:
                r.fail(f"{path.relative_to(suite_dir)} cites {cited.group(1)}, not in the spec")


def check_lint(r: Results) -> None:
    with r.test("this script passes mypy and ruff"):
        sources = [
            str(TEST / "consistency.py"),
            str(ROOT / "src" / "purepy_conformance" / "__init__.py"),
        ]
        for tool in (
            ["mypy", "--strict", "--python-version", PYTHON_VERSION],
            ["ruff", "check"],
            ["ruff", "format", "--check"],
        ):
            proc = run([*tool, *sources])
            if proc.returncode != 0:
                r.fail((proc.stdout + proc.stderr).strip()[:400])
                break


def mypy_errors(paths: list[str], cwd: pathlib.Path) -> set[str]:
    """Paths of the files mypy reports errors in, relative to cwd"""
    proc = run(
        [
            "mypy",
            "--python-version",
            PYTHON_VERSION,
            "--config-file",
            str(TEST / MYPY_INI),
            "--no-error-summary",
            "--no-color-output",
            *paths,
        ],
        cwd=cwd,
    )
    return {line.split(":", 1)[0] for line in proc.stdout.splitlines() if ": error:" in line}


def check_mypy_compatibility(r: Results, suite_dir: pathlib.Path) -> None:
    with r.test("mypy compatibility"):
        agrees = suite_dir / PythonOutcome.SUCCEEDS / PurePyOutcome.AGREES
        found = [test for test in tests(suite_dir) if agrees in test.parents]
        modules = [str(test.relative_to(suite_dir)) for test in found if test.is_file()]
        reported_bug = {
            str(test.relative_to(suite_dir)) for test in found if MYPY_BUG in test.parts
        }
        rejected = mypy_errors(modules, suite_dir)
        # A program is checked from its own directory, so that its modules resolve
        for program in (test for test in found if test.is_dir()):
            if len(mypy_errors([MAIN], program)) > 0:
                rejected.add(str(program.relative_to(suite_dir)))
        for path in sorted(rejected - reported_bug):
            r.fail(f"{path} rejected by mypy")
        for path in sorted(reported_bug - rejected):
            r.fail(f"{path} accepted by mypy; reported bug fixed")


def main() -> None:
    consistency = Results()
    check_unique_rule_names(consistency)
    with suite() as suite_dir:
        check_rule_attribution(consistency, suite_dir)
        check_lint(consistency)
        check_mypy_compatibility(consistency, suite_dir)
    consistency.summary()
    sys.exit(1 if consistency.failed else 0)


if __name__ == "__main__":
    main()
