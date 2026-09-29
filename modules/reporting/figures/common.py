"""
Common utilities for figure generation.
Independent of UI or FigureConfig class.
"""

import math
import os
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt

DPI = 150

# Static Color Palette (as requested)
COLORS = {
    "power": "#4CAF50",
    "pace": "#00BCD4",  # Cyan/Turquoise for pace (min/km)
    "vt1": "#FFA726",
    "vt2": "#EF5350",
    "smo2": "#42A5F5",
    "cp": "#AB47BC",
    "hr": "#EF5350",
    "ve": "#4CAF50",
    "grid": "#EEEEEE",
    "text": "#2C3E50",
    "secondary": "#999999",
}


def get_color(key: str) -> str:
    """Safely get color from palette with default fallback."""
    return COLORS.get(key, "#999999")


def apply_common_style(fig, ax, **kwargs):
    """Apply standard styling to a figure and primary axis."""
    ax.grid(True, linestyle="--", alpha=0.3, color=get_color("grid"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    title_size = kwargs.get("title_size", 14)
    font_size = kwargs.get("font_size", 10)

    ax.title.set_fontsize(title_size)
    ax.xaxis.label.set_fontsize(font_size)
    ax.yaxis.label.set_fontsize(font_size)


def save_figure(fig, output_path: Optional[str] = None, **kwargs) -> bytes:
    """Save figure to buffer and optionally to file."""
    fmt = kwargs.get("format", "png")
    dpi = kwargs.get("dpi", 150)

    buf = BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    data = buf.getvalue()

    if output_path:
        path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    return data


def json_pace_pairs(
    time_series: Dict[str, Any], target_key: str, min_target: Optional[float] = None
) -> Tuple[List[float], List[float], List[float]]:
    """Pace/target/time triples from the JSON fallback, filtered like the DataFrame branch.

    ``persistence_save._extract_time_series_data`` stores every row, standstills included:
    a stopped athlete has pace 0 (NaN, written as 0), and a missing sensor is a column of
    zeros. The DataFrame branches drop those with ``0 < pace < 1200``; without the same
    filter a PDF regenerated from a saved report draws a different map than the PDF from
    the session that produced it. ``min_target`` is the floor of the branch being mirrored
    (30 bpm for heart rate, 0 for SmO₂, ``None`` when that branch has no floor at all), and
    NaN is dropped the way ``isna()`` drops it there — the three lists are filtered
    together so their indices stay aligned. Pace stays in sec/km, the unit it is stored in;
    the caller converts for display.
    """
    pace_sec = time_series.get("pace_sec_per_km", time_series.get("pace", [])) or []
    target = time_series.get(target_key, []) or []
    times = time_series.get("time_sec", []) or []

    pace_data: List[float] = []
    target_data: List[float] = []
    time_data: List[float] = []
    for index, (pace, value) in enumerate(zip(pace_sec, target, strict=False)):
        if not isinstance(pace, (int, float)) or not isinstance(value, (int, float)):
            continue
        if math.isnan(pace) or math.isnan(value):
            continue
        if not 0 < pace < 1200:
            continue
        if min_target is not None and value <= min_target:
            continue
        pace_data.append(pace)
        target_data.append(value)
        if index < len(times):
            time_data.append(times[index])

    return pace_data, target_data, time_data


def time_to_minutes(values: List[float], column_name: Optional[str] = None) -> List[float]:
    """Minutes, whichever of the accepted time columns supplied the values.

    ``column_name`` is the column they came from, or ``None`` for the JSON's ``time_sec``.
    The DataFrame branches accept ``time_min`` as well as ``time``/``seconds``, while the
    saved JSON only carries seconds — mixing the two colours one run on scales 60 times
    apart. Minutes are the unit both sides can reach without losing the clock: seconds are
    divided, never multiplied back by the 1/60 that produced them.
    """
    if column_name == "time_min":
        return list(values)
    return [value / 60 for value in values]


def create_empty_figure(message: str, title: str, output_path: Optional[str] = None, **kwargs):
    """Create a figure with an error/empty message and optionally save it."""
    figsize = kwargs.get("figsize", (10, 6))
    dpi = kwargs.get("dpi", 150)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color="red")
    ax.set_title(title, fontsize=kwargs.get("title_size", 14), fontweight="bold")
    ax.axis("off")

    if output_path:
        return save_figure(fig, output_path, **kwargs)
    return fig
