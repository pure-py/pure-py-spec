---
name: purepy-editor
description: PurePy-specific additions to the technical-authoring, coding-conventions and github skills.
---

# PurePy editor conventions

## Style

- Nouns used by the spec for more than one kind of thing need qualifying: "entry" always (a context entry or a class entry); "outcome" when static and evaluation outcomes are both in play; "signature" rarely, since a module signature and a function signature seldom share a paragraph.

## GitHub issues

- New issues: add to the PurePy project with Status either Planned or Proposed.
- Default label: `spec-1.0`, unless the issue is an extension or config.
- Features under consideration, not yet committed to, also get the `Proposed` label.

## LaTeX

- Rebuild the paper after every change to verify that it builds without errors.
- Put primes outside `\vec`, not inside: `\vec{e}'`, not `\vec{e'}`.

## Conformance suite

- Before pushing a change to the suite, run `make check-suite-mechanisation`; a test ahead of the mechanisation is listed in `test/expected-failures.txt` against the open issue for the mechanisation change. The pre-push hook in `script/hooks` runs the check and refuses the push if it fails.
