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
from dataclasses import dataclass, field


# --- Result type ---------------------------------------------------------------
# Errors are dicts with line/col/msg; ok() is None.

ILL_FORMED = 3

def ok():
    return None

def ill_formed(node, msg):
    return {"line": getattr(node, "lineno", None), "col": getattr(node, "col_offset", None), "msg": msg, "kind": ILL_FORMED}

def is_ok(result):
    return result is None


# --- Contexts (Γ) and result types ---------------------------------------------
# Γ is a mapping from variable names to a definite-assignment status (tt/ff).
# A statement's result type is one of TyReturns or TyAssigns (modelled after
# Fluid's WellFormed.purs). TyAssigns will eventually carry a Δ.

TT = "tt"
FF = "ff"


@dataclass(frozen=True)
class TyReturns:
    pass


@dataclass(frozen=True)
class TyAssigns:
    delta: dict = field(default_factory=dict)


TY_RETURNS = TyReturns()
TY_ASSIGNS = TyAssigns()                       # convenience: empty Δ


BUILTINS = {
    "print": TT,
    "type": TT,
    "range": TT,
    "len": TT,
}


def empty_context():
    return {}


def extend(gamma, delta):
    """Γ ⨄ Δ (override). Right-biased."""
    new = dict(gamma)
    new.update(delta)
    return new


def meet(a, b):
    """∧ on B: tt ∧ tt = tt; else ff."""
    if a == TT and b == TT:
        return TT
    return FF


def merge_delta(d1, d2):
    """Pointwise merge: k in both → meet; k in only one → ff."""
    result = {}
    for k in set(d1.keys()) | set(d2.keys()):
        if k in d1 and k in d2:
            result[k] = meet(d1[k], d2[k])
        else:
            result[k] = FF
    return result


def merge_results(rs):
    """Returns is unit for merge; otherwise merge the Δs of the Assigns branches."""
    assigns_branches = [r for r in rs if isinstance(r, TyAssigns)]
    if not assigns_branches:
        return TY_RETURNS
    delta = assigns_branches[0].delta
    return TyAssigns(_fold_merge(delta, assigns_branches[1:]))


def _fold_merge(acc, branches):
    if not branches:
        return acc
    return _fold_merge(merge_delta(acc, branches[0].delta), branches[1:])


def runion_delta(d1, d2):
    """Right-biased override on Δ."""
    return {**d1, **d2}


def runion_results(r1, r2):
    """Sequential composition on result types (the seq case)."""
    if isinstance(r1, TyReturns):
        return r1                              # Returns absorbs anything that follows
    if isinstance(r2, TyReturns):
        return r2                              # Assigns Δ runion Returns = Returns
    return TyAssigns(runion_delta(r1.delta, r2.delta))


def result_type(node):
    """Classify a statement node's result type per fig/well-formed.tex.
    Pure analysis; does not check well-formedness."""
    if isinstance(node, ast.Pass):
        return TY_ASSIGNS
    if isinstance(node, ast.Assign):
        return TyAssigns({t.id: TT for t in node.targets if isinstance(t, ast.Name)})
    if isinstance(node, ast.Expr):
        return TY_ASSIGNS                       # expr-stmt
    if isinstance(node, ast.Assert):
        return TY_ASSIGNS
    if isinstance(node, ast.Return):
        return TY_RETURNS                       # return / return-none
    if isinstance(node, ast.FunctionDef):
        return TyAssigns({node.name: TT})       # singleton mutual region
    if isinstance(node, ast.If):
        # Merge of branch result types, plus implicit Assigns ∅ if no else.
        branches = [result_type_of_block(node.body)]
        if node.orelse:
            branches.append(result_type_of_block(node.orelse))
        else:
            branches.append(TY_ASSIGNS)
        return merge_results(branches)
    return TY_ASSIGNS


def result_type_of_block(block):
    """Result type of a non-empty block: fold runion_results over the items.
    Per seq, an earlier-returning head forces Returns; otherwise Δ accumulates."""
    if len(block) == 1:
        return _result_type_of_item(block[0])
    return runion_results(_result_type_of_item(block[0]), result_type_of_block(block[1:]))


def _result_type_of_item(stmt):
    """At this level the input is a raw ast statement (block is flat from
    Python's ast). Mutual regions are grouped at check-time, not here."""
    return result_type(stmt)


# --- Well-formedness check -----------------------------------------------------
# check_block : block, Γ -> (R, error)
# check_stmt  : statement, Γ -> (R, error)
# check_expr  : expression, Γ -> error


def check_block(block, gamma):
    """Check that a block is well-formed. Recurses over items, where an item
    is either a single non-FunctionDef statement or a list of contiguous
    FunctionDefs (a mutual region)."""
    items = items_of_block(block)
    return check_items(items, gamma)


def check_items(items, gamma):
    if len(items) == 1:
        return check_item(items[0], gamma)
    # cons: item :: tail. (seq rule)
    head = items[0]
    tail = items[1:]
    err = check_item(head, gamma)
    if not is_ok(err):
        return err
    # seq rule pattern-matches `Γ ⊢ s : Assigns Δ` on the head, so a returning
    # head with a non-empty tail is ill-formed (unreachable code).
    if isinstance(item_result_type(head), TyReturns):
        first_unreachable = tail[0]
        node = first_unreachable[0] if isinstance(first_unreachable, list) else first_unreachable
        return ill_formed(node, "[seq] unreachable statement")
    # seq rule's captures(s) ∩ assignsF(b) = ∅ side condition
    reassigned = captures_item(head) & assigns_items(tail)
    if reassigned:
        name = sorted(reassigned)[0]
        node = find_first_reassigning(tail, reassigned)
        return ill_formed(node, f"[seq] '{name}' captured by previous statement, reassigned here")
    # Extend Γ by the head's Δ before checking the tail.
    head_result = item_result_type(head)
    delta = head_result.delta if isinstance(head_result, TyAssigns) else {}
    return check_items(tail, extend(gamma, delta))


def item_result_type(item):
    """Result type of an item: a mutual region Assigns its def names; otherwise
    delegate to result_type on the AST node."""
    if isinstance(item, list):
        return TyAssigns({d.name: TT for d in item})
    return result_type(item)


def items_of_block(block):
    """Group a flat statement list into items: single non-def stmts and
    contiguous-def regions (each represented as a list of FunctionDefs)."""
    if not block:
        return []
    head = block[0]
    rest = block[1:]
    if isinstance(head, ast.FunctionDef):
        return _extend_region([head], rest)
    return [head] + items_of_block(rest)


def _extend_region(region, rest):
    if not rest:
        return [region]
    head = rest[0]
    if isinstance(head, ast.FunctionDef):
        return _extend_region(region + [head], rest[1:])
    return [region] + items_of_block(rest)


def check_item(item, gamma):
    if isinstance(item, list):
        return check_mutual_region(item, gamma)
    return check_stmt(item, gamma)


def check_mutual_region(defs, gamma):
    """mutual rule (fig/well-formed.tex). Each region is non-empty."""
    err = check_distinct_names(defs, set())
    if not is_ok(err):
        return err
    return check_bodies(defs, gamma)


def check_bodies(defs, gamma):
    """Per the mutual rule, each body b_i is checked in
        Γ ⨄ tt(\\seq{f}) ⨄ tt(\\seq{x}_i) ⨄ ff(assigns(b_i) \\ \\seq{x}_i).
    Subtract params from assigns before introducing ff so parameters stay tt
    even if reassigned in the body."""
    f_names = {d.name: TT for d in defs}
    return _check_bodies(defs, gamma, f_names)


def _check_bodies(defs, gamma, f_names):
    if not defs:
        return ok()
    d = defs[0]
    params = {a.arg for a in d.args.args}
    locals_ = assigns_block(d.body) - params
    body_gamma = extend(
        extend(extend(gamma, f_names), {p: TT for p in params}),
        {x: FF for x in locals_},
    )
    err = check_block(d.body, body_gamma)
    if not is_ok(err):
        return err
    return _check_bodies(defs[1:], gamma, f_names)


def check_assign_targets(targets, captured):
    """assign rule's `x ∉ captures(e)` side condition for each target."""
    if not targets:
        return ok()
    t = targets[0]
    if isinstance(t, ast.Name) and t.id in captured:
        return ill_formed(t, f"[assign] '{t.id}' captured by right-hand side")
    return check_assign_targets(targets[1:], captured)


def check_distinct_names(defs, seen):
    """mutual rule's distinct-names side condition."""
    if not defs:
        return ok()
    head = defs[0]
    if head.name in seen:
        return ill_formed(head, f"[mutual] duplicate name '{head.name}' in mutual region")
    return check_distinct_names(defs[1:], seen | {head.name})


def check_stmt(s, gamma):
    """Check that s is well-formed. Each branch implements one rule from
    fig/well-formed.tex (its non-result-type obligations)."""
    if isinstance(s, ast.Pass):
        return ok()
    if isinstance(s, ast.Assign):
        # assign rule: Γ ⊢ e ; x ∉ captures(e)
        err = check_expr(s.value, gamma)
        if not is_ok(err):
            return err
        captured = captures(s.value)
        return check_assign_targets(s.targets, captured)
    if isinstance(s, ast.Expr):
        # expr-stmt rule: Γ ⊢ e
        return check_expr(s.value, gamma)
    if isinstance(s, ast.Return):
        if s.value is not None:
            return check_expr(s.value, gamma)
        return ok()
    if isinstance(s, ast.If):
        # if / if-else rules: condition well-formed; each branch well-formed.
        err = check_expr(s.test, gamma)
        if not is_ok(err):
            return err
        err = check_block(s.body, gamma)
        if not is_ok(err):
            return err
        if s.orelse:
            return check_block(s.orelse, gamma)
        return ok()
    if isinstance(s, ast.Assert):
        # assert rule: Γ ⊢ e ; Γ ⊢ e'
        err = check_expr(s.test, gamma)
        if not is_ok(err):
            return err
        if s.msg is not None:
            return check_expr(s.msg, gamma)
        return ok()
    # FunctionDef should be handled via check_mutual_region (items grouping).
    # Unrecognised forms: should have been rejected by purepy_parse.
    return ok()


def check_expr(e, gamma):
    """Γ ⊢ e. Implements the var rule (Γ(x) = tt) and recursive descent."""
    if isinstance(e, ast.Name):
        if gamma.get(e.id) != TT:
            return ill_formed(e, f"[var] '{e.id}' is not definitely assigned")
        return ok()
    if isinstance(e, ast.Constant):
        return ok()
    if isinstance(e, ast.Lambda):
        # lambda rule: type body in Γ extended with params at tt
        params = {a.arg for a in e.args.args}
        gamma_ = extend(gamma, {p: TT for p in params})
        return check_expr(e.body, gamma_)
    if isinstance(e, ast.Call):
        err = check_expr(e.func, gamma)
        if not is_ok(err):
            return err
        return check_exprs(e.args, gamma)
    if isinstance(e, ast.BinOp):
        err = check_expr(e.left, gamma)
        if not is_ok(err):
            return err
        return check_expr(e.right, gamma)
    if isinstance(e, ast.UnaryOp):
        return check_expr(e.operand, gamma)
    if isinstance(e, ast.BoolOp):
        return check_exprs(e.values, gamma)
    if isinstance(e, ast.Compare):
        err = check_expr(e.left, gamma)
        if not is_ok(err):
            return err
        return check_exprs(e.comparators, gamma)
    if isinstance(e, ast.IfExp):
        err = check_expr(e.test, gamma)
        if not is_ok(err):
            return err
        err = check_expr(e.body, gamma)
        if not is_ok(err):
            return err
        return check_expr(e.orelse, gamma)
    if isinstance(e, ast.Attribute):
        return check_expr(e.value, gamma)
    if isinstance(e, ast.Subscript):
        err = check_expr(e.value, gamma)
        if not is_ok(err):
            return err
        return check_expr(e.slice, gamma)
    if isinstance(e, (ast.List, ast.Tuple)):
        return check_exprs(e.elts, gamma)
    if isinstance(e, ast.Dict):
        err = check_exprs([k for k in e.keys if k is not None], gamma)
        if not is_ok(err):
            return err
        return check_exprs(e.values, gamma)
    if isinstance(e, ast.ListComp):
        return check_comprehension(e.elt, e.generators, gamma)
    return ok()


def check_comprehension(elt, generators, gamma):
    """Check a comprehension `elt for g_1 ... g_n` in Γ. Each generator's iter
    is checked in the current Γ; its target is bound, and guards / remaining
    generators / the elt are checked in the extended Γ."""
    if not generators:
        return check_expr(elt, gamma)
    g = generators[0]
    err = check_expr(g.iter, gamma)
    if not is_ok(err):
        return err
    gamma_ = extend(gamma, {n: TT for n in names_in_target(g.target)})
    err = check_exprs(g.ifs, gamma_)
    if not is_ok(err):
        return err
    return check_comprehension(elt, generators[1:], gamma_)


def check_exprs(es, gamma):
    if not es:
        return ok()
    err = check_expr(es[0], gamma)
    if not is_ok(err):
        return err
    return check_exprs(es[1:], gamma)


# --- Pattern metafunctions -----------------------------------------------------


def binds(pattern):
    """Set of variable names introduced by a pattern (spec: fig:aux)."""
    if isinstance(pattern, (ast.MatchValue, ast.MatchSingleton)):
        return set()
    if isinstance(pattern, ast.MatchAs) and pattern.pattern is None:
        return {pattern.name} if pattern.name else set()
    if isinstance(pattern, ast.MatchSequence):
        result = set()
        for p in pattern.patterns:
            result |= binds(p)
        return result
    raise AssertionError(f"unexpected pattern: {type(pattern).__name__}")


# --- Free variables and captures (metafunctions over expressions) -------------
# Per fig/well-formed.tex prose: `fv` is the standard free-variables function;
# `captures(e)` is the set of variables captured by closures (lambdas / nested
# defs) within `e`. For a non-lambda expression, captures distributes over
# subexpressions; for a lambda, captures(lambda x⃗: e') = fv(e') \ {x⃗}.


def fv(e):
    """Free variables of an expression."""
    if isinstance(e, ast.Name):
        return {e.id}
    if isinstance(e, ast.Constant):
        return set()
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        return fv(e.body) - params
    if isinstance(e, ast.Call):
        return fv(e.func) | fv_list(e.args)
    if isinstance(e, ast.BinOp):
        return fv(e.left) | fv(e.right)
    if isinstance(e, ast.UnaryOp):
        return fv(e.operand)
    if isinstance(e, ast.BoolOp):
        return fv_list(e.values)
    if isinstance(e, ast.Compare):
        return fv(e.left) | fv_list(e.comparators)
    if isinstance(e, ast.IfExp):
        return fv(e.test) | fv(e.body) | fv(e.orelse)
    if isinstance(e, ast.Attribute):
        return fv(e.value)
    if isinstance(e, ast.Subscript):
        return fv(e.value) | fv(e.slice)
    if isinstance(e, (ast.List, ast.Tuple)):
        return fv_list(e.elts)
    if isinstance(e, ast.Dict):
        return fv_list([k for k in e.keys if k is not None]) | fv_list(e.values)
    if isinstance(e, ast.ListComp):
        return fv_comprehension(e.elt, e.generators)
    return set()


def fv_list(es):
    if not es:
        return set()
    return fv(es[0]) | fv_list(es[1:])


def fv_comprehension(elt, generators):
    """fv of `elt for g_1 ... g_n`. Each generator's iter is evaluated in the
    enclosing scope (before its target binds); guards and remaining generators
    see the bound names."""
    if not generators:
        return fv(elt)
    g = generators[0]
    target_names = names_in_target(g.target)
    rest = fv_list(g.ifs) | fv_comprehension(elt, generators[1:])
    return fv(g.iter) | (rest - target_names)


def names_in_target(target):
    """Names bound by a comprehension/for target (single Name or Tuple thereof)."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Tuple):
        return _names_in_targets(target.elts)
    return set()


def _names_in_targets(targets):
    if not targets:
        return set()
    return names_in_target(targets[0]) | _names_in_targets(targets[1:])


def captures(e):
    """Variables captured by closures within e."""
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        return fv(e.body) - params
    if isinstance(e, ast.Name):
        return set()
    if isinstance(e, ast.Constant):
        return set()
    if isinstance(e, ast.Call):
        return captures(e.func) | captures_list(e.args)
    if isinstance(e, ast.BinOp):
        return captures(e.left) | captures(e.right)
    if isinstance(e, ast.UnaryOp):
        return captures(e.operand)
    if isinstance(e, ast.BoolOp):
        return captures_list(e.values)
    if isinstance(e, ast.Compare):
        return captures(e.left) | captures_list(e.comparators)
    if isinstance(e, ast.IfExp):
        return captures(e.test) | captures(e.body) | captures(e.orelse)
    if isinstance(e, ast.Attribute):
        return captures(e.value)
    if isinstance(e, ast.Subscript):
        return captures(e.value) | captures(e.slice)
    if isinstance(e, (ast.List, ast.Tuple)):
        return captures_list(e.elts)
    if isinstance(e, ast.Dict):
        return captures_list([k for k in e.keys if k is not None]) | captures_list(e.values)
    if isinstance(e, ast.ListComp):
        return captures_comprehension(e.elt, e.generators)
    return set()


def captures_list(es):
    if not es:
        return set()
    return captures(es[0]) | captures_list(es[1:])


def captures_comprehension(elt, generators):
    if not generators:
        return captures(elt)
    g = generators[0]
    target_names = names_in_target(g.target)
    rest = captures_list(g.ifs) | captures_comprehension(elt, generators[1:])
    return captures(g.iter) | (rest - target_names)


# --- fv / assignsF / captures lifted to statements and blocks -----------------


def fv_stmt(s):
    if isinstance(s, ast.Pass):
        return set()
    if isinstance(s, ast.Assign):
        return fv(s.value)
    if isinstance(s, ast.Expr):
        return fv(s.value)
    if isinstance(s, ast.Return):
        return fv(s.value) if s.value is not None else set()
    if isinstance(s, ast.Assert):
        result = fv(s.test)
        if s.msg is not None:
            result = result | fv(s.msg)
        return result
    if isinstance(s, ast.If):
        return fv(s.test) | fv_block(s.body) | fv_block(s.orelse)
    if isinstance(s, ast.FunctionDef):
        params = {a.arg for a in s.args.args}
        return fv_block(s.body) - params - {s.name}
    return set()


def fv_block(block):
    if not block:
        return set()
    return fv_stmt(block[0]) | fv_block(block[1:])


def assigns_stmt(s):
    """assignsF on a statement (see fig/well-formed.tex equations)."""
    if isinstance(s, ast.Assign):
        return {t.id for t in s.targets if isinstance(t, ast.Name)}
    if isinstance(s, ast.If):
        return assigns_block(s.body) | assigns_block(s.orelse)
    if isinstance(s, ast.FunctionDef):
        return {s.name}
    return set()


def assigns_block(block):
    if not block:
        return set()
    return assigns_stmt(block[0]) | assigns_block(block[1:])


def captures_stmt(s):
    if isinstance(s, ast.Pass):
        return set()
    if isinstance(s, ast.Assign):
        return captures(s.value)
    if isinstance(s, ast.Expr):
        return captures(s.value)
    if isinstance(s, ast.Return):
        return captures(s.value) if s.value is not None else set()
    if isinstance(s, ast.Assert):
        result = captures(s.test)
        if s.msg is not None:
            result = result | captures(s.msg)
        return result
    if isinstance(s, ast.If):
        return captures(s.test) | captures_block(s.body) | captures_block(s.orelse)
    if isinstance(s, ast.FunctionDef):
        return captures_region([s])
    return set()


def captures_block(block):
    if not block:
        return set()
    return captures_stmt(block[0]) | captures_block(block[1:])


def captures_region(defs):
    """captures of a mutual region (fig/well-formed.tex equation)."""
    f_names = {d.name for d in defs}
    return _captures_region_bodies(defs) - f_names


def _captures_region_bodies(defs):
    if not defs:
        return set()
    d = defs[0]
    params = {a.arg for a in d.args.args}
    own = fv_block(d.body) - params - assigns_block(d.body)
    return own | _captures_region_bodies(defs[1:])


def captures_item(item):
    if isinstance(item, list):
        return captures_region(item)
    return captures_stmt(item)


def assigns_item(item):
    if isinstance(item, list):
        return {d.name for d in item}
    return assigns_stmt(item)


def assigns_items(items):
    if not items:
        return set()
    return assigns_item(items[0]) | assigns_items(items[1:])


def find_first_reassigning(items, names):
    """Return the AST node of the first item that assigns any name in `names`."""
    if not items:
        return None
    if assigns_item(items[0]) & names:
        return items[0][0] if isinstance(items[0], list) else items[0]
    return find_first_reassigning(items[1:], names)


def check_module(tree):
    """Top-level entry: check the module body as a block. Γ starts populated
    with the built-in names we support (see BUILTINS)."""
    if not tree.body:
        return ok()
    return check_block(tree.body, dict(BUILTINS))


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
