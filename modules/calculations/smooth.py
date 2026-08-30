"""
Rolling-window smoothing (P2-2, audit v2).

Extracted from `data_processing.py`. Creates `_smooth` and `_smooth_5s`
columns for the metrics that benefit from time-window averaging, plus
`smooth_5s` for short-window plots.

Pace is special: it is a nonlinear metric (sec/km = 1/speed), so it must
be smoothed in the SPEED domain and converted back. Otherwise the rolling
mean of a pace series biases towards slow samples (spending more time
there) and over-estimates the average pace.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .common import WINDOW_LONG, WINDOW_SHORT

# Columns that get a `_smooth` (long) and `_smooth_5s` (short) twin.
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


def apply_smoothing(df_resampled: pd.DataFrame) -> pd.DataFrame:
    """Create smoothed versions of key columns including pace.

    For linear metrics (watts, HR, cadence, ...) the rolling mean is
    correct. For `pace`, we smooth in the speed domain and convert back
    to avoid the nonlinearity bias.
    """
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
