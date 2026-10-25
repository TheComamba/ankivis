import sqlite3
import subprocess
import sys
from datetime import date, datetime

import imageio.v2 as imageio
import numpy as np
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


def test_chart_writes_png(collection_path, tmp_path):
    _fill_reviews(collection_path)
    out = tmp_path / "pie.png"
    result = runner.invoke(
        app,
        [
            "chart",
            "-c",
            str(collection_path),
            "-d",
            "Spanish",
            "--date",
            "2024-03-10",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert str(out) in result.output


def test_chart_default_file_name(collection_path, tmp_path, monkeypatch):
    _fill_reviews(collection_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app, ["chart", "-c", str(collection_path), "-d", "Spanish", "--date", "2024-03-10"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "2024-03-10.png").exists()


def test_export_writes_missing_days(collection_path, tmp_path, monkeypatch):
    _fill_reviews(collection_path)
    out = tmp_path / "frames"
    out.mkdir()
    (out / "2024-02-02.png").write_bytes(b"old")
    monkeypatch.setattr("ankivis.cli._today", lambda: date(2024, 2, 4))
    result = runner.invoke(
        app, ["export", "-c", str(collection_path), "-d", "Spanish", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in out.iterdir()) == [
        "2024-02-01.png",
        "2024-02-02.png",
        "2024-02-03.png",
    ]
    assert (out / "2024-02-02.png").read_bytes() == b"old"
    assert (out / "2024-02-01.png").read_bytes().startswith(b"\x89PNG")
    assert "Wrote 2 images" in result.output

    again = runner.invoke(
        app, ["export", "-c", str(collection_path), "-d", "Spanish", "--out", str(out)]
    )
    assert again.exit_code == 0, again.output
    assert "up to date" in again.output.lower()


def test_export_until_option(collection_path, tmp_path, monkeypatch):
    _fill_reviews(collection_path)
    out = tmp_path / "frames"
    monkeypatch.setattr("ankivis.cli._today", lambda: date(2024, 2, 10))
    result = runner.invoke(
        app,
        [
            "export",
            "-c",
            str(collection_path),
            "-d",
            "Spanish",
            "--out",
            str(out),
            "--until",
            "2024-02-02",
        ],
    )
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in out.iterdir()) == ["2024-02-01.png", "2024-02-02.png"]
    assert "Wrote 2 images" in result.output


def test_export_until_today_is_allowed(collection_path, tmp_path, monkeypatch):
    _fill_reviews(collection_path)
    out = tmp_path / "frames"
    monkeypatch.setattr("ankivis.cli._today", lambda: date(2024, 2, 2))
    args = ["export", "-c", str(collection_path), "-d", "Spanish", "--out", str(out)]
    result = runner.invoke(app, [*args, "--until", "2024-02-02"])
    assert result.exit_code == 0, result.output
    assert (out / "2024-02-02.png").exists()


def test_export_until_in_future_is_rejected(collection_path, tmp_path, monkeypatch):
    _fill_reviews(collection_path)
    out = tmp_path / "frames"
    monkeypatch.setattr("ankivis.cli._today", lambda: date(2024, 2, 2))
    args = ["export", "-c", str(collection_path), "-d", "Spanish", "--out", str(out)]
    result = runner.invoke(app, [*args, "--until", "2024-02-03"])
    assert result.exit_code == 1
    assert "future" in result.output
    assert not out.exists()


def test_export_until_rejects_invalid_date(collection_path, tmp_path):
    args = ["export", "-c", str(collection_path), "-d", "Spanish", "--out", str(tmp_path)]
    result = runner.invoke(app, [*args, "--until", "02.02.2024"])
    assert result.exit_code != 0


def test_export_without_reviews(collection_path, tmp_path):
    out = tmp_path / "frames"
    result = runner.invoke(
        app, ["export", "-c", str(collection_path), "-d", "Spanish", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert "No reviews in Spanish" in result.output
    assert not out.exists()


def test_export_requires_out(collection_path):
    result = runner.invoke(app, ["export", "-c", str(collection_path), "-d", "Spanish"])
    assert result.exit_code != 0


def _write_frames(directory, names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        imageio.imwrite(directory / name, np.full((32, 32, 4), 255, dtype=np.uint8))


def test_video_writes_mp4(tmp_path):
    frames = tmp_path / "frames"
    _write_frames(frames, ["2024-01-01.png", "2024-01-02.png", "2024-01-03.png"])
    out = tmp_path / "progress.mp4"
    result = runner.invoke(app, ["video", "--in", str(frames), "--out", str(out), "--fps", "5"])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "Wrote 3 frames" in result.output
    assert str(out) in result.output


def test_video_default_output_in_input_dir(tmp_path, monkeypatch):
    frames = tmp_path / "frames"
    _write_frames(frames, ["2024-01-01.png"])
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["video", "--in", str(frames)])
    assert result.exit_code == 0, result.output
    assert (frames / "progress.mp4").exists()
    assert not (tmp_path / "progress.mp4").exists()
    assert "Wrote 1 frame " in result.output
    assert str(frames / "progress.mp4") in result.output


def test_video_date_range(tmp_path):
    frames = tmp_path / "frames"
    _write_frames(frames, [f"2024-01-0{d}.png" for d in (1, 2, 3, 4)])
    out = tmp_path / "v.mp4"
    args = ["video", "--in", str(frames), "--out", str(out)]
    result = runner.invoke(app, [*args, "--from", "2024-01-02", "--until", "2024-01-03"])
    assert result.exit_code == 0, result.output
    assert "Wrote 2 frames" in result.output


def test_video_custom_background(tmp_path):
    frames = tmp_path / "frames"
    _write_frames(frames, ["2024-01-01.png"])
    out = tmp_path / "v.mp4"
    args = ["video", "--in", str(frames), "--out", str(out), "--background", "#000000"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output


def test_video_invalid_background(tmp_path):
    frames = tmp_path / "frames"
    _write_frames(frames, ["2024-01-01.png"])
    args = ["video", "--in", str(frames), "--out", str(tmp_path / "v.mp4")]
    result = runner.invoke(app, [*args, "--background", "no-such-colour"])
    assert result.exit_code != 0
    assert "no-such-colour" in result.output


def test_video_empty_dir_reports_error(tmp_path):
    out = tmp_path / "v.mp4"
    result = runner.invoke(app, ["video", "--in", str(tmp_path), "--out", str(out)])
    assert result.exit_code == 1
    assert "YYYY-MM-DD.png" in result.output
    assert not out.exists()


def test_video_requires_in(tmp_path):
    result = runner.invoke(app, ["video", "--out", str(tmp_path / "v.mp4")])
    assert result.exit_code != 0


def test_video_rejects_zero_fps(tmp_path):
    frames = tmp_path / "frames"
    _write_frames(frames, ["2024-01-01.png"])
    result = runner.invoke(app, ["video", "--in", str(frames), "--fps", "0"])
    assert result.exit_code != 0


def test_module_is_executable():
    result = subprocess.run(
        [sys.executable, "-m", "ankivis", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "decks" in result.stdout
