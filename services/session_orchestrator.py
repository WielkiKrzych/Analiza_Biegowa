"""
Session Orchestrator Service

High-level orchestration of session processing pipeline.
Coordinates data loading, validation, metrics calculation, and storage preparation.

PERFORMANCE OPTIMIZATIONS:
- @st.cache_data for heavy calculations (cached between re-runs)
- Cached inputs are serialized to bytes for hash stability
- Cache invalidation on file changes via hash
"""

import logging
import pickle
from typing import Any, Dict, Tuple

import pandas as pd
import pyarrow
import streamlit as st

from modules.calculations.data_processing import process_data
from modules.calculations.thermal import read_core_hsi, summarize_core_hsi
from modules.config import Config

from .data_validation import validate_dataframe
from .session_analysis import apply_smo2_smoothing, calculate_session_metrics, resample_dataframe

logger = logging.getLogger(__name__)


def _serialize_df_for_cache(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to bytes for stable cache key."""
    import io

    bio = io.BytesIO()
    df.to_parquet(bio, index=False)
    return bio.getvalue()


def _process_session_core(
    df_raw: pd.DataFrame, threshold_pace: float
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], str | None]:
    """Validate and process the same input for cached and recovery paths."""
    is_valid, error = validate_dataframe(df_raw)
    if not is_valid:
        return pd.DataFrame(), pd.DataFrame(), {}, error

    hsi = summarize_core_hsi(df_raw)
    if "heat_strain_index" in df_raw:
        df_raw["heat_strain_index"] = read_core_hsi(df_raw["heat_strain_index"])
    df_plot = apply_smo2_smoothing(process_data(df_raw))
    metrics = calculate_session_metrics(df_plot, threshold_pace)
    metrics["heat_strain"] = hsi
    return df_plot, resample_dataframe(df_plot), metrics, None


@st.cache_data(ttl=3600, show_spinner=False)
def _process_session_cached(
    df_bytes: bytes,
    threshold_pace: float,
) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """Cached session processing — thin wrapper that serializes around
    `_process_session_core` so the cache key is stable across Streamlit
    re-runs.
    """
    import io

    df_raw = pd.read_parquet(io.BytesIO(df_bytes))
    df_plot, df_plot_resampled, metrics, error_msg = _process_session_core(df_raw, threshold_pace)
    if error_msg:
        return b"", b"", {"_error": error_msg}

    return (
        _serialize_df_for_cache(df_plot),
        _serialize_df_for_cache(df_plot_resampled),
        metrics,
    )


def process_uploaded_session(
    df_raw: pd.DataFrame,
    threshold_pace: float = Config.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict[str, Any] | None, str | None]:
    """Return processed plot frames and metrics, or an input error message."""
    import io

    df_bytes = _serialize_df_for_cache(df_raw)

    try:
        df_plot_bytes, df_resampled_bytes, metrics = _process_session_cached(
            df_bytes, threshold_pace
        )

        if metrics.get("_error"):
            return None, None, None, metrics["_error"]

        df_plot = pd.read_parquet(io.BytesIO(df_plot_bytes))
        df_plot_resampled = pd.read_parquet(io.BytesIO(df_resampled_bytes))

        return df_plot, df_plot_resampled, metrics, None

    except (OSError, pyarrow.ArrowInvalid, pickle.UnpicklingError) as e:
        # Cache/deserialization failure — re-run the core pipeline once on
        # the freshly-deserialized DataFrame (no re-serialization needed).
        # Any other exception type (ValueError, KeyError, …) propagates so
        # the underlying bug is not masked.
        logger.warning("Cache deserialization failed, running uncached: %s", e)
        df_raw_retry = pd.read_parquet(io.BytesIO(df_bytes))
        df_plot, df_plot_resampled, metrics, error_msg = _process_session_core(
            df_raw_retry, threshold_pace
        )
        if error_msg:
            return None, None, None, error_msg
        return df_plot, df_plot_resampled, metrics, None
