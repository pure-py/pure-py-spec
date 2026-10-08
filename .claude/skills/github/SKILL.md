---
name: github
description: Conventions for commits, GitHub issues, pull requests, the project board and meeting issues, including a terse writing style for titles, commit messages and bullet lists. Use whenever committing or working with GitHub issues or pull requests.
---

# Git and GitHub conventions

## Terse style

Commit messages, issue titles and bulleted lists are telegraphic:

- Drop articles and filler ("Rebinds variable", not "Rebinds a variable")
- Titles and task-list items are noun phrases naming the thing, not the action ("Syntax of types", not "Define the syntax of types")
- One point per bullet, no framing or hedging clauses
- No weasel-words ("honest", "clean", "obvious", "simply")
- No trailing period on a bullet or a title
- Commit subject line short, imperative or noun phrase; detail in the body

## Commits

- Fix a committed mistake with a new commit; never amend, and never `git stash`

## Permissions

- When an action is refused for lack of permission, stop and report it; never work around the refusal
  with another account, another token or a bypass flag

## Referring to an issue

- Give its number, title and URL: #181, Classes for built-in types,
  https://github.com/OWNER/REPO/issues/181

## Issues

- Before starting work on an issue, assign it to the user and to the account you run as (`gh api user --jq .login`)
- Check with the user before creating an issue, unless explicitly instructed to create one
- Add content to an issue (body, comment, closing comment) only when asked; otherwise create, edit or close it and nothing more
- Link an external resource inline where the body mentions it, not in a **See also** paragraph
- When an issue references other issues, end with a **See also** paragraph:

  ```
  ## See also

  - #36
  - #50
  ```

- In a bullet list, link another issue as bare `#N`, which GitHub renders with its title

## Project board

- To read or set an issue's board Status, query the `projectItems` of the issue (in fluid,
  `script/issue-status.sh <issue> [Status]`); never `gh project item-list`, which fetches the
  whole board and trips the GraphQL rate limit
- Closing an issue does not change its Status; set `Done` or `Rejected` explicitly

## Pull requests

- Titles are noun phrases, in the terse style above
- The body is empty, or `Closes #N` alone: no summary of the changes, no attribution footer, no session link

## Meeting issues

- Meeting issues are titled `YYYY-MM-DD`; set Type to `Meeting`
- Body sections: `## Adjacent meetings` (links to previous), then `## To discuss` containing `### Resolved since [date]`, `### New issues since [date]`, `### Work since [date]`
- Bullet lists of bare `#N` for issues; brief notes for work items
