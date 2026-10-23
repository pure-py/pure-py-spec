# Harbor

Harbor records every run of the evaluation pipeline as trials, one per problem
and condition, and shows them in its viewer. Each trial keeps the prompt, the
answer and its repair rounds, the checker and official-test verdicts, token usage,
and the rewards below. Harbor never calls a model and never re-runs code: the
pipeline is the only place where generation and evaluation happen.

## Import a run

```sh
bash scripts/harbor-import.sh --file results/RUN/MODEL.json
```

This creates the pinned Harbor environment in `.cache/harbor-venv` from
`harbor/requirements.lock` when it is missing, records the run under
`.cache/harbor/jobs/`, and writes `results/RUN/harbor/MODEL.json`: the result
file plus a `harbor` section naming the job. `--output` chooses another export
path; `--concurrency` sets the number of trials recorded at once. Importing the
same file again reuses its frozen task bundle. The CI workflow imports the smoke
run on both platforms.

## View

```sh
.cache/harbor-venv/bin/python harbor_runner.py view
```

`harbor_runner.py export JOB` rewrites the export of an existing job.

## Rewards

- `checker_evaluated`, `tests_evaluated`: 1 when the verdict is known
- `checker_passed`, `official_tests_passed`, `joint_passed`: present only when evaluated
- `attempts`, `rejections`, `rounds_to_acceptance`: the repair loop as recorded

## GPU runs with Slurm

`harbor/qwen.sbatch` runs a local model on a GPU node: it starts a vLLM
OpenAI-compatible server for the pinned snapshot, runs `scripts/evaluate.sh`
against it, and imports the result. Set `MODEL_ID` and `MODEL_REVISION`;
`BENCHMARK`, `DIFFICULTY`, `MAX_TOKENS`, `REPAIR_ROUNDS` and `MAX_MODEL_LEN`
are optional. The node needs `uv` and `bubblewrap`, since the pipeline runs the
official tests in a sandbox and stops if none is available. Results are written
to `results/slurm-JOBID/`.
