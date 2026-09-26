---
name: coding-conventions
description: Shared conventions for code in any language (comments, docstrings, identifiers, defensive code, commit granularity). Use whenever writing or editing code, alongside the language-specific skill (agda-implementor, spec-implementor).
---

# Coding conventions

Language-specific skills (agda-implementor, spec-implementor) add to these and do not repeat them.

## Comments and docstrings

- Comment only what the code cannot show. Never narrate how the code came about: no process
  commentary, no reasoning that produced the code, no source-file names.
- Brief and factual. Telegraphic, without articles, as in table cells and rule side conditions
  ("Collapse duplicate rows", not "This collapses the duplicate rows"). Bare imperative for
  operations ("Collapse", not "Collapses"); contractions fine ("can't cancel").
- A definition named after a construct of the specification or paper it implements needs no
  docstring; the specification defines it. Describe only helpers with no counterpart there.
- Plain terms in identifiers and comments; no coined vocabulary.

## Identifiers

- Name a thing after what it denotes, never by initials, primes or digits.
- Use the specification's or paper's metavariable conventions, not a library's.

## Code

- No defensive coding. If a case shouldn't arise, assert it; don't silently return a safe default.

## Commits

- Commit each verified unit of work as you go; don't sit on uncommitted work. Message style and
  branch, issue and pull request conventions are in the github-issues skill.

## Reporting

- Report the current state of the code, not how it got there: no pre-commit moves, branch
  history or intermediate names. Mention history only when the user must act on it (e.g. a
  rebase to pull).
