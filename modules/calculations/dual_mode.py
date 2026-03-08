"""
Dual Mode Support Module.

Supports both pace-based and power-based analysis.
Automatically detects available metrics and adapts calculations.
"""

from typing import Dict, Optional, Union, Any
import pandas as pd
import numpy as np


def detect_available_metrics(df: pd.DataFrame) -> Dict[str, bool]:
    """Detect which metrics are available in the data."""
    return {
        "has_pace": "pace" in df.columns or "speed" in df.columns,
        "has_power": "power" in df.columns or "watts" in df.columns,
        "has_cadence": "cadence" in df.columns,
        "has_gct": "ground_contact" in df.columns or "gct" in df.columns,
        "has_hr": "heartrate" in df.columns or "hr" in df.columns,
        "has_elevation": "elevation" in df.columns or "altitude" in df.columns,
    }


def get_primary_metric(df: pd.DataFrame, prefer_power: bool = True) -> str:
    """Determine primary metric for analysis."""
    metrics = detect_available_metrics(df)
    
    if prefer_power and metrics["has_power"]:
        return "power"
    elif metrics["has_pace"]:
        return "pace"
    elif metrics["has_power"]:
        return "power"
    else:
        return "unknown"


def get_metric_column(df: pd.DataFrame, metric_type: str) -> Optional[str]:
    """Get actual column name for a metric type."""
    column_mappings = {
        "pace": ["pace", "speed", "avg_pace"],
        "power": ["power", "watts", "running_power"],
        "cadence": ["cadence", "spm", "steps_per_minute"],
        "hr": ["heartrate", "hr", "heart_rate"],
    }
    
    candidates = column_mappings.get(metric_type, [])
    for col in candidates:
        if col in df.columns:
            return col
    
    return None


def calculate_normalized_pace(df: Union[pd.DataFrame, Any], rolling_window_sec: int = 30) -> float:
    """Calculate Normalized Pace (NP equivalent for running).
    
    CRITICAL FIX: Handles pace=0 to avoid division by zero.
    """
    from modules.calculations.common import ensure_pandas
    
    df = ensure_pandas(df)
    col = get_metric_column(df, "pace")
    
    if col is None:
        return 0.0
    
    # CRITICAL FIX: Filter out invalid pace values (0, NaN, negative)
    # Minimum pace = 60 sec/km (1:00/km = sprint) for safety
    pace = df[col].replace(0, np.nan).replace(-np.inf, np.nan)
    pace = pace.ffill().bfill().clip(lower=60, upper=3600)  # 1:00 to 60:00 min/km
    
    # Convert to speed for calculation
    speed = 1000.0 / pace
    
    # Rolling average
    rolling = speed.rolling(window=rolling_window_sec, min_periods=1).mean()
    
    # 4th power (like NP)
    rolling_pow4 = np.power(rolling, 4)
    avg_pow4 = np.nanmean(rolling_pow4)
    
    if np.isnan(avg_pow4) or avg_pow4 <= 0:
        return 0.0
    
    # 4th root
    normalized_speed = np.power(avg_pow4, 0.25)
    
    # Convert back to pace
    normalized_pace = 1000.0 / normalized_speed if normalized_speed > 0 else 0
    
    return float(normalized_pace)


def calculate_running_stress_score(
    df: pd.DataFrame,
    threshold_pace: float,
    duration_sec: float
) -> float:
    """
    Calculate Running Stress Score (RSS) - running equivalent of TSS.
    RSS = (Normalized Pace / Threshold Pace)^2 * Duration (hours) * 100
    
    CRITICAL FIX: Cap Intensity Factor at 2.0 to prevent extreme values.
    """
    np_pace = calculate_normalized_pace(df)
    
    if threshold_pace <= 0 or duration_sec <= 0:
        return 0.0
    
    if np_pace <= 0:
        return 0.0
    
    # Intensity factor (pace ratio - note: lower pace = higher intensity)
    intensity_factor = threshold_pace / np_pace
    
    # CRITICAL FIX: Cap IF at 2.0 to prevent absurd RSS values
    intensity_factor = min(intensity_factor, 2.0)
    
    duration_hours = duration_sec / 3600
    
    rss = intensity_factor**2 * duration_hours * 100
    
    return round(rss, 1)
