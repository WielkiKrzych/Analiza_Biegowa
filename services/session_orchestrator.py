"""
Session Orchestrator Service

High-level orchestration of session processing pipeline.
Coordinates data loading, validation, metrics calculation, and storage preparation.
"""

import pandas as pd
from datetime import date
from typing import Dict, Any, Optional, Tuple

from .session_analysis import (
    calculate_extended_metrics,
    apply_smo2_smoothing,
    resample_dataframe,
)
from .data_validation import validate_dataframe

from modules.calculations import (
    calculate_w_prime_balance,
    calculate_metrics,
    calculate_advanced_kpi,
    calculate_z2_drift,
    calculate_heat_strain_index,
    process_data,
)


def process_uploaded_session(
    df_raw: pd.DataFrame,
    cp_input: float,
    w_prime_input: float,
    rider_weight: float,
    vt1_watts: float,
    vt2_watts: float
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
    # Validate data
    is_valid, error_msg = validate_dataframe(df_raw)
    if not is_valid:
        return None, None, None, error_msg
    
    # Process data
    df_clean_pl = process_data(df_raw)
    
    # Calculate base metrics
    metrics = calculate_metrics(df_clean_pl, cp_input)
    
    # Calculate W' balance
    df_w_prime = calculate_w_prime_balance(df_clean_pl, cp_input, w_prime_input)
    
    # Calculate advanced KPIs
    decoupling_percent, ef_factor = calculate_advanced_kpi(df_clean_pl)
    
    # Calculate Z2 drift
    drift_z2 = calculate_z2_drift(df_clean_pl, cp_input)
    
    # Calculate Heat Strain Index
    df_with_hsi = calculate_heat_strain_index(df_w_prime)
    df_plot = df_with_hsi
    
    # Calculate extended metrics
    metrics = calculate_extended_metrics(
        df_plot, metrics, rider_weight, vt1_watts, vt2_watts, ef_factor
    )
    
    # Apply SmO2 smoothing
    df_plot = apply_smo2_smoothing(df_plot)
    
    # Resample for performance
    df_plot_resampled = resample_dataframe(df_plot)
    
    # Store intermediate values in metrics for later use
    # We use a leading underscore convention for internal values
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
    tss_header: float
) -> Dict[str, Any]:
    """Prepare session data for database storage."""
    return {
        'date': date.today().isoformat(),
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
