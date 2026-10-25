"""Read-only access to an Anki collection (``collection.anki2``)."""

import shutil
import sqlite3
import tempfile
from pathlib import Path

DEFAULT_PROFILE = "User 1"
DEFAULT_ANKI_BASE = Path.home() / ".local" / "share" / "Anki2"


def default_collection_path(profile: str = DEFAULT_PROFILE, base: Path | None = None) -> Path:
    """Return the path of the collection for *profile* (``~/.local/share/Anki2/<profile>/``)."""
    return (base or DEFAULT_ANKI_BASE) / profile / "collection.anki2"


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
