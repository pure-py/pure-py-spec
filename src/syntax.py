import ast
import sys
from collections.abc import Callable

OP_SYMBOLS: dict[type, str] = {
    ast.BitOr: "|",
    ast.BitAnd: "&",
    ast.BitXor: "^",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.MatMult: "@",
    ast.Invert: "~",
}


class ParseError(Exception):
    exit_code: int  # overridden by subclass
    msg: str

    def __init__(self, node: ast.AST, msg: str):
        self.line: int | None = getattr(node, "lineno", None)
        self.col: int | None = getattr(node, "col_offset", None)
        self.msg = msg
        super().__init__(msg)


class Prohibited(ParseError):
    exit_code = 1


class NotYetSupported(ParseError):
    exit_code = 2

    def __init__(self, node: ast.AST, feature: str, issue: int):
        super().__init__(node, f"{feature} not yet supported (#{issue})")


class PatList(ast.MatchSequence):
    """Sequence pattern written with brackets."""


class PatTuple(ast.MatchSequence):
    """Sequence pattern written with parentheses, or bare."""


def map_tree(f: Callable[[ast.AST], ast.AST], node: ast.AST) -> ast.AST:
    """Rebuild node bottom-up, applying f to each node. Subtrees f leaves alone are shared, not copied."""
    fields: dict[str, object] = {}
    for name in node._fields:
        v = getattr(node, name)
        if isinstance(v, ast.AST):
            fields[name] = map_tree(f, v)
        elif isinstance(v, list):
            new = [map_tree(f, x) if isinstance(x, ast.AST) else x for x in v]
            fields[name] = v if all(a is b for a, b in zip(new, v)) else new
        else:
            fields[name] = v
    unchanged = all(fields[name] is getattr(node, name) for name in node._fields)
    return f(node if unchanged else ast.copy_location(type(node)(**fields), node))


def classify_sequence(source: str) -> Callable[[ast.AST], ast.AST]:
    """Python's parser gives list and tuple patterns one node type; the source text tells them apart."""

    def classify(node: ast.AST) -> ast.AST:
        if not isinstance(node, ast.MatchSequence):
            return node
        segment = ast.get_source_segment(source, node)
        assert segment is not None
        cls = PatList if segment.startswith("[") else PatTuple
        return ast.copy_location(cls(patterns=node.patterns), node)

    return classify


def parse(source: str, filename: str) -> ast.Module:
    tree = map_tree(classify_sequence(source), ast.parse(source, filename=filename))
    assert isinstance(tree, ast.Module)
    return tree


def check_stmt(node: ast.stmt) -> None:
    if isinstance(node, ast.Pass):
        return
    if isinstance(node, ast.Assign):
        if len(node.targets) != 1:
            raise Prohibited(node, "multiple assignment targets")
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            raise NotYetSupported(node, "destructuring assignment", 54)
        check_expr(node.value)
        return
    if isinstance(node, ast.Return):
        if node.value is not None:
            check_expr(node.value)
        return
    if isinstance(node, ast.If):
        check_expr(node.test)
        check_body(node.body)
        check_body(node.orelse)
        return
    if isinstance(node, ast.FunctionDef):
        check_arguments(node.args)
        if len(node.decorator_list) > 0:
            raise NotYetSupported(node, "decorators", 58)
        if node.returns is not None:
            raise Prohibited(node, "return type annotations prohibited")
        check_body(node.body)
        return
    if isinstance(node, ast.Expr):
        check_expr(node.value)
        return
    if isinstance(node, ast.Assert):
        check_expr(node.test)
        if node.msg is not None:
            check_expr(node.msg)
        return
    if isinstance(node, ast.AugAssign):
        raise Prohibited(node, "augmented assignment (+=, etc.) prohibited")
    if isinstance(node, ast.AnnAssign):
        raise Prohibited(node, "annotated assignment prohibited")
    if isinstance(node, ast.Delete):
        raise Prohibited(node, "del prohibited")
    if isinstance(node, ast.For):
        raise Prohibited(node, "for loops prohibited")
    if isinstance(node, ast.While):
        raise Prohibited(node, "while loops prohibited")
    if isinstance(node, ast.With):
        raise Prohibited(node, "with statements prohibited")
    if isinstance(node, ast.AsyncFunctionDef):
        raise Prohibited(node, "async prohibited")
    if isinstance(node, ast.AsyncFor):
        raise Prohibited(node, "async prohibited")
    if isinstance(node, ast.AsyncWith):
        raise Prohibited(node, "async prohibited")
    if isinstance(node, ast.Raise):
        raise Prohibited(node, "raise prohibited")
    if isinstance(node, ast.Try):
        raise Prohibited(node, "try/except prohibited")
    if isinstance(node, ast.Import):
        if len(node.names) != 1:
            raise NotYetSupported(node, "multi-target import (import a, b)", 53)
        if node.names[0].asname is not None:
            raise NotYetSupported(node, "import-as", 53)
        return
    if isinstance(node, ast.ImportFrom):
        if node.level > 0:
            raise NotYetSupported(node, "relative imports", 53)
        if node.module is None:
            raise NotYetSupported(node, "from-import with no module", 53)
        for alias in node.names:
            if alias.name == "*":
                raise NotYetSupported(node, "from M import *", 53)
            if alias.asname is not None:
                raise NotYetSupported(node, "from-import-as", 53)
        return
    if isinstance(node, ast.Global):
        raise Prohibited(node, "global prohibited")
    if isinstance(node, ast.Nonlocal):
        raise Prohibited(node, "nonlocal prohibited")
    if isinstance(node, ast.ClassDef):
        check_classdef(node)
        return
    if isinstance(node, ast.Match):
        check_expr(node.subject)
        for case in node.cases:
            if case.guard is not None:
                raise NotYetSupported(case, "case guards", 83)
            check_pattern(case.pattern)
            check_body(case.body)
        return
    if isinstance(node, ast.Break):
        raise Prohibited(node, "break prohibited")
    if isinstance(node, ast.Continue):
        raise Prohibited(node, "continue prohibited")
    raise Prohibited(node, f"unknown statement type: {type(node).__name__}")


def check_classdef(node: ast.ClassDef) -> None:
    if any(isinstance(b, ast.Name) and b.id == "Enum" for b in node.bases):
        raise NotYetSupported(node, "enum classes", 86)
    if len(node.decorator_list) != 1:
        raise Prohibited(node, "class must have exactly the @dataclass decorator")
    deco = node.decorator_list[0]
    if not (isinstance(deco, ast.Name) and deco.id == "dataclass"):
        raise Prohibited(node, "only the @dataclass decorator is supported on classes")
    if len(node.bases) > 1:
        raise Prohibited(node, "multiple inheritance prohibited")
    if len(node.bases) > 0 and not isinstance(node.bases[0], ast.Name):
        raise Prohibited(node, "base class must be a simple name")
    if len(node.keywords) > 0:
        raise Prohibited(node, "class keyword arguments prohibited")
    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
        return
    for stmt in node.body:
        check_field(stmt)


def check_field(stmt: ast.stmt) -> None:
    if not isinstance(stmt, ast.AnnAssign):
        raise Prohibited(stmt, "dataclass body may contain only field declarations")
    if not isinstance(stmt.target, ast.Name):
        raise Prohibited(stmt, "field target must be a simple name")
    if stmt.value is not None:
        raise Prohibited(stmt, "field default values prohibited")
    if not (isinstance(stmt.annotation, ast.Name) and stmt.annotation.id == "Any"):
        raise Prohibited(stmt, "field type annotation must be Any")


def is_qualified_name(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) or (
        isinstance(node, ast.Attribute) and is_qualified_name(node.value)
    )


def check_pattern(node: ast.pattern) -> None:
    if isinstance(node, ast.MatchValue):
        v = node.value
        if isinstance(v, ast.Constant) and isinstance(v.value, (int, float, str)):
            return
        if (
            isinstance(v, ast.UnaryOp)
            and isinstance(v.op, (ast.UAdd, ast.USub))
            and isinstance(v.operand, ast.Constant)
            and isinstance(v.operand.value, (int, float))
        ):
            return
        if isinstance(v, ast.Attribute):
            raise NotYetSupported(node, "attribute value patterns", 86)
        raise NotYetSupported(node, "complex value patterns", 83)
    if isinstance(node, ast.MatchSingleton):
        return
    if isinstance(node, ast.MatchAs):
        if node.pattern is not None:
            check_pattern(node.pattern)
        return
    if isinstance(node, ast.MatchSequence):
        for p in node.patterns:
            if isinstance(p, ast.MatchStar):
                raise NotYetSupported(node, "star patterns", 84)
            check_pattern(p)
        return
    if isinstance(node, ast.MatchClass):
        if not is_qualified_name(node.cls):
            raise Prohibited(node, "class pattern head must be a qualified name")
        for p in list(node.patterns) + list(node.kwd_patterns):
            check_pattern(p)
        return
    if isinstance(node, ast.MatchMapping):
        if node.rest is not None:
            raise NotYetSupported(node, "rest capture in dict patterns", 84)
        for key in node.keys:
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                raise Prohibited(key, "dict pattern keys must be string literals")
        for sub in node.patterns:
            check_pattern(sub)
        return
    if isinstance(node, ast.MatchOr):
        raise NotYetSupported(node, "or-patterns", 85)
    if isinstance(node, ast.MatchStar):
        raise NotYetSupported(node, "star patterns", 84)
    raise Prohibited(node, f"unknown pattern type: {type(node).__name__}")


def check_expr(node: ast.expr) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, str, bool, type(None))):
            return
        if isinstance(node.value, (bytes, complex)):
            raise Prohibited(node, f"{type(node.value).__name__} literals prohibited")
        raise Prohibited(node, f"prohibited literal type: {type(node.value).__name__}")
    if isinstance(node, ast.Name):
        return
    if isinstance(node, ast.BinOp):
        allowed = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
        if not isinstance(node.op, allowed):
            sym = OP_SYMBOLS.get(type(node.op), type(node.op).__name__)
            raise Prohibited(node, f"binary operator '{sym}' prohibited")
        check_expr(node.left)
        check_expr(node.right)
        return
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            check_expr(node.operand)
            return
        if isinstance(node.op, (ast.UAdd, ast.USub)):
            check_expr(node.operand)
            return
        sym = OP_SYMBOLS.get(type(node.op), type(node.op).__name__)
        raise Prohibited(node, f"unary operator '{sym}' prohibited")
    if isinstance(node, ast.BoolOp):
        if len(node.values) > 2:
            raise NotYetSupported(node, "chained boolean operator", 82)
        for v in node.values:
            check_expr(v)
        return
    if isinstance(node, ast.Compare):
        if len(node.ops) > 1:
            raise NotYetSupported(node, "chained comparison", 82)
        for op in node.ops:
            if isinstance(op, (ast.Is, ast.IsNot)):
                raise NotYetSupported(node, "identity operator (is/is not)", 81)
        check_expr(node.left)
        for c in node.comparators:
            check_expr(c)
        return
    if isinstance(node, ast.Call):
        check_expr(node.func)
        for a in node.args:
            check_expr(a)
        for k in node.keywords:
            check_keyword(k)
        return
    if isinstance(node, ast.IfExp):
        check_expr(node.test)
        check_expr(node.body)
        check_expr(node.orelse)
        return
    if isinstance(node, ast.Lambda):
        check_arguments(node.args)
        check_expr(node.body)
        return
    if isinstance(node, ast.List):
        for e in node.elts:
            check_expr(e)
        return
    if isinstance(node, ast.Tuple):
        for e in node.elts:
            check_expr(e)
        return
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if key is not None:
                check_expr(key)
        for v in node.values:
            check_expr(v)
        return
    if isinstance(node, ast.Set):
        raise NotYetSupported(node, "set literals", 147)
    if isinstance(node, ast.Attribute):
        check_expr(node.value)
        return
    if isinstance(node, ast.Subscript):
        check_expr(node.value)
        check_expr(node.slice)
        return
    if isinstance(node, ast.ListComp):
        check_expr(node.elt)
        for g in node.generators:
            check_generator(g)
        return
    if isinstance(node, ast.DictComp):
        check_expr(node.key)
        check_expr(node.value)
        for g in node.generators:
            check_generator(g)
        return
    if isinstance(node, ast.SetComp):
        raise NotYetSupported(node, "set comprehensions", 147)
    if isinstance(node, ast.Slice):
        raise NotYetSupported(node, "slicing", 59)
    if isinstance(node, ast.GeneratorExp):
        raise Prohibited(node, "generator expressions prohibited")
    if isinstance(node, ast.NamedExpr):
        raise Prohibited(node, "walrus operator (:=) prohibited")
    if isinstance(node, ast.Starred):
        raise Prohibited(node, "starred expressions prohibited")
    if isinstance(node, ast.Await):
        raise Prohibited(node, "async prohibited")
    if isinstance(node, ast.Yield):
        raise Prohibited(node, "yield prohibited")
    if isinstance(node, ast.YieldFrom):
        raise Prohibited(node, "yield prohibited")
    if isinstance(node, ast.JoinedStr):
        raise NotYetSupported(node, "f-strings", 55)
    if isinstance(node, ast.FormattedValue):
        raise NotYetSupported(node, "f-strings", 55)
    raise Prohibited(node, f"unknown expression type: {type(node).__name__}")


def check_body(stmts: list[ast.stmt]) -> None:
    for s in stmts:
        check_stmt(s)


def check_keyword(node: ast.keyword) -> None:
    check_expr(node.value)


def check_generator(node: ast.comprehension) -> None:
    if node.is_async:
        raise Prohibited(node, "async comprehensions prohibited")
    if not isinstance(node.target, ast.Name):
        raise NotYetSupported(node, "destructuring in comprehensions", 54)
    check_expr(node.iter)
    for i in node.ifs:
        check_expr(i)


def check_arguments(node: ast.arguments) -> None:
    if node.vararg is not None:
        raise NotYetSupported(node, "*args", 57)
    if node.kwarg is not None:
        raise NotYetSupported(node, "**kwargs", 57)
    if len(node.kwonlyargs) > 0:
        raise Prohibited(node, "keyword-only arguments prohibited")
    if len(node.defaults) > 0:
        raise NotYetSupported(node, "default arguments", 56)
    if len(node.kw_defaults) > 0:
        raise NotYetSupported(node, "default arguments", 56)
    if len(node.posonlyargs) > 0:
        raise Prohibited(node, "positional-only arguments prohibited")


def check_module(node: ast.Module) -> ParseError | None:
    try:
        check_body(node.body)
        return None
    except ParseError as e:
        return e


def check_file(filename: str) -> ParseError | None:
    with open(filename) as f:
        source = f.read()
    return check_module(parse(source, filename))


def format_result(result: ParseError | None, filename: str) -> str:
    if result is None:
        return f"{filename}: ok"
    if result.line is not None:
        return f"{filename}:{result.line}:{result.col}: {result.msg}"
    return f"{filename}: {result.msg}"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: parse.py <file.py> [<file.py> ...]")
        sys.exit(1)
    exit_code = 0
    for filename in sys.argv[1:]:
        result = check_file(filename)
        print(format_result(result, filename))
        if result is not None:
            exit_code = result.exit_code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
