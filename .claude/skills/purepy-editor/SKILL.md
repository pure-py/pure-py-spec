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

- Unless instructed otherwise, make edits to specification prose and rules in change markup, using the macros of `tex/change-tracking.tex`: `\added`, `\deleted` and `\replaced{new}{old}` inline, the capitalised variants for a margin change bar, and `AddedBlock` and `DeletedBlock` for whole paragraphs or display material. Rewrite a section body as a `DeletedBlock` of the old text followed by an `AddedBlock` of the new.
- End the old text inside `\replaced` with a space, so that the grey and green runs do not abut.
- Markup is accepted later, in a commit titled "Change markup accepted"; `make -B paper.pdf FINAL=1` (or `PurePy-spec.pdf`) builds the clean version.
- Rebuild the paper after every change to verify that it builds without errors.
- Put primes outside `\vec`, not inside: `\vec{e}'`, not `\vec{e'}`.
