"""
Summary helpers: small pure-calculation utilities used across summary sections.

These are lightweight functions with no Streamlit rendering — they compute
NP (Normalized Power), estimate CP/W', and hash DataFrames for caching.
"""

import logging
from typing import Tuple

import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

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
    """Estymacja CP i W' z danych MMP.

    Why this does not use `canonical_physio`
    ----------------------------------------
    The canonical CP/FTP source is `canonical_physio._extract_cp_ftp`, but it
    reads a *saved report* dict (`data["cp_model"]["cp_watts"]`,
    `data["thresholds"]["ftp_watts"]`). This panel is rendered from the
    in-memory frame and `app.py` passes `cp_input=0`, so there is no report to
    read and nothing canonical to import. The value is fitted locally from the
    MMP curve instead.

    What that means for the user: the CP shown here can differ from the CP in a
    previously saved report, because the two come from different inputs.

    To rewire this, the session pipeline would have to publish a canonical CP on
    `metrics` the way it already publishes `vo2_max_est`, and `app.py` would have
    to pass that in instead of `0`.
    """
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
    except (ValueError, TypeError) as e:
        # Returning (0, 0) renders "--" in the summary panel. That is the right
        # outcome for a degenerate work-time fit, but it used to happen in
        # complete silence — log why the card is empty.
        logger.warning("CP/W' estimation failed (%s); summary shows no estimate.", e)
        return 0, 0
