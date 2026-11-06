from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "PurePy-spec.tex"
JUDGEMENT_INDEX = ROOT / "spec" / "fig" / "judgement-index.tex"

INPUT = re.compile(r"\\(?:spec)?input\{(spec/[^{}#]+)\}")
COMMENT = re.compile(r"(?<!\\)%.*")
ARG = r"\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}"
DELETED = re.compile(
    rf"\\begin\{{DeletedBlock\}}.*?\\end\{{DeletedBlock\}}|\\[dD]eleted{ARG}", re.DOTALL
)
REPLACED = re.compile(rf"\\[rR]eplaced{ARG}{ARG}")
ADDED = re.compile(rf"\\[aA]dded{ARG}")
TOKEN = re.compile(
    r"\\(?P<begin>begin|end)\{(?:figure\*?|subfigure)\}"
    r"|lab=\{\\ruleName\{(?P<rule>[a-z0-9-]+)\}\}"
    r"|\\label\{fig:(?P<label>[a-z0-9-]+)\}"
    r"|\\shadebox\{(?P<form>\$.*?\$)"
)
JUDGEMENT = re.compile(r"^(\$.*?\$) &.*\\judgementFigref\{([a-z-]+)\}\{[a-z0-9-]+\}", re.MULTILINE)


def source(f: pathlib.Path) -> str:
    """Read f, expanding inputs, accepting change markup and removing comments"""
    text = COMMENT.sub("", f.read_text(encoding="utf-8"))
    text = ADDED.sub(lambda m: m[1], REPLACED.sub(lambda m: m[1], DELETED.sub("", text)))
    return INPUT.sub(lambda m: source((ROOT / m[1]).with_suffix(".tex")), text)


@dataclass(frozen=True)
class Rule:
    figure: str
    judgement: str


@dataclass
class Figure:
    rules: list[tuple[str, str]] = field(default_factory=list)
    label: str | None = None


def rules(text: str) -> dict[str, Rule]:
    """Label of innermost labelled figure or subfigure containing each rule, and form of last
    judgement before rule"""
    found: dict[str, Rule] = {}
    # Figure and subfigure environments enclosing rule, label or judgement form being read, innermost last
    enclosing: list[Figure] = []
    form = None
    for m in TOKEN.finditer(text):
        if m["begin"] == "begin":
            if not enclosing:
                form = None
            enclosing.append(Figure())
        elif m["begin"] == "end":
            fig = enclosing.pop()
            if fig.label is not None:
                found.update((rule, Rule(fig.label, j)) for rule, j in fig.rules)
            else:
                assert enclosing, (
                    f"figure containing {', '.join(r for r, _ in fig.rules)} has no label"
                )
                enclosing[-1].rules.extend(fig.rules)
        elif not enclosing:
            assert m["rule"] is None, f"rule {m['rule']} outside any figure"
        elif m["rule"] is not None:
            assert form is not None, f"rule {m['rule']} before any judgement form"
            enclosing[-1].rules.append((m["rule"], form))
        elif m["label"] is not None:
            enclosing[-1].label = m["label"]
        else:
            form = m["form"]
    return found


def judgements() -> dict[str, str]:
    """Form of each judgement in index, by name"""
    return {name: form for form, name in JUDGEMENT.findall(source(JUDGEMENT_INDEX))}
