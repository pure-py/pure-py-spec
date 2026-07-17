---
name: spec-implementor
description: Discipline for keeping the checker (and other implementations) in one-to-one correspondence with the spec. Use whenever syncing implementation with spec, or reviewing either against the other.
---

# Spec implementor

Behavioral agreement is not the finish line. A sync is complete only when the
spec and the implementation are in one-to-one correspondence, checked in both
directions.

## Method

1. Build two inventories: spec constructs (judgements, rules, metafunctions,
   operators, technical terms, section headings) and implementation identifiers
   (functions, classes, constants, test taxonomy, docs).
2. Match by name. Every unmatched item, in either direction, gets exactly one
   of:
   - **rename** to the spec's name (the spec is the reference; `wraps` in the
     spec means a function called `wraps` in the checker);
   - **delete** as dead code or a displaced term (unused macros, stale labels,
     helpers with no callers);
   - **excuse** as a true implementation detail with no spec-level counterpart
     (e.g. memoizing module contexts, which is caching for idempotent
     checking). Record the excuse.
3. Watch for the same name meaning different things on the two sides (the spec
   distinguishes override from extend; the implementation must not use one
   name for both).
4. Diagnostics may refine the spec's single failure mode into specific reasons;
   that is a sanctioned refinement. Name each reason after the prohibition or
   premise it enforces.

## Order of work

Spec first, then tests, then implementation. When the spec changes, write or
adjust the failing test before touching the checker.

## Why behavioral auditing misses this

Walking the spec's rules and asking "does the implementation compute the right
verdict" filters out every divergence that changes no verdict: misnamed
functions, displaced terminology, dead helpers, stale taxonomy. Those are
visible only to the inventory comparison above, so run it even when all tests
pass.
