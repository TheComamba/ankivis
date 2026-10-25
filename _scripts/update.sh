#!/usr/bin/env bash
# Upgrade all dependencies to the newest versions allowed by pyproject.toml.
#
# Only releases uploaded at least MIN_PACKAGE_AGE ago (default: P1D = one day) are considered,
# to reduce exposure to freshly published malicious releases (supply-chain attacks).

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

create_venv

if ! pip_supports_upload_cutoff; then
    # pip versions without --uploaded-prior-to silently ignore PIP_UPLOADED_PRIOR_TO,
    # so pip has to be upgraded once before the age restriction can be enforced.
    echo "pip in $VENV_DIR does not support --uploaded-prior-to; upgrading pip first" >&2
    "$VENV_PYTHON" -m pip install --quiet --upgrade pip
fi

if ! pip_supports_upload_cutoff; then
    echo "Error: pip does not support --uploaded-prior-to; refusing to update without age restriction" >&2
    exit 1
fi

# Set via the environment (not a CLI flag) so the restriction also applies to the pip
# self-upgrade in install_deps and to pip subprocesses building isolated build environments.
export PIP_UPLOADED_PRIOR_TO="$MIN_PACKAGE_AGE"
echo "Only considering packages uploaded at least $MIN_PACKAGE_AGE ago" >&2

install_deps --upgrade --upgrade-strategy eager

echo "Installed packages:"
"$VENV_PYTHON" -m pip list --format=columns
