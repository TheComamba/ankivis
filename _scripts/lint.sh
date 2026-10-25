#!/usr/bin/env bash
# Lint and check formatting with ruff inside the virtual environment.
# Pass --fix to apply automatic fixes and reformat instead of only checking.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

fix=false
for arg in "$@"; do
    case "$arg" in
        --fix) fix=true ;;
        *)
            echo "Usage: $0 [--fix]" >&2
            exit 2
            ;;
    esac
done

ensure_venv
cd "$ROOT_DIR"

if [[ "$fix" == true ]]; then
    "$VENV_PYTHON" -m ruff check --fix .
    "$VENV_PYTHON" -m ruff format .
else
    "$VENV_PYTHON" -m ruff check .
    "$VENV_PYTHON" -m ruff format --check .
fi
