"""Render a deck's intervals on one day as a pie chart PNG.

Cards are sorted by interval so that the colours flow as a smooth gradient around the pie.
Cards with the same interval are merged into one wedge. Unlearned cards form a transparent
wedge at the end. A legend below the pie shows the colours of representative intervals; its
entries do not depend on the data. The image is square with a transparent background and a
fixed size (configurable, :data:`DEFAULT_SIZE` pixels by default), so that the frames of a
video all match. The whole layout, including text, scales with the size.
"""

from collections import Counter
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Patch

from ankivis.colors import MAX_INTERVAL, MIN_INTERVAL, interval_color

FIGSIZE = (8.0, 8.0)  # inches; the layout (font sizes, line widths) is designed for this
DPI = 100
DEFAULT_SIZE = round(FIGSIZE[0] * DPI)  # pixels (width = height)
MIN_SIZE = 100
TEXT_COLOR = "#333333"
OUTLINE_COLOR = "#999999"

# Representative intervals (days) shown in the legend; ``None`` = unlearned.
LEGEND_ENTRIES: tuple[tuple[float | None, str], ...] = (
    (MIN_INTERVAL, f"≤ {MIN_INTERVAL} day"),
    (7, "1 week"),
    (30, "1 month"),
    (90, "3 months"),
    (365, "1 year"),
    (MAX_INTERVAL, "≥ 2 years"),
    (None, "unlearned"),
)

Segment = tuple[float | None, int]


def pie_segments(intervals: Mapping[int, float | None]) -> list[Segment]:
    """Group cards by interval: ``[(interval, card count), ...]`` sorted ascending.

    Unlearned cards (``None``) come last.
    """
    counts = Counter(intervals.values())
    learned = sorted((ivl, n) for ivl, n in counts.items() if ivl is not None)
    if None in counts:
        learned.append((None, counts[None]))
    return learned


def _title(intervals: Mapping[int, float | None], day: date, title: str | None) -> str:
    total = len(intervals)
    learned = sum(1 for ivl in intervals.values() if ivl is not None)
    heading = day.isoformat() if title is None else f"{title} – {day.isoformat()}"
    noun = "card" if total == 1 else "cards"
    percent = 100 * learned / total if total else 0.0
    return f"{heading}\n{total} {noun}, {learned} learned ({percent:.0f}%)"


def _add_legend(fig: Figure) -> None:
    """Add the fixed interval → colour legend at the bottom of *fig*."""
    handles = [
        Patch(
            facecolor=interval_color(ivl),
            edgecolor=OUTLINE_COLOR if ivl is None else interval_color(ivl),
            label=label,
        )
        for ivl, label in LEGEND_ENTRIES
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=11,
        labelcolor=TEXT_COLOR,
        bbox_to_anchor=(0.5, 0.0),
    )


def size_dpi(size: int) -> float:
    """DPI that renders the :data:`FIGSIZE` figure as a *size* × *size* pixel image.

    Scaling the DPI instead of the figure keeps all proportions, including text. The figure
    is 8 inches wide, so ``size / 8`` is exact in floating point and no pixel is lost.
    """
    if size < MIN_SIZE:
        raise ValueError(f"Image size must be at least {MIN_SIZE} px, got {size}")
    return size / FIGSIZE[0]


def build_figure(
    intervals: Mapping[int, float | None],
    day: date,
    title: str | None = None,
    size: int = DEFAULT_SIZE,
) -> Figure:
    """Build (without saving) the *size* × *size* px pie chart figure for *intervals* on *day*."""
    fig = Figure(figsize=FIGSIZE, dpi=size_dpi(size))
    FigureCanvasAgg(fig)
    fig.patch.set_alpha(0.0)
    fig.suptitle(_title(intervals, day, title), color=TEXT_COLOR, fontsize=16)

    # Pie centred at the figure centre, leaving room for the title above and legend below.
    ax = fig.add_axes((0.1, 0.12, 0.8, 0.76))
    ax.set_aspect("equal")
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.axis("off")
    ax.patch.set_alpha(0.0)

    segments = pie_segments(intervals)
    if segments:
        wedges, _ = ax.pie(
            [count for _, count in segments],
            colors=[interval_color(ivl) for ivl, _ in segments],
            startangle=90,
            counterclock=True,
            wedgeprops={"linewidth": 0.5, "antialiased": True},
        )
        # A thin edge in the wedge's own colour hides antialiasing seams between neighbours.
        for wedge in wedges:
            wedge.set_edgecolor(wedge.get_facecolor())
        # Restore the fixed limits (pie() may change them) so every frame has the same scale.
        ax.set_xlim(-1.05, 1.05)
        ax.set_ylim(-1.05, 1.05)
    # Outline of the whole pie, so that transparent (unlearned) parts remain visible.
    ax.add_patch(Circle((0, 0), 1.0, fill=False, edgecolor=OUTLINE_COLOR, linewidth=1))
    _add_legend(fig)
    return fig


def render_pie(
    intervals: Mapping[int, float | None],
    day: date,
    path: Path | str,
    title: str | None = None,
    size: int = DEFAULT_SIZE,
) -> Path:
    """Render the pie chart for *intervals* on *day* to the PNG file *path* and return it.

    The image is *size* × *size* pixels.
    """
    path = Path(path)
    dpi = size_dpi(size)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = build_figure(intervals, day, title, size)
    fig.savefig(path, dpi=dpi, transparent=True, format="png")
    return path
