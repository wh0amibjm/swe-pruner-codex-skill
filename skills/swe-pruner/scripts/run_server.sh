#!/usr/bin/env bash
set -euo pipefail

# Start SWE-Pruner FastAPI server (bash wrapper).
#
# Environment:
#   SWEPRUNER_MODEL_PATH  Optional model directory
#
# Usage:
#   ./scripts/run_server.sh [--host 127.0.0.1] [--port 8000] [--model-path /path/to/model]

PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="127.0.0.1"
PORT="8000"
MODEL_PATH="${SWEPRUNER_MODEL_PATH:-$HOME/.cache/swe-pruner/model}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host|-h)
      HOST="${2:-}"; shift 2;;
    --port|-p)
      PORT="${2:-}"; shift 2;;
    --model-path|-m)
      MODEL_PATH="${2:-}"; shift 2;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2;;
  esac
done

if [[ ! -f "$MODEL_PATH/model.safetensors" ]]; then
  echo "Missing model weights: $MODEL_PATH/model.safetensors" >&2
  echo "Download first:" >&2
  echo "  python3 ./scripts/download_model.py --out \"$MODEL_PATH\"" >&2
  exit 1
fi

export SWEPRUNER_MODEL_PATH="$MODEL_PATH"

if command -v swe-pruner >/dev/null 2>&1; then
  exec swe-pruner serve --host "$HOST" --port "$PORT" --model-path "$MODEL_PATH"
fi

exec "$PYTHON_BIN" -m swe_pruner.online_serving serve --host "$HOST" --port "$PORT" --model-path "$MODEL_PATH"
