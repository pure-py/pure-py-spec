from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from itertools import takewhile

from diagram.node.project import Project, required
from diagram.node.repository import Repository

TOKEN = re.compile(r'"(?P<quoted>[^"]*)"|(?P<bare>[^\s"]+)')
KEYWORDS = {
    "session",
    "in",
    "=",
    "+",
    "description",
    "options",
    "sessions",
    "directories",
    "theories",
}
KEYWORDS |= {"document_theories", "document_files", "export_files", "export_classpath"}


@dataclass(frozen=True)
class IsabelleProject(Project):
    """Isabelle sessions of a ROOT file, named after the first"""

    file = "ROOT"
    icon = "isabelle.png"
    sessions: tuple[str, ...]
    imports: tuple[str, ...]  # Parents and listed sessions of the sessions

    @classmethod
    def recognise(cls, repo: Repository, path: pathlib.PurePath) -> Project | None:
        tokens = [
            m["quoted"] if m["quoted"] is not None else m["bare"]
            for m in TOKEN.finditer((repo.path / path).read_text())
        ]
        after = {i: tokens[i + 1] for i in range(len(tokens) - 1)}
        sessions = tuple(after[i] for i, t in enumerate(tokens) if t == "session" and i in after)
        if not sessions:
            return None
        second = next((i for i, t in enumerate(tokens) if t == "session" and i > 0), len(tokens))
        description = next(
            (after[i] for i, t in enumerate(tokens[:second]) if t == "description"), None
        )
        listed = tuple(
            entry
            for i, t in enumerate(tokens)
            if t == "sessions"
            for entry in takewhile(lambda u: u not in KEYWORDS, tokens[i + 1 :])
        )
        parents = tuple(
            after[i] for i, t in enumerate(tokens) if t == "=" and after.get(i + 1) == "+"
        )
        return cls(
            repo.name,
            sessions[0],
            required(description, path),
            path.parent,
            sessions,
            parents + listed,
        )
