#!/usr/bin/env python3
import argparse
import pathlib
import re
import sys

from purepy.conformance import (
    MODULE_LEVEL,
    SUITE,
    PurePyOutcome,
    PythonOutcome,
    Runner,
    run,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEST = ROOT / "test"
SRC = ROOT / "src" / "purepy"
MYPY_INI = "mypy.ini"
MYPY_BUG = "mypy-bug"
PYTHON_VERSION = (ROOT / ".python-version").read_text().strip()

RULE_NAME = re.compile(r"\\ruleName\{([a-z0-9-]+)\}")
RULE_DEF = re.compile(r"lab=\{\\ruleName\{([a-z0-9-]+)\}\}")
CITATION = re.compile(r"# rule: ([a-z0-9-]+)")


def check_unique_rule_names(r: Runner) -> None:
    with r.test("unique rule names"):
        where: dict[str, list[str]] = {}
        for source in ("spec", "paper"):
            for f in sorted((ROOT / source).rglob("*.tex")):
                for name in RULE_DEF.findall(f.read_text(encoding="utf-8")):
                    where.setdefault(name, []).append(str(f.relative_to(ROOT)))
        for name, files in sorted(where.items()):
            if len(files) > 1:
                r.fail(f"{name} in {', '.join(files)}")


def check_rule_attribution(r: Runner) -> None:
    with r.test("rule attribution"):
        spec = {
            m
            for f in sorted((ROOT / "spec").rglob("*.tex"))
            for m in RULE_NAME.findall(f.read_text(encoding="utf-8"))
        }
        for path in sorted((SRC / SUITE).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            cited = CITATION.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
            if cited is not None and cited.group(1) not in spec:
                r.fail(f"{path.relative_to(SRC / SUITE)} cites {cited.group(1)}")


def check_lint(r: Runner) -> None:
    with r.test("checker type-checks"):
        sources = sorted(str(path) for path in SRC.glob("*.py")) + [str(TEST / "run-all.py")]
        for tool in (
            ["mypy", "--strict", "--python-version", PYTHON_VERSION],
            ["ruff", "check"],
            ["ruff", "format", "--check"],
        ):
            proc = run([*tool, *sources])
            if proc.returncode != 0:
                r.fail((proc.stdout + proc.stderr).strip()[:400])
                break


def check_mypy_compatibility(r: Runner) -> None:
    with r.test("mypy compatibility"):
        paths = sorted(
            (SRC / SUITE / MODULE_LEVEL / PythonOutcome.NO_EXCEPTION / PurePyOutcome.RESULT).rglob(
                "*.py"
            )
        )
        # mypy reports paths relative to its working directory
        relative = [str(path.relative_to(ROOT)) for path in paths]
        reported_bug = {str(path.relative_to(ROOT)) for path in paths if MYPY_BUG in path.parts}
        proc = run(
            [
                "mypy",
                "--python-version",
                PYTHON_VERSION,
                "--config-file",
                str(pathlib.Path("test") / MYPY_INI),
                "--no-error-summary",
                "--no-color-output",
                *relative,
            ],
            cwd=ROOT,
        )
        rejected = {
            line.split(":", 1)[0] for line in proc.stdout.splitlines() if ": error:" in line
        }
        for path in sorted(rejected - reported_bug):
            r.fail(f"{path} rejected by mypy")
        for path in sorted(reported_bug - rejected):
            r.fail(f"{path} accepted by mypy; reported bug fixed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("interpreter", nargs="?", default="python3")
    parser.add_argument("--no-mypy", action="store_true")
    parser.add_argument(
        "--no-run", action="store_true", help="check the tests without running them"
    )
    parser.add_argument(
        "--jobs", type=int, help="number of tests run in parallel (default: number of cores)"
    )
    args = parser.parse_args()
    r = Runner(None if args.no_run else args.interpreter, None)

    print("cross-references")
    check_unique_rule_names(r)
    check_rule_attribution(r)

    if not args.no_mypy:
        print("mypy and ruff over src/purepy")
        check_lint(r)
        check_mypy_compatibility(r)

    r.run_suite(SRC / SUITE, args.jobs)
    r.summary()
    sys.exit(1 if r.failed else 0)


if __name__ == "__main__":
    main()
