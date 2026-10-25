"""Export one pie chart PNG per day, skipping days whose image already exists.

Files are named ``YYYY-MM-DD.png``, so a directory of exports can be resumed at any time: a
second run only renders the days that are still missing. The intervals of all requested days
are computed in a single pass over the review log instead of one query per day.
"""

import sqlite3
from collections.abc import Callable, Iterable, Iterator, Sequence
from datetime import date, timedelta, tzinfo
from pathlib import Path

from ankivis.chart import render_pie
from ankivis.history import (
    REVLOG_MANUAL,
    deck_filter,
    end_of_day_ms,
    first_review_date,
    revlog_interval_days,
)

Renderer = Callable[..., Path]
Intervals = dict[int, float | None]


def image_path(out_dir: Path | str, day: date) -> Path:
    """Path of the image for *day* inside *out_dir*."""
    return Path(out_dir) / f"{day.isoformat()}.png"


def missing_days(out_dir: Path | str, start: date, end: date) -> list[date]:
    """Days from *start* to *end* (both inclusive) that have no image in *out_dir* yet."""
    count = (end - start).days + 1
    days = (start + timedelta(days=i) for i in range(max(count, 0)))
    return [day for day in days if not image_path(out_dir, day).exists()]


def daily_intervals(
    conn: sqlite3.Connection,
    deck_ids: Sequence[int],
    days: Iterable[date],
    tz: tzinfo | None = None,
) -> Iterator[tuple[date, Intervals]]:
    """Yield ``(day, {card_id: interval})`` for each of *days* in chronological order.

    The result for each day equals :func:`ankivis.history.intervals_at`, but cards and review
    log are read only once and replayed in order, which is much faster for long ranges.
    """
    days = sorted(set(days))
    if not days:
        return
    if not deck_ids:
        for day in days:
            yield day, {}
        return
    last_cutoff = end_of_day_ms(days[-1], tz)
    condition, params = deck_filter(deck_ids)
    cards = conn.execute(
        f"SELECT c.id FROM cards AS c WHERE c.id <= ? AND {condition} ORDER BY c.id",
        [last_cutoff, *params],
    ).fetchall()
    reviews = conn.execute(
        f"""
        SELECT r.id, r.cid, r.ivl, r.type
        FROM revlog AS r JOIN cards AS c ON c.id = r.cid
        WHERE r.id <= ? AND (r.ivl != 0 OR r.type = {REVLOG_MANUAL}) AND {condition}
        ORDER BY r.id
        """,
        [last_cutoff, *params],
    ).fetchall()

    latest: Intervals = {}  # newest interval per card, whether the card exists yet or not
    current: Intervals = {}  # cards that exist at the current cutoff
    card_pos = review_pos = 0
    for day in days:
        cutoff = end_of_day_ms(day, tz)
        while review_pos < len(reviews) and reviews[review_pos][0] <= cutoff:
            _, cid, ivl, rtype = reviews[review_pos]
            latest[cid] = revlog_interval_days(ivl, rtype)
            if cid in current:
                current[cid] = latest[cid]
            review_pos += 1
        while card_pos < len(cards) and cards[card_pos][0] <= cutoff:
            cid = int(cards[card_pos][0])
            current[cid] = latest.get(cid)
            card_pos += 1
        yield day, dict(current)


def export_days(
    conn: sqlite3.Connection,
    deck_ids: Sequence[int],
    out_dir: Path | str,
    days: Iterable[date],
    title: str | None = None,
    tz: tzinfo | None = None,
    render: Renderer | None = None,
) -> Iterator[Path]:
    """Render the image of each of *days* into *out_dir*, yielding each path once written.

    Existing files are overwritten. If rendering fails or is interrupted, the incomplete
    image is removed so that a later run renders that day again.
    """
    render = render_pie if render is None else render
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for day, intervals in daily_intervals(conn, deck_ids, days, tz):
        path = image_path(out_dir, day)
        try:
            render(intervals, day, path, title=title)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        yield path


def days_to_export(
    conn: sqlite3.Connection,
    deck_ids: Sequence[int],
    out_dir: Path | str,
    last: date,
    tz: tzinfo | None = None,
) -> list[date] | None:
    """Missing days from the first review up to *last* (inclusive).

    Returns ``None`` if there are no reviews. Callers usually pass yesterday as *last*, because
    the state of today may still change.
    """
    first = first_review_date(conn, deck_ids, tz)
    if first is None:
        return None
    return missing_days(out_dir, first, last)


def export_missing(
    conn: sqlite3.Connection,
    deck_ids: Sequence[int],
    out_dir: Path | str,
    last: date,
    title: str | None = None,
    tz: tzinfo | None = None,
    render: Renderer | None = None,
) -> list[Path]:
    """Render every missing day from the first review up to *last*; return the new paths."""
    days = days_to_export(conn, deck_ids, out_dir, last, tz)
    if not days:
        return []
    return list(export_days(conn, deck_ids, out_dir, days, title, tz, render))
