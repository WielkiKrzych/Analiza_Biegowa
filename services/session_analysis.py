"""Shared running metrics and plot data transforms."""

from typing import Any

import numpy as np
import pandas as pd

from modules.calculations.dual_mode import calculate_normalized_pace, calculate_running_stress_score
from modules.calculations.pace import (
    calculate_pace_duration_curve,
    calculate_pace_zones_time,
    estimate_vo2max_from_pace,
)
from modules.config import Config


def mean_moving_pace(pace: pd.Series) -> float | None:
    moving = pace.where(pace.gt(0) & np.isfinite(pace)).dropna()
    return float(1 / (1 / moving).mean()) if not moving.empty else None


def _stat(df: pd.DataFrame, column: str, method: str) -> float | None:
    if column not in df:
        return None
    series = df[column].where(np.isfinite(df[column])).dropna()
    if column in {"heartrate", "cadence", "tymeventilation", "tymebreathrate"}:
        series = series[series.gt(0)]
    return float(getattr(series, method)()) if not series.empty else None


def calculate_session_metrics(df: pd.DataFrame, threshold_pace: float) -> dict[str, Any]:
    duration = float(df["time"].iloc[-1] - df["time"].iloc[0])
    distance = _stat(df, "distance", "max")
    if distance is None or distance <= 0:
        # The frame is sampled every second. Stops contribute zero distance.
        distance = float((1000 / df["pace"].where(df["pace"].gt(0))).sum())
    best_five = calculate_pace_duration_curve(df, durations=[300]).get(300)
    return {
        "duration_sec": duration,
        "distance_km": distance / 1000,
        "avg_pace": mean_moving_pace(df["pace"]),
        "avg_gap": mean_moving_pace(df["gap"]) if "gap" in df else None,
        "normalized_pace": calculate_normalized_pace(df) or None,
        "rss": calculate_running_stress_score(df, threshold_pace, duration),
        "pace_zones": calculate_pace_zones_time(df, threshold_pace),
        "avg_hr": _stat(df, "heartrate", "mean"),
        "max_hr": _stat(df, "heartrate", "max"),
        "avg_cadence": _stat(df, "cadence", "mean"),
        "avg_smo2": _stat(df, "smo2", "mean"),
        "avg_vent": _stat(df, "tymeventilation", "mean"),
        "avg_rr": _stat(df, "tymebreathrate", "mean"),
        "avg_core": _stat(df, "core_temperature", "mean"),
        "avg_rmssd": _stat(df, "rmssd", "mean"),
        "vo2_max_est": estimate_vo2max_from_pace(best_five) if best_five else None,
    }


def apply_smo2_smoothing(df: pd.DataFrame) -> pd.DataFrame:
    """Apply smoothing to SmO2 data if present.

    Args:
        df: DataFrame with optional 'smo2' column

    Returns:
        DataFrame with 'smo2_smooth_ultra' column added if smo2 exists
    """
    if "smo2" in df.columns:
        df = df.copy()  # Avoid SettingWithCopyWarning
        df["smo2_smooth_ultra"] = (
            df["smo2"].rolling(window=Config.ROLLING_WINDOW_60S, center=True, min_periods=1).mean()
        )
    return df


def resample_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Resample DataFrame if it exceeds threshold size.

    Args:
        df: Original DataFrame

    Returns:
        Resampled DataFrame if size > threshold, otherwise original
    """
    if len(df) > Config.RESAMPLE_THRESHOLD:
        return df.iloc[:: Config.RESAMPLE_STEP, :].copy()
    return df
