#!/usr/bin/env bash
# Run linting (via lint.sh) and the test suite inside the virtual environment.
# Extra arguments are passed to pytest, e.g. `_scripts/test.sh -k decks -v`.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

ensure_venv
"$ROOT_DIR/_scripts/lint.sh"
cd "$ROOT_DIR"
exec "$VENV_PYTHON" -m pytest "$@"
