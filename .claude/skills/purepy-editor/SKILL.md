---
name: purepy-editor
description: Conventions for editing the PurePy spec and related GitHub issues.
---

# PurePy editor conventions

## Style

- Minimal. State the thing; stop.

## GitHub issues

- When an issue references other issues or external resources, add a **See also** paragraph at the end with a bullet list of links. Example:

  ```
  ## See also

  - Python language reference, §6.10 Comparisons: https://docs.python.org/3/reference/expressions.html#comparisons
  - #36
  - #50
  ```

  Use this for: cross-references to related issues, links to the Python language reference, links to other external specs.

- When linking to another GitHub issue in a bullet list, write just the bare `#N` reference — GitHub renders the issue title inline.
