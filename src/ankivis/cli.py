"""Command line interface for ankivis."""

from pathlib import Path
from typing import Annotated

import typer

from ankivis.db import DEFAULT_PROFILE, default_collection_path, open_collection
from ankivis.decks import Deck, deck_ids, find_deck, format_deck_list, list_decks, pick_deck

app = typer.Typer(
    help="Visualise learning progress for an Anki deck.",
    no_args_is_help=True,
)

CollectionOption = Annotated[
    Path | None,
    typer.Option(
        "--collection",
        "-c",
        help="Path to collection.anki2 (overrides --profile).",
        dir_okay=False,
    ),
]
ProfileOption = Annotated[
    str,
    typer.Option("--profile", "-p", help="Anki profile name (~/.local/share/Anki2/<profile>)."),
]


@app.callback()
def main() -> None:
    """Visualise learning progress for an Anki deck."""


@app.command()
def hello() -> None:
    """Print a greeting (sanity check)."""
    typer.echo("Hello, world")


def _load_decks(collection: Path | None, profile: str) -> list[Deck]:
    path = collection if collection is not None else default_collection_path(profile)
    try:
        conn = open_collection(path)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    try:
        return list_decks(conn)
    finally:
        conn.close()


def select_deck(decks: list[Deck], deck: str | None) -> Deck:
    """Resolve ``--deck NAME|ID`` or prompt interactively when *deck* is ``None``."""
    if deck is None:
        try:
            return pick_deck(
                decks, prompt=lambda text: typer.prompt(text, type=str), echo=typer.echo
            )
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1) from exc
    found = find_deck(decks, deck)
    if found is None:
        typer.echo(f"Error: deck not found: {deck}", err=True)
        raise typer.Exit(1)
    return found


@app.command("decks")
def decks_command(
    collection: CollectionOption = None,
    profile: ProfileOption = DEFAULT_PROFILE,
    pick: Annotated[
        bool, typer.Option("--pick", help="Interactively pick a deck from the list.")
    ] = False,
    deck: Annotated[
        str | None, typer.Option("--deck", "-d", help="Select a deck by name or id.")
    ] = None,
    subdecks: Annotated[
        bool, typer.Option("--subdecks/--no-subdecks", help="Include subdecks of the selection.")
    ] = True,
) -> None:
    """List decks as a numbered list, or select one with --pick / --deck."""
    all_decks = _load_decks(collection, profile)
    if not pick and deck is None:
        for line in format_deck_list(all_decks):
            typer.echo(line)
        return
    selected = select_deck(all_decks, deck)
    ids = deck_ids(all_decks, selected, include_subdecks=subdecks)
    typer.echo(f"Selected: {selected.name} ({selected.id})")
    typer.echo("Deck ids: " + ", ".join(str(i) for i in ids))
