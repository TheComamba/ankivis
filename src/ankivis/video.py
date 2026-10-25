"""Combine the daily ``YYYY-MM-DD.png`` images into an MP4 video or an animated GIF.

Frames are ordered chronologically by the date in their file name; other files are ignored.
Neither H.264 MP4 nor (fully) GIF supports an alpha channel, so transparent pixels are blended
onto a background colour. The output is first written to a temporary file next to the target,
so an interrupted or failed run never leaves a truncated file behind.
"""

import re
from collections.abc import Callable, Iterator
from datetime import date
from enum import StrEnum
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from matplotlib.colors import to_rgb
from PIL import Image

DEFAULT_FPS = 10
DEFAULT_BACKGROUND = "white"
FRAME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.png$")
# GIF frame delays are stored in hundredths of a second, and browsers slow down delays
# below 2/100 s, so faster GIFs would not play at the requested speed.
MAX_GIF_FPS = 50

RGB = tuple[int, int, int]


class VideoFormat(StrEnum):
    """Supported output formats; the value doubles as the file extension."""

    MP4 = "mp4"
    GIF = "gif"


class NoFramesError(Exception):
    """Raised when there are no frames to put into a video."""


def resolve_format(out_path: Path | str | None, fmt: VideoFormat | str | None) -> VideoFormat:
    """Pick the output format from *fmt* or, if that is ``None``, from *out_path*'s extension.

    Defaults to MP4. Raises ``ValueError`` if *fmt* is unknown or contradicts a known extension.
    """
    suffix = Path(out_path).suffix.lower().lstrip(".") if out_path is not None else ""
    from_suffix = VideoFormat(suffix) if suffix in set(VideoFormat) else None
    if fmt is None:
        return from_suffix or VideoFormat.MP4
    try:
        chosen = VideoFormat(str(fmt).lower())
    except ValueError as exc:
        choices = ", ".join(f.value for f in VideoFormat)
        raise ValueError(f"unknown format: {fmt} (choose from {choices})") from exc
    if from_suffix is not None and from_suffix != chosen:
        name = Path(out_path).name if out_path is not None else ""
        raise ValueError(f"format {chosen.value} does not match the file name {name}")
    return chosen


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


def gif_durations(count: int, fps: float) -> list[int]:
    """Per-frame GIF delays in milliseconds (multiples of 10) that average out to *fps*.

    GIF stores delays in hundredths of a second, so e.g. 30 fps alternates 30/40 ms delays
    instead of drifting by rounding every frame to the same value.
    """
    ticks = [round(i * 100 / fps) for i in range(count + 1)]
    return [(b - a) * 10 for a, b in zip(ticks, ticks[1:], strict=False)]


def _rgb_frames(
    frames: list[Path], background: RGB, on_frame: Callable[[Path], object] | None
) -> Iterator[np.ndarray]:
    """Yield the flattened frames, checking they all have the same size."""
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
        yield rgb
        if on_frame is not None:
            on_frame(path)


def _write_mp4(rgb_frames: Iterator[np.ndarray], path: Path, fps: float) -> None:
    writer = imageio.get_writer(
        path,
        format="FFMPEG",
        mode="I",
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=16,
    )
    try:
        for rgb in rgb_frames:
            writer.append_data(rgb)
    finally:
        writer.close()


def _write_gif(rgb_frames: Iterator[np.ndarray], path: Path, fps: float, count: int) -> None:
    # Each frame gets its own 256-colour palette. Dithering is off: it makes flat areas
    # shimmer from frame to frame and bloats the file. Frames are converted to palette mode
    # one by one, so only 1 byte per pixel is kept in memory while Pillow assembles the GIF.
    paletted = (
        Image.fromarray(rgb).quantize(colors=256, dither=Image.Dither.NONE) for rgb in rgb_frames
    )
    first = next(paletted)
    first.save(
        path,
        format="GIF",
        save_all=True,
        append_images=paletted,
        duration=gif_durations(count, fps),
        loop=0,  # repeat forever
        optimize=False,
    )


def make_video(
    img_dir: Path | str,
    out_path: Path | str,
    fps: float = DEFAULT_FPS,
    background: RGB = (255, 255, 255),
    start: date | None = None,
    end: date | None = None,
    on_frame: Callable[[Path], object] | None = None,
    fmt: VideoFormat | str | None = None,
) -> int:
    """Write the ``YYYY-MM-DD.png`` frames of *img_dir* as a video to *out_path*.

    *fmt* selects an H.264 MP4 or a looping animated GIF; if ``None`` it is taken from the
    extension of *out_path* (MP4 for anything other than ``.gif``).

    Returns the number of frames. *on_frame* is called with each frame's path once it has
    been added. Raises :class:`NoFramesError` if there are no frames and ``ValueError`` for an
    invalid *fps* or format, or frames of different sizes.
    """
    video_format = resolve_format(out_path, fmt)
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    if video_format is VideoFormat.GIF and fps > MAX_GIF_FPS:
        raise ValueError(f"GIF supports at most {MAX_GIF_FPS} fps, got {fps}")
    frames = frame_paths(img_dir, start, end)
    if not frames:
        raise NoFramesError(f"No frames named YYYY-MM-DD.png found in {img_dir}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.name}.partial.{video_format.value}")
    rgb_frames = _rgb_frames(frames, background, on_frame)
    try:
        if video_format is VideoFormat.GIF:
            _write_gif(rgb_frames, tmp_path, fps, len(frames))
        else:
            _write_mp4(rgb_frames, tmp_path, fps)
        tmp_path.replace(out_path)
    finally:
        rgb_frames.close()
        tmp_path.unlink(missing_ok=True)
    return len(frames)
