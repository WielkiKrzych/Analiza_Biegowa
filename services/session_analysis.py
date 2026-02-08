"""
Session Analysis Service

Handles all session-level metrics calculations including:
- Header metrics (NP, IF, TSS)
- Extended metrics (VO2max estimation, carbs, pulse power, etc.)
- SmO2 smoothing
- DataFrame resampling
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
from modules.config import Config

# ============================================================
# Re-exporting constants for backward compatibility
# ============================================================
ROLLING_WINDOW_5MIN = Config.ROLLING_WINDOW_5MIN
ROLLING_WINDOW_30S = Config.ROLLING_WINDOW_30S
ROLLING_WINDOW_60S = Config.ROLLING_WINDOW_60S
RESAMPLE_THRESHOLD = Config.RESAMPLE_THRESHOLD
RESAMPLE_STEP = Config.RESAMPLE_STEP
MIN_WATTS_ACTIVE = Config.MIN_WATTS_ACTIVE
MIN_HR_ACTIVE = Config.MIN_HR_ACTIVE
MIN_RECORDS_FOR_ROLLING = Config.MIN_RECORDS_FOR_ROLLING


def calculate_header_metrics(df: pd.DataFrame, cp: float) -> Tuple[float, float, float]:
    """Calculate NP, IF, and TSS for the header display.

    Centralizes the calculation to avoid duplication.

    Args:
        df: DataFrame with 'watts' column
        cp: Critical Power in watts

    Returns:
        Tuple of (NP, IF, TSS)
    """
    if "watts" not in df.columns or len(df) < Config.MIN_RECORDS_FOR_ROLLING:
        return 0.0, 0.0, 0.0

    rolling_30s = df["watts"].rolling(window=Config.ROLLING_WINDOW_30S, min_periods=1).mean()
    np_val = np.power(np.mean(np.power(rolling_30s, 4)), 0.25)

    if pd.isna(np_val):
        np_val = df["watts"].mean()

    if cp > 0:
        if_val = np_val / cp
        duration_sec = len(df)
        tss_val = (duration_sec * np_val * if_val) / (cp * 3600) * 100
    else:
        if_val = 0.0
        tss_val = 0.0

    return float(np_val), float(if_val), float(tss_val)


def calculate_extended_metrics(
    df: pd.DataFrame,
    metrics: Dict[str, Any],
    rider_weight: float,
    vt1_watts: float,
    vt2_watts: float,
    ef_factor: float,
) -> Dict[str, Any]:
    """Calculate extended metrics for the session.

    Aggregates various physiological and performance metrics.

    Args:
        df: DataFrame with session data
        metrics: Base metrics dictionary to extend
        rider_weight: Rider weight in kg
        vt1_watts: VT1 threshold in watts
        vt2_watts: VT2 threshold in watts
        ef_factor: Efficiency factor from advanced KPI

    Returns:
        Extended metrics dictionary
    """
    # Import here to avoid circular dependency
    from modules.calculations import (
        calculate_normalized_power,
        estimate_carbs_burned,
        calculate_power_duration_curve,
        estimate_vlamax_from_pdc,
    )

    if "watts" in df.columns:
        metrics["np"] = calculate_normalized_power(df)
        metrics["work_kj"] = df["watts"].sum() / 1000
        metrics["carbs_total"] = estimate_carbs_burned(df, vt1_watts, vt2_watts)

        # Power Duration Curve & VLamax estimation
        pdc = calculate_power_duration_curve(df)
        metrics["vlamax_est"] = (
            estimate_vlamax_from_pdc(pdc, rider_weight) if pdc and rider_weight > 0 else 0
        )

        # VO2max estimation
        mmp_5m = df["watts"].rolling(Config.ROLLING_WINDOW_5MIN).mean().max()
        if not pd.isna(mmp_5m) and rider_weight > 0:
            power_per_kg = mmp_5m / rider_weight
            metrics["vo2_max_est"] = 16.61 + 8.87 * power_per_kg
        else:
            metrics["vo2_max_est"] = 0

    if "hsi" in df.columns:
        metrics["max_hsi"] = df["hsi"].max()

    if "core_temperature" in df.columns:
        metrics["max_core"] = df["core_temperature"].max()
        metrics["avg_core"] = df["core_temperature"].mean()

    if "rmssd" in df.columns:
        metrics["avg_rmssd"] = df["rmssd"].mean()
    elif "hrv" in df.columns:
        metrics["avg_rmssd"] = df["hrv"].mean()

    # Efficiency factor
    metrics["ef_factor"] = ef_factor

    # Average Pulse Power
    metrics["avg_pp"] = _calculate_average_pulse_power(df)

    return metrics


def _calculate_average_pulse_power(df: pd.DataFrame) -> float:
    """Calculate average pulse power for active zones."""
    if "watts" not in df.columns or "heartrate" not in df.columns:
        return 0.0

    mask = (df["watts"] > Config.MIN_WATTS_ACTIVE) & (df["heartrate"] > Config.MIN_HR_ACTIVE)
    if mask.sum() == 0:
        return 0.0

    hr_values = df.loc[mask, "heartrate"]
    watts_values = df.loc[mask, "watts"]
    safe_mask = hr_values > 0

    if safe_mask.sum() == 0:
        return 0.0

    return (watts_values[safe_mask] / hr_values[safe_mask]).mean()


def apply_smo2_smoothing(df: pd.DataFrame) -> pd.DataFrame:
    """Apply smoothing to SmO2 data if present.

    Args:
        df: DataFrame with optional 'smo2' column

    Returns:
        DataFrame with 'smo2_smooth_ultra' column added if smo2 exists
    """
    if "smo2" in df.columns:
        df["smo2_smooth_ultra"] = (
            df["smo2"].rolling(window=Config.ROLLING_WINDOW_60S, center=True, min_periods=1).mean()
        )
    return df


def resample_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Resample DataFrame if it exceeds threshold size.

    Args:
        df: Original DataFrame

    Returns:
        Resampled DataFrame if size > threshold, otherwise original
    """
    if len(df) > Config.RESAMPLE_THRESHOLD:
        return df.iloc[:: Config.RESAMPLE_STEP, :].copy()
    return df
