"""
Pace utilities for running analysis.

Conversions between pace (min/km) and speed (m/s).
"""

import numpy as np


def pace_to_speed(pace_sec_per_km: float) -> float:
    """
    Convert pace (seconds per km) to speed (m/s).

    Args:
        pace_sec_per_km: Pace in seconds per kilometer

    Returns:
        Speed in meters per second

    Example:
        >>> pace_to_speed(300)  # 5:00 min/km
        3.333...
    """
    if pace_sec_per_km <= 0:
        return 0.0
    # 1000 meters / pace seconds
    return 1000.0 / pace_sec_per_km


def speed_to_pace(speed_m_per_s: float) -> float:
    """
    Convert speed (m/s) to pace (seconds per km).

    Args:
        speed_m_per_s: Speed in meters per second

    Returns:
        Pace in seconds per kilometer

    Example:
        >>> speed_to_pace(3.333)  # 3.33 m/s
        300.0  # 5:00 min/km
    """
    if speed_m_per_s <= 0:
        return float("inf")
    # 1000 meters / speed
    return 1000.0 / speed_m_per_s


def format_pace(pace_sec_per_km: float) -> str:
    """
    Format pace as mm:ss string.

    Args:
        pace_sec_per_km: Pace in seconds per kilometer

    Returns:
        Formatted string like "5:00"
    """
    if pace_sec_per_km <= 0 or not np.isfinite(pace_sec_per_km):
        return "--:--"

    minutes = int(pace_sec_per_km // 60)
    seconds = int(pace_sec_per_km % 60)
    return f"{minutes}:{seconds:02d}"


def pace_to_seconds(pace_str: str) -> float:
    """
    Convert mm:ss string to seconds per km.

    Args:
        pace_str: Pace string like "5:00" or "5:30"

    Returns:
        Seconds per kilometer
    """
    try:
        parts = pace_str.strip().split(":")
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        elif len(parts) == 1:
            return float(parts[0]) * 60  # Assume minutes only
    except (ValueError, IndexError):
        pass
    return 0.0


def seconds_to_pace_str(seconds: float) -> str:
    """
    Convert seconds to mm:ss pace string.

    Args:
        seconds: Seconds per kilometer

    Returns:
        Formatted pace string
    """
    return format_pace(seconds)


def calculate_pace(distance_m: float, time_sec: float) -> float:
    """
    Calculate pace (sec/km) from distance and time.

    Args:
        distance_m: Distance in meters
        time_sec: Time in seconds

    Returns:
        Pace in seconds per kilometer
    """
    if distance_m <= 0 or time_sec <= 0:
        return 0.0
    # pace = time / distance * 1000
    return time_sec / distance_m * 1000


def pace_array_to_speed_array(pace_array: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion of pace array to speed array.

    Args:
        pace_array: Array of paces in sec/km

    Returns:
        Array of speeds in m/s
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        speed = np.where(pace_array > 0, 1000.0 / pace_array, 0.0)
    return speed


def speed_array_to_pace_array(speed_array: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion of speed array to pace array.

    Args:
        speed_array: Array of speeds in m/s

    Returns:
        Array of paces in sec/km
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        pace = np.where(speed_array > 0, 1000.0 / speed_array, np.inf)
    return pace
