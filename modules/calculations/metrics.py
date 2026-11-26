"""Trend calculation for session charts."""

import numpy as np


def calculate_trend(x, y):
    """Calculate linear trend line.

    Args:
        x: X values (usually time)
        y: Y values (metric to trend)

    Returns:
        Array of trend values or None
    """
    try:
        idx = np.isfinite(x) & np.isfinite(y)
        if np.sum(idx) < 2:
            return None
        z = np.polyfit(x[idx], y[idx], 1)
        p = np.poly1d(z)
        return p(x)
    except (ValueError, TypeError, np.linalg.LinAlgError):
        # why: None is already this function's explicit "no trend line" answer
        # - the "fewer than 2 finite points" guard above returns it too.
        return None
