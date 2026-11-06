#!/usr/bin/env python3
"""Write figure number of each rule and judgement to standard output as JSON"""

from __future__ import annotations

import json
import re
import sys

from spec_sources import ROOT, SPEC, rules, source

LABELS = ROOT / "xref" / "PurePy-spec.aux"

NEWLABEL = re.compile(r"\\newlabel\{fig:([a-z0-9-]+)\}\{\{([^{}]*)\}")
JUDGEMENT_FIGURE = re.compile(r"\\judgementFigure\{([a-z-]+)\}\{([a-z0-9-]+)\}")


def main() -> None:
    aux = LABELS.read_text(encoding="utf-8")
    numbers = {label: number.replace(r"\nobreakdash --", "\u2013") for label, number in NEWLABEL.findall(aux)}
    json.dump(
        {
            "rules": {
                name: numbers[rule.figure] for name, rule in sorted(rules(source(SPEC)).items())
            },
            "judgements": {name: numbers[label] for name, label in JUDGEMENT_FIGURE.findall(aux)},
        },
        sys.stdout,
        indent=2,
    )
    print()


if __name__ == "__main__":
    main()
