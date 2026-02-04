#!/usr/bin/env bash
set -euo pipefail

# Pruned cat (bash wrapper).
#
# Usage:
#   ./scripts/pcat.sh --file path/to/big_file.py --query "focus question"
#
# This wrapper just forwards to pcat.py so it works on macOS/Linux/WSL.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" "$SCRIPT_DIR/pcat.py" "$@"

