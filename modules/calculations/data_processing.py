"""
SRP: Moduł odpowiedzialny za przetwarzanie surowych danych treningowych.

IMPORTANT: Pace is a NONLINEAR metric (sec/km = 1/speed).
Averaging pace with .mean() gives INCORRECT results.
Always convert to speed for averaging, then convert back.
"""

import logging
from typing import Any, Union

import numpy as np
import pandas as pd

from .common import WINDOW_LONG, WINDOW_SHORT, ensure_pandas
from .gap import calculate_gap, calculate_grade, smooth_elevation

logger = logging.getLogger(__name__)


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
    # Always work on a copy to avoid mutating the caller's DataFrame
    df_pd = ensure_pandas(df).copy()

    if "time" not in df_pd.columns:
        df_pd["time"] = np.arange(len(df_pd)).astype(float)
    df_pd["time"] = pd.to_numeric(df_pd["time"], errors="coerce")

    # Remove rows with NaN time before creating index
    df_pd = df_pd.dropna(subset=["time"])

    # Fill missing time values sequentially if there are duplicates or gaps
    if df_pd["time"].isna().any() or len(df_pd) == 0:
        df_pd["time"] = np.arange(len(df_pd)).astype(float)

    df_pd = df_pd.sort_values("time").reset_index(drop=True)

    # Derive pace from speed columns if pace not present
    # Prefer speed_m_s (explicit m/s) over velocity_smooth (ambiguous units)
    if "pace" not in df_pd.columns:
        speed_col = None
        if "speed_m_s" in df_pd.columns:
            speed_col = "speed_m_s"
        elif "velocity_smooth" in df_pd.columns:
            speed_col = "velocity_smooth"
        if speed_col is not None:
            speed_vals = pd.to_numeric(df_pd[speed_col], errors="coerce")
            # speed in m/s → pace in sec/km: pace = 1000 / speed
            speed_safe = speed_vals.replace(0, np.nan)
            df_pd["pace"] = 1000.0 / speed_safe
            logger.info(f"Derived pace from '{speed_col}' column")

    df_pd["time_dt"] = pd.to_timedelta(df_pd["time"], unit="s")

    # Ensure index has no NaN
    df_pd = df_pd[df_pd["time_dt"].notna()]
    df_pd = df_pd.set_index("time_dt")

    num_cols = df_pd.select_dtypes(include=["float64", "int64"]).columns.tolist()
    if num_cols:
        df_pd[num_cols] = df_pd[num_cols].interpolate(method="linear").ffill().bfill()

    # CRITICAL FIX: Handle pace resampling correctly
    # Pace is NONLINEAR (sec/km = 1/speed). Must convert to speed, average, convert back.
    pace_col = "pace" if "pace" in df_pd.columns else None

    if pace_col:
        # Convert pace to speed (m/s) for correct averaging
        pace_valid = df_pd[pace_col].replace(0, np.nan).replace(-np.inf, np.nan)
        speed_backup = 1000.0 / pace_valid  # m/s = 1000m / (sec/km)
        df_pd["_speed_ms"] = speed_backup

    try:
        df_numeric = df_pd.select_dtypes(include=[np.number])
        df_resampled = df_numeric.resample("1s").mean()
        df_resampled = df_resampled.interpolate(method="linear").ffill().bfill()
    except (ValueError, TypeError) as e:
        logger.warning(f"Resampling failed, using raw data: {e}")
        df_resampled = df_pd

    # CRITICAL FIX: Convert speed back to pace after resampling
    if "_speed_ms" in df_resampled.columns:
        speed_avg = df_resampled["_speed_ms"]
        speed_avg = speed_avg.replace(0, np.nan).replace(np.inf, np.nan)
        df_resampled["pace"] = 1000.0 / speed_avg
        df_resampled = df_resampled.drop(columns=["_speed_ms"], errors="ignore")

    df_resampled["time"] = df_resampled.index.total_seconds()
    df_resampled["time_min"] = df_resampled["time"] / 60.0

    # Create smoothed versions of key columns
    smooth_cols = [
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

    for col in smooth_cols:
        if col in df_resampled.columns:
            df_resampled[f"{col}_smooth"] = (
                df_resampled[col].rolling(window=WINDOW_LONG, min_periods=1).mean()
            )
            df_resampled[f"{col}_smooth_5s"] = (
                df_resampled[col].rolling(window=WINDOW_SHORT, min_periods=1).mean()
            )

    # Smooth pace separately (using speed domain for correctness)
    if "pace" in df_resampled.columns:
        pace_raw = df_resampled["pace"].replace(0, np.nan)
        speed_raw = 1000.0 / pace_raw
        speed_smooth = speed_raw.rolling(window=WINDOW_LONG, min_periods=1).mean()
        df_resampled["pace_smooth"] = 1000.0 / speed_smooth.replace(0, np.nan)

    # FEATURE: Calculate GAP (Grade-Adjusted Pace) with smoothed elevation
    if "pace" in df_resampled.columns:
        if "elevation" in df_resampled.columns or "altitude" in df_resampled.columns:
            elev_col = "elevation" if "elevation" in df_resampled.columns else "altitude"
            elev = df_resampled[elev_col].ffill().bfill().values

            # Calculate per-sample horizontal distance (m) from pace
            distance_m = (1000.0 / df_resampled["pace"].replace(0, np.nan)).fillna(0).values

            # Smooth elevation over ~20m horizontal distance to reduce GPS noise
            elev_smooth = smooth_elevation(elev, distance_m, smooth_distance_m=20.0)

            elev_diff = np.diff(elev_smooth, prepend=elev_smooth[0])
            grade = calculate_grade(elev_diff, np.maximum(distance_m, 0.01))
            df_resampled["gap"] = calculate_gap(df_resampled["pace"].values, grade)

    df_resampled = df_resampled.reset_index(drop=True)

    return df_resampled
