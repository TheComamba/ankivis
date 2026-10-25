#!/usr/bin/env bash
# Shared helpers for the scripts in _scripts/. Source this file, do not execute it.
#
# Provides:
#   ROOT_DIR      absolute path of the repository root
#   VENV_DIR      absolute path of the virtual environment
#   VENV_PYTHON   python interpreter inside the virtual environment
#   create_venv   create the virtual environment if it does not exist
#   install_deps  install ankivis (editable) with dev dependencies; extra pip args are passed on
#   ensure_venv   run the full setup if the virtual environment does not exist yet
#   MIN_PACKAGE_AGE                 minimum upload age (ISO 8601 duration) for update.sh, default P1D
#   pip_supports_upload_cutoff      succeed if the venv's pip understands --uploaded-prior-to

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
PYTHON="${PYTHON:-python3}"

# Supply-chain protection: only install releases that have been public for at least this long,
# so that freshly published (possibly compromised) releases have time to be detected and yanked.
MIN_PACKAGE_AGE="${MIN_PACKAGE_AGE:-P1D}"

pip_supports_upload_cutoff() {
    "$VENV_PYTHON" -m pip install --help 2>/dev/null | grep -q -- '--uploaded-prior-to'
}

create_venv() {
    if [[ ! -x "$VENV_PYTHON" ]]; then
        echo "Creating virtual environment in $VENV_DIR" >&2
        "$PYTHON" -m venv "$VENV_DIR"
    fi
}

install_deps() {
    "$VENV_PYTHON" -m pip install --quiet --upgrade pip
    "$VENV_PYTHON" -m pip install --quiet "$@" -e "$ROOT_DIR[dev]"
}

ensure_venv() {
    if [[ ! -x "$VENV_PYTHON" ]]; then
        create_venv
        install_deps
    fi
}
