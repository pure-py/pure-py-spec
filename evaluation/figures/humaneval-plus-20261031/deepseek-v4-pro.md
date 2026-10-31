# deepseek-v4-pro

Benchmark: HumanEval+
Problems: 163 of 164
Typed interfaces: 29 of 163
Scope: The HumanEval selection, with the extra EvalPlus tests; --all-problems runs all 164.
PurePy checker: 0.22.3
Maximum checker-feedback repair rounds: 3

Output format: tagged-code-v1

| Condition | Stage | Checker Accepts | Official Tests Pass | Both Pass | Checker Unknown | Tests Unknown |
|---|---|---:|---:|---:|---:|---:|
| python | initial | 2/163 | 157/163 | 2/163 | 0 | 0 |
| python | final | 2/163 | 157/163 | 2/163 | 0 | 0 |
| purepy | initial | 132/163 | 141/163 | 117/163 | 0 | 0 |
| purepy | final | 161/163 | 141/163 | 140/163 | 0 | 0 |

Initial and repaired results are reported separately; Python answers receive no feedback.
Unknown verdicts come from exhausted API or tool retries, truncated responses and format failures; they count neither as passes nor as rejections.

## Retries

Generation retries repeat the same messages without checker or test feedback. Tool retries evaluate the same source. Neither counts as a checker-feedback repair round.

| Condition | Generation Retries | Verification Retries |
|---|---:|---:|
| python | 3 | 0 |
| purepy | 101 | 2 |

## Output Format

| Condition | Stage | Compliant | Noncompliant | Unknown | Details |
|---|---|---:|---:|---:|---|
| python | initial | 163 | 0 | 0 | {"valid": 163} |
| python | final | 163 | 0 | 0 | {"valid": 163} |
| purepy | initial | 163 | 0 | 0 | {"valid": 163} |
| purepy | final | 163 | 0 | 0 | {"valid": 163} |

## Checker Rejections

python: {"excluded_by_design": 151, "library_or_name_resolution": 7, "static_type_or_wellformedness": 3}
purepy: {"library_or_name_resolution": 6, "static_type_or_wellformedness": 10, "syntax_restriction_review": 24}

## RQ3

Positive values mean Python leads; negative values mean PurePy leads.

initial: Python minus PurePy official-test pass rate = 9.8 percentage points; Python tests minus valid PurePy = 24.5 percentage points.
final: Python minus PurePy official-test pass rate = 9.8 percentage points; Python tests minus valid PurePy = 10.4 percentage points.

On the problems whose PurePy answer the checker accepted, both conditions' official-test pass rates measure the restrictions' effect on correctness.

initial: 132 accepted problems; PurePy passes 117/132 (88.6%), Python passes 130/132 (98.5%); Python minus PurePy = 9.8 percentage points.
final: 161 accepted problems; PurePy passes 140/161 (87.0%), Python passes 155/161 (96.3%); Python minus PurePy = 9.3 percentage points.

## Per-Solution Outcomes

| Task | Condition | Generation | Initial Format | Final Format | Initial Checker | Final Checker | Initial Tests | Final Tests | Repairs To Acceptance |
|---|---|---|---|---|---|---|---|---|---|
| HumanEval/0 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/0 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/1 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/1 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/2 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/2 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/3 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/3 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/4 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/4 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/5 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/5 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/6 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/6 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/7 | python | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/7 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/8 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/8 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/9 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/9 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/10 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/10 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/11 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/11 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/12 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/12 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/13 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/13 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/14 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/14 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/15 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/15 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/16 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/16 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/17 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/17 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/18 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/18 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/19 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/19 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/20 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/20 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/21 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/21 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/22 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/22 | purepy | complete | valid | valid | False | False | False | False | None |
| HumanEval/23 | python | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/23 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/24 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/24 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/25 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/25 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/26 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/26 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/27 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/27 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/28 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/28 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/29 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/29 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/30 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/30 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/31 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/31 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/33 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/33 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/34 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/34 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/35 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/35 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/36 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/36 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/37 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/37 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/38 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/38 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/39 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/39 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/40 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/40 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/41 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/41 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/42 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/42 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/43 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/43 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/44 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/44 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/45 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/45 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/46 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/46 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/47 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/47 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/48 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/48 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/49 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/49 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/50 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/50 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/51 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/51 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/52 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/52 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/53 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/53 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/54 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/54 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/55 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/55 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/56 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/56 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/57 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/57 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/58 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/58 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/59 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/59 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/60 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/60 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/61 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/61 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/62 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/62 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/63 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/63 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/64 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/64 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/65 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/65 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/66 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/66 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/67 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/67 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/68 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/68 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/69 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/69 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/70 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/70 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/71 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/71 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/72 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/72 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/73 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/73 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/74 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/74 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/75 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/75 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/76 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/76 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/77 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/77 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/78 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/78 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/79 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/79 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/80 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/80 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/81 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/81 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/82 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/82 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/83 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/83 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/84 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/84 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/85 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/85 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/86 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/86 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/87 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/87 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/88 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/88 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/89 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/89 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/90 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/90 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/91 | python | complete | valid | valid | False | False | False | False | None |
| HumanEval/91 | purepy | complete | valid | valid | False | True | False | False | 1 |
| HumanEval/92 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/92 | purepy | complete | valid | valid | False | True | False | False | 1 |
| HumanEval/93 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/93 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/94 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/94 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/95 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/95 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/96 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/96 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/97 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/97 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/98 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/98 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/99 | python | complete | valid | valid | False | False | False | False | None |
| HumanEval/99 | purepy | complete | valid | valid | False | True | False | False | 1 |
| HumanEval/100 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/100 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/101 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/101 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/102 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/102 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/103 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/103 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/104 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/104 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/105 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/105 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/106 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/106 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/107 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/107 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/108 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/108 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/109 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/109 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/110 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/110 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/111 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/111 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/112 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/112 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/113 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/113 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/114 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/114 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/115 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/115 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/116 | python | complete | valid | valid | False | False | False | False | None |
| HumanEval/116 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/117 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/117 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/118 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/118 | purepy | complete | valid | valid | False | True | True | True | 2 |
| HumanEval/119 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/119 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/120 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/120 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/121 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/121 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/122 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/122 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/123 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/123 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/124 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/124 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/125 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/125 | purepy | complete | valid | valid | False | True | False | False | 1 |
| HumanEval/126 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/126 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/127 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/127 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/128 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/128 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/129 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/129 | purepy | complete | valid | valid | False | True | True | True | 2 |
| HumanEval/130 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/130 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/131 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/131 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/132 | python | complete | valid | valid | False | False | False | False | None |
| HumanEval/132 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/133 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/133 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/134 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/134 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/135 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/135 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/136 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/136 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/137 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/137 | purepy | complete | valid | valid | False | False | True | True | None |
| HumanEval/138 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/138 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/139 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/139 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/140 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/140 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/141 | python | complete | valid | valid | False | False | False | False | None |
| HumanEval/141 | purepy | complete | valid | valid | False | True | False | False | 1 |
| HumanEval/142 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/142 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/143 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/143 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/144 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/144 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/145 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/145 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/146 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/146 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/147 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/147 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/148 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/148 | purepy | complete | valid | valid | False | True | False | True | 2 |
| HumanEval/149 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/149 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/150 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/150 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/151 | python | complete | valid | valid | False | False | False | False | None |
| HumanEval/151 | purepy | complete | valid | valid | False | True | True | False | 1 |
| HumanEval/152 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/152 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/153 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/153 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/154 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/154 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/155 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/155 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/156 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/156 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/157 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/157 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/158 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/158 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/159 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/159 | purepy | complete | valid | valid | True | True | True | True | 0 |
| HumanEval/160 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/160 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/161 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/161 | purepy | complete | valid | valid | True | True | False | False | 0 |
| HumanEval/162 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/162 | purepy | complete | valid | valid | False | True | True | True | 1 |
| HumanEval/163 | python | complete | valid | valid | False | False | True | True | None |
| HumanEval/163 | purepy | complete | valid | valid | True | True | False | False | 0 |

## Rejection Details

The checker reports one diagnostic per run, so the next round's diagnostic may name a different feature.

| Task | Condition | Round | Category | Restriction | Next Round Clears Feature | Diagnostic |
|---|---|---:|---|---|---|---|
| HumanEval/0 | python | 0 | excluded_by_design | loop | None | solution.py:6:4: for loops prohibited |
| HumanEval/1 | python | 0 | excluded_by_design | loop | None | solution.py:6:4: for loops prohibited |
| HumanEval/2 | python | 0 | library_or_name_resolution | unavailable or undefined name | None | solution.py:1:0: unknown module 'math' |
| HumanEval/3 | python | 0 | excluded_by_design | loop | None | solution.py:3:4: for loops prohibited |
| HumanEval/3 | purepy | 0 | static_type_or_wellformedness | manual review required | True | solution.py:22:12: 'min_prefix' is already declared |
| HumanEval/4 | python | 0 | excluded_by_design | generator_expression | None | solution.py:5:14: generator expressions prohibited |
| HumanEval/5 | python | 0 | excluded_by_design | loop | None | solution.py:5:4: for loops prohibited |
| HumanEval/6 | python | 0 | excluded_by_design | loop | None | solution.py:6:4: for loops prohibited |
| HumanEval/8 | python | 0 | excluded_by_design | loop | None | solution.py:4:4: for loops prohibited |
| HumanEval/9 | python | 0 | excluded_by_design | loop | None | solution.py:6:4: for loops prohibited |
| HumanEval/10 | python | 0 | excluded_by_design | slicing | None | solution.py:2:28: slicing prohibited |
| HumanEval/11 | python | 0 | excluded_by_design | generator_expression | None | solution.py:5:18: generator expressions prohibited |
| HumanEval/12 | python | 0 | library_or_name_resolution | unavailable or undefined name | None | solution.py:1:0: module 'typing' has no member 'List' |
| HumanEval/12 | purepy | 0 | library_or_name_resolution | unavailable or undefined name | True | solution.py:1:0: module 'typing' has no member 'Optional' |
| HumanEval/13 | python | 0 | library_or_name_resolution | unavailable or undefined name | None | solution.py:1:0: unknown module 'math' |
| HumanEval/14 | python | 0 | excluded_by_design | slicing | None | solution.py:2:19: slicing prohibited |
| HumanEval/15 | python | 0 | excluded_by_design | generator_expression | None | solution.py:8:19: generator expressions prohibited |
| HumanEval/16 | python | 0 | library_or_name_resolution | unavailable or undefined name | None | solution.py:8:15: 'set' is not defined |
| HumanEval/17 | python | 0 | excluded_by_design | variable_declaration | None | solution.py:2:4: 'note_to_beats' is assigned but never declared |
| HumanEval/18 | python | 0 | excluded_by_design | generator_expression | None | solution.py:2:14: generator expressions prohibited |
| HumanEval/19 | python | 0 | library_or_name_resolution | unavailable or undefined name | None | solution.py:1:0: module 'typing' has no member 'List' |
| HumanEval/20 | python | 0 | excluded_by_design | loop | None | solution.py:6:4: for loops prohibited |
| HumanEval/21 | python | 0 | excluded_by_design | variable_declaration | None | solution.py:2:4: 'min_val' is assigned but never declared |
| HumanEval/22 | python | 0 | library_or_name_resolution | unavailable or undefined name | None | solution.py:1:0: module 'typing' has no member 'Any' |
| HumanEval/22 | purepy | 0 | library_or_name_resolution | unavailable or undefined name | False | solution.py:1:0: module 'typing' has no member 'Any' |
| HumanEval/22 | purepy | 1 | library_or_name_resolution | unavailable or undefined name | None | solution.py:2:33: 'isinstance' is not defined |
| HumanEval/22 | purepy | 2 | static_type_or_wellformedness | manual review required | False | solution.py:2:33: values of type object have no attributes |
| HumanEval/22 | purepy | 3 | static_type_or_wellformedness | manual review required | None | solution.py:3:13: 'int' is not a declared class |
| HumanEval/24 | python | 0 | excluded_by_design | loop | None | solution.py:9:4: while loops prohibited |
| HumanEval/25 | python | 0 | excluded_by_design | loop | None | solution.py:4:4: while loops prohibited |
| HumanEval/26 | python | 0 | library_or_name_resolution | unavailable or undefined name | None | solution.py:1:0: module 'typing' has no member 'List' |
| HumanEval/27 | python | 0 | static_type_or_wellformedness | manual review required | None | solution.py:2:11: values of type str have no attributes |
| HumanEval/28 | python | 0 | static_type_or_wellformedness | manual review required | None | solution.py:2:11: values of type Literal[''] have no attributes |
| HumanEval/29 | python | 0 | static_type_or_wellformedness | manual review required | None | solution.py:3:34: values of type str have no attributes |
| HumanEval/30 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/31 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/33 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/34 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/35 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/36 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/37 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/38 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/39 | python | 0 | excluded_by_design | loop | None | solution.py:6:4: for loops prohibited |
| HumanEval/40 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/41 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/42 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/43 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/44 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/45 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/46 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/47 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/48 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/49 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/50 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/51 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/51 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:2:11: chained boolean operator prohibited |
| HumanEval/52 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/53 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/54 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/55 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/56 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/57 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/57 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:19:16: chained boolean operator prohibited |
| HumanEval/58 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/59 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/60 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/61 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/62 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated return type prohibited |
| HumanEval/63 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/64 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/64 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:2:12: chained boolean operator prohibited |
| HumanEval/65 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/66 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/67 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/67 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:2:11: chained boolean operator prohibited |
| HumanEval/68 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/69 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/70 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/71 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/71 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:2:18: chained boolean operator prohibited |
| HumanEval/72 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/73 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/74 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/75 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/76 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/77 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/78 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/78 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:2:35: chained boolean operator prohibited |
| HumanEval/79 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/80 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/80 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:12:11: chained boolean operator prohibited |
| HumanEval/81 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/82 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/83 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/83 | purepy | 0 | static_type_or_wellformedness | manual review required | True | solution.py:4:11: expected type int, given float |
| HumanEval/84 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/85 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/86 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/87 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/88 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/89 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/90 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/91 | python | 0 | excluded_by_design | type_annotation | None | solution.py:4:0: unannotated parameter prohibited |
| HumanEval/91 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:11:11: chained boolean operator prohibited |
| HumanEval/92 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/92 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:5:11: chained boolean operator prohibited |
| HumanEval/93 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/94 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/95 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/95 | purepy | 0 | library_or_name_resolution | unavailable or undefined name | True | solution.py:14:47: 'isinstance' is not defined |
| HumanEval/96 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/97 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/98 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/98 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:2:11: chained boolean operator prohibited |
| HumanEval/99 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/99 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:48:27: chained boolean operator prohibited |
| HumanEval/100 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/101 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/102 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/103 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/104 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/105 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/106 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/107 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/108 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/109 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/110 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/111 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/112 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/113 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/113 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:2:11: chained boolean operator prohibited |
| HumanEval/114 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/115 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/116 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/117 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/118 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/118 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | False | solution.py:2:11: chained boolean operator prohibited |
| HumanEval/118 | purepy | 1 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:30:7: chained boolean operator prohibited |
| HumanEval/119 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/120 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/121 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/122 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/123 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/124 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/124 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:3:8: chained boolean operator prohibited |
| HumanEval/125 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/125 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:6:11: chained boolean operator prohibited |
| HumanEval/126 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/126 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:16:23: chained boolean operator prohibited |
| HumanEval/127 | python | 0 | excluded_by_design | loop | None | solution.py:9:4: while loops prohibited |
| HumanEval/128 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/129 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/129 | purepy | 0 | syntax_restriction_review | destructuring in comprehensions prohibited | None | solution.py: destructuring in comprehensions prohibited |
| HumanEval/129 | purepy | 1 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:20:37: chained boolean operator prohibited |
| HumanEval/130 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/131 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/132 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/133 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/134 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/135 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/136 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/137 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/137 | purepy | 0 | library_or_name_resolution | unavailable or undefined name | None | solution.py:63:7: 'isinstance' is not defined |
| HumanEval/137 | purepy | 1 | static_type_or_wellformedness | manual review required | False | solution.py:64:13: 'str' is not a declared class |
| HumanEval/137 | purepy | 2 | static_type_or_wellformedness | manual review required | None | solution.py:63:22: values of type int have no attributes |
| HumanEval/137 | purepy | 3 | library_or_name_resolution | unavailable or undefined name | None | solution.py:1:0: module 'builtins' has no member 'isinstance' |
| HumanEval/138 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/139 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/139 | purepy | 0 | static_type_or_wellformedness | manual review required | True | solution.py:10:24: expected type int, given float |
| HumanEval/140 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/141 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/141 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:8:11: chained boolean operator prohibited |
| HumanEval/142 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/143 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/144 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/145 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/146 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/146 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:10:35: chained boolean operator prohibited |
| HumanEval/147 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/148 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/148 | purepy | 0 | syntax_restriction_review | annotation that is not a type expression prohibited | None | solution.py:8:59: annotation that is not a type expression prohibited |
| HumanEval/148 | purepy | 1 | static_type_or_wellformedness | manual review required | True | solution.py:11:11: no overload of '+' at operand types tuple[str] and object |
| HumanEval/149 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/150 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/151 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/151 | purepy | 0 | static_type_or_wellformedness | manual review required | True | solution.py:3:13: 'int' is not a declared class |
| HumanEval/152 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/153 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/154 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/155 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/156 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/157 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/157 | purepy | 0 | syntax_restriction_review | chained boolean operator prohibited | True | solution.py:2:27: chained boolean operator prohibited |
| HumanEval/158 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/159 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/160 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/160 | purepy | 0 | static_type_or_wellformedness | manual review required | True | solution.py:19:34: expected type int, given float |
| HumanEval/161 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
| HumanEval/162 | python | 0 | excluded_by_design | type_annotation | None | solution.py:3:0: unannotated parameter prohibited |
| HumanEval/162 | purepy | 0 | syntax_restriction_review | binary operator '<<' prohibited | True | solution.py:73:17: binary operator '<<' prohibited |
| HumanEval/163 | python | 0 | excluded_by_design | type_annotation | None | solution.py:1:0: unannotated parameter prohibited |
