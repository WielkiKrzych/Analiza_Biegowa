"""Ventilation utility functions — time parsing and formatting."""

from __future__ import annotations


def _parse_time_to_seconds(t_str):
    """Parse time string (hh:mm:ss or mm:ss) to seconds."""
    try:
        parts = list(map(int, t_str.split(":")))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 1:
            return parts[0]
    except (ValueError, AttributeError):
        return None
    return None


def _format_time(s):
    """Format seconds to hh:mm:ss or mm:ss string."""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"
