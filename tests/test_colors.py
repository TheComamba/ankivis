"""Tests for mapping intervals to colours (``ankivis.colors``)."""

import colorsys
import math

import pytest

from ankivis.colors import MAX_INTERVAL, MIN_INTERVAL, interval_color, interval_hue

RED = (1.0, 0.0, 0.0, 1.0)
BLUE = (0.0, 0.0, 1.0, 1.0)


def hue_of(rgba: tuple[float, float, float, float]) -> float:
    """Hue in degrees of an RGBA colour."""
    return colorsys.rgb_to_hsv(*rgba[:3])[0] * 360


def test_unlearned_is_fully_transparent():
    assert interval_color(None)[3] == 0.0


@pytest.mark.parametrize("ivl", [0.0, 1 / 1440, 0.5, 1.0, MIN_INTERVAL])
def test_short_intervals_are_red(ivl):
    assert interval_color(ivl) == pytest.approx(RED)


@pytest.mark.parametrize("ivl", [MAX_INTERVAL, 730.0, 731.0, 5000.0])
def test_long_intervals_are_blue(ivl):
    assert interval_color(ivl) == pytest.approx(BLUE)


def test_boundaries():
    assert MIN_INTERVAL == 1
    assert MAX_INTERVAL == 730  # 2 years


def test_learned_colours_are_opaque_and_saturated():
    for ivl in [1, 2, 5, 10, 30, 100, 300, 730]:
        r, g, b, a = interval_color(ivl)
        assert a == 1.0
        _, s, v = colorsys.rgb_to_hsv(r, g, b)
        assert s == pytest.approx(1.0)
        assert v == pytest.approx(1.0)


def test_hue_is_monotonic():
    samples = [1 + i * 0.73 for i in range(1000)]
    hues = [interval_hue(ivl) for ivl in samples]
    assert all(a <= b for a, b in zip(hues, hues[1:], strict=False))
    assert hues[0] == 0.0
    assert hues[-1] == pytest.approx(240.0)


def test_hue_of_colour_matches_interval_hue():
    for ivl in [1.5, 3, 20, 99, 400]:
        assert hue_of(interval_color(ivl)) == pytest.approx(interval_hue(ivl), abs=1e-6)


def test_hue_is_log_scaled():
    # The geometric midpoint of 1 and 730 is at half the hue range (green-ish, 120°).
    assert interval_hue(math.sqrt(MAX_INTERVAL)) == pytest.approx(120.0)
    # Rainbow order: orange before yellow before green before blue.
    assert 0 < interval_hue(2) < 60 < interval_hue(100) < 240


def test_hue_of_unlearned_is_none():
    assert interval_hue(None) is None
