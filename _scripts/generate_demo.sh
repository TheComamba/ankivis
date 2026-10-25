#!/usr/bin/env bash
# Generate the demo GIF shown in the README (demo.gif) from the Neo-Quenya deck.
#
# MAINTAINER ONLY: this script is intended to be run by the repository owner.
# It relies on the owner's personal Anki collection (a "Neo-Quenya" deck with
# review history up to 2024-12-03) and will most likely fail for anyone else.
# To render your own data, use `_scripts/run.sh export ...` instead.
#
# The daily frames are rendered into a temporary folder that is removed afterwards.
# Extra arguments (e.g. --profile NAME or --collection PATH) are passed on to the export command.
#
# Environment overrides:
#   DEMO_DECK    deck name or id      (default: Neo-Quenya)
#   DEMO_UNTIL   last rendered date   (default: 2024-12-03)
#   DEMO_FPS     frames per second    (default: 10)
#   DEMO_SIZE    frame size in pixels (default: 400)

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

DECK="${DEMO_DECK:-Neo-Quenya}"
UNTIL="${DEMO_UNTIL:-2024-12-03}"
FPS="${DEMO_FPS:-10}"
SIZE="${DEMO_SIZE:-400}"
GIF="$ROOT_DIR/demo.gif"

ensure_venv

FRAMES_DIR="$(mktemp -d)"
trap 'rm -rf "$FRAMES_DIR"' EXIT

"$VENV_PYTHON" -m ankivis export --deck "$DECK" --out "$FRAMES_DIR" --until "$UNTIL" --size "$SIZE" "$@"
"$VENV_PYTHON" -m ankivis video --in "$FRAMES_DIR" --out "$GIF" --until "$UNTIL" --fps "$FPS"
