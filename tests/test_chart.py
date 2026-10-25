"""Tests for pie chart rendering (``ankivis.chart``)."""

import math
from datetime import date

import matplotlib.image
import pytest
from matplotlib.patches import Wedge

from ankivis.chart import (
    DEFAULT_SIZE,
    DPI,
    FIGSIZE,
    LEGEND_ENTRIES,
    MIN_SIZE,
    build_figure,
    pie_segments,
    render_pie,
)
from ankivis.colors import interval_color

DAY = date(2024, 3, 10)
WIDTH, HEIGHT = round(FIGSIZE[0] * DPI), round(FIGSIZE[1] * DPI)


def wedges(fig) -> list[Wedge]:
    (ax,) = fig.axes
    return [p for p in ax.patches if isinstance(p, Wedge)]


def wedge_span(wedge: Wedge) -> float:
    return (wedge.theta2 - wedge.theta1) % 360 or 360.0


def test_segments_are_sorted_and_grouped():
    intervals = {1: 30.0, 2: None, 3: 0.01, 4: 30.0, 5: 730.0, 6: None, 7: 2.0}
    assert pie_segments(intervals) == [(0.01, 1), (2.0, 1), (30.0, 2), (730.0, 1), (None, 2)]


def test_segments_of_empty_deck():
    assert pie_segments({}) == []


def test_wedge_colours_follow_sorted_intervals():
    intervals = {10: 400.0, 11: 1.0, 12: None, 13: 20.0, 14: 20.0}
    fig = build_figure(intervals, DAY)
    found = wedges(fig)
    expected = [1.0, 20.0, 400.0, None]
    assert len(found) == len(expected)
    for wedge, ivl in zip(found, expected, strict=True):
        assert wedge.get_facecolor() == pytest.approx(interval_color(ivl))


def test_wedge_sizes_are_proportional_to_card_counts():
    intervals = {1: 5.0, 2: 5.0, 3: 5.0, 4: 50.0}
    spans = [wedge_span(w) for w in wedges(build_figure(intervals, DAY))]
    assert spans == pytest.approx([270.0, 90.0])


def test_title_contains_date_and_counts():
    intervals = {1: 5.0, 2: None, 3: 0.001}
    fig = build_figure(intervals, DAY, title="Spanish")
    text = fig.texts[0].get_text() if fig.texts else fig.axes[0].get_title()
    assert "Spanish" in text
    assert "2024-03-10" in text
    assert "3 cards" in text
    assert "2 learned" in text
    assert "(67%)" in text


def test_title_percentage_without_cards():
    fig = build_figure({}, DAY)
    text = fig.texts[0].get_text() if fig.texts else fig.axes[0].get_title()
    assert "0 cards, 0 learned (0%)" in text


def test_render_creates_png_with_fixed_dimensions(tmp_path):
    out = render_pie({1: 3.0, 2: 100.0, 3: None}, DAY, tmp_path / "day.png")
    assert out == tmp_path / "day.png"
    image = matplotlib.image.imread(out)
    assert image.shape == (HEIGHT, WIDTH, 4)


def test_render_has_transparent_background(tmp_path):
    out = render_pie({1: 3.0}, DAY, tmp_path / "day.png")
    image = matplotlib.image.imread(out)
    assert image[0, 0, 3] == 0.0  # corner pixel outside the pie
    centre = image[HEIGHT // 2, WIDTH // 2]
    assert centre[3] == pytest.approx(1.0)


@pytest.mark.parametrize("intervals", [{}, {1: None, 2: None}], ids=["empty", "unlearned"])
def test_render_without_learned_cards_does_not_crash(tmp_path, intervals):
    out = render_pie(intervals, DAY, tmp_path / "day.png")
    assert matplotlib.image.imread(out).shape == (HEIGHT, WIDTH, 4)


def test_all_unlearned_gives_single_transparent_wedge():
    (wedge,) = wedges(build_figure({1: None, 2: None}, DAY))
    assert wedge.get_facecolor()[3] == 0.0


def test_dimensions_identical_across_days(tmp_path):
    a = render_pie({1: 1.0}, DAY, tmp_path / "a.png")
    b = render_pie({i: float(i) for i in range(1, 2000)}, date(2025, 1, 1), tmp_path / "b.png")
    assert matplotlib.image.imread(a).shape == matplotlib.image.imread(b).shape


@pytest.mark.parametrize("intervals", [{}, {1: 5.0}, {1: None, 2: 400.0}])
def test_legend_maps_intervals_to_colours(intervals):
    fig = build_figure(intervals, DAY)
    (legend,) = fig.legends
    labels = [t.get_text() for t in legend.get_texts()]
    assert labels == [label for _, label in LEGEND_ENTRIES]
    for handle, (ivl, _) in zip(legend.legend_handles, LEGEND_ENTRIES, strict=True):
        assert handle.get_facecolor() == pytest.approx(interval_color(ivl))


def test_render_creates_parent_directories(tmp_path):
    out = render_pie({1: 1.0}, DAY, tmp_path / "nested" / "dir" / "day.png")
    assert out.exists()


def test_default_size_is_800_px():
    assert DEFAULT_SIZE == WIDTH == HEIGHT == 800


@pytest.mark.parametrize("size", [MIN_SIZE, 333, 480, 1080, 1920])
def test_render_with_custom_size(tmp_path, size):
    out = render_pie({1: 3.0, 2: 100.0, 3: None}, DAY, tmp_path / "day.png", size=size)
    image = matplotlib.image.imread(out)
    assert image.shape == (size, size, 4)
    assert image[0, 0, 3] == 0.0
    # Inside the first wedge (90°–210°): at 150°, half the pie radius from the centre. The
    # centre pixel itself is unsuitable: all wedges meet there and antialiasing blends them.
    radius = 0.76 * size / 2.1  # axes height / y-range of the axes
    row = round(size / 2 - 0.5 * radius * math.sin(math.radians(150)))
    col = round(size / 2 + 0.5 * radius * math.cos(math.radians(150)))
    assert image[row, col, 3] == pytest.approx(1.0)


@pytest.mark.parametrize("size", [0, -5, MIN_SIZE - 1])
def test_render_rejects_too_small_size(tmp_path, size):
    with pytest.raises(ValueError, match="at least"):
        render_pie({1: 1.0}, DAY, tmp_path / "day.png", size=size)
    assert not (tmp_path / "day.png").exists()
