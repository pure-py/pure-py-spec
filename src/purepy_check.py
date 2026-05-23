"""PurePy well-formedness checker.

Runs after the syntactic check (purepy_parse.py) succeeds. Decides whether a
syntactically-valid PurePy program satisfies the well-formedness rules in
fig/well-formed.tex (definite assignment, captured-variable rules, mutual
region distinct-names, etc.).

Currently a skeleton: every rule returns "well-formed" with a placeholder
result type. The structural recursion is wired up so real rules can be added
incrementally without further refactoring.

Design constraint: this checker is itself written in (approximately) PurePy,
so that we can eventually self-host. That means:
  - No loops; use recursion (mutual recursion for AST traversal).
  - No mutation; functions return new values rather than updating state.
  - No exceptions; use explicit result values (ok / ill_formed).
  - Only constructs PurePy supports: def, assign, return, if/else, lambdas,
    function calls, attribute access. Pattern matching is fine once #8 lands.
The use of `ast` module nodes is a temporary convenience; longer-term we'd
process a PurePy representation of the AST (e.g. via dataclasses).
"""

import ast
import sys


# --- Result type ---------------------------------------------------------------
# Errors are dicts with line/col/msg; ok() is None.

ILL_FORMED = 3

def ok():
    return None

def ill_formed(node, msg):
    return {"line": getattr(node, "lineno", None), "col": getattr(node, "col_offset", None), "msg": msg, "kind": ILL_FORMED}

def is_ok(result):
    return result is None


# --- Contexts (Γ) and result types (R) ----------------------------------------
# Γ is a mapping from variable names to a definite-assignment status (tt/ff).
# R is either ('assigns', Δ) or ('returns',), per fig/syntax.tex.

TT = "tt"
FF = "ff"


def empty_context():
    return {}


def extend(gamma, delta):
    """Γ ⨄ Δ (override). Right-biased."""
    new = dict(gamma)
    new.update(delta)
    return new


def assigns(delta):
    return ("assigns", delta)


def returns():
    return ("returns",)


def is_assigns(r):
    return r[0] == "assigns"


def is_returns(r):
    return r[0] == "returns"


def bindings(r):
    """Extract Δ from Assigns Δ; empty for Returns."""
    if is_assigns(r):
        return r[1]
    return {}


# --- Well-formedness check -----------------------------------------------------
# check_block : block, Γ -> (R, error)
# check_stmt  : statement, Γ -> (R, error)
# check_expr  : expression, Γ -> error


def check_block(block, gamma):
    """Γ ⊢ b : R. Skeleton: recurse over the cons structure of the block."""
    if len(block) == 1:
        # singleton (leaf): just the statement's result
        return check_stmt(block[0], gamma)
    # cons: s :: tail. (seq rule)
    head = block[0]
    tail = block[1:]
    r_head, err = check_stmt(head, gamma)
    if not is_ok(err):
        return r_head, err
    # TODO: enforce captures(head) ∩ assigns(tail) = ∅ side condition
    gamma_ = extend(gamma, bindings(r_head))
    r_tail, err = check_block(tail, gamma_)
    if not is_ok(err):
        return r_tail, err
    # TODO: combine via R ⊕ R (the runion semiring on result types)
    return r_tail, ok()


def check_stmt(s, gamma):
    """Γ ⊢ s : R. Each branch implements one rule from fig/well-formed.tex."""
    # Mutual-region grouping happens at check_block level (contiguous defs);
    # for now treat each FunctionDef in isolation.
    if isinstance(s, ast.Pass):
        # pass rule: Γ ⊢ pass : Assigns ∅
        return assigns({}), ok()
    if isinstance(s, ast.Assign):
        # assign rule: Γ ⊢ e ; x ∉ captures(e) ⟹ Γ ⊢ x = e : Assigns {x:tt}
        err = check_expr(s.value, gamma)
        if not is_ok(err):
            return assigns({}), err
        delta = {target.id: TT for target in s.targets if isinstance(target, ast.Name)}
        return assigns(delta), ok()
    if isinstance(s, ast.Expr):
        # expr-stmt rule: Γ ⊢ e ⟹ Γ ⊢ e : Assigns ∅
        err = check_expr(s.value, gamma)
        return assigns({}), err
    if isinstance(s, ast.Return):
        # return / return-none rules
        if s.value is not None:
            err = check_expr(s.value, gamma)
            if not is_ok(err):
                return returns(), err
        return returns(), ok()
    if isinstance(s, ast.If):
        # if / if-else rules: condition well-formed; each branch well-formed
        err = check_expr(s.test, gamma)
        if not is_ok(err):
            return assigns({}), err
        # Recurse into the two branches (Python flattens elif into nested If).
        # TODO: merge branch results via R₁ ⊕ R₂ ⊕ ... ⊕ Assigns ∅ (if no else)
        r_then, err = check_block(s.body, gamma)
        if not is_ok(err):
            return r_then, err
        if s.orelse:
            r_else, err = check_block(s.orelse, gamma)
            if not is_ok(err):
                return r_else, err
        return assigns({}), ok()
    if isinstance(s, ast.FunctionDef):
        # mutual rule (treating a single def as a singleton region for now).
        # TODO: group contiguous FunctionDefs into a single region; bind all
        # f_i in each body's context; enforce distinct names.
        # TODO: subtract params from assigns(body) before introducing ff.
        return assigns({s.name: TT}), ok()
    if isinstance(s, ast.Assert):
        # assert rule: Γ ⊢ e ; Γ ⊢ e' ⟹ Γ ⊢ assert e, e' : Assigns ∅
        err = check_expr(s.test, gamma)
        if not is_ok(err):
            return assigns({}), err
        if s.msg is not None:
            err = check_expr(s.msg, gamma)
            if not is_ok(err):
                return assigns({}), err
        return assigns({}), ok()
    # Unrecognised statement form: should have been rejected by purepy_parse.
    return assigns({}), ok()


def check_expr(e, gamma):
    """Γ ⊢ e. Skeleton: always accept.

    TODO: implement var rule (Γ(x) = tt), lambda rule (typing in extended Γ).
    """
    return ok()


def check_module(tree):
    """Top-level entry: check the module body as a block in the empty context."""
    if not tree.body:
        # empty module is trivially well-formed
        return ok()
    _, err = check_block(tree.body, empty_context())
    return err


# --- I/O -----------------------------------------------------------------------

def check_file(filename):
    source = open(filename).read()
    tree = ast.parse(source, filename=filename)
    return check_module(tree)


def format_result(result, filename):
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
        print("Usage: purepy_check.py <file.py> [<file.py> ...]")
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
