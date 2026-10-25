"""Tests for exporting one pie chart PNG per day (``ankivis.export``)."""

import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ankivis.export import daily_intervals, export_days, export_missing, missing_days
from ankivis.history import intervals_at

BERLIN = ZoneInfo("Europe/Berlin")
DECK = 1700000000002
SUBDECK = 1700000000003
OTHER = 1

LEARN, REVIEW, RELEARN, FILTERED_REVIEW, MANUAL = 0, 1, 2, 3, 4


def ms(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    """Epoch milliseconds of a Berlin local time."""
    return int(datetime(year, month, day, hour, minute, tzinfo=BERLIN).timestamp() * 1000)


@pytest.fixture
def conn(make_collection: Callable[..., Path]) -> sqlite3.Connection:
    connection = sqlite3.connect(make_collection())
    yield connection
    connection.close()


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    """Empty output directory (separate from the collection file in ``tmp_path``)."""
    path = tmp_path / "frames"
    path.mkdir()
    return path


def add_card(conn: sqlite3.Connection, cid: int, did: int = DECK) -> int:
    conn.execute(
        "INSERT INTO cards VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '')",
        (cid, cid, did),
    )
    return cid


def add_review(conn: sqlite3.Connection, rid: int, cid: int, ivl: int, rtype: int = REVIEW):
    conn.execute(
        "INSERT INTO revlog VALUES (?, ?, 0, 3, ?, 0, 2500, 1000, ?)", (rid, cid, ivl, rtype)
    )


class FakeRender:
    """Stand-in for ``render_pie`` that records calls and writes a tiny file."""

    def __init__(self) -> None:
        self.calls: list[tuple[date, Path, dict, str | None]] = []

    def __call__(self, intervals, day, path, title=None):
        path = Path(path)
        path.write_bytes(b"png")
        self.calls.append((day, path, dict(intervals), title))
        return path

    @property
    def days(self) -> list[date]:
        return [day for day, *_ in self.calls]


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


# --- missing_days ------------------------------------------------------------------------


def test_missing_days_skips_existing_files(tmp_path):
    (tmp_path / "2024-03-02.png").write_bytes(b"x")
    (tmp_path / "2024-03-04.png").write_bytes(b"x")
    (tmp_path / "unrelated.png").write_bytes(b"x")
    result = missing_days(tmp_path, date(2024, 3, 1), date(2024, 3, 5))
    assert result == [date(2024, 3, 1), date(2024, 3, 3), date(2024, 3, 5)]


def test_missing_days_inclusive_bounds(tmp_path):
    assert missing_days(tmp_path, date(2024, 3, 1), date(2024, 3, 1)) == [date(2024, 3, 1)]


def test_missing_days_empty_range(tmp_path):
    assert missing_days(tmp_path, date(2024, 3, 2), date(2024, 3, 1)) == []


def test_missing_days_nonexistent_dir(tmp_path):
    result = missing_days(tmp_path / "new", date(2024, 3, 1), date(2024, 3, 2))
    assert result == [date(2024, 3, 1), date(2024, 3, 2)]


# --- daily_intervals (single pass) -------------------------------------------------------


def _history(conn: sqlite3.Connection) -> None:
    a = add_card(conn, ms(2024, 3, 1, 8))
    b = add_card(conn, ms(2024, 3, 2, 9))
    c = add_card(conn, ms(2024, 3, 3, 10), SUBDECK)
    d = add_card(conn, ms(2024, 3, 1, 9), OTHER)
    add_card(conn, ms(2024, 3, 6, 9))  # created after the range
    add_review(conn, ms(2024, 3, 1, 9), a, -600, LEARN)
    add_review(conn, ms(2024, 3, 1, 23, 59), a, 1, LEARN)
    add_review(conn, ms(2024, 3, 2, 0, 0), a, 3)
    add_review(conn, ms(2024, 3, 2, 10), b, 2)
    add_review(conn, ms(2024, 3, 3, 11), b, 0, FILTERED_REVIEW)  # ignored: no reschedule
    add_review(conn, ms(2024, 3, 4, 11), b, 0, MANUAL)  # reset
    add_review(conn, ms(2024, 3, 4, 12), c, -60, RELEARN)
    add_review(conn, ms(2024, 3, 5, 12), a, 10)
    add_review(conn, ms(2024, 3, 2, 12), d, 50)
    conn.commit()


def test_daily_intervals_matches_intervals_at(conn):
    _history(conn)
    ids = [DECK, SUBDECK]
    days = _days(date(2024, 2, 28), date(2024, 3, 7))
    result = dict(daily_intervals(conn, ids, days, tz=BERLIN))
    assert list(result) == days
    for day in days:
        assert result[day] == intervals_at(conn, ids, day, tz=BERLIN), day


def test_daily_intervals_only_requested_days(conn):
    _history(conn)
    days = [date(2024, 3, 5), date(2024, 3, 2)]  # unsorted, with gaps
    result = list(daily_intervals(conn, [DECK, SUBDECK], days, tz=BERLIN))
    assert [day for day, _ in result] == [date(2024, 3, 2), date(2024, 3, 5)]
    assert result[1][1] == intervals_at(conn, [DECK, SUBDECK], date(2024, 3, 5), tz=BERLIN)


def test_daily_intervals_no_decks(conn):
    _history(conn)
    result = list(daily_intervals(conn, [], [date(2024, 3, 5)], tz=BERLIN))
    assert result == [(date(2024, 3, 5), {})]


# --- export_missing ----------------------------------------------------------------------


def test_export_range_first_review_to_last_day(conn, out_dir):
    _history(conn)
    render = FakeRender()
    written = export_missing(
        conn, [DECK, SUBDECK], out_dir, date(2024, 3, 5), tz=BERLIN, render=render
    )
    expected = _days(date(2024, 3, 1), date(2024, 3, 5))
    assert render.days == expected
    assert written == [out_dir / f"{day.isoformat()}.png" for day in expected]
    assert sorted(p.name for p in out_dir.iterdir()) == [f"{d.isoformat()}.png" for d in expected]


def test_export_skips_existing_files(conn, out_dir):
    _history(conn)
    (out_dir / "2024-03-02.png").write_bytes(b"old")
    (out_dir / "2024-03-04.png").write_bytes(b"old")
    render = FakeRender()
    export_missing(conn, [DECK, SUBDECK], out_dir, date(2024, 3, 5), tz=BERLIN, render=render)
    assert render.days == [date(2024, 3, 1), date(2024, 3, 3), date(2024, 3, 5)]
    assert (out_dir / "2024-03-02.png").read_bytes() == b"old"


def test_export_is_idempotent(conn, out_dir):
    _history(conn)
    export_missing(conn, [DECK], out_dir, date(2024, 3, 5), tz=BERLIN, render=FakeRender())
    render = FakeRender()
    written = export_missing(conn, [DECK], out_dir, date(2024, 3, 5), tz=BERLIN, render=render)
    assert written == []
    assert render.calls == []


def test_export_passes_intervals_and_title(conn, out_dir):
    _history(conn)
    render = FakeRender()
    export_missing(
        conn,
        [DECK, SUBDECK],
        out_dir,
        date(2024, 3, 3),
        title="Spanish",
        tz=BERLIN,
        render=render,
    )
    for day, path, intervals, title in render.calls:
        assert title == "Spanish"
        assert path == out_dir / f"{day.isoformat()}.png"
        assert intervals == intervals_at(conn, [DECK, SUBDECK], day, tz=BERLIN)


def test_export_includes_last_day(conn, out_dir):
    _history(conn)
    render = FakeRender()
    export_missing(conn, [DECK], out_dir, date(2024, 3, 1), tz=BERLIN, render=render)
    assert render.days == [date(2024, 3, 1)]


def test_export_nothing_when_last_day_before_first_review(conn, out_dir):
    _history(conn)
    render = FakeRender()
    written = export_missing(conn, [DECK], out_dir, date(2024, 2, 29), tz=BERLIN, render=render)
    assert written == []
    assert render.calls == []


def test_export_without_reviews(conn, out_dir):
    add_card(conn, ms(2024, 3, 1))
    conn.commit()
    render = FakeRender()
    assert export_missing(conn, [DECK], out_dir, date(2024, 3, 6), render=render) == []
    assert render.calls == []


def test_export_creates_output_dir(conn, out_dir):
    _history(conn)
    out = out_dir / "a" / "b"
    export_missing(conn, [DECK], out, date(2024, 3, 2), tz=BERLIN, render=FakeRender())
    assert (out / "2024-03-01.png").exists()
    assert (out / "2024-03-02.png").exists()


def test_export_days_yields_each_path_lazily(conn, out_dir):
    _history(conn)
    render = FakeRender()
    days = [date(2024, 3, 2), date(2024, 3, 4)]
    paths = export_days(conn, [DECK], out_dir, days, tz=BERLIN, render=render)
    assert render.calls == []  # nothing happens before iteration
    assert next(paths) == out_dir / "2024-03-02.png"
    assert render.days == [date(2024, 3, 2)]
    assert list(paths) == [out_dir / "2024-03-04.png"]
    assert render.days == days


def test_export_failed_render_leaves_no_file(conn, out_dir):
    _history(conn)

    def broken(intervals, day, path, title=None):
        Path(path).write_bytes(b"partial")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        export_missing(conn, [DECK], out_dir, date(2024, 3, 6), tz=BERLIN, render=broken)
    assert not any(p.name.endswith(".png") for p in out_dir.iterdir())


def test_export_with_real_renderer(conn, out_dir):
    _history(conn)
    written = export_missing(conn, [DECK, SUBDECK], out_dir, date(2024, 3, 2), tz=BERLIN)
    assert [p.name for p in written] == ["2024-03-01.png", "2024-03-02.png"]
    for path in written:
        assert path.read_bytes().startswith(b"\x89PNG")
