"""List the decks of an Anki collection and let the user pick one."""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

SEPARATOR = "::"
_DB_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class Deck:
    id: int
    name: str


def _sort_key(deck: Deck) -> list[str]:
    return [part.casefold() for part in deck.name.split(SEPARATOR)]


def _has_decks_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'decks'"
    ).fetchone()
    return row is not None


def list_decks(conn: sqlite3.Connection) -> list[Deck]:
    """Return all decks sorted by their hierarchical name (case-insensitive).

    Supports the modern ``decks`` table (name parts separated by ``\\x1f``) as well as the
    legacy JSON stored in ``col.decks``. Names are returned with ``::`` as separator.
    """
    if _has_decks_table(conn):
        rows = conn.execute("SELECT id, name FROM decks").fetchall()
        decks = [Deck(int(did), name.replace(_DB_SEPARATOR, SEPARATOR)) for did, name in rows]
    else:
        row = conn.execute("SELECT decks FROM col").fetchone()
        data = json.loads(row[0]) if row and row[0] else {}
        decks = [Deck(int(d["id"]), d["name"]) for d in data.values()]
    return sorted(decks, key=_sort_key)


def find_deck(decks: list[Deck], query: str) -> Deck | None:
    """Find a deck by exact name, case-insensitive name, or id."""
    query = query.strip()
    for deck in decks:
        if deck.name == query:
            return deck
    folded = query.casefold()
    for deck in decks:
        if deck.name.casefold() == folded:
            return deck
    if query.lstrip("-").isdigit():
        did = int(query)
        for deck in decks:
            if deck.id == did:
                return deck
    return None


def deck_ids(decks: list[Deck], deck: Deck, include_subdecks: bool = True) -> list[int]:
    """Return the id of *deck* and, optionally, the ids of all its subdecks."""
    if not include_subdecks:
        return [deck.id]
    prefix = (deck.name + SEPARATOR).casefold()
    return [d.id for d in decks if d.id == deck.id or d.name.casefold().startswith(prefix)]


def format_deck_list(decks: list[Deck]) -> list[str]:
    """Return ``"<n>. <name>"`` lines, numbered from 1."""
    return [f"{i}. {deck.name}" for i, deck in enumerate(decks, start=1)]


def pick_deck(
    decks: list[Deck],
    prompt: Callable[[str], str] = input,
    echo: Callable[[str], object] = print,
) -> Deck:
    """Show a numbered deck list and ask until a valid number, name or id is entered."""
    if not decks:
        raise ValueError("The collection contains no decks.")
    for line in format_deck_list(decks):
        echo(line)
    while True:
        answer = prompt("Pick a deck (number, name or id)").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(decks):
            return decks[int(answer) - 1]
        deck = find_deck(decks, answer) if answer else None
        if deck is not None:
            return deck
        echo(f"Invalid selection: {answer!r}. Enter a number between 1 and {len(decks)}.")
