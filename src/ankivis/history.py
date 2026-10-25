"""Reconstruct card intervals at a past date from the review log.

Anki stores every answer (and manual scheduling change) in the ``revlog`` table. Its ``id``
is the epoch time in milliseconds, ``ivl`` is the interval after the answer: positive values
are days, negative values are (re)learning steps in seconds. Card ids are the creation time
in epoch milliseconds as well.
"""

import sqlite3
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, tzinfo

SECONDS_PER_DAY = 86400

# revlog.type value for manual changes ("Forget"/reset, "Set due date").
REVLOG_MANUAL = 4


def end_of_day_ms(day: date, tz: tzinfo | None = None) -> int:
    """Return local 23:59:59.999 of *day* in *tz* as epoch milliseconds.

    Without *tz*, the system's local timezone is used. Days with a DST change are handled
    correctly because the result is derived from the following midnight.
    """
    next_midnight = datetime.combine(day + timedelta(days=1), time(), tzinfo=tz)
    return round(next_midnight.timestamp()) * 1000 - 1


def _deck_filter(deck_ids: Sequence[int]) -> tuple[str, list[int]]:
    """SQL condition matching cards whose (original) deck is in *deck_ids*.

    Cards in a filtered deck keep their home deck in ``odid``.
    """
    placeholders = ", ".join("?" for _ in deck_ids)
    return f"(CASE WHEN c.odid != 0 THEN c.odid ELSE c.did END) IN ({placeholders})", list(deck_ids)


def _to_days(ivl: int | None, rtype: int | None) -> float | None:
    if ivl is None or (rtype == REVLOG_MANUAL and ivl == 0):
        return None
    if ivl > 0:
        return float(ivl)
    return -ivl / SECONDS_PER_DAY


def intervals_at(
    conn: sqlite3.Connection,
    deck_ids: Sequence[int],
    day: date,
    tz: tzinfo | None = None,
) -> dict[int, float | None]:
    """Return ``{card_id: interval in days}`` as it was at the end of *day*.

    Only cards that existed on *day* (card id ≤ end of day) are included. For each card, the
    latest relevant revlog row up to the end of the day determines the interval:

    * ``ivl > 0`` → days, ``ivl < 0`` → ``-ivl / 86400`` days (learning step in seconds)
    * a reset (``type == 4 and ivl == 0``) or no row at all → ``None`` (unlearned)

    Other rows with ``ivl == 0`` (e.g. filtered-deck reviews without rescheduling) do not
    change the schedule and are skipped.
    """
    if not deck_ids:
        return {}
    cutoff = end_of_day_ms(day, tz)
    condition, params = _deck_filter(deck_ids)
    rows = conn.execute(
        f"""
        SELECT c.id, r.ivl, r.type
        FROM cards AS c
        LEFT JOIN revlog AS r ON r.id = (
            SELECT max(rl.id) FROM revlog AS rl
            WHERE rl.cid = c.id AND rl.id <= ?
              AND (rl.ivl != 0 OR rl.type = {REVLOG_MANUAL})
        )
        WHERE c.id <= ? AND {condition}
        """,
        [cutoff, cutoff, *params],
    ).fetchall()
    return {int(cid): _to_days(ivl, rtype) for cid, ivl, rtype in rows}


def first_review_date(
    conn: sqlite3.Connection,
    deck_ids: Sequence[int],
    tz: tzinfo | None = None,
) -> date | None:
    """Return the local date (in *tz*) of the earliest revlog entry of the decks' cards.

    Returns ``None`` if there are no reviews.
    """
    if not deck_ids:
        return None
    condition, params = _deck_filter(deck_ids)
    row = conn.execute(
        f"""
        SELECT min(r.id) FROM revlog AS r
        JOIN cards AS c ON c.id = r.cid
        WHERE {condition}
        """,
        params,
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return datetime.fromtimestamp(row[0] / 1000, tz=tz).date()
