"""Combine the daily ``YYYY-MM-DD.png`` images into an MP4 video.

Frames are ordered chronologically by the date in their file name; other files are ignored.
MP4 (H.264) has no alpha channel, so transparent pixels are blended onto a background colour.
The video is first written to a temporary file next to the target, so an interrupted or
failed run never leaves a truncated video behind.
"""

import re
from collections.abc import Callable
from datetime import date
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from matplotlib.colors import to_rgb

DEFAULT_FPS = 10
DEFAULT_BACKGROUND = "white"
FRAME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.png$")

RGB = tuple[int, int, int]


class NoFramesError(Exception):
    """Raised when there are no frames to put into a video."""


def parse_color(value: str) -> RGB:
    """Parse a matplotlib colour (``"white"``, ``"#ff8000"``, ...) into 8-bit RGB.

    Raises ``ValueError`` for unknown colours.
    """
    try:
        rgb = to_rgb(value)
    except ValueError as exc:
        raise ValueError(f"invalid colour: {value}") from exc
    r, g, b = (round(c * 255) for c in rgb)
    return r, g, b


def frame_date(path: Path) -> date | None:
    """Date encoded in a frame's file name, or ``None`` if it is not a ``YYYY-MM-DD.png``."""
    match = FRAME_PATTERN.match(path.name)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def frame_paths(
    img_dir: Path | str, start: date | None = None, end: date | None = None
) -> list[Path]:
    """``YYYY-MM-DD.png`` files in *img_dir*, sorted by date, optionally within [start, end]."""
    img_dir = Path(img_dir)
    if not img_dir.is_dir():
        raise NoFramesError(f"{img_dir} is not a directory")
    frames: list[tuple[date, Path]] = []
    for path in img_dir.iterdir():
        day = frame_date(path)
        if day is None or not path.is_file():
            continue
        if (start is not None and day < start) or (end is not None and day > end):
            continue
        frames.append((day, path))
    return [path for _, path in sorted(frames)]


def flatten(pixels: np.ndarray, background: RGB) -> np.ndarray:
    """Blend an image (grey, grey+alpha, RGB or RGBA) onto *background*; return 8-bit RGB."""
    pixels = np.asarray(pixels)
    if pixels.dtype != np.uint8:
        scale = np.iinfo(pixels.dtype).max if pixels.dtype.kind in "ui" else 1.0
        pixels = np.clip(np.rint(pixels.astype(np.float64) / scale * 255), 0, 255)
        pixels = pixels.astype(np.uint8)
    if pixels.ndim == 2:
        pixels = pixels[:, :, np.newaxis]
    channels = pixels.shape[2]
    if channels in (1, 2):  # grey (+ alpha) → RGB (+ alpha)
        grey = np.repeat(pixels[:, :, :1], 3, axis=2)
        pixels = np.concatenate([grey, pixels[:, :, 1:]], axis=2)
    if pixels.shape[2] == 3:
        return pixels.copy()
    rgb = pixels[:, :, :3].astype(np.float64)
    alpha = pixels[:, :, 3:4].astype(np.float64) / 255.0
    bg = np.asarray(background, dtype=np.float64)
    blended = rgb * alpha + bg * (1.0 - alpha)
    return np.clip(np.rint(blended), 0, 255).astype(np.uint8)


def make_video(
    img_dir: Path | str,
    out_path: Path | str,
    fps: float = DEFAULT_FPS,
    background: RGB = (255, 255, 255),
    start: date | None = None,
    end: date | None = None,
    on_frame: Callable[[Path], object] | None = None,
) -> int:
    """Write the ``YYYY-MM-DD.png`` frames of *img_dir* as an H.264 MP4 to *out_path*.

    Returns the number of frames. *on_frame* is called with each frame's path once it has
    been added. Raises :class:`NoFramesError` if there are no frames and ``ValueError`` for an
    invalid *fps* or frames of different sizes.
    """
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    frames = frame_paths(img_dir, start, end)
    if not frames:
        raise NoFramesError(f"No frames named YYYY-MM-DD.png found in {img_dir}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.name}.partial.mp4")
    try:
        writer = imageio.get_writer(
            tmp_path,
            format="FFMPEG",
            mode="I",
            fps=fps,
            codec="libx264",
            pixelformat="yuv420p",
            macro_block_size=16,
        )
        try:
            shape: tuple[int, ...] | None = None
            for path in frames:
                rgb = flatten(imageio.imread(path), background)
                if shape is None:
                    shape = rgb.shape
                elif rgb.shape != shape:
                    raise ValueError(
                        f"{path.name} is {rgb.shape[1]}×{rgb.shape[0]} px, "
                        f"but the first frame is {shape[1]}×{shape[0]} px"
                    )
                writer.append_data(rgb)
                if on_frame is not None:
                    on_frame(path)
        finally:
            writer.close()
        tmp_path.replace(out_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return len(frames)
