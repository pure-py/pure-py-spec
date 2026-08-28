---
name: purepy-editor
description: Conventions for editing the PurePy spec and related GitHub issues.
---

# PurePy editor conventions

## Style

- Minimal. State the thing; stop.
- No weasel-words like "honest", "clean", "obvious", "simply".
- Table cells and figure captions are telegraphic: no articles ("Rebinds variable", not "Rebinds a variable").
- Never write "entry" on its own: it is a context entry or a class entry.
- Name things with nouns, not free relative clauses: "matched shapes", not "what it matches"; "the residual", not "what is left over".
- Prefer a participle or a named term to a postmodifying relative clause: "variables assigned in the body", not "the variables the body assigns"; "the residual", not "the part it leaves". Where a metafunction names the concept, use its name.
- No defensive coding. If a case shouldn't arise, assert it; don't silently return a safe default.

## Git

- Commit after every coherent change; don't sit on uncommitted work.

## GitHub issues

- New issues: add to the PurePy project with Status either Planned or Proposed.

- Issue titles and task-list items are noun phrases (e.g. "Syntax of types", not "Define the syntax of types").

- When an issue references other issues or external resources, add a **See also** paragraph at the end with a bullet list of links. Example:

  ```
  ## See also

  - Python language reference, §6.10 Comparisons: https://docs.python.org/3/reference/expressions.html#comparisons
  - #36
  - #50
  ```

  Use this for: cross-references to related issues, links to the Python language reference, links to other external specs.

- When linking to another GitHub issue in a bullet list, write just the bare `#N` reference — GitHub renders the issue title inline.

## Pull requests

- Titles are noun phrases, like issue titles.
- The body is empty, or `Closes #N` alone. The issue carries the content; do not summarise the changes in the PR.

## Meetings

- Meeting issues are titled `YYYY-MM-DD`; set Type to `Meeting`.
- Body sections: `## Adjacent meetings` (links to previous), then `## To discuss` containing `### Resolved since [date]`, `### New issues since [date]`, `### Work since [date]`.
- Bullet lists of bare `#N` for issues; brief notes for work items.
