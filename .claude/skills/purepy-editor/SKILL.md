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
- Object relative clauses are a recurring problem. In "the values that no case matches", the head noun
  "values" is the object of the verb inside the clause: the reader holds the noun while a new subject
  ("no case") appears, then attaches the noun as the object of "matches". The construction has three
  forms, all banned:
  1. Relativiser dropped: "the values no case matches", "the type the expression synthesises", "the
     variables the body assigns".
  2. Relativiser present: "the values that no case matches", "the type which the expression synthesises".
  3. Reduced to a passive participle whose agent carries a negation or a quantifier: "the values matched
     by no case", "the shapes matched by every case", "a name bound by neither branch". The negation or
     quantifier is hidden in the agent phrase and the reader has to expand it.

  The fix is to make the head noun the subject of its own modifier:
  - Name the thing where a term or metafunction exists: "the residual", not "the values that no case
    matches"; "the matched shapes", not "the shapes the pattern matches".
  - Otherwise, where the modifier is affirmative and its agent is a plain noun phrase, use a passive
    participle: "variables assigned in the body", "the type synthesised by the expression".
  - Otherwise, where the modifier carries a negation or a quantifier, write a full relative clause with
    "which" or "that", put the negation on the verb, and use "any" under the negation: "the values which
    are not matched by any case", not "the values matched by no case" and not "the values that no case
    matches"; "the shapes which every case matches" is still an object relative, so write "the shapes
    which are matched by every case".

  Test: the noun before the modifier must be the grammatical subject of the modifier's verb, and no
  "no", "neither", "every" or "each" may appear inside the agent phrase of a participle.
- Name things with nouns, not free relative clauses: "matched shapes", not "what it matches"; "the residual", not "what is left over".
- Clause-final pro-forms ("leaves none", "the others", "the same holds", "so does") are a verbal tic: resist them even where unambiguous, because the pattern becomes conspicuous with repetition. Pointing back is fine when deliberate and clear; the default is to repeat the noun ("leaves an empty residual", "the remaining members") or restructure.
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
