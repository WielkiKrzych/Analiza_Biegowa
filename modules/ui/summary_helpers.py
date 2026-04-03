"""
Summary helpers: small pure-calculation utilities used across summary sections.

These are lightweight functions with no Streamlit rendering — they compute
NP (Normalized Power), estimate CP/W', and hash DataFrames for caching.
"""

from typing import Tuple

import pandas as pd
from scipy import stats

__all__ = ["_hash_dataframe", "_calculate_np", "_estimate_cp_wprime"]


def _hash_dataframe(df: pd.DataFrame) -> str:
    """Create a hash of DataFrame for cache key generation."""
    if df is None or df.empty:
        return "empty"
    sample = df.head(100).to_json()
    shape_str = f"{df.shape}_{list(df.columns)}"
    import hashlib

    return hashlib.md5(f"{shape_str}_{sample}".encode()).hexdigest()[:16]


def _calculate_np(watts_series) -> float:
    """Obliczenie Normalized Power."""
    if len(watts_series) < 30:
        return watts_series.mean()
    rolling_avg = watts_series.rolling(30, min_periods=1).mean()
    fourth_power = rolling_avg**4
    return fourth_power.mean() ** 0.25


def _estimate_cp_wprime(df_plot) -> Tuple[float, float]:
    """Estymacja CP i W' z danych MMP."""
    if "watts" not in df_plot.columns or len(df_plot) < 1200:
        return 0, 0

    durations = [180, 300, 600, 900, 1200]
    valid_durations = [d for d in durations if d < len(df_plot)]

    if len(valid_durations) < 3:
        return 0, 0

    work_values = []
    for d in valid_durations:
        p = df_plot["watts"].rolling(window=d).mean().max()
        if not pd.isna(p):
            work_values.append(p * d)
        else:
            return 0, 0

    try:
        slope, intercept, _, _, _ = stats.linregress(valid_durations, work_values)
        return slope, intercept
    except Exception:
        return 0, 0
