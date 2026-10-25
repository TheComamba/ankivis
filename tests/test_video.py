from datetime import date
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest
from PIL import Image

from ankivis.video import (
    NoFramesError,
    VideoFormat,
    flatten,
    frame_paths,
    gif_durations,
    make_video,
    parse_color,
    resolve_format,
)

SIZE = 32  # divisible by 16, so the encoder does not resize the frames


def _frame(path: Path, rgba: tuple[int, int, int, int], size: int = SIZE) -> Path:
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[:, :] = rgba
    imageio.imwrite(path, pixels)
    return path


def _read_frames(path: Path) -> list[np.ndarray]:
    reader = imageio.get_reader(path)
    try:
        return [np.asarray(frame) for frame in reader]
    finally:
        reader.close()


def test_frame_paths_sorted_chronologically_and_ignores_other_files(tmp_path):
    for name in ("2024-03-02.png", "2024-02-28.png", "2024-03-01.png"):
        _frame(tmp_path / name, (255, 0, 0, 255))
    (tmp_path / "notes.txt").write_text("hi")
    _frame(tmp_path / "cover.png", (0, 0, 0, 255))
    _frame(tmp_path / "2024-02-30.png", (0, 0, 0, 255))  # not a real date
    _frame(tmp_path / "2024-3-5.png", (0, 0, 0, 255))  # not zero-padded
    (tmp_path / "2024-03-03.png").mkdir()  # a directory, not a frame
    paths = frame_paths(tmp_path)
    assert [p.name for p in paths] == ["2024-02-28.png", "2024-03-01.png", "2024-03-02.png"]


def test_frame_paths_date_range(tmp_path):
    for day in (1, 2, 3, 4):
        _frame(tmp_path / f"2024-03-0{day}.png", (255, 0, 0, 255))
    paths = frame_paths(tmp_path, start=date(2024, 3, 2), end=date(2024, 3, 3))
    assert [p.name for p in paths] == ["2024-03-02.png", "2024-03-03.png"]


def test_flatten_blends_alpha_onto_background():
    rgba = np.array(
        [[[255, 0, 0, 255], [0, 0, 255, 0], [0, 0, 0, 128]]],
        dtype=np.uint8,
    )
    rgb = flatten(rgba, (255, 255, 255))
    assert rgb.dtype == np.uint8
    assert rgb.shape == (1, 3, 3)
    assert rgb[0, 0].tolist() == [255, 0, 0]
    assert rgb[0, 1].tolist() == [255, 255, 255]
    assert rgb[0, 2].tolist() == [127, 127, 127]


def test_flatten_accepts_rgb_and_grayscale():
    rgb = np.full((2, 2, 3), 7, dtype=np.uint8)
    assert flatten(rgb, (0, 0, 0)).tolist() == rgb.tolist()
    gray = np.full((2, 2), 9, dtype=np.uint8)
    assert flatten(gray, (0, 0, 0)).shape == (2, 2, 3)


def test_parse_color():
    assert parse_color("white") == (255, 255, 255)
    assert parse_color("#000000") == (0, 0, 0)
    assert parse_color("#ff8000") == (255, 128, 0)
    with pytest.raises(ValueError):
        parse_color("no-such-colour")


def test_make_video_writes_all_frames(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    _frame(frames / "2024-01-01.png", (255, 0, 0, 255))
    _frame(frames / "2024-01-02.png", (0, 0, 255, 0))  # fully transparent
    _frame(frames / "2024-01-03.png", (0, 0, 255, 255))
    (frames / "readme.txt").write_text("ignored")
    out = tmp_path / "progress.mp4"

    count = make_video(frames, out, fps=5, background=(255, 255, 255))

    assert count == 3
    assert out.exists()
    read = _read_frames(out)
    assert len(read) == 3
    assert read[0].shape == (SIZE, SIZE, 3)
    # Lossy codec: compare the centre pixel with a tolerance.
    centre = SIZE // 2
    red, white, blue = (f[centre, centre].astype(int) for f in read)
    assert red[0] > 200 and red[1] < 60 and red[2] < 60
    assert all(c > 200 for c in white)  # transparency flattened onto white
    assert blue[2] > 200 and blue[0] < 60 and blue[1] < 60


def test_make_video_fps(tmp_path):
    _frame(tmp_path / "2024-01-01.png", (255, 0, 0, 255))
    _frame(tmp_path / "2024-01-02.png", (255, 0, 0, 255))
    out = tmp_path / "out" / "video.mp4"  # parent directory is created
    make_video(tmp_path, out, fps=4)
    reader = imageio.get_reader(out)
    try:
        assert reader.get_meta_data()["fps"] == pytest.approx(4)
    finally:
        reader.close()


def test_make_video_empty_dir_raises(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    out = tmp_path / "video.mp4"
    with pytest.raises(NoFramesError, match="YYYY-MM-DD.png"):
        make_video(tmp_path, out)
    assert not out.exists()


def test_make_video_missing_dir_raises(tmp_path):
    with pytest.raises(NoFramesError, match="not a directory"):
        make_video(tmp_path / "missing", tmp_path / "video.mp4")


def test_make_video_rejects_mismatched_frame_sizes(tmp_path):
    _frame(tmp_path / "2024-01-01.png", (255, 0, 0, 255))
    _frame(tmp_path / "2024-01-02.png", (255, 0, 0, 255), size=48)
    out = tmp_path / "video.mp4"
    with pytest.raises(ValueError, match="2024-01-02.png"):
        make_video(tmp_path, out)
    assert not out.exists()


def test_make_video_rejects_invalid_fps(tmp_path):
    _frame(tmp_path / "2024-01-01.png", (255, 0, 0, 255))
    with pytest.raises(ValueError, match="fps"):
        make_video(tmp_path, tmp_path / "video.mp4", fps=0)


def test_make_video_reports_progress(tmp_path):
    for day in (1, 2, 3):
        _frame(tmp_path / f"2024-01-0{day}.png", (255, 0, 0, 255))
    seen: list[Path] = []
    make_video(tmp_path, tmp_path / "video.mp4", on_frame=seen.append)
    assert [p.name for p in seen] == ["2024-01-01.png", "2024-01-02.png", "2024-01-03.png"]


def test_resolve_format():
    assert resolve_format("a.mp4", None) is VideoFormat.MP4
    assert resolve_format("a.GIF", None) is VideoFormat.GIF
    assert resolve_format("a.bin", None) is VideoFormat.MP4
    assert resolve_format(None, None) is VideoFormat.MP4
    assert resolve_format(None, "gif") is VideoFormat.GIF
    assert resolve_format("a.bin", "GIF") is VideoFormat.GIF
    assert resolve_format("a.gif", VideoFormat.GIF) is VideoFormat.GIF
    with pytest.raises(ValueError, match="does not match"):
        resolve_format("a.mp4", "gif")
    with pytest.raises(ValueError, match="unknown format"):
        resolve_format("a.mp4", "avi")


def test_gif_durations_average_to_fps():
    assert gif_durations(3, 10) == [100, 100, 100]
    durations = gif_durations(30, 30)
    assert set(durations) == {30, 40}
    assert sum(durations) == 1000
    assert gif_durations(0, 10) == []


def test_make_video_writes_gif(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    _frame(frames / "2024-01-01.png", (255, 0, 0, 255))
    _frame(frames / "2024-01-02.png", (0, 0, 255, 0))  # fully transparent
    _frame(frames / "2024-01-03.png", (0, 0, 255, 255))
    out = tmp_path / "progress.gif"
    seen: list[Path] = []

    count = make_video(frames, out, fps=5, background=(255, 255, 255), on_frame=seen.append)

    assert count == 3
    assert len(seen) == 3
    assert not list(tmp_path.glob(".*partial*"))
    with Image.open(out) as gif:
        assert gif.format == "GIF"
        assert gif.n_frames == 3
        assert gif.info.get("loop") == 0
        colours, durations = [], []
        for i in range(gif.n_frames):
            gif.seek(i)
            durations.append(gif.info["duration"])
            colours.append(gif.convert("RGB").getpixel((SIZE // 2, SIZE // 2)))
    assert colours == [(255, 0, 0), (255, 255, 255), (0, 0, 255)]
    assert durations == [200, 200, 200]


def test_make_video_gif_with_explicit_format(tmp_path):
    _frame(tmp_path / "2024-01-01.png", (0, 255, 0, 255))
    out = tmp_path / "out" / "anim.bin"
    make_video(tmp_path, out, fmt="gif")
    assert out.read_bytes()[:6] == b"GIF89a"


def test_make_video_gif_rejects_mismatched_frame_sizes(tmp_path):
    _frame(tmp_path / "2024-01-01.png", (255, 0, 0, 255))
    _frame(tmp_path / "2024-01-02.png", (255, 0, 0, 255), size=48)
    out = tmp_path / "video.gif"
    with pytest.raises(ValueError, match="2024-01-02.png"):
        make_video(tmp_path, out)
    assert not out.exists()
    assert not list(tmp_path.glob(".*partial*"))


def test_make_video_gif_rejects_too_high_fps(tmp_path):
    _frame(tmp_path / "2024-01-01.png", (255, 0, 0, 255))
    with pytest.raises(ValueError, match="GIF"):
        make_video(tmp_path, tmp_path / "video.gif", fps=60)
