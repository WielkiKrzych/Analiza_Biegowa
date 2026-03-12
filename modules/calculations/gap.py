"""
Grade-Adjusted Pace (GAP) Module.

Adjusts pace for elevation changes to provide equivalent flat pace.
"""

from typing import Union
import numpy as np


def calculate_grade(elevation_change_m, distance_m):
    """Calculate grade percentage. Supports scalars and arrays/Series."""
    elevation_change_m = np.asarray(elevation_change_m, dtype=float)
    distance_m = np.asarray(distance_m, dtype=float)
    return np.where(distance_m > 0, (elevation_change_m / distance_m) * 100, 0.0)


def pace_to_gap_factor(grade: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Calculate GAP adjustment factor for given grade.
    Based on metabolic cost curves.
    Vectorized for numpy array support.
    """
    grade = np.asarray(grade)
    factor = np.where(
        grade >= 0,
        # Uphill: polynomial approximation
        1 - (0.03 * grade) + (0.0005 * grade**2),
        # Downhill: diminishing returns below -10%
        np.where(
            np.abs(grade) <= 10,
            1 + (0.018 * np.abs(grade)) - (0.0004 * np.abs(grade)**2),
            1 + (0.018 * 10) - (0.0004 * 100) + 0.001 * (np.abs(grade) - 10)
        )
    )
    return np.clip(factor, 0.7, 1.3)


def calculate_gap(pace_sec_per_km: Union[float, np.ndarray], grade: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Calculate Grade-Adjusted Pace.
    GAP shows what the pace would be on flat ground equivalent.
    """
    factor = pace_to_gap_factor(grade)
    return pace_sec_per_km * factor
