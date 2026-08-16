from __future__ import annotations

import ast

def is_catch_all(p: ast.pattern) -> bool:
    return isinstance(p, ast.MatchAs) and p.pattern is None

def literal_value(pat: ast.MatchValue) -> object:
    v = pat.value
    if isinstance(v, ast.Constant):
        return v.value
    if isinstance(v, ast.UnaryOp) and isinstance(v.operand, ast.Constant):
        operand_value = v.operand.value
        assert isinstance(operand_value, (int, float))
        return -operand_value if isinstance(v.op, ast.USub) else operand_value
    raise AssertionError(f'unexpected MatchValue payload: {type(v).__name__}')

def dict_key(k: ast.expr) -> str:
    assert isinstance(k, ast.Constant) and isinstance(k.value, str)
    return k.value

def subsumes(p: ast.pattern, q: ast.pattern) -> bool:
    if isinstance(q, ast.MatchAs) and q.pattern is not None:
        return subsumes(p, q.pattern)
    if isinstance(p, ast.MatchAs) and p.pattern is not None:
        return subsumes(p.pattern, q)
    if isinstance(q, ast.MatchAs) and q.pattern is None:
        return True
    if isinstance(p, ast.MatchValue) and isinstance(q, ast.MatchValue):
        return literal_value(p) == literal_value(q)
    if isinstance(p, ast.MatchSingleton) and isinstance(q, ast.MatchSingleton):
        return p.value is q.value
    if isinstance(p, ast.MatchMapping) and isinstance(q, ast.MatchMapping):
        p_keys = {dict_key(k): sub for k, sub in zip(p.keys, p.patterns)}
        q_keys = {dict_key(k): sub for k, sub in zip(q.keys, q.patterns)}
        if not set(q_keys) <= set(p_keys):
            return False
        return all(subsumes(p_keys[k], sub) for k, sub in q_keys.items())
    if isinstance(p, ast.MatchSequence) and isinstance(q, ast.MatchSequence):
        if bool(getattr(p, 'is_list_pattern', False)) != bool(getattr(q, 'is_list_pattern', False)):
            return False
        if len(p.patterns) != len(q.patterns):
            return False
        return all((subsumes(pi, qi) for pi, qi in zip(p.patterns, q.patterns)))
    return False

def pattern_vars(p: ast.pattern) -> list[str]:
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return []
    if isinstance(p, ast.MatchAs):
        sub = pattern_vars(p.pattern) if p.pattern is not None else []
        return sub + ([p.name] if p.name else [])
    if isinstance(p, ast.MatchSequence):
        return [v for sub in p.patterns for v in pattern_vars(sub)]
    if isinstance(p, ast.MatchClass):
        return [v for sub in p.patterns for v in pattern_vars(sub)] + \
               [v for sub in p.kwd_patterns for v in pattern_vars(sub)]
    if isinstance(p, ast.MatchMapping):
        return [v for sub in p.patterns for v in pattern_vars(sub)]
    raise AssertionError(f'unexpected pattern: {type(p).__name__}')
