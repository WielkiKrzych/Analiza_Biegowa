"""
Grade-Adjusted Pace (GAP) Module.

Adjusts pace for elevation changes to provide equivalent flat pace.
Uses Minetti et al. (2002) metabolic cost model for physiological accuracy.
"""

from typing import Union

import numpy as np

# Minetti et al. (2002) metabolic cost of running on grades
# Table: grade (%) -> relative cost compared to flat (cost_grade / cost_0%)
# Source: "Energy cost of walking and running at extreme uphill and downhill slopes"
# J Appl Physiol 93:1039-1046, 2002
_MINETTI_GRADES = np.array(
    [-45, -40, -35, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45],
    dtype=np.float64,
)

_MINETTI_COSTS = np.array(
    [
        5.20,
        4.00,
        3.10,
        2.40,
        1.80,
        1.40,
        1.05,
        0.78,
        0.68,
        1.00,
        1.50,
        2.10,
        2.90,
        3.80,
        4.80,
        5.90,
        7.10,
        8.40,
        9.80,
    ],
    dtype=np.float64,
)

# Pre-compute: GAP factor = cost_flat / cost_grade
# factor < 1 means uphill -> faster equivalent flat pace (lower sec/km)
# factor > 1 means moderate downhill -> slower equivalent flat pace
_MINETTI_FACTORS = _MINETTI_COSTS[9] / _MINETTI_COSTS  # cost_0% / cost_grade


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
    For moderate downhill: factor > 1 (downhill running still costs energy)
    For steep downhill: factor < 1 (very steep downhill is metabolically expensive)

    Vectorized for numpy array support.
    """
    grade = np.asarray(grade, dtype=float)

    # Clamp grade to Minetti table range
    grade_clamped = np.clip(grade, -45, 45)

    # Interpolate GAP factor from Minetti cost table
    factor = np.interp(grade_clamped, _MINETTI_GRADES, _MINETTI_FACTORS)

    # Safety clamp: GAP should not deviate more than 5x from actual pace
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
