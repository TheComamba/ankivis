import sqlite3
import subprocess
import sys
from datetime import date, datetime

from typer.testing import CliRunner

from ankivis.cli import app

runner = CliRunner()


def test_help_lists_decks_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "decks" in result.output


def test_decks_prints_numbered_list(collection_path):
    result = runner.invoke(app, ["decks", "--collection", str(collection_path)])
    assert result.exit_code == 0, result.output
    lines = [line.strip() for line in result.output.splitlines() if line.strip()]
    assert lines == ["1. Default", "2. Spanish", "3. Spanish::Verbs"]


def test_decks_uses_profile_path(collection_path, monkeypatch):
    monkeypatch.setattr("ankivis.cli.default_collection_path", lambda profile: collection_path)
    result = runner.invoke(app, ["decks", "--profile", "Someone"])
    assert result.exit_code == 0, result.output
    assert "Spanish::Verbs" in result.output


def test_decks_without_profile_autodetects(collection_path, monkeypatch):
    # collection_path lives in <tmp>/collection.anki2; build a profile dir layout instead.
    base = collection_path.parent / "Anki2"
    (base / "Benutzer 1").mkdir(parents=True)
    collection_path.rename(base / "Benutzer 1" / "collection.anki2")
    (base / "addons21").mkdir()
    monkeypatch.setattr("ankivis.db.DEFAULT_ANKI_BASE", base)
    result = runner.invoke(app, ["decks"])
    assert result.exit_code == 0, result.output
    assert "3. Spanish::Verbs" in result.output


def test_decks_ambiguous_profile_reports_error(tmp_path, monkeypatch):
    for name in ("Alice", "Bob"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "collection.anki2").touch()
    monkeypatch.setattr("ankivis.db.DEFAULT_ANKI_BASE", tmp_path)
    result = runner.invoke(app, ["decks"])
    assert result.exit_code == 1
    assert "--profile" in result.output


def test_decks_missing_collection(tmp_path):
    result = runner.invoke(app, ["decks", "--collection", str(tmp_path / "missing.anki2")])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_decks_pick_interactive(collection_path):
    result = runner.invoke(
        app, ["decks", "--collection", str(collection_path), "--pick"], input="x\n2\n"
    )
    assert result.exit_code == 0, result.output
    assert "Invalid" in result.output
    assert "Selected: Spanish (1700000000002)" in result.output
    assert "Deck ids: 1700000000002, 1700000000003" in result.output


def test_decks_with_deck_option_by_name(collection_path):
    result = runner.invoke(
        app, ["decks", "--collection", str(collection_path), "--deck", "Spanish", "--no-subdecks"]
    )
    assert result.exit_code == 0, result.output
    assert "Selected: Spanish (1700000000002)" in result.output
    assert "Deck ids: 1700000000002" in result.output
    assert "1700000000003" not in result.output


def test_decks_with_deck_option_by_id(collection_path):
    result = runner.invoke(app, ["decks", "--collection", str(collection_path), "--deck", "1"])
    assert result.exit_code == 0, result.output
    assert "Selected: Default (1)" in result.output


def test_decks_with_unknown_deck(collection_path):
    result = runner.invoke(app, ["decks", "--collection", str(collection_path), "--deck", "French"])
    assert result.exit_code != 0
    assert "French" in result.output


def _ms(year: int, month: int, day: int) -> int:
    """Epoch ms at local noon (robust against the system timezone)."""
    return int(datetime(year, month, day, 12).timestamp() * 1000)


def _fill_reviews(path, n_cards: int = 12) -> list[int]:
    conn = sqlite3.connect(path)
    cids = []
    for i in range(n_cards):
        cid = _ms(2024, 1, 1) + i
        conn.execute(
            "INSERT INTO cards VALUES (?, ?, 1700000000002, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,"
            " 0, 0, 0, '')",
            (cid, i + 1),
        )
        # Interval on 2024-03-10 is i + 1 days; a later review must be ignored.
        conn.execute(
            "INSERT INTO revlog VALUES (?, ?, 0, 3, ?, 0, 2500, 1000, 1)",
            (_ms(2024, 2, 1) + i, cid, i + 1),
        )
        conn.execute(
            "INSERT INTO revlog VALUES (?, ?, 0, 3, 999, 0, 2500, 1000, 1)",
            (_ms(2024, 4, 1) + i, cid),
        )
        cids.append(cid)
    conn.commit()
    conn.close()
    return cids


def test_intervals_prints_top_ten(collection_path):
    cids = _fill_reviews(collection_path)
    result = runner.invoke(
        app,
        ["intervals", "-c", str(collection_path), "-d", "Spanish", "--date", "2024-03-10"],
    )
    assert result.exit_code == 0, result.output
    lines = [line.strip() for line in result.output.splitlines() if line.strip()]
    assert lines[0] == "Largest intervals in Spanish on 2024-03-10:"
    assert lines[1] == f"1. card {cids[11]}: 12 d"
    assert lines[10] == f"10. card {cids[2]}: 3 d"
    assert len(lines) == 11
    assert "999" not in result.output


def test_intervals_top_option(collection_path):
    _fill_reviews(collection_path)
    result = runner.invoke(
        app,
        [
            "intervals",
            "-c",
            str(collection_path),
            "-d",
            "Spanish",
            "--date",
            "2024-03-10",
            "--top",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len([line for line in result.output.splitlines() if "card" in line]) == 2


def test_intervals_without_learned_cards(collection_path):
    result = runner.invoke(
        app, ["intervals", "-c", str(collection_path), "-d", "Spanish", "--date", "2024-03-10"]
    )
    assert result.exit_code == 0, result.output
    assert "No learned cards in Spanish on 2024-03-10." in result.output


def test_intervals_defaults_to_today(collection_path, monkeypatch):
    cids = _fill_reviews(collection_path)
    monkeypatch.setattr("ankivis.cli._today", lambda: date(2024, 3, 10))
    result = runner.invoke(app, ["intervals", "-c", str(collection_path), "-d", "Spanish"])
    assert result.exit_code == 0, result.output
    assert "Largest intervals in Spanish on 2024-03-10:" in result.output
    assert f"1. card {cids[11]}: 12 d" in result.output


def test_intervals_today_includes_all_reviews(collection_path):
    # End of today lies in the future; every existing review must still be counted.
    cids = _fill_reviews(collection_path)
    result = runner.invoke(app, ["intervals", "-c", str(collection_path), "-d", "Spanish"])
    assert result.exit_code == 0, result.output
    assert f"on {date.today().isoformat()}:" in result.output
    # All cards now have the (tied) interval 999; ties are ordered by card id.
    assert f" 1. card {cids[0]}: 999 d" in result.output
    assert f"10. card {cids[9]}: 999 d" in result.output


def test_intervals_rejects_invalid_date(collection_path):
    result = runner.invoke(
        app, ["intervals", "-c", str(collection_path), "-d", "Spanish", "--date", "10.03.2024"]
    )
    assert result.exit_code != 0


def test_module_is_executable():
    result = subprocess.run(
        [sys.executable, "-m", "ankivis", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "decks" in result.stdout
