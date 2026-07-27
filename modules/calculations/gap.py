"""
Grade-Adjusted Pace (GAP) Module.

Adjusts pace for elevation changes to provide equivalent flat pace.
Uses Minetti et al. (2002) metabolic cost model for physiological accuracy.
"""

from typing import Union

import numpy as np

# Minetti et al. (2002) metabolic cost of running on grades.
# Source: "Energy cost of walking and running at extreme uphill and downhill slopes"
# J Appl Physiol 93:1039-1046, 2002.
#
# The paper fits the cost of RUNNING (Cr, J/kg/m) to a 5th-order polynomial of
# the gradient i (as a fraction, valid for -0.45 <= i <= +0.45):
#
#   Cr(i) = 155.4*i^5 - 30.4*i^4 - 43.3*i^3 + 46.3*i^2 + 19.5*i + 3.6
#
# Key physiological features this reproduces (and which a hand-typed table
# easily gets wrong): the cost MINIMUM sits at roughly -20% grade, not near
# flat, and steep downhills (-45%) cost only ~1.1x flat because of eccentric
# braking — they are NOT several times more expensive than flat running.
_MINETTI_GRADE_MIN = -45.0
_MINETTI_GRADE_MAX = 45.0

_MINETTI_GRADES = np.arange(_MINETTI_GRADE_MIN, _MINETTI_GRADE_MAX + 0.5, 0.5, dtype=np.float64)


def _minetti_cr(grade_pct: np.ndarray) -> np.ndarray:
    """Metabolic cost of running [J/kg/m] per Minetti (2002), grade in percent."""
    i = np.asarray(grade_pct, dtype=np.float64) / 100.0
    return 155.4 * i**5 - 30.4 * i**4 - 43.3 * i**3 + 46.3 * i**2 + 19.5 * i + 3.6


_MINETTI_COSTS = _minetti_cr(_MINETTI_GRADES) / _minetti_cr(np.array(0.0))

# Pre-compute: GAP factor = cost_flat / cost_grade
# factor < 1 means uphill -> faster equivalent flat pace (lower sec/km)
# factor > 1 means downhill -> slower equivalent flat pace
_MINETTI_FACTORS = 1.0 / _MINETTI_COSTS


def calculate_grade(elevation_change_m, distance_m):
    """Calculate grade percentage. Supports scalars and arrays/Series."""
    elevation_change_m = np.asarray(elevation_change_m, dtype=float)
    distance_m = np.asarray(distance_m, dtype=float)
    return np.where(distance_m > 0, (elevation_change_m / distance_m) * 100, 0.0)


def smooth_elevation(
    elevation: np.ndarray, distance_m: np.ndarray, smooth_distance_m: float = 20.0
) -> np.ndarray:
    """Smooth elevation data over a horizontal distance window.

    GPS elevation is noisy at 1-second resolution. Smoothing over 10-30m
    horizontal distance reduces grade noise before GAP calculation.

    Args:
        elevation: Raw elevation array
        distance_m: Per-sample horizontal distance array (meters)
        smooth_distance_m: Smoothing window in meters (default: 20m)

    Returns:
        Smoothed elevation array
    """
    elevation = np.asarray(elevation, dtype=float)
    distance_m = np.asarray(distance_m, dtype=float)

    if len(elevation) < 3:
        return elevation.copy()

    # Cumulative distance for distance-based windowing
    cum_dist = np.cumsum(np.abs(distance_m))
    smoothed = np.empty_like(elevation)

    for i in range(len(elevation)):
        # Find indices within smooth_distance_m window centered on i
        center_dist = cum_dist[i]
        half_window = smooth_distance_m / 2.0
        mask = (cum_dist >= center_dist - half_window) & (cum_dist <= center_dist + half_window)
        smoothed[i] = np.mean(elevation[mask])

    return smoothed


def pace_to_gap_factor(grade: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Calculate GAP adjustment factor using Minetti (2002) metabolic cost model.

    The factor converts actual pace to flat-equivalent pace:
      GAP = pace * factor

    For uphill: factor < 1 (actual pace is slow, equivalent flat pace is faster)
    For flat: factor = 1
    For downhill down to ~-20%: factor > 1 and rising (running is cheaper than
        flat, so the flat-equivalent pace is slower); the maximum benefit sits
        at the metabolic minimum near -20%.
    For downhill steeper than ~-20%: factor falls back towards 1 as eccentric
        braking cost rises again (~1.1 at -45%, i.e. close to flat cost).

    Vectorized for numpy array support.
    """
    grade = np.asarray(grade, dtype=float)

    # Clamp grade to the range Minetti's polynomial was fitted on
    grade_clamped = np.clip(grade, _MINETTI_GRADE_MIN, _MINETTI_GRADE_MAX)

    # Interpolate GAP factor from Minetti cost curve
    factor = np.interp(grade_clamped, _MINETTI_GRADES, _MINETTI_FACTORS)

    # Safety clamp. With the correct Minetti curve these bounds are only just
    # reached at the extremes (+45% -> 0.185, -20% -> 2.01), so they act as a
    # guard against bad grade data rather than as a model parameter.
    return np.clip(factor, 0.2, 2.0)


def calculate_gap(
    pace_sec_per_km: Union[float, np.ndarray], grade: Union[float, np.ndarray]
) -> Union[float, np.ndarray]:
    """
    Calculate Grade-Adjusted Pace using Minetti (2002) model.
    GAP shows what the pace would be on flat ground equivalent.
    """
    factor = pace_to_gap_factor(grade)
    return pace_sec_per_km * factor
