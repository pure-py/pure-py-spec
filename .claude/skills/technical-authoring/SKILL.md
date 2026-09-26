---
name: technical-authoring
description: House style for drafting and editing technical prose (papers, specifications, notes, issues, code comments) with Roly. Plain, factual, conventional English; no rhetorical compression or editorial colour. Use whenever drafting or revising paper or specification text, and when asked to "lose the ticks".
---

# Technical authoring style

Direct, factual, conventional prose. Minimal: state the thing and stop. Every rule below comes from a specific correction during drafting; the before/after pairs are from those sessions.

This skill is kept in two places, `~/.claude/skills` and `.claude/skills` in the pure-py-spec repository; keep the copies identical.

## Sentence construction

- Avoid overly pity constructions: "It's yours, not a leftover." is too blunt and relies too heavily on the comma as a pivot from assertion to contrast point.
- Spell out logical connectives; prefer "because X" or "so that X" over a bare colon-assertion.
  - Before: "The Boolean Jacobian instead records 1: disjunction cannot cancel."
  - After: "The Boolean Jacobian instead records 1, because dependency information combines by disjunction and disjunction cannot cancel."
- No cleft constructions: "X is what makes...", "this is where...", "is exactly...", "is precisely...". Use a direct verb with a named subject.
  - Before: "Idempotent addition is what relates the algebra to an order."
  - After: "Idempotent addition induces an order."
  - Before: "The entry for price a is where they part company."
  - After: "They differ at the entry for price a."
- Do not coordinate two clauses with "and" where the second acts on the result of the first and ends on a pronoun pointing back at it. Subordinate the second clause instead, so the dependency is carried by the grammar rather than by word order.
  - Before: "A match scrutinee synthesises a type, and each case checks against it."
  - After: "A match scrutinee synthesises a type, against which each case is checked."
  - Before: "every rule passes it down unchanged, and a return has no rule where it is empty" (the second "it" reads as the return).
  This belongs with the comma-pivot and cleft rules above: all three use rhythm where a subordinating word would state the relation.
- Do not hang a comparison on a trailing "as in X" or "as X do", and never end a sentence on "do" or "does" standing in for an earlier verb phrase; name the shared thing and state the relation, or lead with "following".
  - Before: "Matching a pattern against a shape takes the scrutinee's type into account, as the uncovered sets of Karachalias et al. do."
  - After: "Matching a pattern against a shape takes the scrutinee's type into account, following the uncovered sets of Karachalias et al."
- Clause-final pro-forms ("leaves none", "the others", "the same holds", "so does") are a verbal tic: resist them even where unambiguous, because the pattern becomes conspicuous with repetition. Pointing back is fine when deliberate and clear; the default is to repeat the noun ("leaves an empty residual", "the remaining members") or restructure.
- No zero relative clauses stacking a noun against a bare subject-verb ("every edge a rule adds"); use a
  participle ("every edge added by a rule").
  - Before: "Every edge a rule adds runs forward in evaluation order."
  - After: "Every edge added by a rule points forward in evaluation order."
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
  The test also catches a possessive relative, "a function whose cases overlap", where the head noun is
  not the subject of "overlap": write "a function with overlapping cases".
- A negation goes on the verb, not on a noun phrase, whether that phrase is the agent of a participle
  (form 3 above) or the object of a verb: "does not fix any length", not "fixes no length"; "is not
  bound in either branch", not "is bound in neither branch". Where an affirmative statement says the
  same thing, prefer it: "admits values of every length".
- When a sentence quantifies over a finite set it has already introduced, refer to that set definitely:
  "not matched by any of the cases" (the cases of this match), not "not matched by any case"; "each of
  the branches", not "each branch". This applies only when a specific set is in scope. A general claim
  keeps the bare noun: "a variable pattern matches any shape".
- Name things with nouns, not free relative clauses: "matched shapes", not "what it matches"; "the residual", not "what is left over".
- A symbol must be bound in the sentence or by a judgement form stated just before it; otherwise name the thing.
  - Before: "A return checks its expression against τ" (nothing in the paragraph binds τ).
  - After: "A return checks its expression against the return type."
- Do not open a subclause with a bare abstract noun ("...: agreement, except where..."). Give it a subject and verb ("the two agree, except where...").
- No nested colons or semicolons within a sentence.
- Never open a sentence with a metafunction name, a rule name, or other mathematics ("captures(s) is the set of ...", "var applies whenever ..."); lead with a word ("The set of ... is captures(s)", "The var rule applies whenever ...").
- A condition takes "if" or "when", not "where": "undefined if two declarations share a name". "Where" reads as a place, so reserve it for quantifying over positions ("the rows differ where the pattern is a literal") and for binding a symbol ("where n is the arity").
- State the goal before the construction; do not stipulate a requirement ("we require the meet to cohere") before saying what it achieves — it reads as apropos of nothing. Similarly avoid "the coherence pays off", which implies an obligation never stated.

## Word choice

Each of these has drawn a correction:

- Editorial colour and weasel-words: "honest"/"honestly", "fib", "conceal", "arguably", "to be fair", "clean", "obvious", "simply".
- Metaphor and private jargon: "lands", "spine", "swept across", "walking the axis", "destination", "stage-factorisation" and similar compounds. "Story" sparingly; prefer a concrete noun ("the semimodule picture").
- "Rung" and "ladder": banned project-wide, in prose and in discussion.
- Vague nominal back-reference: "the algebra", "the structure". Name the referent.
- "Own" as a distinguishing qualifier ("the node's own positions"): state the distinction instead
  (the positions at the node itself, not those of its descendants).
- Invented terms where standard ones exist: "translation" not "shift"; "the other factor" not "cofactor". Check a term is standard before leaning on it, and cite where useful. Do not coin terminology, in the text or in conversation ("foreign module", "fresh position"); use the document's own terms or plain description ("a module other than the current one").
- "though" as a subordinating conjunction: prefer "although". The fixed phrase "even though" and the adverbial "though" meaning however are unaffected.
- Guidance-speak when the content is a trade-off: report the trade-off factually rather than telling the reader what they "should use".

## Terminology and notation

- Introduce a term before relying on it; if it first appears mid-argument ("orthogonality", "specialising", "De Morgan dual"), move its introduction to where the concept first appears. Italicise on first definition only, and drop italics that add nothing.
- Qualify a noun that the document uses for more than one kind of thing wherever the bare noun could be misread: a context entry or a class entry, not "entry".
- Do not shorten a term to its head noun: "mutual region", never "region" on its own, even on a
  second mention in the same paragraph. The head noun alone reads as an ordinary word.
- Keep variable sorts consistent within a section (a, b for scalars; x, y for semimodule elements).
- Use every metavariable of a sort before reaching for a prime: two types are sigma and tau, not tau and tau prime. A prime is for the third of a sort, or where the two are the same thing at different stages.
- One notation per object across the paper: S² rather than a mix of S ⊕ S and 𝕀; follow whichever convention earlier sections established.
- Write a structure out as a tuple at first use if its components matter.
- Prefer prose quantification ("changes by at most δ") over symbols the text will not reuse (δx).
- In double-blind submissions: "earlier work on X", never "our earlier work".

## Telegraphic text

- Table cells, figure captions and rule side conditions are telegraphic: no articles ("Rebinds variable", not "Rebinds a variable"; "neither list type nor union"). A gloss in apposition after a comma or colon within a cell keeps a leading article, which marks where the gloss begins, and no other: "head, a literal, class or list of length n", not "head, a literal, a class or a list of length n"; "context, a finite map from variables to entries".

## Comments and checklists

- Do not state a date or time without first checking it against the clock or the record; relative
  words like "yesterday" and "today" go wrong when a session crosses midnight.

- Code comments: see the coding-conventions skill.
- Checklists and issues: state the task directly ("Move X here; add Y"), no scene-setting.
- Meta-commentary about the document (what moved where, what supersedes what) belongs in the issue tracker, never in the text — including inside change markup.

## Structure

- When contrasting two things, frame the sentence around the one dimension of contrast and leave out machinery irrelevant to it (e.g. both maps oriented the same way, so the contrast is join- versus meet-preservation).
- Prefer parallel headings for sibling sections; if two sections share their setup, consider a common parent that states the setup once.
- Mark conjectures as conjectures; do not present a suspicion as a finding.

## LaTeX

- Name a source file after the definitions it contains, and rename it when they change. A figure label
  follows the file name.
- A macro is named after what it renders (\baseType for base-type, not \widen), and is renamed when the
  rendered name changes.

## References in conversation

- When referring to a figure, lemma, definition or section of the specification or paper, give its name
  and its number in the current PDF, so it can be found without a search. For example: the shape-typing
  figure, Figure 4.13 in the specification. Look the number up (a draft-mode `pdflatex` run's `.aux` has
  every label's number); don't guess it.
