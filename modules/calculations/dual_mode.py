"""
Dual Mode Support Module.

Supports both pace-based and power-based analysis.
Automatically detects available metrics and adapts calculations.

Running-specific: Uses 3rd-power speed normalization (Skiba rTSS model)
instead of Coggan's 4th-power (which is validated only for cycling power).
"""

from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd


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
    """Calculate Normalized Pace for running using 3rd-power speed model.

    Uses Skiba's running-specific approach: the metabolic cost of running
    scales approximately with the 3rd power of speed (not 4th as in cycling
    power). This avoids overweighting short fast bursts.

    Algorithm:
    1. Convert pace to speed (m/s)
    2. Apply 30s rolling mean
    3. Raise to 3rd power (running-specific, not 4th)
    4. Average across session
    5. Take 3rd root
    6. Convert back to pace
    """
    from modules.calculations.common import ensure_pandas

    df = ensure_pandas(df)
    col = get_metric_column(df, "pace")

    if col is None:
        return 0.0

    # Filter out invalid pace values (0, NaN, negative)
    # Clip to physiological range: 60 sec/km (sprint) to 900 sec/km (brisk walk)
    # Exclude stopped periods (>900 sec/km) from NP calculation
    pace = df[col].replace(0, np.nan).replace(-np.inf, np.nan)
    pace = pace.clip(lower=60, upper=900)
    pace = pace.dropna()

    if len(pace) < rolling_window_sec:
        return float(pace.mean()) if len(pace) > 0 else 0.0

    # Convert to speed for calculation
    speed = 1000.0 / pace

    # Rolling average
    rolling = speed.rolling(window=rolling_window_sec, min_periods=1).mean()

    # 3rd power (running-specific: VO2-speed relationship ~cubic)
    rolling_pow3 = np.power(rolling, 3)
    avg_pow3 = np.nanmean(rolling_pow3)

    if np.isnan(avg_pow3) or avg_pow3 <= 0:
        return 0.0

    # 3rd root
    normalized_speed = np.power(avg_pow3, 1.0 / 3.0)

    # Convert back to pace
    normalized_pace = 1000.0 / normalized_speed if normalized_speed > 0 else 0

    return float(normalized_pace)


def calculate_running_stress_score(
    df: pd.DataFrame, threshold_pace: float, duration_sec: float
) -> float:
    """
    Calculate Running Stress Score (rTSS) - running equivalent of TSS.

    Uses Skiba's rTSS model with linear IF relationship (not quadratic):
      rTSS = (duration_sec * NGP_speed * IF) / (threshold_speed * 3600) * 100

    This avoids the Coggan IF² scaling which is not physiologically
    validated for running (overestimates stress for fast/short runs,
    underestimates for long/slow runs).

    Cap Intensity Factor at 2.0 to prevent extreme values.
    """
    np_pace = calculate_normalized_pace(df)

    if threshold_pace <= 0 or duration_sec <= 0:
        return 0.0

    if np_pace <= 0:
        return 0.0

    # Intensity factor (pace ratio - note: lower pace = higher intensity)
    intensity_factor = threshold_pace / np_pace

    # Cap IF at 2.0 to prevent absurd RSS values
    intensity_factor = min(intensity_factor, 2.0)

    duration_hours = duration_sec / 3600

    # Linear IF for running (not IF² like Coggan's cycling TSS)
    rss = intensity_factor * duration_hours * 100

    return round(rss, 1)
