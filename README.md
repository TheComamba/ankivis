# ankivis
Visualise learning progress for an Anki deck.

## Scripts

All scripts can be called from any directory and use the virtual environment in `.venv/`.

| Script | Purpose |
|---|---|
| `_scripts/setup.sh` | Create `.venv` and install ankivis with dev dependencies |
| `_scripts/run.sh [ARGS]` | Run ankivis, e.g. `_scripts/run.sh --help` |
| `_scripts/lint.sh [--fix]` | Run ruff (lint + format check); `--fix` applies fixes and reformats |
| `_scripts/test.sh [PYTEST ARGS]` | Run `lint.sh`, then pytest |
| `_scripts/update.sh` | Upgrade all dependencies to the newest allowed versions |

Shared logic lives in `_scripts/lib/shared.sh`.

## Usage

```sh
_scripts/setup.sh
_scripts/run.sh hello
```

### Decks

The collection is opened read-only. If Anki is running and the database is locked, ankivis
reads from a temporary copy instead. By default it reads
`~/.local/share/Anki2/<profile>/collection.anki2` (profile `User 1`).

```sh
_scripts/run.sh decks                                   # numbered list of all decks
_scripts/run.sh decks --profile "Alice"                 # another Anki profile
_scripts/run.sh decks --collection path/to/collection.anki2
_scripts/run.sh decks --pick                            # pick interactively (number, name or id)
_scripts/run.sh decks --deck "Spanish::Verbs"           # select by name or id
_scripts/run.sh decks --deck Spanish --no-subdecks      # exclude subdecks
```
