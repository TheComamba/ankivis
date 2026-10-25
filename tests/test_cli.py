import subprocess
import sys

from typer.testing import CliRunner

from ankivis.cli import app

runner = CliRunner()


def test_hello_prints_hello_world():
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello, world" in result.output


def test_help_lists_hello_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "hello" in result.output


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


def test_module_is_executable():
    result = subprocess.run(
        [sys.executable, "-m", "ankivis", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "hello" in result.stdout
