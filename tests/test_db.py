import sqlite3
from pathlib import Path

import pytest

from ankivis.db import default_collection_path, open_collection


def test_default_collection_path_uses_profile():
    path = default_collection_path("Alice")
    assert path == Path.home() / ".local" / "share" / "Anki2" / "Alice" / "collection.anki2"


def test_default_collection_path_default_profile():
    assert default_collection_path().parent.name == "User 1"


def test_default_collection_path_custom_base(tmp_path):
    assert default_collection_path("Bob", base=tmp_path) == tmp_path / "Bob" / "collection.anki2"


def test_open_collection_reads_data(collection_path):
    conn = open_collection(collection_path)
    try:
        assert conn.execute("SELECT count(*) FROM decks").fetchone()[0] == 3
    finally:
        conn.close()


def test_open_collection_is_read_only(collection_path):
    conn = open_collection(collection_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM decks")
    finally:
        conn.close()
    # The original file is untouched.
    check = sqlite3.connect(collection_path)
    assert check.execute("SELECT count(*) FROM col").fetchone()[0] == 1
    check.close()


def test_open_collection_supports_unicase_collation(collection_path):
    conn = open_collection(collection_path)
    try:
        rows = conn.execute("SELECT name FROM decks ORDER BY name").fetchall()
        assert len(rows) == 3
    finally:
        conn.close()


def test_open_collection_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_collection(tmp_path / "nope.anki2")


def test_open_collection_falls_back_to_copy_when_locked(collection_path):
    locker = sqlite3.connect(collection_path, isolation_level=None)
    locker.execute("BEGIN EXCLUSIVE")
    try:
        conn = open_collection(collection_path, timeout=0.05)
        try:
            assert conn.execute("SELECT count(*) FROM decks").fetchone()[0] == 3
        finally:
            conn.close()
    finally:
        locker.execute("ROLLBACK")
        locker.close()
