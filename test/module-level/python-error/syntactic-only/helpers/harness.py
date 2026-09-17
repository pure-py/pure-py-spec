"""Harness for syntactic-only tests: cases ast.parse genuinely cannot produce (e.g. an
empty from-import name list), so we hand-build the AST and check PurePy rejects it.
Constructs that ast.parse accepts but Python rejects at compile belong in
python-error/static as real source, not here."""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

from check_module import PREDEFINED_MODULES, check_module
from reasons import IllFormed
from type_syntax import QualifiedName
from syntax import Unsupported, check_syntax_module


def expect_rejected(m: ast.Module, msg_contains: str = "") -> None:
    q = QualifiedName(('<test>',))
    M = {p: ast.Module(body=[], type_ignores=[]) for p in PREDEFINED_MODULES}
    M[q] = m
    result: IllFormed | Unsupported | None = check_syntax_module(m)
    if result is None:
        try:
            check_module(m, M, q, {})
        except IllFormed as e:
            result = e
    if result is None:
        print("FAIL: expected rejection but got ok", file=sys.stderr)
        sys.exit(1)
    if len(msg_contains) > 0 and msg_contains not in result.msg:
        print(f"FAIL: expected message containing {msg_contains!r}, got {result.msg!r}", file=sys.stderr)
        sys.exit(1)
    print(f"ok: {result.msg}")
