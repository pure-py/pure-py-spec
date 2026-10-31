# HumanEval+ Checker-Feedback Repair

Pilot results on 163 of 164 HumanEval+ v0.1.10 problems, with PurePy v0.22.3 and
Python 3.12.13. HumanEval/32 is excluded because the pinned EvalPlus 0.3.1 grader
does not record a passing outcome for its reference solution. This pilot has not
yet applied the paper's input/output type eligibility screening.

## Results

Each cell gives passing problems out of 163. Python answers receive no feedback.

| Model | Stage | Python: tests | PurePy: checker | PurePy: tests | PurePy: checker + tests |
|---|---|---:|---:|---:|---:|
| Claude Opus 5.5 | Initial | 155/163 | 140/163 | 148/163 | 132/163 |
| Claude Opus 5.5 | Repaired | 155/163 | 161/163 | 148/163 | 146/163 |
| DeepSeek V4 Pro | Initial | 157/163 | 132/163 | 141/163 | 117/163 |
| DeepSeek V4 Pro | Repaired | 157/163 | 161/163 | 141/163 | 140/163 |

Checker acceptance and test correctness are separate measures. Repair increases
the number of answers passing both checks, although the total number passing the
tests stays unchanged. Each model gains one test-passing answer and loses one:

| Model | Tests fail to pass | Tests pass to fail |
|---|---|---|
| Claude Opus 5.5 | HumanEval/22 | HumanEval/151 |
| DeepSeek V4 Pro | HumanEval/148 | HumanEval/151 |

Both models still fail the checker on HumanEval/22 and HumanEval/137 after three
repair rounds. Every final answer has a completed generation and known checker
and test verdicts. Unresolved API errors, truncated responses and tool failures: 0.

## Protocol

Repair targets the 23 checker-rejected Claude answers and 31 checker-rejected
DeepSeek answers. The model receives its previous response and checker diagnostics,
never official-test outcomes. Repair stops at checker acceptance or three total
feedback rounds, even when the accepted answer fails tests. API retries repeat
the same messages within the same round; they do not add feedback rounds. Initial
requests allow 16,384 tokens; retries of truncated answers allow 65,536 tokens.

The model JSON files preserve the initial answer, every feedback round, raw
responses, extracted code, diagnostics, test outcomes and request history.
Original experiment paths and hashes remain in the provenance records; those
intermediate local files are not required to read these results or render the
figure. Verification retry records are stored in the optional `runs` field.

## Files

- [Claude records](claude-opus-5-5.json) and [per-problem report](claude-opus-5-5.md)
- [DeepSeek records](deepseek-v4-pro.json) and [per-problem report](deepseek-v4-pro.md)
- [Cross-model report](comparison.md)
- [Figure data](../humaneval-plus.json), [PNG](comparison.png) and [PDF](comparison.pdf)

From `evaluation/`, render the paper figure without calling a model:

```bash
uv run --locked python evaluation.py figure figures/humaneval-plus.json --output ../paper/fig/evaluation-generation.pdf
```

The figure includes Python, initial PurePy and repaired PurePy outcomes. Python
bars show only test outcomes in both panels.
