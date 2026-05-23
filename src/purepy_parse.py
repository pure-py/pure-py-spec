"""PurePy reference parser: decides whether a Python AST belongs to the PurePy subset."""

import ast
import sys


# --- Result type ---------------------------------------------------------------

UNSUPPORTED = 1
NOT_YET = 2

def ok():
    return None

def unsupported(node, msg):
    return {"line": getattr(node, "lineno", None), "col": getattr(node, "col_offset", None), "msg": msg, "kind": UNSUPPORTED}

def not_yet(node, msg):
    return {"line": getattr(node, "lineno", None), "col": getattr(node, "col_offset", None), "msg": msg, "kind": NOT_YET}

def is_ok(result):
    return result is None


# --- Helpers -------------------------------------------------------------------

def first_err(results):
    """Return the first error in a list of results, or ok()."""
    for r in results:
        if not is_ok(r):
            return r
    return ok()

def check_all(nodes, checker):
    """Apply checker to each node, returning the first error."""
    return first_err([checker(node) for node in nodes])


# --- Statement checking --------------------------------------------------------

def check_stmt(node):
    """Check whether a statement AST node is in the PurePy subset."""

    if isinstance(node, ast.Pass):
        return ok()

    if isinstance(node, ast.Assign):
        # Single target, must be a simple name (not tuple unpacking, not attribute/subscript)
        if len(node.targets) != 1:
            return unsupported(node, "multiple assignment targets")
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            return not_yet(node, "destructuring assignment not yet supported (#54)")
        return check_expr(node.value)

    if isinstance(node, ast.Return):
        if node.value is None:
            return ok()
        return check_expr(node.value)

    if isinstance(node, ast.If):
        test_result = check_expr(node.test)
        if not is_ok(test_result):
            return test_result
        body_result = check_body(node.body)
        if not is_ok(body_result):
            return body_result
        # orelse is either empty, a single If (elif), or a body (else)
        return check_body(node.orelse)

    if isinstance(node, ast.FunctionDef):
        args_result = check_arguments(node.args)
        if not is_ok(args_result):
            return args_result
        if len(node.decorator_list) > 0:
            return not_yet(node, "decorators not yet supported (#58)")
        if node.returns is not None:
            return unsupported(node, "return type annotations not supported")
        return check_body(node.body)

    if isinstance(node, ast.Expr):
        # Expression statement (e.g. bare function call): the expression is
        # evaluated and its value discarded. See #66.
        return check_expr(node.value)

    if isinstance(node, ast.Assert):
        # assert <test> [, <msg>]. The msg expression, if present, is only
        # evaluated on failure (#60).
        check_expr(node.test)
        if node.msg is not None:
            check_expr(node.msg)
        return

    # --- Excluded statement forms ---

    if isinstance(node, ast.AugAssign):
        return unsupported(node, "augmented assignment (+=, etc.) not supported")

    if isinstance(node, ast.AnnAssign):
        return unsupported(node, "annotated assignment not supported")

    if isinstance(node, ast.Delete):
        return unsupported(node, "del not supported")

    if isinstance(node, ast.For):
        return unsupported(node, "for loops not supported (use list comprehensions)")

    if isinstance(node, ast.While):
        return unsupported(node, "while loops not supported")

    if isinstance(node, ast.With):
        return unsupported(node, "with statements not supported")

    if isinstance(node, ast.AsyncFunctionDef):
        return unsupported(node, "async not supported")

    if isinstance(node, ast.AsyncFor):
        return unsupported(node, "async not supported")

    if isinstance(node, ast.AsyncWith):
        return unsupported(node, "async not supported")

    if isinstance(node, ast.Raise):
        return unsupported(node, "raise not supported")

    if isinstance(node, ast.Try):
        return unsupported(node, "try/except not supported")

    if isinstance(node, ast.Import):
        return not_yet(node, "import not yet supported (#53)")

    if isinstance(node, ast.ImportFrom):
        return not_yet(node, "import not yet supported (#53)")

    if isinstance(node, ast.Global):
        return not_yet(node, "global not yet supported (#40)")

    if isinstance(node, ast.Nonlocal):
        return unsupported(node, "nonlocal not supported")

    if isinstance(node, ast.ClassDef):
        return not_yet(node, "class definitions not yet supported (#8)")

    if isinstance(node, ast.Match):
        return not_yet(node, "match not yet supported (#8)")

    if isinstance(node, ast.Break):
        return unsupported(node, "break not supported")

    if isinstance(node, ast.Continue):
        return unsupported(node, "continue not supported")

    return unsupported(node, f"unknown statement type: {type(node).__name__}")


# --- Expression checking -------------------------------------------------------

def check_expr(node):
    """Check whether an expression AST node is in the PurePy subset."""

    if isinstance(node, ast.Constant):
        # int, float, str, bool, None
        if isinstance(node.value, (int, float, str, bool, type(None))):
            return ok()
        if isinstance(node.value, (bytes, complex)):
            return unsupported(node, f"{type(node.value).__name__} literals not supported")
        return unsupported(node, f"unsupported literal type: {type(node.value).__name__}")

    if isinstance(node, ast.Name):
        return ok()

    if isinstance(node, ast.BinOp):
        left_result = check_expr(node.left)
        if not is_ok(left_result):
            return left_result
        return check_expr(node.right)

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return check_expr(node.operand)
        if isinstance(node.op, (ast.UAdd, ast.USub)):
            return check_expr(node.operand)
        return unsupported(node, f"unsupported unary operator: {type(node.op).__name__}")

    if isinstance(node, ast.BoolOp):
        return check_all(node.values, check_expr)

    if isinstance(node, ast.Compare):
        left_result = check_expr(node.left)
        if not is_ok(left_result):
            return left_result
        return check_all(node.comparators, check_expr)

    if isinstance(node, ast.Call):
        func_result = check_expr(node.func)
        if not is_ok(func_result):
            return func_result
        args_result = check_all(node.args, check_expr)
        if not is_ok(args_result):
            return args_result
        return check_all(node.keywords, check_keyword)

    if isinstance(node, ast.IfExp):
        test_result = check_expr(node.test)
        if not is_ok(test_result):
            return test_result
        body_result = check_expr(node.body)
        if not is_ok(body_result):
            return body_result
        return check_expr(node.orelse)

    if isinstance(node, ast.Lambda):
        args_result = check_arguments(node.args)
        if not is_ok(args_result):
            return args_result
        return check_expr(node.body)

    if isinstance(node, ast.List):
        return check_all(node.elts, check_expr)

    if isinstance(node, ast.Tuple):
        # Tuple expressions accepted; tuple unpacking in assignments is #54
        return check_all(node.elts, check_expr)

    if isinstance(node, ast.Dict):
        keys_result = check_all([k for k in node.keys if k is not None], check_expr)
        if not is_ok(keys_result):
            return keys_result
        return check_all(node.values, check_expr)

    if isinstance(node, ast.Set):
        return check_all(node.elts, check_expr)

    if isinstance(node, ast.Attribute):
        return check_expr(node.value)

    if isinstance(node, ast.Subscript):
        value_result = check_expr(node.value)
        if not is_ok(value_result):
            return value_result
        return check_expr(node.slice)

    if isinstance(node, ast.ListComp):
        elt_result = check_expr(node.elt)
        if not is_ok(elt_result):
            return elt_result
        return check_all(node.generators, check_comprehension)

    if isinstance(node, ast.DictComp):
        # #52
        key_result = check_expr(node.key)
        if not is_ok(key_result):
            return key_result
        value_result = check_expr(node.value)
        if not is_ok(value_result):
            return value_result
        return check_all(node.generators, check_comprehension)

    if isinstance(node, ast.SetComp):
        # #52
        elt_result = check_expr(node.elt)
        if not is_ok(elt_result):
            return elt_result
        return check_all(node.generators, check_comprehension)

    if isinstance(node, ast.Slice):
        # Slicing (#59) — accepted for now
        lower_result = check_expr(node.lower) if node.lower is not None else ok()
        if not is_ok(lower_result):
            return lower_result
        upper_result = check_expr(node.upper) if node.upper is not None else ok()
        if not is_ok(upper_result):
            return upper_result
        step_result = check_expr(node.step) if node.step is not None else ok()
        return step_result

    # --- Excluded expression forms ---

    if isinstance(node, ast.GeneratorExp):
        return unsupported(node, "generator expressions not supported (use list comprehensions)")

    if isinstance(node, ast.NamedExpr):
        return unsupported(node, "walrus operator (:=) not supported (#27)")

    if isinstance(node, ast.Starred):
        return unsupported(node, "starred expressions not supported")

    if isinstance(node, ast.Await):
        return unsupported(node, "async not supported")

    if isinstance(node, ast.Yield):
        return unsupported(node, "yield not supported")

    if isinstance(node, ast.YieldFrom):
        return unsupported(node, "yield not supported")

    if isinstance(node, ast.JoinedStr):
        return not_yet(node, "f-strings not yet supported (#55)")

    if isinstance(node, ast.FormattedValue):
        return not_yet(node, "f-strings not yet supported (#55)")

    return unsupported(node, f"unknown expression type: {type(node).__name__}")


# --- Helper node checking ------------------------------------------------------

def check_body(stmts):
    """Check a list of statements (a body)."""
    return check_all(stmts, check_stmt)

def check_keyword(node):
    """Check a keyword argument in a function call."""
    return check_expr(node.value)

def check_comprehension(node):
    """Check a comprehension generator (for ... in ... if ...)."""
    if node.is_async:
        return unsupported(node, "async comprehensions not supported")
    if not isinstance(node.target, ast.Name):
        return not_yet(node, "destructuring in comprehensions not yet supported (#54)")
    iter_result = check_expr(node.iter)
    if not is_ok(iter_result):
        return iter_result
    return check_all(node.ifs, check_expr)

def check_arguments(node):
    """Check function/lambda arguments are simple (no defaults, *args, **kwargs, etc.)."""
    if node.vararg is not None:
        return not_yet(node, "*args not yet supported (#57)")
    if node.kwarg is not None:
        return not_yet(node, "**kwargs not yet supported (#57)")
    if len(node.kwonlyargs) > 0:
        return unsupported(node, "keyword-only arguments not supported")
    if len(node.defaults) > 0:
        return not_yet(node, "default arguments not yet supported (#56)")
    if len(node.kw_defaults) > 0:
        return not_yet(node, "default arguments not yet supported (#56)")
    if len(node.posonlyargs) > 0:
        return unsupported(node, "positional-only arguments not supported")
    return ok()


# --- Module-level checking -----------------------------------------------------

def check_module(node):
    """Check a module (top-level) AST node."""
    if not isinstance(node, ast.Module):
        return unsupported(node, "expected a module")
    return check_body(node.body)


# --- Entry point ---------------------------------------------------------------

def check_file(filename):
    """Parse and check a Python file."""
    source = open(filename).read()
    tree = ast.parse(source, filename=filename)
    return check_module(tree)

def format_result(result, filename):
    """Format a check result for display."""
    if is_ok(result):
        return f"{filename}: ok"
    line = result["line"]
    col = result["col"]
    msg = result["msg"]
    if line is not None:
        return f"{filename}:{line}:{col}: {msg}"
    return f"{filename}: {msg}"

def main():
    if len(sys.argv) < 2:
        print("Usage: purepy_parse.py <file.py> [<file.py> ...]")
        sys.exit(1)
    exit_code = 0
    for filename in sys.argv[1:]:
        result = check_file(filename)
        print(format_result(result, filename))
        if not is_ok(result):
            exit_code = result["kind"]
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
