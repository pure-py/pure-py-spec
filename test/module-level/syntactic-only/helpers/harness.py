"""Build ASTs which ast.parse can't produce and check PurePy rejects them."""

import ast

from purepy.check_module import PREDEFINED_MODULES, check_module
from purepy.reasons import IllFormed
from purepy.syntax import Unsupported, check_syntax_module
from purepy.type_syntax import Name


def expect_rejected(m: ast.Module, msg_contains: str = "") -> None:
    q = Name(("<test>",))
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
        print(
            f"FAIL: expected message containing {msg_contains!r}, got {result.msg!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"ok: {result.msg}")
