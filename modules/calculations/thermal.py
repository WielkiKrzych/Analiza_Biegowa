"""Recorded CORE heat strain and core temperature statistics."""

from typing import TypedDict, Union

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


def calculate_thermal_drift_rate(temperature: pd.Series, time_sec: pd.Series) -> float | None:
    """Return the slope in Celsius per hour when the recording is long enough."""
    valid = np.isfinite(temperature) & np.isfinite(time_sec)
    time = time_sec[valid]
    if len(time) < 60 or time.iloc[-1] <= time.iloc[0]:
        return None
    return float(linregress(time, temperature[valid]).slope * 3600)
