"""Continuous time in a speed band."""

import pandas as pd


def compute_tte(speed: pd.Series, target_pct: float, threshold: float, tol_pct: float = 5.0) -> int:
    """Return the longest qualifying sequence in one-second samples."""
    target = threshold * target_pct / 100
    if target <= 0:
        return 0
    in_range = speed.between(target * (1 - tol_pct / 100), target * (1 + tol_pct / 100))
    longest = current = 0
    for valid in in_range:
        current = current + 1 if valid else 0
        longest = max(longest, current)
    return longest


def format_tte(seconds: int) -> str:
    """Format TTE duration to mm:ss string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "05:30")
    """
    if seconds <= 0:
        return "00:00"

    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:02d}:{secs:02d}"
