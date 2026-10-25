# ankivis
Visualise learning progress for an Anki deck.

## Development setup

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Usage

```sh
.venv/bin/ankivis --help
.venv/bin/ankivis hello
```

## Tests and linting

```sh
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```
