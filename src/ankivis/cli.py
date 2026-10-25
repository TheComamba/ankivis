"""Command line interface for ankivis."""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from ankivis.db import ProfileError, default_collection_path, open_collection
from ankivis.decks import Deck, deck_ids, find_deck, format_deck_list, list_decks, pick_deck
from ankivis.history import format_interval, intervals_at, largest_intervals

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
    str | None,
    typer.Option(
        "--profile",
        "-p",
        help="Anki profile name (a folder inside Anki's data folder, e.g. "
        "~/.local/share/Anki2 on Linux, ~/Library/Application Support/Anki2 on macOS, "
        "%APPDATA%\\Anki2 on Windows). Detected automatically if there is only one.",
    ),
]


@app.callback()
def main() -> None:
    """Visualise learning progress for an Anki deck."""


def _open(collection: Path | None, profile: str | None) -> sqlite3.Connection:
    try:
        path = collection if collection is not None else default_collection_path(profile)
        return open_collection(path)
    except (FileNotFoundError, ProfileError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


def _load_decks(collection: Path | None, profile: str | None) -> list[Deck]:
    conn = _open(collection, profile)
    try:
        return list_decks(conn)
    finally:
        conn.close()


def _today() -> date:
    """Today in the system's local timezone (separate function so tests can patch it)."""
    return date.today()


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
    profile: ProfileOption = None,
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


@app.command("intervals")
def intervals_command(
    collection: CollectionOption = None,
    profile: ProfileOption = None,
    deck: Annotated[
        str | None, typer.Option("--deck", "-d", help="Select a deck by name or id.")
    ] = None,
    subdecks: Annotated[
        bool, typer.Option("--subdecks/--no-subdecks", help="Include subdecks of the selection.")
    ] = True,
    top: Annotated[int, typer.Option("--top", "-n", min=1, help="Number of cards to show.")] = 10,
    on: Annotated[
        datetime | None,
        typer.Option(
            "--date",
            help="Date (YYYY-MM-DD) whose end-of-day state is shown. Defaults to today.",
            formats=["%Y-%m-%d"],
            show_default=False,
        ),
    ] = None,
) -> None:
    """Print the cards with the largest intervals on a specific date (default: today)."""
    target = on.date() if on is not None else _today()
    conn = _open(collection, profile)
    try:
        all_decks = list_decks(conn)
        selected = select_deck(all_decks, deck)
        ids = deck_ids(all_decks, selected, include_subdecks=subdecks)
        intervals = intervals_at(conn, ids, target)
    finally:
        conn.close()
    day = target.isoformat()
    largest = largest_intervals(intervals, top)
    if not largest:
        typer.echo(f"No learned cards in {selected.name} on {day}.")
        return
    typer.echo(f"Largest intervals in {selected.name} on {day}:")
    width = len(str(len(largest)))
    for rank, (cid, ivl) in enumerate(largest, start=1):
        typer.echo(f"{rank:>{width}}. card {cid}: {format_interval(ivl)}")
