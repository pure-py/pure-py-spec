# Module and import formalisation: review checklist

Branch `module-import-cleanup`, two marked-up commits. Blue = added, grey = deleted; strip markup after
review. Figure, definition and section numbers refer to the marked-up PurePy-spec.pdf on this branch.

## Changes made

- [ ] **Dotted-name grammar (Fig. 2).** `q ::= x | q.x` (SimpleName/QualifiedName) replaces the flat
  `x1.x2.....xn+1`, which used centred dots against the house rule and was destructured inconsistently:
  cons at the head in rule import, dots at the tail everywhere else (names judgement, links, submodules).
  A one-line `root` metafunction (Fig. 24) supplies the head where rule import and eval-import
  (Figs. 10a, 17a) need it.

- [ ] **Dependency graph deleted (§3.2, Fig. 24, Fig. 11b).** The `imports` and `deps` metafunctions and
  the graph G_M restated, edge for edge, the load premises already present in the import rules, and had
  drifted: the `p != q` clause in the plain-import case of `deps` contradicted the §3.2 claim that the
  enclosing-ancestor exception "appears only in the from-import clause". The clause was vacuous for
  well-formed programs and mattered only for modules nobody imports, where treatment was inconsistent:
  in a never-imported module `u`, `import u.sub` slipped through while `from u import z` was rejected.
  All three are deleted along with the acyclicity premise of rule program (Fig. 11b).

- [ ] **Program well-formedness checks every module (Fig. 11b).** Rule program now requires a load
  derivation for each module in dom(M) rather than for `__main__` only. Import cycles are ill-formed
  because the inductively-read load judgement admits no finite derivation for them (§3.2 prose).
  Semantic change: modules that are never imported are now fully checked. This matches what a checker
  over a source tree does in practice, but changes the status of some programs.

- [ ] **loads-to replaced by links (Figs. 10b, 17b).** Three defects in loads-to: its result was bound
  but discarded in both from-import rules; its skip bound was the empty name for plain imports, which
  the grammar of q does not include, so `q <= epsilon` was ill-typed; and the enclosing rule never
  produced a value that was used. The new links judgement has two rules, no bound, and is used only by
  plain import to build the binding for the target's root, loading each proper prefix and linking each
  module into its parent.

- [ ] **from-import loads ancestors directly (Figs. 10a, 17a).** The rule now has an explicit premise
  loading each proper prefix of the target not enclosing the importing module. The premise is kept in
  the dynamic rule as well because ancestor loading can fail observably (a failing top-level assert),
  matching Python. The §3.2 prose "necessarily still in progress" was wrong (the ancestor may or may not
  be mid-load) and now reads "may still be loading".

- [ ] **Member import elementwise (Figs. 9, 16).** The judgement now imports one name at a time (two
  rules: member, submodule) and the from-import rules quantify over the imported names, matching the
  house forall-i idiom. The nil/cons plumbing and the override accumulation are gone. With the
  `imports` metafunction deleted, the judgement name no longer clashes with it.

- [ ] **Rule-name deduplication (Figs. 16, 17).** The dynamic figures reused the static rule names
  verbatim (imp-nil, imp-member, imp-submodule, loads-to-*). Dynamic rules now carry eval- prefixes
  (eval-imp-member, eval-imp-submodule, eval-links-simple, eval-links-qualified), consistent with the
  other evaluation figures.

- [ ] **Stray turnstile dropped (Fig. 17a).** The import-prefix evaluation judgement was written
  `|- iota-bar => rho` with a turnstile no other evaluation judgement has; now `iota-bar => rho`.

- [ ] **Predefined modules get load axioms (Figs. 11b, 18b; Definition 6; Fig. 5).** Rule module
  requires a body in M, and predefined modules such as builtins have none that PurePy can express, so
  `import math` had no derivation. New axiom rules predefined and eval-predefined give each predefined
  module its context and environment directly. Definition 6 (Predefined contexts and environments)
  generalises the old Definition 5 (Builtins context) and includes `__name__`; numbering shifts down by
  one once markup is stripped. §3.2 prose updated ("bodies are implementation-defined").

- [ ] **Values typed by context entries (Fig. 15).** env-cons placed no constraint on the entry paired
  with a value, so a well-formed environment could bind a module entry to a plain value and the load
  correspondence stated in §4 was vacuous on entry shapes. The value judgement is now `v : theta`:
  ordinary values at tt, module references and class entries at the corresponding entry.
  val-mod-loaded also drops its load premise, which was wrong for entries extended with submodule
  bindings by links or by repeated imports. A short prose introduction precedes Fig. 15.

- [ ] **Program result documented (§4, Fig. 18b).** `M => n` had an unexplained n that is always 0. A
  prose sentence now documents the result as the program's exit status; sys.exit remains unmodelled.

- [ ] **Ambient conventions stated (§3.2).** The prose now notes that the enclosing module name q is
  ambient in the rules that check or evaluate a single module's body, alongside the existing statement
  for M.

- [ ] **Caption and appendix fixes (Fig. 24, §A.3).** The figure mixing module and class metafunctions
  is recaptioned "Module and class metafunctions"; the §A.3 heading and blurb match.

## Flagged, not changed

- [ ] **Checker out of sync (src/check_program.py).** It carries the deps/imports/has_cycle machinery
  and checks only `__main__` recursively. Sync after review: cycle detection becomes an in-progress
  set, all discovered modules get checked, and any conformance tests relying on unused modules being
  unchecked need adjusting.

- [ ] **math has no members (Fig. 5).** Either give it members (pi, sqrt) or drop it from the table.

- [ ] **Reload claim relies on unmodelled output (§4).** "Loading has no observable effects" holds only
  because print is unmodelled: a top-level print would run once under Python's module cache but
  repeatedly under the cache-free reload semantics. Worth a footnote or an explicit scope remark.

- [ ] **Aliased imports unmentioned (§2.4).** `import a as b` is absent from the grammar but, unlike
  wildcard imports, not listed among the exclusions. Relative imports are already tracked as #126.

- [ ] **Module-reference arity overloading (Definition 1, Fig. 14).** Mod(q) stub versus Mod(q, Gamma)
  loaded are distinguished by arity alone. Kept; split the constructors if too subtle.
