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
from datetime import date
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

from modules.calculations import (
    calculate_advanced_kpi,
    calculate_heat_strain_index,
    calculate_metrics,
    calculate_w_prime_balance,
    calculate_z2_drift,
    process_data,
)

from .data_validation import validate_dataframe
from .session_analysis import apply_smo2_smoothing, calculate_extended_metrics, resample_dataframe


def _serialize_df_for_cache(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to bytes for stable cache key."""
    import io
    bio = io.BytesIO()
    df.to_parquet(bio, index=False)
    return bio.getvalue()


def _df_to_bytes_hash(df: pd.DataFrame) -> str:
    """Generate stable hash for DataFrame cache key."""
    return hashlib.md5(_serialize_df_for_cache(df)).hexdigest()


@st.cache_data(ttl=3600, show_spinner=False)
def _process_session_cached(
    df_bytes: bytes,
    cp_input: float,
    w_prime_input: float,
    rider_weight: float,
    vt1_watts: float,
    vt2_watts: float,
) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """Cached session processing - internal implementation.
    
    Takes serialized DataFrame bytes for stable hashing.
    Returns serialized DataFrames for cache stability.
    """
    import io
    df_raw = pd.read_parquet(io.BytesIO(df_bytes))

    is_valid, error_msg = validate_dataframe(df_raw)
    if not is_valid:
        return b'', b'', {'_error': error_msg}

    df_clean_pl = process_data(df_raw)
    metrics = calculate_metrics(df_clean_pl, cp_input)
    df_w_prime = calculate_w_prime_balance(df_clean_pl, cp_input, w_prime_input)
    decoupling_percent, ef_factor = calculate_advanced_kpi(df_clean_pl)
    drift_z2 = calculate_z2_drift(df_clean_pl, cp_input)
    df_with_hsi = calculate_heat_strain_index(df_w_prime)
    df_plot = df_with_hsi
    metrics = calculate_extended_metrics(
        df_plot, metrics, rider_weight, vt1_watts, vt2_watts, ef_factor
    )
    df_plot = apply_smo2_smoothing(df_plot)
    df_plot_resampled = resample_dataframe(df_plot)

    metrics['_decoupling_percent'] = decoupling_percent
    metrics['_drift_z2'] = drift_z2

    # FIX: Add _df_clean_pl to cached metrics for HRV analysis
    df_clean_pl_bytes = _serialize_df_for_cache(df_clean_pl)
    metrics['_df_clean_pl_bytes'] = df_clean_pl_bytes

    df_plot_bytes = _serialize_df_for_cache(df_plot)
    df_resampled_bytes = _serialize_df_for_cache(df_plot_resampled)

    return df_plot_bytes, df_resampled_bytes, metrics


def process_uploaded_session(
    df_raw: pd.DataFrame,
    cp_input: float = 0,
    w_prime_input: float = 0,
    rider_weight: float = 75.0,
    vt1_watts: float = 0,
    vt2_watts: float = 0
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[Dict[str, Any]], Optional[str]]:
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
    
    Returns:
    (df_plot, df_plot_resampled, metrics, error_message)
    """
    df_bytes = _serialize_df_for_cache(df_raw)

    try:
        df_plot_bytes, df_resampled_bytes, metrics = _process_session_cached(
            df_bytes, cp_input, w_prime_input, rider_weight, vt1_watts, vt2_watts
        )

        if metrics.get('_error'):
            return None, None, None, metrics['_error']

        import io
        df_plot = pd.read_parquet(io.BytesIO(df_plot_bytes))
        df_plot_resampled = pd.read_parquet(io.BytesIO(df_resampled_bytes))

        # FIX: Deserialize _df_clean_pl_bytes to _df_clean_pl for HRV analysis
        if '_df_clean_pl_bytes' in metrics:
            metrics['_df_clean_pl'] = pd.read_parquet(io.BytesIO(metrics['_df_clean_pl_bytes']))
            del metrics['_df_clean_pl_bytes']  # Remove bytes to save memory

        return df_plot, df_plot_resampled, metrics, None

    except Exception as e:
        logger.warning("Cached session processing failed, falling back to uncached: %s", e)
        import io
        df_raw = pd.read_parquet(io.BytesIO(df_bytes))
        is_valid, error_msg = validate_dataframe(df_raw)
        if not is_valid:
            return None, None, None, error_msg

        df_clean_pl = process_data(df_raw)
        metrics = calculate_metrics(df_clean_pl, cp_input)
        df_w_prime = calculate_w_prime_balance(df_clean_pl, cp_input, w_prime_input)
        decoupling_percent, ef_factor = calculate_advanced_kpi(df_clean_pl)
        drift_z2 = calculate_z2_drift(df_clean_pl, cp_input)
        df_with_hsi = calculate_heat_strain_index(df_w_prime)
        df_plot = df_with_hsi
        metrics = calculate_extended_metrics(
            df_plot, metrics, rider_weight, vt1_watts, vt2_watts, ef_factor
        )
        df_plot = apply_smo2_smoothing(df_plot)
        df_plot_resampled = resample_dataframe(df_plot)

        metrics['_decoupling_percent'] = decoupling_percent
        metrics['_drift_z2'] = drift_z2
        metrics['_df_clean_pl'] = df_clean_pl

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
        'date': (session_date or date.today()).isoformat(),
        'filename': filename,
        'duration_sec': len(df_plot),
        'tss': tss_header,
        'np': np_header,
        'if_factor': if_header,
        'avg_watts': metrics.get('avg_watts', 0),
        'avg_hr': metrics.get('avg_hr', 0),
        'max_hr': df_plot['heartrate'].max() if 'heartrate' in df_plot.columns else 0,
        'work_kj': metrics.get('work_kj', 0),
        'avg_cadence': metrics.get('avg_cadence', 0),
        'avg_rmssd': metrics.get('avg_rmssd'),
    }


def prepare_sticky_header_data(
    df_plot: pd.DataFrame,
    metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """Prepare data for the sticky header display."""
    return {
        'avg_power': metrics.get('avg_watts', 0),
        'avg_hr': metrics.get('avg_hr', 0),
        'avg_smo2': df_plot['smo2'].mean() if 'smo2' in df_plot.columns else 0,
        'avg_cadence': metrics.get('avg_cadence', 0),
        'avg_ve': metrics.get('avg_vent', 0),
        'duration_min': len(df_plot) / 60 if len(df_plot) > 0 else 0,
    }
