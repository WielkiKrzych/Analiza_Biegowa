"""
SRP: Moduł odpowiedzialny za przetwarzanie surowych danych treningowych.

IMPORTANT: Pace is a NONLINEAR metric (sec/km = 1/speed).
Averaging pace with .mean() gives INCORRECT results.
Always convert to speed for averaging, then convert back.
"""

import logging
from typing import Any, List, Union

import numpy as np
import pandas as pd

from .common import WINDOW_LONG, WINDOW_SHORT, ensure_pandas
from .gap import calculate_gap, calculate_grade, smooth_elevation

logger = logging.getLogger(__name__)

SMOOTH_COLS: List[str] = [
    "watts",
    "heartrate",
    "cadence",
    "smo2",
    "torque",
    "core_temperature",
    "skin_temperature",
    "velocity_smooth",
    "tymebreathrate",
    "tymeventilation",
    "thb",
    "o2hb",
    "hhb",
]


def _prepare_time_index(df_pd: pd.DataFrame) -> pd.DataFrame:
    """Ensure time column exists, is numeric, sorted, and set as timedelta index."""
    if "time" not in df_pd.columns:
        df_pd["time"] = np.arange(len(df_pd)).astype(float)
    df_pd["time"] = pd.to_numeric(df_pd["time"], errors="coerce")

    df_pd = df_pd.dropna(subset=["time"])

    if df_pd["time"].isna().any() or len(df_pd) == 0:
        df_pd["time"] = np.arange(len(df_pd)).astype(float)

    df_pd = df_pd.sort_values("time").reset_index(drop=True)

    if "pace" not in df_pd.columns:
        speed_col = None
        if "speed_m_s" in df_pd.columns:
            speed_col = "speed_m_s"
        elif "velocity_smooth" in df_pd.columns:
            speed_col = "velocity_smooth"
        if speed_col is not None:
            speed_vals = pd.to_numeric(df_pd[speed_col], errors="coerce")
            speed_safe = speed_vals.replace(0, np.nan)
            df_pd["pace"] = 1000.0 / speed_safe
            logger.info(f"Derived pace from '{speed_col}' column")

    df_pd["time_dt"] = pd.to_timedelta(df_pd["time"], unit="s")
    df_pd = df_pd[df_pd["time_dt"].notna()]
    df_pd = df_pd.set_index("time_dt")

    num_cols = df_pd.select_dtypes(include=["float64", "int64"]).columns.tolist()
    if num_cols:
        df_pd[num_cols] = df_pd[num_cols].interpolate(method="linear").ffill().bfill()

    return df_pd


def _resample_with_pace(df_pd: pd.DataFrame) -> pd.DataFrame:
    """Resample to 1s intervals, correctly handling nonlinear pace via speed domain."""
    if "pace" in df_pd.columns:
        pace_valid = df_pd["pace"].replace(0, np.nan).replace(-np.inf, np.nan)
        df_pd["_speed_ms"] = 1000.0 / pace_valid

    try:
        df_numeric = df_pd.select_dtypes(include=[np.number])
        df_resampled = df_numeric.resample("1s").mean()
        df_resampled = df_resampled.interpolate(method="linear").ffill().bfill()
    except (ValueError, TypeError) as e:
        logger.warning(f"Resampling failed, using raw data: {e}")
        df_resampled = df_pd

    if "_speed_ms" in df_resampled.columns:
        speed_avg = df_resampled["_speed_ms"].replace(0, np.nan).replace(np.inf, np.nan)
        df_resampled["pace"] = 1000.0 / speed_avg
        df_resampled = df_resampled.drop(columns=["_speed_ms"], errors="ignore")

    return df_resampled


def _apply_smoothing(df_resampled: pd.DataFrame) -> pd.DataFrame:
    """Create smoothed versions of key columns including pace."""
    for col in SMOOTH_COLS:
        if col in df_resampled.columns:
            df_resampled[f"{col}_smooth"] = (
                df_resampled[col].rolling(window=WINDOW_LONG, min_periods=1).mean()
            )
            df_resampled[f"{col}_smooth_5s"] = (
                df_resampled[col].rolling(window=WINDOW_SHORT, min_periods=1).mean()
            )

    if "pace" in df_resampled.columns:
        pace_raw = df_resampled["pace"].replace(0, np.nan)
        speed_raw = 1000.0 / pace_raw
        speed_smooth = speed_raw.rolling(window=WINDOW_LONG, min_periods=1).mean()
        df_resampled["pace_smooth"] = 1000.0 / speed_smooth.replace(0, np.nan)

    return df_resampled


def _calculate_gap_if_available(df_resampled: pd.DataFrame) -> pd.DataFrame:
    """Calculate GAP (Grade-Adjusted Pace) when elevation data is present."""
    if "pace" not in df_resampled.columns:
        return df_resampled

    has_elev = "elevation" in df_resampled.columns or "altitude" in df_resampled.columns
    if not has_elev:
        return df_resampled

    elev_col = "elevation" if "elevation" in df_resampled.columns else "altitude"
    elev = df_resampled[elev_col].ffill().bfill().values

    distance_m = (1000.0 / df_resampled["pace"].replace(0, np.nan)).fillna(0).values

    elev_smooth = smooth_elevation(elev, distance_m, smooth_distance_m=20.0)

    elev_diff = np.diff(elev_smooth, prepend=elev_smooth[0])
    grade = calculate_grade(elev_diff, np.maximum(distance_m, 0.01))
    df_resampled["gap"] = calculate_gap(df_resampled["pace"].values, grade)

    return df_resampled


def process_data(df: Union[pd.DataFrame, Any]) -> pd.DataFrame:
    """Process raw data: resample, smooth, and add time columns.

    This function:
    1. Ensures time column exists and is numeric
    2. Resamples to 1 second intervals (CORRECTLY handling nonlinear pace)
    3. Interpolates missing values
    4. Creates smoothed versions of key metrics (including pace)
    5. Calculates GAP (Grade-Adjusted Pace) with smoothed elevation

    Args:
        df: Raw DataFrame from CSV/file

    Returns:
        Processed DataFrame ready for analysis
    """
    df_pd = ensure_pandas(df).copy()
    df_pd = _prepare_time_index(df_pd)
    df_resampled = _resample_with_pace(df_pd)

    df_resampled["time"] = df_resampled.index.total_seconds()
    df_resampled["time_min"] = df_resampled["time"] / 60.0

    df_resampled = _apply_smoothing(df_resampled)
    df_resampled = _calculate_gap_if_available(df_resampled)
    df_resampled = df_resampled.reset_index(drop=True)

    return df_resampled
