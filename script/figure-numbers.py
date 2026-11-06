#!/usr/bin/env python3
"""Figure number of each rule of the specification and of each judgement figure label, as JSON on standard
output, from the specification sources and the labels of its last build. A rule belongs to the innermost
labelled figure or subfigure containing it, and a judgement figure is a labelled figure or subfigure containing
the box of a judgement form."""

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
    """Label of the figure of each rule, and the judgement figure labels"""
    figs = Figures()
    # Open figures and subfigures, innermost last; an unlabelled one passes its contents to its parent
    open_: list[Figure] = []
    for m in TOKEN.finditer(text):
        if m["begin"] == "begin":
            open_.append(Figure())
        elif m["begin"] == "end":
            fig = open_.pop()
            if fig.label is not None:
                figs.rules.update((rule, fig.label) for rule in fig.rules)
                if fig.judgement:
                    figs.judgements.append(fig.label)
            else:
                assert open_, f"figure containing {', '.join(fig.rules)} has no label"
                open_[-1].rules.extend(fig.rules)
                open_[-1].judgement |= fig.judgement
        elif not open_:
            assert m["rule"] is None, f"rule {m['rule']} outside any figure"
        elif m["rule"] is not None:
            open_[-1].rules.append(m["rule"])
        elif m["label"] is not None:
            open_[-1].label = m["label"]
        else:
            open_[-1].judgement = True
    return figs


def main() -> None:
    # En dash in a figure number written as its TeX ligature
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
