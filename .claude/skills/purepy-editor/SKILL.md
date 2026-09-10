---
name: purepy-editor
description: Conventions for editing the PurePy spec and its GitHub issues; defers to the github-issues skill for general issue, pull request and meeting conventions.
---

# PurePy editor conventions

## Style

- Minimal. State the thing; stop.
- No weasel-words like "honest", "clean", "obvious", "simply".
- Table cells, figure captions and rule side conditions are telegraphic: no articles ("Rebinds variable", not "Rebinds a variable"; "neither list type nor union").
- Never write "entry" on its own: it is a context entry or a class entry.
- Use every metavariable of a sort before reaching for a prime: two types are sigma and tau, not tau and tau prime. A prime is for the third of a sort, or where the two are the same thing at different stages.
- A related tic: dropping the relativiser from an object relative clause ("the values no case has matched"). Write it out ("the values that no case has matched"), or better, spell the phrase plainly ("the values which have not been matched by any case"); the participle rule below still applies where a participle reads naturally.
- Clause-final pro-forms ("leaves none", "the others", "the same holds", "so does") are a verbal tic: resist them even where unambiguous, because the pattern becomes conspicuous with repetition. Pointing back is fine when deliberate and clear; the default is to repeat the noun ("leaves an empty residual", "the remaining members") or restructure.
- Name things with nouns, not free relative clauses: "matched shapes", not "what it matches"; "the residual", not "what is left over".
- Prefer a participle or a named term to a postmodifying relative clause: "variables assigned in the body", not "the variables the body assigns"; "the residual", not "the part it leaves". Where a metafunction names the concept, use its name.
- A condition takes "if" or "when", not "where": "undefined if two declarations share a name". "Where" reads as a place, so reserve it for quantifying over positions ("the rows differ where the pattern is a literal") and for binding a symbol ("where n is the arity").
- Do not coin terminology, in the spec or in conversation ("foreign module", "fresh position"). Use the spec's own terms or plain description ("a module other than the current one").
- No defensive coding. If a case shouldn't arise, assert it; don't silently return a safe default.

## LaTeX

- Name a source file after the definitions it contains, and rename it when they change. A figure label
  follows the file name.
- A macro is named after what it renders (\baseType for base-type, not \widen), and is renamed when the
  rendered name changes.

## Git

- Commit after every coherent change; don't sit on uncommitted work.

## References in conversation

- When referring to a figure, lemma, definition or section of the specification or paper, give its name
  and its number in the current PDF, so it can be found without a search. For example: the shape-typing
  figure, Figure 4.13 in the specification. Look the number up (a draft-mode `pdflatex` run's `.aux` has
  every label's number); don't guess it.

## GitHub issues

General issue, pull request and meeting conventions are in the `github-issues` skill; use it. PurePy-specific:

- New issues: add to the PurePy project with Status either Planned or Proposed.
