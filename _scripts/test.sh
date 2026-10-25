#!/usr/bin/env bash
# Run linting and the test suite inside the virtual environment.
# Extra arguments are passed to pytest, e.g. `_scripts/test.sh -k decks -v`.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

ensure_venv
cd "$ROOT_DIR"
"$VENV_PYTHON" -m ruff check .
"$VENV_PYTHON" -m ruff format --check .
exec "$VENV_PYTHON" -m pytest "$@"
