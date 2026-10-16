"""from M import (empty name list) — Python: SyntaxError. PurePy: grammar requires
the name list to be non-empty."""
import ast
from helpers.harness import expect_rejected

tree = ast.Module(
    body=[ast.ImportFrom(module="sys", names=[], level=0)],
    type_ignores=[],
)
ast.fix_missing_locations(tree)
expect_rejected(tree, "empty")
