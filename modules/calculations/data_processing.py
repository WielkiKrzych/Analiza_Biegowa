"""
Raw data processing pipeline (thin orchestrator, P2-2 audit v2).

Original 165-line module split into:
  - `time_index.py`  — time column normalization, pace derivation
  - `smooth.py`      — rolling-window smoothing (incl. pace-in-speed-domain)
  - `gap.py`         — Grade-Adjusted Pace (was already separate)
  - this file        — resampling + glue

Steps:
  1. `prepare_time_index` — normalize time, derive pace from speed
  2. `resample_with_pace` — resample to 1 s in the SPEED domain
  3. `apply_smoothing`    — add _smooth / _smooth_5s columns
  4. `calculate_gap`      — grade-adjusted pace (when elevation present)
  5. reset index, return

IMPORTANT: Pace is a NONLINEAR metric (sec/km = 1/speed).
Averaging pace with .mean() gives INCORRECT results. Always convert to
speed for averaging, then convert back.
"""

import logging
from typing import Any, Union

import numpy as np
import pandas as pd

from .common import ensure_pandas
from .gap import calculate_gap, calculate_grade, smooth_elevation
from .smooth import apply_smoothing
from .time_index import prepare_time_index

logger = logging.getLogger(__name__)


def resample_with_pace(df_pd: pd.DataFrame) -> pd.DataFrame:
    """Resample to 1s intervals, correctly handling nonlinear pace via speed domain.

    P2-2: this used to be `_resample_with_pace` (private). Now public so
    it can be unit-tested directly without going through `process_data`.

    Does not mutate *df_pd*: the `_speed_ms` scratch column is written to a
    copy, so it cannot leak into a caller-owned frame.
    """
    df_pd = df_pd.copy()

    if "pace" in df_pd:
        pace = df_pd["pace"]
        df_pd["_speed_ms"] = (1000.0 / pace.where(pace.gt(0))).fillna(0)
    df_numeric = df_pd.select_dtypes(include=[np.number])
    grid = df_numeric.resample("1s").mean()
    df_resampled = grid.interpolate(method="linear", limit=5, limit_area="inside")

    if "_speed_ms" in grid:
        speed = grid["_speed_ms"]
        missing = speed.isna()
        gap_length = missing.groupby((~missing).cumsum()).transform("sum")
        # A few missed GPS samples can be interpolated. A pause stays at zero.
        speed = df_resampled.pop("_speed_ms").where(gap_length <= 5, 0).fillna(0)
        df_resampled["pace"] = (1000.0 / speed.where(speed.gt(0))).fillna(0)
    for channel in ("watts", "heat_strain_index"):
        if channel in grid:
            df_resampled[channel] = grid[channel]

    return df_resampled


def _calculate_gap_if_available(df_resampled: pd.DataFrame) -> pd.DataFrame:
    """Calculate GAP (Grade-Adjusted Pace) when elevation data is present.

    Mutates df_resampled in place.
    """
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

    P2-2 (audit v2): this was a 165-line module with 4 private helpers.
    It is now a thin orchestrator over `time_index`, `resample_with_pace`,
    `apply_smoothing`, and `_calculate_gap_if_available`. The helpers
    live in their own modules so each can be tested and reused
    independently.
    """
    df_pd = ensure_pandas(df).copy()
    df_pd = prepare_time_index(df_pd)
    df_resampled = resample_with_pace(df_pd)

    df_resampled["time"] = df_resampled.index.total_seconds()
    df_resampled["time_min"] = df_resampled["time"] / 60.0

    df_resampled = apply_smoothing(df_resampled)
    df_resampled = _calculate_gap_if_available(df_resampled)
    df_resampled = df_resampled.reset_index(drop=True)

    return df_resampled
