#!/usr/bin/env bash
set -euo pipefail

# Download model weights from HuggingFace (bash wrapper).
#
# Usage:
#   ./scripts/download_model.sh [--out /path/to/model] [--repo ayanami-kitasan/code-pruner]

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" "$SCRIPT_DIR/download_model.py" "$@"

