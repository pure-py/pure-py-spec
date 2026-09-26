---
name: github-issues
description: Conventions for creating, editing, closing, referring to and organising GitHub issues, pull requests and meeting issues, including a terse writing style for titles, commit messages and bullet lists. Use whenever working with GitHub issues or pull requests.
---

# GitHub issue conventions

## Terse style

Commit messages, issue titles and bulleted lists are telegraphic. Write them tersely:

- Drop articles and filler ("Rebinds variable", not "Rebinds a variable")
- Titles and task-list items are noun phrases, naming the thing, not the action ("Syntax of types", not "Define the syntax of types")
- One point per bullet; state it and stop, no framing or hedging clauses
- No weasel-words ("honest", "clean", "obvious", "simply")
- No trailing period on a bullet or a title
- Commit subject line: short, imperative or noun phrase; put any detail in the body

## Referring to an issue

- When referring to an issue, give its number, its title and its URL, so it can be opened
  without a search. For example: #181, Classes for built-in types,
  https://github.com/OWNER/REPO/issues/181

## Issues

- Add content to an issue, whether a body, a comment or a closing comment, only when asked to. Otherwise create, edit or close it and nothing more
- When an issue references other issues or external resources, add a **See also** paragraph at the end with a bullet list of links. Example:

  ```
  ## See also

  - External specification, §6.10: https://example.org/spec#section
  - #36
  - #50
  ```

  Use this for cross-references to related issues and links to external specifications or documentation
- When linking to another GitHub issue in a bullet list, write just the bare `#N` reference, so GitHub renders the issue title inline

## Pull requests

- Titles are noun phrases, in the terse style above
- The body is empty, or `Closes #N` alone. The issue carries the content; do not summarise the changes in the PR

## Meeting issues

- Meeting issues are titled `YYYY-MM-DD`; set Type to `Meeting`
- Body sections: `## Adjacent meetings` (links to previous), then `## To discuss` containing `### Resolved since [date]`, `### New issues since [date]`, `### Work since [date]`
- Bullet lists of bare `#N` for issues; brief notes for work items
