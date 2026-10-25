"""Shared fixtures: build small synthetic SQLite databases that mirror the Anki schema.

Tests never touch a real Anki collection.
"""

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

# (id, name with "::" separators) – deliberately unsorted, incl. a subdeck.
DEFAULT_DECKS: list[tuple[int, str]] = [
    (1700000000002, "Spanish"),
    (1, "Default"),
    (1700000000003, "Spanish::Verbs"),
]


def _unicase(a: str, b: str) -> int:
    a, b = a.casefold(), b.casefold()
    return (a > b) - (a < b)


def _create_common_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE col (
            id integer PRIMARY KEY, crt integer NOT NULL, mod integer NOT NULL,
            scm integer NOT NULL, ver integer NOT NULL, dty integer NOT NULL,
            usn integer NOT NULL, ls integer NOT NULL, conf text NOT NULL,
            models text NOT NULL, decks text NOT NULL, dconf text NOT NULL,
            tags text NOT NULL
        );
        CREATE TABLE notes (
            id integer PRIMARY KEY, guid text NOT NULL, mid integer NOT NULL,
            mod integer NOT NULL, usn integer NOT NULL, tags text NOT NULL,
            flds text NOT NULL, sfld integer NOT NULL, csum integer NOT NULL,
            flags integer NOT NULL, data text NOT NULL
        );
        CREATE TABLE cards (
            id integer PRIMARY KEY, nid integer NOT NULL, did integer NOT NULL,
            ord integer NOT NULL, mod integer NOT NULL, usn integer NOT NULL,
            type integer NOT NULL, queue integer NOT NULL, due integer NOT NULL,
            ivl integer NOT NULL, factor integer NOT NULL, reps integer NOT NULL,
            lapses integer NOT NULL, left integer NOT NULL, odue integer NOT NULL,
            odid integer NOT NULL, flags integer NOT NULL, data text NOT NULL
        );
        CREATE TABLE revlog (
            id integer PRIMARY KEY, cid integer NOT NULL, usn integer NOT NULL,
            ease integer NOT NULL, ivl integer NOT NULL, lastIvl integer NOT NULL,
            factor integer NOT NULL, time integer NOT NULL, type integer NOT NULL
        );
        """
    )


def build_collection(
    path: Path,
    decks: list[tuple[int, str]] | None = None,
    *,
    legacy: bool = False,
) -> Path:
    """Create a synthetic Anki collection at *path*.

    Modern format (default): decks live in the ``decks`` table, names separated by ``\\x1f``
    and the name column uses Anki's custom ``unicase`` collation.
    Legacy format: decks are stored as JSON in ``col.decks``.
    """
    decks = DEFAULT_DECKS if decks is None else decks
    conn = sqlite3.connect(path)
    try:
        conn.create_collation("unicase", _unicase)
        _create_common_tables(conn)
        legacy_json = "{}"
        if legacy:
            legacy_json = json.dumps({str(did): {"id": did, "name": name} for did, name in decks})
        else:
            conn.executescript(
                """
                CREATE TABLE decks (
                    id integer PRIMARY KEY NOT NULL,
                    name text NOT NULL COLLATE unicase,
                    mtime_secs integer NOT NULL, usn integer NOT NULL,
                    common blob NOT NULL, kind blob NOT NULL
                );
                CREATE UNIQUE INDEX idx_decks_name ON decks (name);
                """
            )
            conn.executemany(
                "INSERT INTO decks VALUES (?, ?, 0, 0, x'', x'')",
                [(did, name.replace("::", "\x1f")) for did, name in decks],
            )
        conn.execute(
            "INSERT INTO col VALUES (1, 0, 0, 0, 18, 0, 0, 0, '{}', '{}', ?, '{}', '{}')",
            (legacy_json,),
        )
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def make_collection(tmp_path: Path) -> Callable[..., Path]:
    """Factory fixture: ``make_collection(decks=None, legacy=False, name=...)``."""

    def _make(
        decks: list[tuple[int, str]] | None = None,
        *,
        legacy: bool = False,
        name: str = "collection.anki2",
    ) -> Path:
        return build_collection(tmp_path / name, decks, legacy=legacy)

    return _make


@pytest.fixture
def collection_path(make_collection: Callable[..., Path]) -> Path:
    """A modern-format collection with three decks (incl. a subdeck)."""
    return make_collection()
