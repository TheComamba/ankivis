import pytest

from ankivis.db import open_collection
from ankivis.decks import Deck, deck_ids, find_deck, list_decks, pick_deck

EXPECTED = [
    Deck(1, "Default"),
    Deck(1700000000002, "Spanish"),
    Deck(1700000000003, "Spanish::Verbs"),
]


@pytest.fixture
def decks(collection_path):
    conn = open_collection(collection_path)
    try:
        return list_decks(conn)
    finally:
        conn.close()


def test_list_decks_modern_schema(decks):
    assert decks == EXPECTED


def test_list_decks_legacy_json(make_collection):
    conn = open_collection(make_collection(legacy=True))
    try:
        assert list_decks(conn) == EXPECTED
    finally:
        conn.close()


def test_list_decks_sorted_case_insensitively_by_path(make_collection):
    path = make_collection(
        [(1, "b"), (2, "A::z"), (3, "a b"), (4, "A")],
    )
    conn = open_collection(path)
    try:
        names = [d.name for d in list_decks(conn)]
    finally:
        conn.close()
    # Parent "A" comes before its children; "A::z" before "a b" since components are compared.
    assert names == ["A", "A::z", "a b", "b"]


def test_find_deck_by_name(decks):
    assert find_deck(decks, "Spanish::Verbs") == EXPECTED[2]


def test_find_deck_by_name_case_insensitive(decks):
    assert find_deck(decks, "spanish") == EXPECTED[1]


def test_find_deck_by_id(decks):
    assert find_deck(decks, "1700000000003") == EXPECTED[2]


def test_find_deck_unknown(decks):
    assert find_deck(decks, "French") is None


def test_deck_ids_include_subdecks(decks):
    assert deck_ids(decks, EXPECTED[1]) == [1700000000002, 1700000000003]


def test_deck_ids_without_subdecks(decks):
    assert deck_ids(decks, EXPECTED[1], include_subdecks=False) == [1700000000002]


def test_deck_ids_does_not_match_name_prefix(make_collection):
    path = make_collection([(1, "Span"), (2, "Spanish"), (3, "Span::X")])
    conn = open_collection(path)
    try:
        all_decks = list_decks(conn)
    finally:
        conn.close()
    assert deck_ids(all_decks, Deck(1, "Span")) == [1, 3]


def _scripted(answers):
    it = iter(answers)
    prompts = []

    def prompt(text):
        prompts.append(text)
        return next(it)

    return prompt, prompts


def test_pick_deck_by_number(decks):
    prompt, _ = _scripted(["2"])
    assert pick_deck(decks, prompt=prompt, echo=lambda _: None) == EXPECTED[1]


def test_pick_deck_accepts_name_and_id(decks):
    prompt, _ = _scripted(["Spanish::Verbs"])
    assert pick_deck(decks, prompt=prompt, echo=lambda _: None) == EXPECTED[2]
    prompt, _ = _scripted(["1"])
    assert pick_deck(decks, prompt=prompt, echo=lambda _: None) == EXPECTED[0]


def test_pick_deck_reprompts_on_invalid_input(decks):
    messages = []
    prompt, prompts = _scripted(["0", "4", "abc", "", "3"])
    assert pick_deck(decks, prompt=prompt, echo=messages.append) == EXPECTED[2]
    assert len(prompts) == 5
    assert sum("Invalid" in m for m in messages) == 4


def test_pick_deck_prints_numbered_list(decks):
    messages = []
    prompt, _ = _scripted(["1"])
    pick_deck(decks, prompt=prompt, echo=messages.append)
    text = "\n".join(messages)
    assert "1. Default" in text
    assert "3. Spanish::Verbs" in text


def test_pick_deck_without_decks_raises():
    with pytest.raises(ValueError):
        pick_deck([], prompt=lambda _: "1", echo=lambda _: None)
