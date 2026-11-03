"""Dependency diagram of the organisation's repositories, as SVG"""

import html
import pathlib
import re
import subprocess
import sys

from diagram.edge import Edge
from diagram.node.repository import Repository
from diagram.organisation import Organisation

ICON = pathlib.Path(__file__).resolve().parent / "icon"
D2 = ["d2", "--pad", "16", "--elk-nodeNodeBetweenLayers", "30", "--elk-edgeNodeBetweenLayers", "15"]
D2 += ["--elk-padding", "[top=40,left=20,bottom=20,right=20]"]


def label(lines: list[str]) -> str:
    return "\\n".join(lines)


def node(org: Organisation, repo: Repository) -> str:
    """Repository, drawn as its project when it holds one, otherwise containing its projects"""
    own = org.projects[repo.name]
    version = [repo.version] if repo.version else []
    if len(own) == 1:
        (p,) = own
        names = [repo.name] + ([p.name] if p.name != repo.name else [])
        return f'"{repo.name}": "{label(names + version + p.lines())}" {{ class: standalone; icon: {ICON / p.icon} }}\n'
    inner = "".join(
        f'  "{p.name}": "{label([p.name, *p.lines()])}" {{ class: project; icon: {ICON / p.icon} }}\n'
        for p in own
    )
    return (
        f'"{repo.name}": "{" ".join([repo.name, *version])}" {{\n  class: repository\n{inner}}}\n'
    )


def d2(org: Organisation) -> str:
    edges = sorted(
        {e for kind in Edge.kinds() for e in kind.find(org)},
        key=lambda e: (org.node_id(e.target), org.node_id(e.source), e.label),
    )
    links = "".join(
        f"{org.node_id(e.source)} -> {org.node_id(e.target)}: {e.label} "
        f'{{ style: {{ stroke: "{e.style().colour}"; stroke-dash: {e.style().dash}; font-size: 17 }} }}\n'
        for e in edges
    )
    return f"""vars: {{ d2-config: {{ layout-engine: elk }} }}
direction: down
classes: {{
  project: {{ width: 230; style.font-size: 16 }}
  standalone: {{ width: 230; style.font-size: 16 }}
  repository: {{ style.font-size: 20 }}
}}
{"".join(node(org, r) for r in org.repositories)}{links}"""


def italicise(svg: str, lines: set[str]) -> str:
    """Description lines of node labels in the italic font, which D2 can't set within a label"""
    return re.sub(
        r"(<tspan[^>]*)>([^<]*)</tspan>",
        lambda m: (
            f'{m[1]} class="text-italic">{m[2]}</tspan>' if html.unescape(m[2]) in lines else m[0]
        ),
        svg,
    )


def main() -> None:
    root, output = map(pathlib.Path, sys.argv[1:])
    org = Organisation.load(root)
    lines = {line for ps in org.projects.values() for p in ps for line in p.lines()}
    glyphs = "".join(sorted({c for line in lines for c in line if not c.isspace()}))
    # Italic label in white, so the italic font embedded by D2 has every glyph of the descriptions
    source = d2(org) + (
        f'glyphs: "{glyphs}" {{ near: bottom-right; shape: text; style: {{ italic: true; bold: false;'
        ' font-size: 8; font-color: "#FFFFFF" } }\n'
    )
    drawn = subprocess.run(
        [*D2, "-", "-"], input=source, capture_output=True, text=True, check=False
    )
    if drawn.returncode != 0:
        sys.exit(drawn.stderr)
    output.write_text(italicise(drawn.stdout, lines))
