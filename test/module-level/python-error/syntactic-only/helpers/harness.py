"""Harness for syntactic-only tests: cases ast.parse genuinely cannot produce (e.g. an
empty from-import name list), so we hand-build the AST and check PurePy rejects it.
Constructs that ast.parse accepts but Python rejects at compile belong in
python-error/static as real source, not here."""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

from check_module import PREDEFINED_MODULES, module_result


def expect_rejected(tree: ast.Module, msg_contains: str = "") -> None:
    q = '<test>'
    M = {p: ast.Module(body=[], type_ignores=[]) for p in PREDEFINED_MODULES}
    M[q] = tree
    result = module_result(tree, M, q)
    if result is None:
        print("FAIL: expected rejection but got ok", file=sys.stderr)
        sys.exit(1)
    if msg_contains and msg_contains not in result.msg:
        print(f"FAIL: expected message containing {msg_contains!r}, got {result.msg!r}", file=sys.stderr)
        sys.exit(1)
    print(f"ok: {result.msg}")
