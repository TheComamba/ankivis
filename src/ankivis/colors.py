"""Map card intervals to colours.

Short intervals are red, long ones blue; in between the colour runs through the rainbow
(red → orange → yellow → green → blue, HSV hue 0° → 240°) on a logarithmic scale, so that
the difference between 1 and 10 days is as visible as the one between 73 and 730 days.
Unlearned cards (``None``) are fully transparent.
"""

import colorsys
import math

RGBA = tuple[float, float, float, float]

MIN_INTERVAL = 1  # days; at or below → red
MAX_INTERVAL = 730  # days (2 years); at or above → blue
MAX_HUE = 240.0  # degrees; blue

TRANSPARENT: RGBA = (0.0, 0.0, 0.0, 0.0)


def interval_hue(ivl: float | None) -> float | None:
    """HSV hue in degrees (0 = red … 240 = blue) for an interval in days, ``None`` if unlearned."""
    if ivl is None:
        return None
    if ivl <= MIN_INTERVAL:
        return 0.0
    if ivl >= MAX_INTERVAL:
        return MAX_HUE
    fraction = math.log(ivl / MIN_INTERVAL) / math.log(MAX_INTERVAL / MIN_INTERVAL)
    return MAX_HUE * fraction


def interval_color(ivl: float | None) -> RGBA:
    """RGBA colour (components in 0…1) for an interval in days; transparent if unlearned."""
    hue = interval_hue(ivl)
    if hue is None:
        return TRANSPARENT
    r, g, b = colorsys.hsv_to_rgb(hue / 360, 1.0, 1.0)
    return (r, g, b, 1.0)
