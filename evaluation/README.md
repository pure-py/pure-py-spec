# PurePy Evaluation

The pipeline uses Python 3.12 and the PurePy v0.22.3 release wheel pinned by
hash in `pyproject.toml`; dependencies are fixed in `uv.lock`.

## Run

Install `uv`. On Linux, also install `bubblewrap`. Generated code runs in an OS
sandbox without provider credentials, network access or access to project files;
a run stops if no sandbox is available.

For a self-contained smoke test:

```bash
bash scripts/smoke.sh
```

This downloads a checksum-verified Ollama release and a small local model into
`.cache/`, starts a private local server, runs two HumanEval problems, writes
results and plots, and stops the server.

With an existing Ollama server:

```bash
bash scripts/evaluate.sh --model qwen2.5-coder:0.5b --limit 2 --repair-rounds 1
```

For a hosted model, set the provider's key in the environment, never in files or
arguments. OpenAI-compatible endpoints use `OPENAI_API_KEY` when set, which also
covers OpenRouter via `--base-url`; the native Anthropic and DeepSeek endpoints
use `ANTHROPIC_API_KEY` and `DEEPSEEK_API_KEY`.

```bash
bash scripts/evaluate.sh --provider deepseek --model deepseek-v4-pro --max-tokens 393216 --repair-rounds 3
bash scripts/evaluate.sh --provider anthropic --model claude-opus-5-5 --max-tokens 16384 --benchmark livecodebench --difficulty hard
```

Select `--benchmark humaneval` or `--benchmark livecodebench`, optionally with
`--difficulty medium` or `--difficulty hard`. `--repair-rounds 0`, the default,
is single-shot. With repair rounds, PurePy checker rejections are fed back to
the model, never test outcomes; repair stops at acceptance or the budget. Python
answers get no feedback. Every raw answer, extracted source, verdict, rejection
and token count is kept, and reports distinguish initial from repaired results.

## Output Format

Prompts and the extraction protocol are versioned as `tagged-code-v1`. A Python
answer must contain one `<python>...</python>` pair and a PurePy answer one
`<purepy>...</purepy>` pair, with source only inside the tags. Only extracted
source reaches the checker and the tests. A single complete pair with text
outside it is evaluated, and its format is recorded as noncompliant. Missing,
mismatched, nested or repeated tags, empty blocks and Markdown fences inside a
block are format failures. Each attempt keeps its `raw_response`, its extracted
`code` and its `output_format` status, and the reports show format compliance
next to the checker and test outcomes.

An answer is left unevaluated, with unknown checker and test verdicts, after an
API error, a truncated response or a format failure. Unknown verdicts never
count as failures or as checker rejections: reports show them separately and
leave a gap unknown when either condition has unevaluated answers.

## Data And Results

HumanEval problems and official tests are downloaded from a fixed upstream
revision and verified by SHA-256. `benchmarks/humaneval.json` holds the frozen
selection: 20 of 164 problems, sampled from the 29 whose interfaces are typed.

LiveCodeBench uses the 20 medium and 20 hard typed call-based problems frozen in
`livecodebench/tasks.json`, out of 207 and 102 eligible in release_v6. Missing
official tests are downloaded from the pinned dataset for the frozen task IDs and
must match the recorded interfaces, counts and hashes; preparation never resamples
tasks. The pinned official grader runs unchanged tests through the same external
`Solution` wrapper for both conditions.

Each run creates a new directory under `results/`. Its model-named JSON holds the
generated code, the per-round checker and test outcomes, the failure modes and
the initial and final totals; `.md`, `.pdf`, `.svg` and `.tex` files are written
beside it. Existing results are never overwritten. Code is also exported as
ordinary `.py` files, one per problem, condition and round:

```text
results/RUN/MODEL.json
results/RUN/solutions/MODEL/HumanEval-2/python.py
results/RUN/solutions/MODEL/HumanEval-2/purepy.py
results/RUN/solutions/MODEL/HumanEval-2/purepy.round-0.py
results/RUN/solutions/MODEL/HumanEval-2/purepy.round-1.py
```

`python.py` and `purepy.py` are the final answer; the round-numbered files keep
the initial answer and each repair. The JSON is the complete record.

Every checker rejection keeps its full diagnostic and a category: features
excluded by design, such as loops and mutation; features not yet supported, such
as function keyword arguments; and cases flagged for manual review. The checker
reports one diagnostic per run, so the next round's diagnostic may name a
different feature.

Runs with matched tasks and protocol can be compared across models:

```bash
uv run --locked python evaluation.py compare results/RUN1/MODEL1.json results/RUN2/MODEL2.json --output results/comparison.json
```

The comparison groups runs by benchmark, tasks, prompts, checker, repair budget
and platform, and reports the Python-minus-PurePy gaps for initial and final
answers. Positive means Python leads. Both reports also restrict the comparison
to the problems whose PurePy answer the checker accepted, giving the pass rates
of the PurePy and Python answers on those problems and their gap. Provider
settings and token budgets are listed but not controlled. `--model-size` records
a known parameter count.

The plot alone can be rendered from any result file:

```bash
uv run --locked python evaluation.py figure results/RUN/MODEL.json --output figure.pdf
```

The paper's evaluation section includes `paper/fig/evaluation-generation.pdf`,
which `make paper.pdf` in the repository root regenerates with this command from
`figures/humaneval-qwen2.5-coder-0.5b.json`. That file is the smoke run for now.

## CI And Harbor

The workflow `.github/workflows/evaluation.yml` runs in this directory on macOS
and Linux whenever evaluation code changes: unit tests, the smoke test, the
Harbor import and the compilation of the generated figure. It checks that the
pipeline works, not what the model answers: wrong code and checker rejections
are ordinary outcomes, while API errors, an unavailable checker or grader, and a
broken sandbox fail the job. Reports are uploaded even when the job fails.

Harbor records each run as trials, one per problem and condition, and shows them
in its viewer:

```bash
bash scripts/harbor-import.sh --file results/RUN/MODEL.json
```

See `harbor/README.md` for the viewer, the rewards and the Slurm job for GPU runs.

## Validate

```bash
uv run --locked python -m unittest discover -s tests -v
bash scripts/check-figure.sh results/RUN/MODEL.tex
```
