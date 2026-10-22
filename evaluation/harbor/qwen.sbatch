#!/bin/bash
#SBATCH --account=brics.b6bt
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=1
#SBATCH --cpus-per-task=16
#SBATCH --time=04:00:00
#SBATCH --chdir=/projects/b6bt/purepy_evaluation/lcb
#SBATCH --output=/projects/b6bt/purepy_evaluation/lcb/.cache/slurm-%j.log
set -euo pipefail
: "${MODEL_ID:?MODEL_ID is required}"
: "${MODEL_REVISION:?MODEL_REVISION is required}"
PROJECT_ROOT=/projects/b6bt/purepy_evaluation/lcb
INFERENCE_PYTHON=/projects/public/brics/tutorials/distributed_vllm/.venv/bin/python
MODEL_PATH=/projects/b6bt/hf_cache/hub/models--${MODEL_ID//\//--}/snapshots/${MODEL_REVISION}
PORT=${PORT:-8000}
export HF_HUB_OFFLINE=1
export HF_HOME=/projects/b6bt/hf_cache
export TOKENIZERS_PARALLELISM=false
export XDG_CACHE_HOME=${PROJECT_ROOT}/.cache
export VLLM_CACHE_ROOT=${PROJECT_ROOT}/.cache/vllm
export VLLM_CONFIG_ROOT=${PROJECT_ROOT}/.cache/vllm_config
export TRITON_CACHE_DIR=${PROJECT_ROOT}/.cache/triton
export CUDA_CACHE_PATH=${PROJECT_ROOT}/.cache/cuda
export TORCH_EXTENSIONS_DIR=${PROJECT_ROOT}/.cache/torch_extensions
export FLASHINFER_WORKSPACE_BASE=${PROJECT_ROOT}
mkdir -p "$VLLM_CACHE_ROOT" "$VLLM_CONFIG_ROOT" "$TRITON_CACHE_DIR" "$CUDA_CACHE_PATH" "$TORCH_EXTENSIONS_DIR"
test -f "$MODEL_PATH/model.safetensors.index.json" || { echo "model snapshot not found: $MODEL_PATH" >&2; exit 1; }
"$INFERENCE_PYTHON" -m vllm.entrypoints.openai.api_server --model "$MODEL_PATH" \
  --served-model-name "$MODEL_ID" --host 127.0.0.1 --port "$PORT" --dtype bfloat16 \
  --tensor-parallel-size 1 --max-model-len "${MAX_MODEL_LEN:-16384}" --max-num-seqs 2 \
  --gpu-memory-utilization 0.85 --generation-config vllm --seed 0 --enforce-eager \
  > "$PROJECT_ROOT/.cache/vllm-$SLURM_JOB_ID.log" 2>&1 &
server=$!
trap 'kill "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true' EXIT
for attempt in $(seq 1 450); do
  kill -0 "$server" 2>/dev/null || { echo "vLLM exited before startup; see .cache/vllm-$SLURM_JOB_ID.log" >&2; exit 1; }
  if curl --fail --silent "http://127.0.0.1:$PORT/v1/models" >/dev/null; then
    break
  fi
  sleep 2
done
curl --fail --silent "http://127.0.0.1:$PORT/v1/models" >/dev/null || { echo "vLLM startup timed out" >&2; exit 1; }
name=${MODEL_ID##*/}
output="results/slurm-$SLURM_JOB_ID/$name.json"
bash scripts/evaluate.sh --provider openai --base-url "http://127.0.0.1:$PORT/v1" --model "$MODEL_ID" \
  --benchmark "${BENCHMARK:-livecodebench}" ${DIFFICULTY:+--difficulty "$DIFFICULTY"} \
  --max-tokens "${MAX_TOKENS:-16384}" --repair-rounds "${REPAIR_ROUNDS:-3}" --output "$output"
bash scripts/harbor-import.sh --file "$output"
