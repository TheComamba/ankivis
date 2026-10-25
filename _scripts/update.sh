#!/usr/bin/env bash
# Upgrade all dependencies to the newest versions allowed by pyproject.toml.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

create_venv
install_deps --upgrade --upgrade-strategy eager

echo "Installed packages:"
"$VENV_PYTHON" -m pip list --format=columns
