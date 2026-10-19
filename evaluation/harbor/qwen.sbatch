#!/bin/bash
#SBATCH --account=brics.b6bt
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=1
#SBATCH --cpus-per-task=16
#SBATCH --time=04:00:00
#SBATCH --chdir=/projects/b6bt/purepy_evaluation/lcb
#SBATCH --output=/projects/b6bt/purepy_evaluation/lcb/.cache/harbor-gpu-%j.log
set -euo pipefail
PROJECT_ROOT=/projects/b6bt/purepy_evaluation/lcb
INFERENCE_PYTHON=/projects/public/brics/tutorials/distributed_vllm/.venv/bin/python
: "${MODEL_ID:?MODEL_ID is required}"
: "${MODEL_REVISION:?MODEL_REVISION is required}"
HUB_FOLDER=models--${MODEL_ID//\//--}
MODEL_PATH=/projects/b6bt/hf_cache/hub/${HUB_FOLDER}/snapshots/${MODEL_REVISION}
export HF_HUB_OFFLINE=1
export HF_HOME=/projects/b6bt/hf_cache
export TOKENIZERS_PARALLELISM=false
export VLLM_CACHE_ROOT=${PROJECT_ROOT}/.cache/vllm
export TRITON_CACHE_DIR=${PROJECT_ROOT}/.cache/triton
export FLASHINFER_WORKSPACE_BASE=${PROJECT_ROOT}
export XDG_CACHE_HOME=${PROJECT_ROOT}/.cache
export CUDA_CACHE_PATH=${PROJECT_ROOT}/.cache/cuda
export TORCH_EXTENSIONS_DIR=${PROJECT_ROOT}/.cache/torch_extensions
export VLLM_CONFIG_ROOT=${PROJECT_ROOT}/.cache/vllm_config
mkdir -p "$VLLM_CACHE_ROOT" "$TRITON_CACHE_DIR" "$CUDA_CACHE_PATH" "$TORCH_EXTENSIONS_DIR" "$VLLM_CONFIG_ROOT"
exec srun "$PROJECT_ROOT/.cache/harbor-venv/bin/python" "$PROJECT_ROOT/harbor_runner.py" gpu \
    --benchmark livecodebench --model "$MODEL_ID" --model-path "$MODEL_PATH" \
    --model-revision "$MODEL_REVISION" --inference-python "$INFERENCE_PYTHON" --max-tokens 16384
