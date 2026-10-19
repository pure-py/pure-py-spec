---
name: purepy-definition
description: Explain, generate, translate, or review code against the versioned PurePy functional subset of Python. Use when a task explicitly targets PurePy or asks for its language constraints or experiment prompt. Ordinary Python tasks do not require this skill.
metadata:
  specification-version: "0.19.0"
  checker-commit: "68486f84cf80cbc6a4a954dc5d3953951e37b9e3"
---

# PurePy Definition

Use PurePy core v0.19.0, pinned to the checker commit above, unless the user or
experiment configuration selects another version. PurePy is a statically checked
functional subset of Python. A well-formed program is valid Python; a run with a
defined PurePy result agrees with Python. Static acceptance, semantic validity
of a run, and task correctness are separate claims.

## Read the language contract

Read [references/definition.md](references/definition.md) before generating,
translating, reviewing, or assembling a PurePy prompt. It is the standalone
English language definition for this version, including the supported library
surface. Its syntax inventory is a practical summary, not the formal grammar.

Read [references/examples.md](references/examples.md) when an example would
clarify a restriction or when rewriting a Python idiom. Read
[references/sources.md](references/sources.md) when reconciling versions,
checking provenance, or discussing the research context.

## Apply the definition

- Preserve the requested function name, parameters, input domain, return
  behavior, and test interface. Add required annotations without silently
  changing the problem. If its interface needs a feature outside the selected
  subset, report that incompatibility instead of weakening the task or tests.
- Use typed functions, single assignment, explicit Boolean conditions,
  comprehensions, recursion, higher-order functions, and supported dataclasses.
  Python containers remain usable, but their mutation is excluded by the
  language discipline.
- Check the actual predefined signatures. Python familiarity does not imply
  availability: v0.19.0 requires `range(start, stop)`; `sum`, `sorted`, slicing,
  built-in value methods, and conversion calls such as `str(x)` are unavailable.
- Treat core PurePy, proposed extensions, and unchecked PurePy as distinct
  targets. Partial application and pattern clauses in function definitions are
  extensions, not this core. Unchecked PurePy needs its own grammar policy with
  optional annotations; the ordinary reference syntax checker requires function
  annotations and is not already that experimental checker.

## Validate when tools are available

Use the official checker at the selected revision. Follow the upstream README
for environment setup; Python 3.12 is the pinned runtime for this revision.
From a checkout of that revision:

```bash
uv run --locked python src/check_module.py path/to/solution.py
uv run --locked python src/check_program.py path/to/main.py
```

Use the module checker for a self-contained solution with predefined imports;
use the program checker for dependencies in user modules. Record the revision,
command, exit code, and diagnostic. At this revision, exit 0 means acceptance;
exit 1 covers parse/prohibited failures, exit 2 identifies features not yet
supported, exit 3 identifies module ill-formedness, and exit 4 identifies program
ill-formedness such as an import cycle. An unexpected exception is a tooling failure,
not evidence that the candidate is invalid.

Run the requested functional tests separately under CPython. Neither CPython
execution nor mypy acceptance proves PurePy membership. Static acceptance and
passing tests do not establish semantic validity for all possible inputs.
If tools are unavailable, label the result as reviewed but not checker-verified.

For ordinary development, repair diagnosed violations while preserving behavior.
For experimental generation, preserve the raw first response and first-round
verdict before any repair. Apply only the repair budget and feedback configured
by the experiment; this skill does not authorize additional model calls or a
benchmark run. The language definition can be supplied as fixed prompt text
without supplying these agent workflow instructions.

For this project's initial pilot, the user has specified one Python solution
and one PurePy solution per problem, using one model and 15-20 problems with
existing official tests. Record the first outputs as generated; no repair loop
or selection among multiple samples is configured. Keep official test outcomes,
PurePy checker acceptance, and exact checker violation diagnostics separate.

## Report appropriately

Follow the user's requested output format. For a review, identify the violated
rule and a concrete rewrite. For validated code, distinguish checker acceptance
from functional test results. For experiments, report the observed first-round
and repaired results separately. Cite the pinned source when explaining a
version-dependent boundary.
