"""case (x, x): — Python: SyntaxError 'multiple assignments to name x in pattern'.
PurePy: pat-list rejects via linearity premise."""
import ast
from helpers.harness import expect_rejected

# match v:
#     case (x, x):
#         pass
match_stmt = ast.Match(
    subject=ast.Name(id="v", ctx=ast.Load()),
    cases=[
        ast.match_case(
            pattern=ast.MatchSequence(patterns=[
                ast.MatchAs(name="x", pattern=None),
                ast.MatchAs(name="x", pattern=None),
            ]),
            guard=None,
            body=[ast.Pass()],
        ),
    ],
)
tree = ast.Module(
    body=[ast.Assign(targets=[ast.Name(id="v", ctx=ast.Store())], value=ast.Constant(value=1)), match_stmt],
    type_ignores=[],
)
ast.fix_missing_locations(tree)
expect_rejected(tree, "repeated variable")
