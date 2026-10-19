#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-.venv}"
uv sync --locked
version=0.40.6
runtime="$PWD/.cache/ollama/$version"
mkdir -p "$runtime"
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64|Darwin-x86_64)
    archive="$runtime/ollama-darwin.tgz"
    asset=ollama-darwin.tgz
    expected=b2b55434865a668decb494110d7fd970eed3ecc8837be2872f672ccbb95df974
    ;;
  Linux-x86_64)
    archive="$runtime/ollama-linux-amd64.tar.zst"
    asset=ollama-linux-amd64.tar.zst
    expected=c164ab8b1b28e2a247c29719b8e404c423c5b83ae64c3ab4e59d50c7ff7fc5e0
    ;;
  *) printf '%s\n' 'Unsupported smoke-test host' >&2; exit 1 ;;
esac
if [ ! -f "$archive" ]; then
  curl --fail --location --retry 2 --output "$archive" "https://github.com/ollama/ollama/releases/download/v$version/$asset"
fi
uv run --locked python -c 'import hashlib,pathlib,sys; assert hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() == sys.argv[2], "Ollama archive checksum mismatch"' "$archive" "$expected"
if [ ! -x "$runtime/ollama" ] && [ ! -x "$runtime/bin/ollama" ]; then
  tar -xf "$archive" -C "$runtime"
fi
ollama="$runtime/ollama"
if [ ! -x "$ollama" ]; then
  ollama="$runtime/bin/ollama"
fi
export OLLAMA_HOST=127.0.0.1:11435
export OLLAMA_MODELS="$PWD/.cache/ollama/models"
export OLLAMA_NO_CLOUD=1
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_CONTEXT_LENGTH=4096
export OLLAMA_KEEP_ALIVE=0
"$ollama" serve > "$runtime/serve.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true' EXIT
ready=0
for attempt in $(seq 1 90); do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    printf '%s\n' 'The smoke-test Ollama server could not start' >&2
    exit 1
  fi
  if curl --fail --silent http://127.0.0.1:11435/api/version >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  printf '%s\n' 'The smoke-test Ollama server did not become ready' >&2
  exit 1
fi
model="${SMOKE_MODEL:-qwen2.5-coder:0.5b}"
"$ollama" pull "$model"
env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u DEEPSEEK_API_KEY bash scripts/evaluate.sh \
  --model "$model" --base-url http://127.0.0.1:11435/v1 \
  --limit "${SMOKE_LIMIT:-2}" --max-tokens 1024 --repair-rounds 1 "$@"
