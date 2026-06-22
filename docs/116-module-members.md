# Static resolution of module members (#116)

Initial design — sketches and open questions only.

## Goal

Statically resolve cross-module references so that:
- `from M import x` checks `x` is a member of `M`.
- `M.y` (where `M` is a known module) checks `y` is a member of `M`.
- `from M import C` makes class `C` usable in constructor/pattern positions.

## Member kinds

A module's static signature `Σ_M` has three kinds of member, partitioned by namespace:

- **vars**: `assigns(𝓜(M))` — top-level bindings.
- **classes**: `dom(Λ_M)` — declared dataclasses.
- **sub-modules**: any `N` with `M` as a strict prefix in `dom(𝓜)`.

Namespaces partition cleanly because:
- vars and classes share the user-name space — disjointness required (see §Disjointness).
- sub-modules live in `dom(𝓜)`, a separate name space.

## Per-module context

A wf check on body of `M` now carries:

- `Γ` — variable context (as today).
- `Λ_M` — classes declared in `M` (as today; used by `class-extend`, `fields(M.C)`, `G_{Λ_M}` acyclicity).
- `Σ : LocalName → Σ_{M'}` — *import map*: names brought into scope by `import` / `from-import`, mapping each local name to the signature of the referenced module.

`Σ` is built incrementally as imports are processed.

## Resolution

- `import M'`: adds `top(M') → Σ_{M'}` to `Σ`, where `top(M')` is the head segment (e.g. `top(foo.bar) = foo`). Bare `foo.bar.x` resolves by chained attribute access through `Σ`.
- `from M' import x_1, …, x_n`: for each `x_i`:
  - if `x_i ∈ vars(Σ_{M'})`: add to `Γ`.
  - if `x_i ∈ classes(Σ_{M'})`: add to *imported classes* (separate from `Λ_M` — see below).
  - if `x_i ∈ subModules(Σ_{M'})`: add to `Σ` (with the referenced module's signature).
  - otherwise: ill-formed (`x_i` not a member of `M'`).

## Constructor / pattern resolution

For `C(...)` and `case C(...)`, the bare `C` is resolved against:

1. `Λ_M` (locally declared classes) — qualified name is `M.C`.
2. *Imported classes* — bare name maps to qualified declaring module (e.g. `Point → foo.Point`).

For `M'.C(...)` and `case M'.C(...)`, `M'` is resolved via `Σ`; `C` must be in `classes(Σ_{M'})`.

In both cases the resolved qualified name `M''.C` is used:
- arity check via `fields(M''.C)`.
- value tag in `Obj(M''.C, ρ)`.

## Inheritance restriction

`class-extend`'s base `B` must be in `Λ_M` (locally declared, as today). Imported classes are *not* eligible as bases — keeps inheritance graphs per-module.

## Disjointness

Within `M`:
- vars vs classes — ill-formed (same user-name space).
- vars vs sub-modules — debatable; sub-module names live in `dom(𝓜)`, separate name space. Provisionally allowed.

## Wf rule sketches

```
Γ ⊢_M m : Δ      (current judgement, threaded with Σ as additional ambient)

import-cons:
  M' = x_1. ... .x_{n+1}
  M' ∈ dom(𝓜)
  Γ ⊎ tt({x_1}) ⊢ m : Δ
  ────
  Γ ⊢ import M' · m : tt({x_1}) ⊎ Δ
  (also: extends Σ_M with x_1 → Σ_{M'})

from-import-cons:
  M' ∈ dom(𝓜)
  for each x_i: x_i ∈ vars(Σ_{M'}) ∪ classes(Σ_{M'}) ∪ subModules(Σ_{M'})
  partition into var_xs / class_xs / mod_xs
  Γ ⊎ tt(var_xs) ⊢ m : Δ
  ────
  Γ ⊢ from M' import x_1, ..., x_n · m : tt(var_xs) ⊎ Δ
  (also: extends imported-classes with class_xs; extends Σ_M with mod_xs)
```

(Sketches; precise threading TBD.)

## Open questions

- **Threading mechanism.** Currently `Λ_M` is ambient. `Σ` could be too, but it grows as imports are processed. Best to thread explicitly?
- **Module sentinel.** `Obj(⊥, ρ)` for modules — but attribute access on `M.y` is now wf-checked statically. Do we still need the `⊥` tag, or can we always use a qualified module name?
- **Predefined modules.** `typing.Any`, `dataclasses.dataclass` are imported via `from typing import Any` etc. Their signatures need to be in `dom(𝓜)` with the right vars exposed.
- **Wildcard imports** (out of scope; #106 excluded them).

## Implementation outline

1. Build `Σ_M` for each module during program-level traversal.
2. Add `Σ` field to `Context`.
3. Wf for `import` / `from-import`: validate members, populate `Σ` / `Γ` / imported-classes.
4. Wf for `Attribute(Name(M), x)` where `M` resolves to a module: validate `x ∈ Σ_M`.
5. Wf for `Call(Attribute(Name(M), C), ...)` and `case Attribute(Name(M), C)(...)`: as constructor / pat-class, with `M.C` resolved against `Σ`.
6. Existing constructor / pat-class wf: also look up bare `C` against imported classes if not in `Λ_M`.
