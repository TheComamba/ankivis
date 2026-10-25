"""Command line interface for ankivis."""

import typer

app = typer.Typer(
    help="Visualise learning progress for an Anki deck.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Visualise learning progress for an Anki deck."""


@app.command()
def hello() -> None:
    """Print a greeting (sanity check)."""
    typer.echo("Hello, world")
