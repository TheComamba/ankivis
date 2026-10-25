"""Render a deck's intervals on one day as a pie chart PNG.

Cards are sorted by interval so that the colours flow as a smooth gradient around the pie.
Cards with the same interval are merged into one wedge. Unlearned cards form a transparent
wedge at the end. The image has a transparent background and a fixed size, so that the
frames of a video all match.
"""

from collections import Counter
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle

from ankivis.colors import interval_color

FIGSIZE = (8.0, 8.0)  # inches
DPI = 100
TEXT_COLOR = "#333333"
OUTLINE_COLOR = "#999999"

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
    return f"{heading}\n{total} {noun}, {learned} learned"


def build_figure(
    intervals: Mapping[int, float | None], day: date, title: str | None = None
) -> Figure:
    """Build (without saving) the pie chart figure for *intervals* on *day*."""
    fig = Figure(figsize=FIGSIZE, dpi=DPI)
    FigureCanvasAgg(fig)
    fig.patch.set_alpha(0.0)
    fig.suptitle(_title(intervals, day, title), color=TEXT_COLOR, fontsize=16)

    ax = fig.add_axes((0.05, 0.02, 0.9, 0.86))
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
            counterclock=False,
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
    return fig


def render_pie(
    intervals: Mapping[int, float | None],
    day: date,
    path: Path | str,
    title: str | None = None,
) -> Path:
    """Render the pie chart for *intervals* on *day* to the PNG file *path* and return it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = build_figure(intervals, day, title)
    fig.savefig(path, dpi=DPI, transparent=True, format="png")
    return path
