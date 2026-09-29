"""
Time index preparation (P2-2, audit v2).

Extracted from `data_processing.py`. Handles the messy first step of the
pipeline: ensuring a numeric `time` column exists, sorting, deriving `pace`
from a speed column when the file only carries GPS speed, and converting
the index to a `timedelta64[ns]` index for resampling.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def prepare_time_index(df_pd: pd.DataFrame) -> pd.DataFrame:
    """Ensure time column exists, is numeric, sorted, and set as timedelta index.

    Steps:
    1. If no `time` column, synthesize one from row index.
    2. Coerce `time` to numeric (errors -> NaN -> drop).
    3. Sort by time, reset index.
    4. Derive `pace` from `speed_m_s` or `velocity_smooth` when missing
       (pace = 1000 / speed, m/s).
    5. Convert to `timedelta64[ns]` index.
    6. Linear interpolate numeric columns, then ffill/bfill edges.

    Mutates df_pd in place. *df_pd* is the top of the `process_data` pipeline,
    which owns the frame it passes in.
    """
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
            logger.info("Derived pace from '%s' column", speed_col)

    df_pd["time_dt"] = pd.to_timedelta(df_pd["time"], unit="s")
    df_pd = df_pd[df_pd["time_dt"].notna()]
    df_pd = df_pd.set_index("time_dt")

    num_cols = df_pd.select_dtypes(include=["float64", "int64"]).columns.tolist()
    if num_cols:
        df_pd[num_cols] = df_pd[num_cols].interpolate(method="linear").ffill().bfill()

    return df_pd
