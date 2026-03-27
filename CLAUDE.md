# Claude Code instructions

See README.md for project structure, build, test, and release docs.

## GitHub issues

- Add new issues to the **PurePy** project.
- Give new issues either **Planned** or **Proposed** status.
- Default label: `spec-1.0` (unless the issue is an extension or config).
- Features under consideration (not yet committed to) also get the `Proposed` label.
- Link issues from the to-do table in §2 of the spec using the `\issue{N}` macro.

## LaTeX

- Always rebuild the paper after every change to verify no build errors.
- Put primes outside `\vec`, not inside (e.g. `\vec{e}'` not `\vec{e'}`).

## GitHub CLI

- Never run `gh auth refresh` or `gh auth login` without `--with-token` — this overwrites the fine-grained PAT with a new OAuth token that lacks private repo access.
