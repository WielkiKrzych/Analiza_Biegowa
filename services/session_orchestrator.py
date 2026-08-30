"""
Session Orchestrator Service

High-level orchestration of session processing pipeline.
Coordinates data loading, validation, metrics calculation, and storage preparation.

PERFORMANCE OPTIMIZATIONS:
- @st.cache_data for heavy calculations (cached between re-runs)
- Cached inputs are serialized to bytes for hash stability
- Cache invalidation on file changes via hash
"""

import hashlib
import logging
import pickle
from datetime import date
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import pyarrow
import streamlit as st

from modules.calculations import (
    calculate_advanced_kpi,
    calculate_heat_strain_index,
    calculate_metrics,
    calculate_w_prime_balance,
    calculate_z2_drift,
    process_data,
)
from modules.calculations.running_power import ensure_power_column
from modules.config import Config

from .data_validation import validate_dataframe
from .session_analysis import apply_smo2_smoothing, calculate_extended_metrics, resample_dataframe

logger = logging.getLogger(__name__)


def _serialize_df_for_cache(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to bytes for stable cache key."""
    import io

    bio = io.BytesIO()
    df.to_parquet(bio, index=False)
    return bio.getvalue()


def _df_to_bytes_hash(df: pd.DataFrame) -> str:
    """Generate stable hash for DataFrame cache key."""
    return hashlib.md5(_serialize_df_for_cache(df)).hexdigest()


def _process_session_core(
    df_raw: pd.DataFrame,
    cp_input: float,
    w_prime_input: float,
    rider_weight: float,
    vt1_watts: float,
    vt2_watts: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], str | None]:
    """Core session processing — shared by cached and uncached paths.

    P1-1 (audit v2): the previous `process_uploaded_session` duplicated ~25
    lines of pipeline code between the cache path and a fallback. The two
    paths have now been merged into this single function. The caller
    handles caching and serialization; this function only deals in
    DataFrames so it is easy to read and monkey-patch in tests.

    Returns:
        (df_plot, df_plot_resampled, metrics, error_message)
        On validation failure, df_plot and df_plot_resampled are empty
        DataFrames and error_message is set.
    """
    is_valid, error_msg = validate_dataframe(df_raw)
    if not is_valid:
        return pd.DataFrame(), pd.DataFrame(), {"_error": error_msg}, error_msg

    df_clean_pl = process_data(df_raw)
    power_estimated = ensure_power_column(df_clean_pl, rider_weight)
    metrics = calculate_metrics(df_clean_pl, cp_input)
    metrics["power_is_estimated"] = power_estimated
    df_w_prime = calculate_w_prime_balance(df_clean_pl, cp_input, w_prime_input)
    decoupling_percent, ef_factor = calculate_advanced_kpi(df_clean_pl)
    drift_z2 = calculate_z2_drift(df_clean_pl, cp_input)
    df_with_hsi = calculate_heat_strain_index(df_w_prime)
    df_plot = df_with_hsi
    metrics = calculate_extended_metrics(
        df_plot, metrics, rider_weight, vt1_watts, vt2_watts, ef_factor
    )
    metrics["power_is_estimated"] = power_estimated
    df_plot = apply_smo2_smoothing(df_plot)
    df_plot_resampled = resample_dataframe(df_plot)

    metrics["_decoupling_percent"] = decoupling_percent
    metrics["_drift_z2"] = drift_z2
    metrics["_df_clean_pl"] = df_clean_pl

    return df_plot, df_plot_resampled, metrics, None


@st.cache_data(ttl=3600, show_spinner=False)
def _process_session_cached(
    df_bytes: bytes,
    cp_input: float,
    w_prime_input: float,
    rider_weight: float,
    vt1_watts: float,
    vt2_watts: float,
) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """Cached session processing — thin wrapper that serializes around
    `_process_session_core` so the cache key is stable across Streamlit
    re-runs.
    """
    import io

    df_raw = pd.read_parquet(io.BytesIO(df_bytes))
    df_plot, df_plot_resampled, metrics, error_msg = _process_session_core(
        df_raw, cp_input, w_prime_input, rider_weight, vt1_watts, vt2_watts
    )
    if error_msg:
        return b"", b"", {"_error": error_msg}

    # Pack _df_clean_pl into bytes for the cache; the public entry point
    # will deserialize it back so callers see a DataFrame.
    df_clean_pl = metrics.pop("_df_clean_pl")
    metrics["_df_clean_pl_bytes"] = _serialize_df_for_cache(df_clean_pl)

    return (
        _serialize_df_for_cache(df_plot),
        _serialize_df_for_cache(df_plot_resampled),
        metrics,
    )


def process_uploaded_session(
    df_raw: pd.DataFrame,
    cp_input: float = 0,
    w_prime_input: float = 0,
    rider_weight: float = Config.DEFAULT_BODY_WEIGHT_KG,
    vt1_watts: float = 0,
    vt2_watts: float = 0,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict[str, Any] | None, str | None]:
    """Process an uploaded session file through the full analysis pipeline.

    Orchestrates:
    1. Data validation
    2. Data processing
    3. Metrics calculation
    4. W' balance computation
    5. Heat strain index
    6. Extended metrics
    7. SmO2 smoothing
    8. Resampling

    P1-1 (audit v2): the previous implementation had a broad
    `except Exception` that re-ran the entire pipeline a second time on any
    failure. Real bugs in `process_data` (ValueError, etc.) were hidden
    behind a "falling back to uncached" warning and the user paid double
    the compute for the same failure. The except is now narrowed to
    cache/deserialization exceptions — any other exception propagates so
    the bug is visible.

    Returns:
    (df_plot, df_plot_resampled, metrics, error_message)
    """
    import io

    df_bytes = _serialize_df_for_cache(df_raw)

    try:
        df_plot_bytes, df_resampled_bytes, metrics = _process_session_cached(
            df_bytes, cp_input, w_prime_input, rider_weight, vt1_watts, vt2_watts
        )

        if metrics.get("_error"):
            return None, None, None, metrics["_error"]

        df_plot = pd.read_parquet(io.BytesIO(df_plot_bytes))
        df_plot_resampled = pd.read_parquet(io.BytesIO(df_resampled_bytes))

        # Deserialize _df_clean_pl_bytes to _df_clean_pl for HRV analysis
        if "_df_clean_pl_bytes" in metrics:
            metrics["_df_clean_pl"] = pd.read_parquet(io.BytesIO(metrics["_df_clean_pl_bytes"]))
            del metrics["_df_clean_pl_bytes"]

        return df_plot, df_plot_resampled, metrics, None

    except (OSError, pyarrow.ArrowInvalid, pickle.UnpicklingError) as e:
        # Cache/deserialization failure — re-run the core pipeline once on
        # the freshly-deserialized DataFrame (no re-serialization needed).
        # Any other exception type (ValueError, KeyError, …) propagates so
        # the underlying bug is not masked.
        logger.warning("Cache deserialization failed, running uncached: %s", e)
        df_raw_retry = pd.read_parquet(io.BytesIO(df_bytes))
        df_plot, df_plot_resampled, metrics, error_msg = _process_session_core(
            df_raw_retry, cp_input, w_prime_input, rider_weight, vt1_watts, vt2_watts
        )
        if error_msg:
            return None, None, None, error_msg
        return df_plot, df_plot_resampled, metrics, None


def prepare_session_record(
    filename: str,
    df_plot: pd.DataFrame,
    metrics: Dict[str, Any],
    np_header: float,
    if_header: float,
    tss_header: float,
    session_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Prepare session data for database storage.

    Args:
        session_date: Date of the session. Defaults to today if not provided.
    """
    return {
        "date": (session_date or date.today()).isoformat(),
        "filename": filename,
        "duration_sec": len(df_plot),
        "tss": tss_header,
        "np": np_header,
        "if_factor": if_header,
        "avg_watts": metrics.get("avg_watts", 0),
        "avg_hr": metrics.get("avg_hr", 0),
        "max_hr": df_plot["heartrate"].max() if "heartrate" in df_plot.columns else 0,
        "work_kj": metrics.get("work_kj", 0),
        "avg_cadence": metrics.get("avg_cadence", 0),
        "avg_rmssd": metrics.get("avg_rmssd"),
    }


def prepare_sticky_header_data(df_plot: pd.DataFrame, metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare data for the sticky header display.

    Running-first: when a ``pace`` column is present the header shows average
    pace (min/km) and cadence in SPM. Power is still passed through so dual-mode
    (running power / cycling) sessions can fall back to watts.
    """
    avg_pace = _mean_running_pace(df_plot)
    return {
        "avg_pace": avg_pace,
        "is_running": avg_pace > 0,
        "avg_power": metrics.get("avg_watts", 0),
        "avg_hr": metrics.get("avg_hr", 0),
        "avg_smo2": df_plot["smo2"].mean() if "smo2" in df_plot.columns else 0,
        "avg_cadence": metrics.get("avg_cadence", 0),
        "avg_ve": metrics.get("avg_vent", 0),
        "duration_min": len(df_plot) / 60 if len(df_plot) > 0 else 0,
    }


def _mean_running_pace(df_plot: pd.DataFrame) -> float:
    """Return mean moving pace in seconds/km, ignoring standing/invalid samples.

    Accepts either a ``pace`` column (sec/km) or a ``speed`` column (m/s).
    """
    if "pace" in df_plot.columns:
        pace = pd.to_numeric(df_plot["pace"], errors="coerce")
        # Keep only plausible moving paces: 2:00–20:00 min/km.
        pace = pace[(pace >= 120) & (pace <= 1200)]
        return float(pace.mean()) if len(pace) > 0 else 0.0
    if "speed" in df_plot.columns:
        speed = pd.to_numeric(df_plot["speed"], errors="coerce")
        speed = speed[speed > 0.5]  # ignore near-stationary samples
        return float(1000.0 / speed.mean()) if len(speed) > 0 else 0.0
    return 0.0
