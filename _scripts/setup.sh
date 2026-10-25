#!/usr/bin/env bash
# Create the virtual environment (if needed) and install ankivis with dev dependencies.
source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

create_venv
install_deps

echo "Setup complete. Run the program with _scripts/run.sh"
