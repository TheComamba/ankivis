#!/usr/bin/env bash
# Run ankivis inside the virtual environment. All arguments are passed through.
source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

ensure_venv
exec "$VENV_PYTHON" -m ankivis "$@"
