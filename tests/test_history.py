"""Tests for reconstructing card intervals at a past date (``ankivis.history``)."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ankivis.history import end_of_day_ms, first_review_date, intervals_at

BERLIN = ZoneInfo("Europe/Berlin")
DECK = 1700000000002
SUBDECK = 1700000000003
OTHER = 1
FILTERED = 1700000000099

# Revlog types as stored by Anki.
LEARN, REVIEW, RELEARN, FILTERED_REVIEW, MANUAL = 0, 1, 2, 3, 4

DAY = date(2024, 3, 10)


def ms(year: int, month: int, day: int, hour: int = 12, minute: int = 0, second: int = 0) -> int:
    """Epoch milliseconds of a Berlin local time."""
    dt = datetime(year, month, day, hour, minute, second, tzinfo=BERLIN)
    return int(dt.timestamp() * 1000)


@pytest.fixture
def conn(make_collection: Callable[..., Path]) -> sqlite3.Connection:
    connection = sqlite3.connect(make_collection())
    yield connection
    connection.close()


_counter = iter(range(1, 10**9))


def add_card(conn: sqlite3.Connection, cid: int, did: int = DECK, odid: int = 0) -> int:
    nid = next(_counter)
    conn.execute(
        "INSERT INTO cards VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?, 0, '')",
        (cid, nid, did, odid),
    )
    return cid


def add_review(conn: sqlite3.Connection, rid: int, cid: int, ivl: int, rtype: int = REVIEW) -> None:
    ease = 0 if rtype == MANUAL else 3
    conn.execute(
        "INSERT INTO revlog VALUES (?, ?, 0, ?, ?, 0, 2500, 1000, ?)",
        (rid, cid, ease, ivl, rtype),
    )


# --- end_of_day_ms ---------------------------------------------------------------------


def test_end_of_day_ms_in_timezone() -> None:
    expected = datetime(2024, 3, 10, 23, 59, 59, 999000, tzinfo=BERLIN)
    assert end_of_day_ms(DAY, BERLIN) == round(expected.timestamp() * 1000)


def test_end_of_day_ms_utc() -> None:
    expected = datetime(2024, 3, 10, 23, 59, 59, 999000, tzinfo=UTC)
    assert end_of_day_ms(DAY, UTC) == round(expected.timestamp() * 1000)


def test_end_of_day_ms_defaults_to_local_timezone() -> None:
    expected = datetime(2024, 3, 10, 23, 59, 59, 999000)  # naive → local time
    assert end_of_day_ms(DAY) == round(expected.timestamp() * 1000)


def test_end_of_day_ms_is_last_millisecond_before_next_day() -> None:
    next_midnight = datetime(2024, 3, 11, tzinfo=BERLIN)
    assert end_of_day_ms(DAY, BERLIN) == round(next_midnight.timestamp() * 1000) - 1


def test_end_of_day_ms_handles_dst_change() -> None:
    # 2024-03-31 has only 23 hours in Berlin; end of day is 21:59:59.999 UTC.
    expected = datetime(2024, 3, 31, 21, 59, 59, 999000, tzinfo=UTC)
    assert end_of_day_ms(date(2024, 3, 31), BERLIN) == round(expected.timestamp() * 1000)


# --- intervals_at ----------------------------------------------------------------------


def test_review_interval_in_days(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 3, 1))
    add_review(conn, ms(2024, 3, 2), cid, 1)
    add_review(conn, ms(2024, 3, 5), cid, 4)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: 4.0}


def test_learning_step_in_seconds(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 3, 1))
    add_review(conn, ms(2024, 3, 10, 9), cid, -600, LEARN)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: pytest.approx(600 / 86400)}


def test_lapse_uses_relearning_step(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 1, 1))
    add_review(conn, ms(2024, 1, 2), cid, 30)
    add_review(conn, ms(2024, 3, 10, 8), cid, -900, RELEARN)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: pytest.approx(900 / 86400)}


def test_card_without_reviews_is_unlearned(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 3, 1))
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: None}


def test_reset_card_is_unlearned(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 1, 1))
    add_review(conn, ms(2024, 1, 2), cid, 20)
    add_review(conn, ms(2024, 3, 3), cid, 0, MANUAL)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: None}


def test_reviews_after_reset_count_again(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 1, 1))
    add_review(conn, ms(2024, 1, 2), cid, 20)
    add_review(conn, ms(2024, 3, 3), cid, 0, MANUAL)
    add_review(conn, ms(2024, 3, 4), cid, 2)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: 2.0}


def test_manual_reschedule_with_interval_is_used(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 1, 1))
    add_review(conn, ms(2024, 1, 2), cid, 3)
    add_review(conn, ms(2024, 3, 3), cid, 45, MANUAL)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: 45.0}


def test_zero_interval_rows_that_are_not_resets_are_ignored(conn: sqlite3.Connection) -> None:
    # e.g. a review in a filtered deck without rescheduling: does not change the schedule.
    cid = add_card(conn, ms(2024, 1, 1))
    add_review(conn, ms(2024, 1, 2), cid, 12)
    add_review(conn, ms(2024, 3, 3), cid, 0, FILTERED_REVIEW)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: 12.0}


def test_reviews_after_cutoff_are_ignored(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 3, 1))
    add_review(conn, ms(2024, 3, 2), cid, 3)
    add_review(conn, ms(2024, 3, 11, 8), cid, 9)
    add_review(conn, ms(2024, 4, 1), cid, 25)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: 3.0}


def test_first_review_after_cutoff_means_unlearned(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 3, 1))
    add_review(conn, ms(2024, 3, 12), cid, 1)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: None}


def test_timezone_boundary_2359_vs_0000(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 3, 1))
    add_review(conn, ms(2024, 3, 9), cid, 1)
    add_review(conn, ms(2024, 3, 10, 23, 59, 59), cid, 5)  # still on DAY
    add_review(conn, ms(2024, 3, 11, 0, 0, 0), cid, 11)  # next day
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: 5.0}
    assert intervals_at(conn, [DECK], DAY + timedelta(days=1), BERLIN) == {cid: 11.0}


def test_timezone_changes_which_reviews_count(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 3, 1))
    add_review(conn, ms(2024, 3, 9), cid, 1)
    # 00:30 Berlin on March 11 is 23:30 UTC on March 10.
    add_review(conn, ms(2024, 3, 11, 0, 30), cid, 7)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: 1.0}
    assert intervals_at(conn, [DECK], DAY, UTC) == {cid: 7.0}


def test_cards_created_after_date_are_excluded(conn: sqlite3.Connection) -> None:
    old = add_card(conn, ms(2024, 3, 1))
    same_day = add_card(conn, ms(2024, 3, 10, 23, 59))
    add_card(conn, ms(2024, 3, 11, 0, 0))
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {old: None, same_day: None}


def test_only_cards_of_given_decks(conn: sqlite3.Connection) -> None:
    a = add_card(conn, ms(2024, 3, 1), DECK)
    b = add_card(conn, ms(2024, 3, 2), SUBDECK)
    add_card(conn, ms(2024, 3, 3), OTHER)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {a: None}
    assert intervals_at(conn, [DECK, SUBDECK], DAY, BERLIN) == {a: None, b: None}


def test_cards_in_filtered_deck_belong_to_original_deck(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 3, 1), did=FILTERED, odid=DECK)
    add_review(conn, ms(2024, 3, 2), cid, 2)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {cid: 2.0}


def test_no_deck_ids_gives_empty_result(conn: sqlite3.Connection) -> None:
    add_card(conn, ms(2024, 3, 1))
    assert intervals_at(conn, [], DAY, BERLIN) == {}


def test_reviews_of_other_cards_do_not_leak(conn: sqlite3.Connection) -> None:
    a = add_card(conn, ms(2024, 3, 1))
    b = add_card(conn, ms(2024, 3, 2))
    add_review(conn, ms(2024, 3, 3), a, 6)
    add_review(conn, ms(2024, 3, 4), b, 2)
    assert intervals_at(conn, [DECK], DAY, BERLIN) == {a: 6.0, b: 2.0}


# --- first_review_date -----------------------------------------------------------------


def test_first_review_date(conn: sqlite3.Connection) -> None:
    a = add_card(conn, ms(2024, 1, 1))
    b = add_card(conn, ms(2024, 1, 2), SUBDECK)
    other = add_card(conn, ms(2023, 1, 1), OTHER)
    add_review(conn, ms(2023, 6, 1), other, 1)
    add_review(conn, ms(2024, 2, 5), a, 1)
    add_review(conn, ms(2024, 2, 3), b, 1)
    assert first_review_date(conn, [DECK], BERLIN) == date(2024, 2, 5)
    assert first_review_date(conn, [DECK, SUBDECK], BERLIN) == date(2024, 2, 3)


def test_first_review_date_uses_timezone(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 1, 1))
    add_review(conn, ms(2024, 3, 11, 0, 30), cid, 1)  # 23:30 UTC on March 10
    assert first_review_date(conn, [DECK], BERLIN) == date(2024, 3, 11)
    assert first_review_date(conn, [DECK], UTC) == date(2024, 3, 10)


def test_first_review_date_includes_filtered_cards(conn: sqlite3.Connection) -> None:
    cid = add_card(conn, ms(2024, 1, 1), did=FILTERED, odid=DECK)
    add_review(conn, ms(2024, 1, 7), cid, 1)
    assert first_review_date(conn, [DECK], BERLIN) == date(2024, 1, 7)


def test_first_review_date_without_reviews_is_none(conn: sqlite3.Connection) -> None:
    add_card(conn, ms(2024, 1, 1))
    assert first_review_date(conn, [DECK], BERLIN) is None
    assert first_review_date(conn, [], BERLIN) is None
