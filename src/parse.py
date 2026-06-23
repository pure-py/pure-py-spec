import ast
import sys
from typing import Optional


OP_SYMBOLS: dict[type, str] = {
    ast.BitOr: '|', ast.BitAnd: '&', ast.BitXor: '^',
    ast.LShift: '<<', ast.RShift: '>>', ast.MatMult: '@',
    ast.Invert: '~',
}


class ParseError(Exception):
    exit_code: int   # overridden by subclass
    msg: str

    def __init__(self, node: ast.AST, msg: str):
        self.line: Optional[int] = getattr(node, 'lineno', None)
        self.col: Optional[int] = getattr(node, 'col_offset', None)
        self.msg = msg
        super().__init__(msg)


class Unsupported(ParseError):
    exit_code = 1


class NotYetSupported(ParseError):
    exit_code = 2

    def __init__(self, node: ast.AST, feature: str, issue: int):
        super().__init__(node, f'{feature} not yet supported (#{issue})')


def check_stmt(node: ast.stmt) -> None:
    if isinstance(node, ast.Pass):
        return
    if isinstance(node, ast.Assign):
        if len(node.targets) != 1:
            raise Unsupported(node, 'multiple assignment targets')
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            raise NotYetSupported(node, 'destructuring assignment', 54)
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
            raise NotYetSupported(node, 'decorators', 58)
        if node.returns is not None:
            raise Unsupported(node, 'return type annotations not supported')
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
        raise Unsupported(node, 'augmented assignment (+=, etc.) not supported')
    if isinstance(node, ast.AnnAssign):
        raise Unsupported(node, 'annotated assignment not supported')
    if isinstance(node, ast.Delete):
        raise Unsupported(node, 'del not supported')
    if isinstance(node, ast.For):
        raise Unsupported(node, 'for loops not supported')
    if isinstance(node, ast.While):
        raise Unsupported(node, 'while loops not supported')
    if isinstance(node, ast.With):
        raise Unsupported(node, 'with statements not supported')
    if isinstance(node, ast.AsyncFunctionDef):
        raise Unsupported(node, 'async not supported')
    if isinstance(node, ast.AsyncFor):
        raise Unsupported(node, 'async not supported')
    if isinstance(node, ast.AsyncWith):
        raise Unsupported(node, 'async not supported')
    if isinstance(node, ast.Raise):
        raise Unsupported(node, 'raise not supported')
    if isinstance(node, ast.Try):
        raise Unsupported(node, 'try/except not supported')
    if isinstance(node, ast.Import):
        if len(node.names) != 1:
            raise NotYetSupported(node, 'multi-target import (import a, b)', 53)
        if node.names[0].asname is not None:
            raise NotYetSupported(node, 'import-as', 53)
        return
    if isinstance(node, ast.ImportFrom):
        if node.level > 0:
            raise NotYetSupported(node, 'relative imports', 53)
        if node.module is None:
            raise NotYetSupported(node, 'from-import with no module', 53)
        for alias in node.names:
            if alias.name == '*':
                raise NotYetSupported(node, 'from M import *', 53)
            if alias.asname is not None:
                raise NotYetSupported(node, 'from-import-as', 53)
        return
    if isinstance(node, ast.Global):
        raise Unsupported(node, 'global not supported')
    if isinstance(node, ast.Nonlocal):
        raise Unsupported(node, 'nonlocal not supported')
    if isinstance(node, ast.ClassDef):
        check_classdef(node)
        return
    if isinstance(node, ast.Match):
        check_expr(node.subject)
        for case in node.cases:
            if case.guard is not None:
                raise NotYetSupported(case, 'case guards', 83)
            check_pattern(case.pattern)
            check_body(case.body)
        return
    if isinstance(node, ast.Break):
        raise Unsupported(node, 'break not supported')
    if isinstance(node, ast.Continue):
        raise Unsupported(node, 'continue not supported')
    raise Unsupported(node, f'unknown statement type: {type(node).__name__}')

def check_classdef(node: ast.ClassDef) -> None:
    if any(isinstance(b, ast.Name) and b.id == 'Enum' for b in node.bases):
        raise NotYetSupported(node, 'enum classes', 86)
    if len(node.decorator_list) != 1:
        raise Unsupported(node, 'class must have exactly the @dataclass decorator')
    deco = node.decorator_list[0]
    if not (isinstance(deco, ast.Name) and deco.id == 'dataclass'):
        raise Unsupported(node, 'only the @dataclass decorator is supported on classes')
    if len(node.bases) > 1:
        raise Unsupported(node, 'multiple inheritance not supported')
    if len(node.bases) > 0 and not isinstance(node.bases[0], ast.Name):
        raise Unsupported(node, 'base class must be a simple name')
    if len(node.keywords) > 0:
        raise Unsupported(node, 'class keyword arguments not supported')
    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
        return
    for stmt in node.body:
        check_field(stmt)

def check_field(stmt: ast.stmt) -> None:
    if not isinstance(stmt, ast.AnnAssign):
        raise Unsupported(stmt, 'dataclass body may contain only field declarations')
    if not isinstance(stmt.target, ast.Name):
        raise Unsupported(stmt, 'field target must be a simple name')
    if stmt.value is not None:
        raise Unsupported(stmt, 'field default values not supported')
    if not (isinstance(stmt.annotation, ast.Name) and stmt.annotation.id == 'Any'):
        raise Unsupported(stmt, 'field type annotation must be Any')

def check_pattern(node: ast.pattern) -> None:
    if isinstance(node, ast.MatchValue):
        v = node.value
        if isinstance(v, ast.Constant) and isinstance(v.value, (int, float, str)):
            return
        if isinstance(v, ast.UnaryOp) and isinstance(v.op, (ast.UAdd, ast.USub)) and isinstance(v.operand, ast.Constant) and isinstance(v.operand.value, (int, float)):
            return
        if isinstance(v, ast.Attribute):
            raise NotYetSupported(node, 'attribute value patterns', 86)
        raise NotYetSupported(node, 'complex value patterns', 83)
    if isinstance(node, ast.MatchSingleton):
        return
    if isinstance(node, ast.MatchAs):
        if node.pattern is not None:
            check_pattern(node.pattern)
        return
    if isinstance(node, ast.MatchSequence):
        for p in node.patterns:
            if isinstance(p, ast.MatchStar):
                raise NotYetSupported(node, 'star patterns', 84)
            check_pattern(p)
        return
    if isinstance(node, ast.MatchClass):
        if not (isinstance(node.cls, ast.Name) or (isinstance(node.cls, ast.Attribute) and isinstance(node.cls.value, ast.Name))):
            raise Unsupported(node, 'class pattern head must be a simple name or single-level qualified name')
        for p in list(node.patterns) + list(node.kwd_patterns):
            check_pattern(p)
        return
    if isinstance(node, ast.MatchMapping):
        raise NotYetSupported(node, 'mapping patterns', 87)
    if isinstance(node, ast.MatchOr):
        raise NotYetSupported(node, 'or-patterns', 85)
    if isinstance(node, ast.MatchStar):
        raise NotYetSupported(node, 'star patterns', 84)
    raise Unsupported(node, f'unknown pattern type: {type(node).__name__}')

def check_expr(node: ast.expr) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, str, bool, type(None))):
            return
        if isinstance(node.value, (bytes, complex)):
            raise Unsupported(node, f'{type(node.value).__name__} literals not supported')
        raise Unsupported(node, f'unsupported literal type: {type(node.value).__name__}')
    if isinstance(node, ast.Name):
        return
    if isinstance(node, ast.BinOp):
        allowed = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
        if not isinstance(node.op, allowed):
            sym = OP_SYMBOLS.get(type(node.op), type(node.op).__name__)
            raise Unsupported(node, f"binary operator '{sym}' not supported")
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
        raise Unsupported(node, f"unary operator '{sym}' not supported")
    if isinstance(node, ast.BoolOp):
        if len(node.values) > 2:
            raise NotYetSupported(node, 'chained boolean operator', 82)
        for v in node.values:
            check_expr(v)
        return
    if isinstance(node, ast.Compare):
        if len(node.ops) > 1:
            raise NotYetSupported(node, 'chained comparison', 82)
        for op in node.ops:
            if isinstance(op, (ast.In, ast.NotIn)):
                raise NotYetSupported(node, 'membership operator (in/not in)', 80)
            if isinstance(op, (ast.Is, ast.IsNot)):
                raise NotYetSupported(node, 'identity operator (is/is not)', 81)
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
        raise NotYetSupported(node, 'set literals', 52)
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
            check_comprehension(g)
        return
    if isinstance(node, ast.DictComp):
        raise NotYetSupported(node, 'dict comprehensions', 52)
    if isinstance(node, ast.SetComp):
        raise NotYetSupported(node, 'set comprehensions', 52)
    if isinstance(node, ast.Slice):
        raise NotYetSupported(node, 'slicing', 59)
    if isinstance(node, ast.GeneratorExp):
        raise Unsupported(node, 'generator expressions not supported')
    if isinstance(node, ast.NamedExpr):
        raise Unsupported(node, 'walrus operator (:=) not supported')
    if isinstance(node, ast.Starred):
        raise Unsupported(node, 'starred expressions not supported')
    if isinstance(node, ast.Await):
        raise Unsupported(node, 'async not supported')
    if isinstance(node, ast.Yield):
        raise Unsupported(node, 'yield not supported')
    if isinstance(node, ast.YieldFrom):
        raise Unsupported(node, 'yield not supported')
    if isinstance(node, ast.JoinedStr):
        raise NotYetSupported(node, 'f-strings', 55)
    if isinstance(node, ast.FormattedValue):
        raise NotYetSupported(node, 'f-strings', 55)
    raise Unsupported(node, f'unknown expression type: {type(node).__name__}')

def check_body(stmts: list[ast.stmt]) -> None:
    for s in stmts:
        check_stmt(s)

def check_keyword(node: ast.keyword) -> None:
    check_expr(node.value)

def check_comprehension(node: ast.comprehension) -> None:
    if node.is_async:
        raise Unsupported(node, 'async comprehensions not supported')
    if not isinstance(node.target, ast.Name):
        raise NotYetSupported(node, 'destructuring in comprehensions', 54)
    check_expr(node.iter)
    for i in node.ifs:
        check_expr(i)

def check_arguments(node: ast.arguments) -> None:
    if node.vararg is not None:
        raise NotYetSupported(node, '*args', 57)
    if node.kwarg is not None:
        raise NotYetSupported(node, '**kwargs', 57)
    if len(node.kwonlyargs) > 0:
        raise Unsupported(node, 'keyword-only arguments not supported')
    if len(node.defaults) > 0:
        raise NotYetSupported(node, 'default arguments', 56)
    if len(node.kw_defaults) > 0:
        raise NotYetSupported(node, 'default arguments', 56)
    if len(node.posonlyargs) > 0:
        raise Unsupported(node, 'positional-only arguments not supported')

def check_module(node: ast.Module) -> Optional[ParseError]:
    try:
        check_body(node.body)
        return None
    except ParseError as e:
        return e

def check_file(filename: str) -> Optional[ParseError]:
    source = open(filename).read()
    tree = ast.parse(source, filename=filename)
    return check_module(tree)

def format_result(result: Optional[ParseError], filename: str) -> str:
    if result is None:
        return f'{filename}: ok'
    if result.line is not None:
        return f'{filename}:{result.line}:{result.col}: {result.msg}'
    return f'{filename}: {result.msg}'

def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: parse.py <file.py> [<file.py> ...]')
        sys.exit(1)
    exit_code = 0
    for filename in sys.argv[1:]:
        result = check_file(filename)
        print(format_result(result, filename))
        if result is not None:
            exit_code = result.exit_code
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
