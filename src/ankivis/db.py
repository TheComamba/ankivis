"""Read-only access to an Anki collection (``collection.anki2``)."""

import os
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

COLLECTION_FILE = "collection.anki2"


def default_anki_base(
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return Anki's data folder (the folder containing the profile directories).

    Mirrors Anki's own lookup:

    * ``ANKI_BASE`` environment variable, if set (all platforms)
    * Windows: ``%APPDATA%\\Anki2``
    * macOS: ``~/Library/Application Support/Anki2``
    * Linux/other: ``$XDG_DATA_HOME/Anki2``, falling back to ``~/.local/share/Anki2``
    """
    platform = platform if platform is not None else sys.platform
    environ = environ if environ is not None else os.environ
    home = home if home is not None else Path.home()

    if anki_base := environ.get("ANKI_BASE"):
        return Path(anki_base).expanduser()
    if platform.startswith("win"):
        appdata = environ.get("APPDATA")
        return (Path(appdata) if appdata else home / "AppData" / "Roaming") / "Anki2"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Anki2"
    xdg = environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else home / ".local" / "share") / "Anki2"


DEFAULT_ANKI_BASE = default_anki_base()


class ProfileError(Exception):
    """The Anki profile cannot be determined automatically."""


def find_profiles(base: Path | None = None) -> list[str]:
    """Return the sorted names of all profile directories that contain a collection."""
    base = base if base is not None else DEFAULT_ANKI_BASE
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / COLLECTION_FILE).is_file())


def default_collection_path(profile: str | None = None, base: Path | None = None) -> Path:
    """Return the collection path for *profile* (``<Anki base>/<profile>/collection.anki2``).

    The Anki base folder is platform dependent, see :func:`default_anki_base`.

    Without *profile*, the profile is detected automatically. This also works for localised
    default profile names such as ``Benutzer 1``. Raises :class:`ProfileError` if there is
    no profile or more than one.
    """
    base = base if base is not None else DEFAULT_ANKI_BASE
    if profile is None:
        profiles = find_profiles(base)
        if not profiles:
            raise ProfileError(f"No Anki profile with a {COLLECTION_FILE} found in {base}.")
        if len(profiles) > 1:
            names = ", ".join(profiles)
            raise ProfileError(
                f"Multiple Anki profiles found ({names}); choose one with --profile."
            )
        profile = profiles[0]
    return base / profile / COLLECTION_FILE


def _unicase(a: str, b: str) -> int:
    """Approximation of Anki's ``unicase`` collation (case-insensitive comparison)."""
    a, b = a.casefold(), b.casefold()
    return (a > b) - (a < b)


class _TempCopyConnection(sqlite3.Connection):
    """Connection to a temporary copy of a collection; deletes the copy on close."""

    temp_dir: Path | None = None

    def close(self) -> None:
        super().close()
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None


def _connect(path: Path, *, read_only: bool, timeout: float, factory=sqlite3.Connection):
    uri = path.resolve().as_uri() + ("?mode=ro" if read_only else "")
    conn = sqlite3.connect(uri, uri=True, timeout=timeout, factory=factory)
    conn.create_collation("unicase", _unicase)
    return conn


def _open_copy(path: Path, timeout: float) -> sqlite3.Connection:
    temp_dir = Path(tempfile.mkdtemp(prefix="ankivis-"))
    target = temp_dir / path.name
    shutil.copy2(path, target)
    # Include an uncommitted write-ahead log so the copy is as current as possible.
    wal = path.with_name(path.name + "-wal")
    if wal.exists():
        shutil.copy2(wal, target.with_name(target.name + "-wal"))
    conn = _connect(target, read_only=False, timeout=timeout, factory=_TempCopyConnection)
    conn.temp_dir = temp_dir
    conn.execute("PRAGMA query_only = ON")
    return conn


def open_collection(path: str | Path, timeout: float = 1.0) -> sqlite3.Connection:
    """Open the collection at *path* read-only.

    If the database cannot be read (e.g. it is locked because Anki is running), a temporary
    copy is opened instead. The copy is removed when the connection is closed.
    """
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Collection not found: {path}")
    conn = _connect(path, read_only=True, timeout=timeout)
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite3.OperationalError:
        conn.close()
        return _open_copy(path, timeout)
    return conn
