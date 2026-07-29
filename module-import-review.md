# Module and import formalisation: review checklist

Branch `module-import-cleanup`, two marked-up commits. Blue = added, grey = deleted; strip markup after
review. Figure, definition and section numbers refer to the marked-up PurePy-spec.pdf on this branch.

## Changes made

- [x] **Dotted-name grammar (Fig. 2).** Resolved: reverted after review. The flat sequence form and the
  head-cons pattern in rules import and eval-import stay; the proposed recursive grammar and root
  metafunction are dropped. Both destructurings are legitimate over the sequence form, and patterns read
  better than a metafunction.

- [x] **Dependency graph deleted (§3.2, Fig. 24, Fig. 11b).** The `imports` and `deps` metafunctions and
  the graph G_M restated, edge for edge, the load premises already present in the import rules, and had
  drifted: the `p != q` clause in the plain-import case of `deps` contradicted the §3.2 claim that the
  enclosing-ancestor exception "appears only in the from-import clause". The clause was vacuous for
  well-formed programs and mattered only for modules nobody imports, where treatment was inconsistent:
  in a never-imported module `u`, `import u.sub` slipped through while `from u import z` was rejected.
  All three are deleted along with the acyclicity premise of rule program (Fig. 11b). Residual
  behaviour change now that the `__main__` entry point is kept: the old graph ranged over all of dom(M),
  so a cycle among never-imported modules was rejected; such modules are now not examined at all
  (tests well-formed/unused_module, well-formed/unused_descendant_import).

- [x] **Program well-formedness (Fig. 11b).** Resolved: kept the `__main__` entry point after review;
  the recursive load premises reach every module the program can load, and a module that is never
  imported is not checked (§3.2 prose states this). The output context metavariable is now Gamma. The
  for-all-modules variant was tried and reverted. Import cycles remain ill-formed because the
  inductively-read load judgement admits no finite derivation for them.

- [x] **loads-to replaced by loads-as (Figs. 10b, 17b).** Three defects in loads-to: its result was bound
  but discarded in both from-import rules; its skip bound was the empty name for plain imports, which
  the grammar of q does not include, so `q <= epsilon` was ill-typed; and the enclosing rule never
  produced a value that was used. The new loads-as judgement has two rules, no bound, and is used only by
  plain import to build the binding for the target's root, loading each proper prefix and recording each
  module as a member of its parent.

- [x] **from-import loads ancestors directly (Figs. 10a, 17a).** The rule now has an explicit premise
  loading each proper prefix of the target not enclosing the importing module. The premise is kept in
  the dynamic rule as well because ancestor loading can fail observably (a failing top-level assert),
  matching Python. The §3.2 prose "necessarily still in progress" was wrong (the ancestor may or may not
  be mid-load) and now reads "may still be loading".

- [x] **Member import elementwise (Figs. 9, 16).** The judgement now imports one name at a time (two
  rules: member, submodule) and the from-import rules quantify over the imported names, matching the
  house forall-i idiom. The nil/cons plumbing and the override accumulation are gone. With the
  `imports` metafunction deleted, the judgement name no longer clashes with it.

- [x] **Rule-name deduplication (Figs. 16, 17).** The dynamic figures reused the static rule names
  verbatim (imp-nil, imp-member, imp-submodule, loads-to-*). Dynamic rules now carry eval- prefixes
  (eval-imp-member, eval-imp-submodule, eval-loads-as-simple, eval-loads-as-qualified), consistent with the
  other evaluation figures.

- [x] **Stray turnstile dropped (Fig. 17a).** The import-prefix evaluation judgement was written
  `|- iota-bar => rho` with a turnstile no other evaluation judgement has; now `iota-bar => rho`.

- [x] **Predefined modules get load axioms (Figs. 11b, 18b; Definition 6; Fig. 5).** Rule module
  requires a body in M, and predefined modules such as builtins have none that PurePy can express, so
  `import math` had no derivation. New axiom rules predefined and eval-predefined give each predefined
  module its context and environment directly. Definition 6 (Predefined contexts and environments)
  generalises the old Definition 5 (Builtins context) and includes `__name__`; numbering shifts down by
  one once markup is stripped. §3.2 prose updated ("bodies are implementation-defined").

- [x] **Values typed by context entries (Fig. 15).** env-cons placed no constraint on the entry paired
  with a value, so a well-formed environment could bind a module entry to a plain value and the load
  correspondence stated in §4 was vacuous on entry shapes. The value judgement is now `v : theta`:
  ordinary values at tt, module references and class entries at the corresponding entry.
  val-mod-loaded also drops its load premise, which was wrong for entries extended with submodule
  bindings by loads-as or by repeated imports. A short prose introduction precedes Fig. 15.

- [x] **Program result documented (§4, Fig. 18b).** `M => n` had an unexplained n that is always 0. A
  prose sentence now documents the result as the program's exit status; sys.exit remains unmodelled.

- [x] **Ambient conventions stated (§3.2).** The prose now notes that the enclosing module name q is
  ambient in the rules that check or evaluate a single module's body, alongside the existing statement
  for M.

- [x] **Caption and appendix fixes (Fig. 24, §A.3).** The figure mixing module and class metafunctions
  is recaptioned "Module and class metafunctions"; the §A.3 heading and blurb match.

## Flagged, not changed

- [x] **Checker out of sync (src/check_program.py).** Resolved: deps and has_cycle deleted; cycles now
  fail during recursive loading via an in-progress stack in check_module, mirroring the inductive
  reading; check_program checks `__main__`, whose load premises reach the import closure; loads_to
  renamed loads_as with the from-import ancestor loop made explicit; the discovery helper formerly called
  imports renamed import_targets. Tests well-formed/unused_module and
  well-formed/unused_descendant_import pin that unreached modules are not checked. Suite 240/240,
  mypy clean.

- [x] **math has no members (Fig. 5).** Either give it members (pi, sqrt) or drop it from the table.

- [x] **Reload claim relies on unmodelled output (§4).** "Loading has no observable effects" holds only
  because print is unmodelled: a top-level print would run once under Python's module cache but
  repeatedly under the cache-free reload semantics. Worth a footnote or an explicit scope remark.

- [x] **Aliased imports unmentioned (§2.4).** `import a as b` is absent from the grammar but, unlike
  wildcard imports, not listed among the exclusions. Relative imports are already tracked as #126.

- [x] **Module-reference arity overloading (Definition 1, Fig. 14).** Mod(q) stub versus Mod(q, Gamma)
  loaded are distinguished by arity alone. Kept; split the constructors if too subtle.
