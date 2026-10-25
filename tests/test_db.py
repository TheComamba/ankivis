import sqlite3
from pathlib import Path

import pytest

from ankivis.db import (
    DEFAULT_ANKI_BASE,
    ProfileError,
    default_anki_base,
    default_collection_path,
    find_profiles,
    open_collection,
)

HOME = Path("/home/user")


def _make_profile(base: Path, name: str, with_collection: bool = True) -> None:
    (base / name).mkdir(parents=True)
    if with_collection:
        (base / name / "collection.anki2").touch()


def test_default_collection_path_uses_profile():
    path = default_collection_path("Alice")
    assert path == DEFAULT_ANKI_BASE / "Alice" / "collection.anki2"


def test_default_anki_base_linux():
    assert default_anki_base("linux", {}, HOME) == HOME / ".local" / "share" / "Anki2"


def test_default_anki_base_linux_xdg_data_home():
    environ = {"XDG_DATA_HOME": "/data"}
    assert default_anki_base("linux", environ, HOME) == Path("/data") / "Anki2"


def test_default_anki_base_macos():
    expected = HOME / "Library" / "Application Support" / "Anki2"
    assert default_anki_base("darwin", {}, HOME) == expected


def test_default_anki_base_windows_appdata():
    environ = {"APPDATA": "/appdata/Roaming"}
    assert default_anki_base("win32", environ, HOME) == Path("/appdata/Roaming") / "Anki2"


def test_default_anki_base_windows_without_appdata():
    expected = HOME / "AppData" / "Roaming" / "Anki2"
    assert default_anki_base("win32", {}, HOME) == expected


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_default_anki_base_env_override(platform):
    environ = {"ANKI_BASE": "/custom/anki", "APPDATA": "/x", "XDG_DATA_HOME": "/y"}
    assert default_anki_base(platform, environ, HOME) == Path("/custom/anki")


def test_default_collection_path_custom_base(tmp_path):
    assert default_collection_path("Bob", base=tmp_path) == tmp_path / "Bob" / "collection.anki2"


def test_find_profiles_only_lists_dirs_with_collection(tmp_path):
    _make_profile(tmp_path, "Benutzer 1")
    _make_profile(tmp_path, "Alice")
    _make_profile(tmp_path, "addons21", with_collection=False)
    _make_profile(tmp_path, "logs", with_collection=False)
    (tmp_path / "prefs21.db").touch()
    assert find_profiles(tmp_path) == ["Alice", "Benutzer 1"]


def test_find_profiles_missing_base(tmp_path):
    assert find_profiles(tmp_path / "missing") == []


def test_default_collection_path_detects_single_profile(tmp_path):
    # Anki localises the default profile name, e.g. "Benutzer 1" in German.
    _make_profile(tmp_path, "Benutzer 1")
    _make_profile(tmp_path, "addons21", with_collection=False)
    assert default_collection_path(base=tmp_path) == tmp_path / "Benutzer 1" / "collection.anki2"


def test_default_collection_path_ambiguous_profiles(tmp_path):
    _make_profile(tmp_path, "Alice")
    _make_profile(tmp_path, "Bob")
    with pytest.raises(ProfileError, match="Alice.*Bob"):
        default_collection_path(base=tmp_path)


def test_default_collection_path_no_profiles(tmp_path):
    with pytest.raises(ProfileError, match="No Anki profile"):
        default_collection_path(base=tmp_path)


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
