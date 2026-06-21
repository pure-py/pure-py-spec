"""case x: ...; case 1: ... — Python: SyntaxError 'name capture x makes remaining
patterns unreachable'. PurePy: pat-list rejects via reachability premise."""
import ast
from helpers.harness import expect_rejected

match_stmt = ast.Match(
    subject=ast.Name(id="v", ctx=ast.Load()),
    cases=[
        ast.match_case(pattern=ast.MatchAs(name="x", pattern=None), guard=None, body=[ast.Pass()]),
        ast.match_case(pattern=ast.MatchValue(value=ast.Constant(value=1)), guard=None, body=[ast.Pass()]),
    ],
)
tree = ast.Module(
    body=[ast.Assign(targets=[ast.Name(id="v", ctx=ast.Store())], value=ast.Constant(value=1)), match_stmt],
    type_ignores=[],
)
ast.fix_missing_locations(tree)
expect_rejected(tree, "unreachable")
