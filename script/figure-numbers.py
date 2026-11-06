#!/usr/bin/env python3
"""Write figure number of each rule and judgement figure, as JSON on standard output, from specification
sources and LaTeX auxiliary file kept from last build"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "PurePy-spec.tex"
LABELS = ROOT / "xref" / "PurePy-spec.aux"

INPUT = re.compile(r"\\(?:spec)?input\{(spec/[^{}#]+)\}")
COMMENT = re.compile(r"(?<!\\)%.*")
ARG = r"\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}"
DELETED = re.compile(
    rf"\\begin\{{DeletedBlock\}}.*?\\end\{{DeletedBlock\}}|\\[dD]eleted{ARG}", re.DOTALL
)
REPLACED = re.compile(rf"\\[rR]eplaced{ARG}{ARG}")
TOKEN = re.compile(
    r"\\(?P<begin>begin|end)\{(?:figure\*?|subfigure)\}"
    r"|lab=\{\\ruleName\{(?P<rule>[a-z0-9-]+)\}\}"
    r"|\\label\{fig:(?P<label>[a-z0-9-]+)\}"
    r"|(?P<judgement>\\shadebox\{)"
)
NEWLABEL = re.compile(r"\\newlabel\{fig:([a-z0-9-]+)\}\{\{([^{}]*)\}")


def source(f: pathlib.Path) -> str:
    """Source of f with inputs expanded, and comments and text in deleted change markup removed"""
    text = COMMENT.sub("", f.read_text(encoding="utf-8"))
    text = REPLACED.sub(lambda m: m[1], DELETED.sub("", text))
    return INPUT.sub(lambda m: source((ROOT / m[1]).with_suffix(".tex")), text)


@dataclass
class Figure:
    rules: list[str] = field(default_factory=list)
    label: str | None = None
    judgement: bool = False


@dataclass
class Figures:
    rules: dict[str, str] = field(default_factory=dict)
    judgements: list[str] = field(default_factory=list)


def figures(text: str) -> Figures:
    """Label of the innermost labelled figure or subfigure containing each rule, and label of each figure or
    subfigure defining a judgement form"""
    figs = Figures()
    # Figure and subfigure environments enclosing the rule, label or judgement form being read, innermost last
    enclosing: list[Figure] = []
    for m in TOKEN.finditer(text):
        if m["begin"] == "begin":
            enclosing.append(Figure())
        elif m["begin"] == "end":
            fig = enclosing.pop()
            if fig.label is not None:
                figs.rules.update((rule, fig.label) for rule in fig.rules)
                if fig.judgement:
                    figs.judgements.append(fig.label)
            else:
                assert enclosing, f"figure containing {', '.join(fig.rules)} has no label"
                enclosing[-1].rules.extend(fig.rules)
                enclosing[-1].judgement |= fig.judgement
        elif not enclosing:
            assert m["rule"] is None, f"rule {m['rule']} outside any figure"
        elif m["rule"] is not None:
            enclosing[-1].rules.append(m["rule"])
        elif m["label"] is not None:
            enclosing[-1].label = m["label"]
        else:
            enclosing[-1].judgement = True
    return figs


def main() -> None:
    # Replace TeX ligature for en dash by en dash character
    numbers = {
        label: number.replace("--", "\u2013")
        for label, number in NEWLABEL.findall(LABELS.read_text(encoding="utf-8"))
    }
    figs = figures(source(SPEC))
    for rule, label in figs.rules.items():
        assert label in figs.judgements, (
            f"rule {rule} in figure {label}, which shows no judgement form"
        )
    json.dump(
        {
            "rules": {rule: numbers[label] for rule, label in sorted(figs.rules.items())},
            "judgements": {label: numbers[label] for label in figs.judgements},
        },
        sys.stdout,
        indent=2,
    )
    print()


if __name__ == "__main__":
    main()
