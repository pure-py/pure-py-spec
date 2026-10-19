# Harbor Experiments

Harbor manages trials, configuration and logs. The existing `experiment.py`
and `livecodebench.py` still define the generation and evaluation protocol.
Python 3.12, the checker revision, prompts, first-response extraction, official
tests, and timeouts are unchanged. There is one sample and no repair or retry.

## Setup

```sh
uv venv --python 3.12 .cache/harbor-venv
uv pip sync --python .cache/harbor-venv/bin/python harbor/requirements.lock
```

## Import And Verify Existing Results

```sh
.cache/harbor-venv/bin/python harbor_runner.py migrate
.cache/harbor-venv/bin/python harbor_runner.py migrate --file livecodebench/Qwen2.5-Coder-32B-Instruct.json --verify --limit 5
.cache/harbor-venv/bin/python harbor_runner.py view
```

Import makes no model calls. By default it runs the original checker and tests
again; `--recorded-only` preserves historical verdicts without re-execution.
`--limit` writes a separate parity report
under `.cache/harbor/parity/`, not a replacement for the full exported result.
Pending and in-flight legacy requests are not launched or counted as failures.
Refresh an import with `migrate` after the original experiment advances. Existing
completed Harbor trials are reused when their frozen inputs have not changed.

An already-running legacy generator can be adopted without restarting it:

```sh
.cache/harbor-venv/bin/python harbor_runner.py follow --file livecodebench/deepseek-v4-pro.json --pid GENERATOR_PID
```

This only reads the producer's atomically saved answers, checks them and updates
the Harbor export. It never calls a model. If the producer exits, unsaved or
unattempted outputs remain unknown; they are not retried or counted as wrong.
The same output is locked against overlapping generators/imports.

Simple, model-named JSON exports are in `harbor/results/<benchmark>/`.
Detailed Harbor tasks, configuration and trial logs are in `.cache/harbor/`.
Original root-level and `livecodebench/` JSON files are never overwritten.
Imported API usage is historical metadata; replay incurs zero new model cost.
Unknown verdicts stay `null`, not `false`; Harbor pass metrics omit unknowns
and also report `checker_evaluated` and `tests_evaluated` counts.

## New One-Shot Experiments

```sh
.cache/harbor-venv/bin/python harbor_runner.py generate --benchmark livecodebench --provider deepseek --model deepseek-v4-pro --max-tokens 393216 --output harbor/results/new-run/deepseek-v4-pro.json
```

Keys are entered through hidden input, never stored in task/config/result files.
The adapter sends the same prompt to the native provider API through the existing
generator. It does not use a coding agent, tools, feedback or extra system prompts.
By default failed, interrupted, and truncated attempts are preserved and never resampled.
Use a new output path when changing prompt or sampling settings.

An explicitly requested completion round can target only incomplete outputs:

```sh
.cache/harbor-venv/bin/python harbor_runner.py generate --benchmark livecodebench --provider deepseek --model deepseek-v4-pro --max-tokens 393216 --difficulty hard --retry-incomplete --output harbor/results/livecodebench/deepseek-v4-pro.json
```

This preserves a full pre-round snapshot in `.cache/harbor/retries/`, records the
selected outputs in `manual_retry_rounds`, and leaves completed answers unchanged,
including completed answers that failed tests or the checker. Each selected output
gets at most one new request in this invocation; there are no automatic retries or
repair feedback. Updated scores include a completion round, not first-attempt
scores. `--difficulty hard` leaves all medium outputs untouched. Original root and
`livecodebench/` results are still read-only. Keys can also be supplied through
`ANTHROPIC_API_KEY` or `DEEPSEEK_API_KEY`; they are never saved in result files.

Qwen accepts an accessible vLLM OpenAI-compatible endpoint via `--provider openai
--api-url http://127.0.0.1:PORT/v1`. GPU inference must remain inside a Slurm
allocation; this adapter never allocates GPUs on a login node. On a Linux GPU
node, use `--generation-only`, then transfer the result and import it on the Mac
with `migrate --file PATH --verify`. Existing submitted GPU jobs are not changed.

`harbor/qwen.sbatch` starts vLLM in the unchanged shared inference environment
and runs the Harbor client in its separate environment. Set `MODEL_ID` and the
pinned `MODEL_REVISION` before submission. It uses the existing 32K LCB context,
BF16, seed 0, temperature 0 and one answer per condition. GPU results are saved
remotely in `harbor/results/livecodebench/`; transfer them to the Mac before
verification. Do not resubmit completed experiments merely to migrate them.

## Execution Boundary

The `EvaluationFiles` backend is a restricted file-only integration, not a
general-purpose container. Shell/tool execution is disabled. Only the trusted
custom verifier invokes the original macOS OS-sandbox workers on generated code.
Candidate workers do not receive model keys or access to project/user files.
Verification fails closed on non-macOS systems; generation-only mode does not
execute candidates. Docker, cloud sandboxes and automatic Slurm provisioning
are not installed or claimed by this migration. Harbor telemetry is disabled.
