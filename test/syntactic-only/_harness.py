"""Harness for syntactic-only tests: cases Python rejects at parse but PurePy rejects
via its own well-formedness rule. We hand-build the AST since ast.parse would refuse."""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from purepy_check import check_module


def expect_rejected(tree: ast.Module, msg_contains: str = "") -> None:
    result = check_module(tree)
    if result is None:
        print("FAIL: expected rejection but got ok", file=sys.stderr)
        sys.exit(1)
    if msg_contains and msg_contains not in result.msg:
        print(f"FAIL: expected message containing {msg_contains!r}, got {result.msg!r}", file=sys.stderr)
        sys.exit(1)
    print(f"ok: {result.msg}")
