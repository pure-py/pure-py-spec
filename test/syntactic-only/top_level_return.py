"""return at module top level — Python: SyntaxError 'return outside function'.
PurePy: module rule requires the body's result type to be Assigns(Δ); a top-level
return would give Returns and fail the rule."""
import ast
from _harness import expect_rejected

tree = ast.Module(
    body=[ast.Return(value=ast.Constant(value=42))],
    type_ignores=[],
)
ast.fix_missing_locations(tree)
expect_rejected(tree, "top-level return")
