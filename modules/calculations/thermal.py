"""Recorded CORE heat strain and core temperature statistics."""

from typing import Optional, TypedDict, Union

import numpy as np
import pandas as pd
from scipy.stats import linregress

HSI_BOUNDS = (1.0, 3.0, 7.0)
HSI_LABELS = ("0 do <1", "1 do <3", "3 do <7", "7 do 10")
MAX_HSI_GAP_SECONDS = 30.0


class HeatStrain(TypedDict):
    peak: float
    mean: float | None
    zone_seconds: dict[str, float]


def read_core_hsi(series: pd.Series) -> pd.Series:
    """Keep only the CORE sensor's recorded 0 to 10 values."""
    values = pd.to_numeric(series, errors="coerce")
    return values.where(values.between(0, 10))


def summarize_core_hsi(df: pd.DataFrame) -> HeatStrain | None:
    if "heat_strain_index" not in df:
        return None
    values = read_core_hsi(df["heat_strain_index"])
    time = df["time"].to_numpy(dtype=float)
    valid = values.notna().to_numpy() & np.isfinite(time)
    if not valid.any():
        return None

    observed = values.to_numpy(dtype=float)[valid]
    intervals = np.diff(time[valid])
    intervals = np.where((intervals > 0) & (intervals <= MAX_HSI_GAP_SECONDS), intervals, 0)
    usable = intervals[intervals > 0]
    last = float(np.median(usable)) if usable.size else 0.0
    weights = np.append(intervals, last)
    zones = np.searchsorted(HSI_BOUNDS, observed, side="right")
    return {
        "peak": float(observed.max()),
        "mean": float(np.average(observed, weights=weights)) if weights.sum() else None,
        "zone_seconds": {
            label: float(weights[zones == index].sum()) for index, label in enumerate(HSI_LABELS)
        },
    }


_CORE_TEMP_ZONES = (
    ("normal", 38.0, "#27AE60", "Normal"),
    ("elevated", 38.5, "#F39C12", "Elevated"),
    ("heat_training", 39.0, "#E67E22", "Heat Training"),
    ("caution", 39.5, "#E74C3C", "Caution"),
    ("danger", float("inf"), "#8E44AD", "Danger"),
)


def classify_core_temp_zone(temp_c: float) -> dict:
    """Classify a single core-temperature reading into a thermal zone.

    Zone thresholds are aligned with the CORE body-temperature sensor:
        normal        : < 38.0 C
        elevated      : 38.0 - 38.5 C
        heat_training : 38.5 - 39.0 C
        caution       : 39.0 - 39.5 C
        danger        : > 39.5 C

    Args:
        temp_c: Core temperature in degrees Celsius.

    Returns:
        dict with keys ``zone``, ``color``, ``label``.

    Raises:
        ValueError: If *temp_c* is not a finite number.
    """
    if not np.isfinite(temp_c):
        raise ValueError(f"temp_c must be a finite number, got {temp_c}")

    for zone_name, upper, color, label in _CORE_TEMP_ZONES:
        if temp_c < upper:
            return {"zone": zone_name, "color": color, "label": label}

    # Fallback (should not be reached due to inf sentinel)
    last = _CORE_TEMP_ZONES[-1]
    return {"zone": last[0], "color": last[1], "label": last[3]}


def calculate_core_temp_zones_time(
    core_temp_series: Union[pd.Series, np.ndarray, list],
    sample_rate_hz: float = 1.0,
) -> dict:
    """Calculate time (in seconds) spent in each CORE thermal zone.

    Args:
        core_temp_series: Sequence of core-temperature readings (Celsius).
        sample_rate_hz: Sampling frequency in Hz (default 1 Hz = 1 sample/s).

    Returns:
        dict mapping zone names to cumulative seconds spent in that zone.

    Raises:
        ValueError: If *sample_rate_hz* is not positive.
    """
    if sample_rate_hz <= 0:
        raise ValueError(f"sample_rate_hz must be positive, got {sample_rate_hz}")

    temps = np.asarray(core_temp_series, dtype=np.float64)
    sample_duration = 1.0 / sample_rate_hz

    zone_seconds: dict = {
        "normal": 0.0,
        "elevated": 0.0,
        "heat_training": 0.0,
        "caution": 0.0,
        "danger": 0.0,
    }

    valid_mask = np.isfinite(temps)
    valid_temps = temps[valid_mask]

    for t in valid_temps:
        zone_info = classify_core_temp_zone(t)
        zone_seconds[zone_info["zone"]] += sample_duration

    return {k: round(v, 2) for k, v in zone_seconds.items()}


def calculate_thermal_drift_rate(
    core_temp_series: Union[pd.Series, np.ndarray, list],
    time_series: Optional[Union[pd.Series, np.ndarray, list]] = None,
    steady_state_only: bool = True,
    pace_series: Optional[Union[pd.Series, np.ndarray, list]] = None,
) -> dict:
    """Calculate the rate of core-temperature rise during activity.

    Uses ordinary-least-squares regression of temperature vs elapsed time
    (in minutes).  When *steady_state_only* is ``True`` and a *pace_series*
    is provided, only segments where the coefficient of variation of pace is
    below 10 % are included.

    Args:
        core_temp_series: Core-temperature readings (Celsius).
        time_series: Elapsed-time values (seconds).  If ``None`` a 1 Hz
            sample rate is assumed (i.e. index == seconds).
        steady_state_only: When ``True``, restrict analysis to steady-state
            segments (pace CV < 10 %).
        pace_series: Pace values (e.g. min/km or m/s) used for the
            steady-state filter.

    Returns:
        dict with drift metrics -- see module docstring for full schema.
    """
    temps = np.asarray(core_temp_series, dtype=np.float64)

    if time_series is not None:
        times_s = np.asarray(time_series, dtype=np.float64)
    else:
        times_s = np.arange(len(temps), dtype=np.float64)

    # Build a boolean mask for valid data
    valid_mask = np.isfinite(temps) & np.isfinite(times_s)

    # Steady-state filtering (rolling window CV of pace < 10 %)
    if steady_state_only and pace_series is not None:
        paces = np.asarray(pace_series, dtype=np.float64)
        if len(paces) == len(temps):
            window = min(60, len(paces))
            pace_pd = pd.Series(paces)
            rolling_mean = pace_pd.rolling(window, min_periods=max(1, window // 2)).mean()
            rolling_std = pace_pd.rolling(window, min_periods=max(1, window // 2)).std()
            cv = (rolling_std / rolling_mean).fillna(0).values
            steady_mask = cv < 0.10
            valid_mask = valid_mask & steady_mask

    temps_f = temps[valid_mask]
    times_f = times_s[valid_mask]

    _empty_result = {
        "drift_c_per_min": 0.0,
        "drift_c_per_hour": 0.0,
        "r_squared": 0.0,
        "start_temp": float(temps[0]) if len(temps) > 0 else 0.0,
        "end_temp": float(temps[-1]) if len(temps) > 0 else 0.0,
        "total_rise": 0.0,
        "classification": "normal",
        "interpretation": "Insufficient data for drift analysis.",
    }

    if len(temps_f) < 60:
        return _empty_result

    # Convert seconds to minutes for regression
    times_min = times_f / 60.0

    slope, intercept, r_value, _p_value, _std_err = linregress(times_min, temps_f)
    r_squared = r_value**2

    start_temp = float(temps_f[0])
    end_temp = float(temps_f[-1])
    total_rise = end_temp - start_temp

    drift_c_per_min = slope
    drift_c_per_hour = slope * 60.0

    # Classification based on hourly drift
    abs_drift_h = abs(drift_c_per_hour)
    if abs_drift_h < 0.5:
        classification = "well_adapted"
        interpretation = (
            f"Thermal drift of {drift_c_per_hour:+.2f} C/h indicates good heat adaptation."
        )
    elif abs_drift_h < 1.0:
        classification = "normal"
        interpretation = (
            f"Thermal drift of {drift_c_per_hour:+.2f} C/h is within "
            "the normal range for endurance activity."
        )
    else:
        classification = "heat_sensitive"
        interpretation = (
            f"Thermal drift of {drift_c_per_hour:+.2f} C/h suggests "
            "elevated heat sensitivity -- consider heat acclimation protocols."
        )

    return {
        "drift_c_per_min": round(drift_c_per_min, 5),
        "drift_c_per_hour": round(drift_c_per_hour, 3),
        "r_squared": round(r_squared, 4),
        "start_temp": round(start_temp, 2),
        "end_temp": round(end_temp, 2),
        "total_rise": round(total_rise, 2),
        "classification": classification,
        "interpretation": interpretation,
    }
