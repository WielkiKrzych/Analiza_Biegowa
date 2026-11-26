"""
Data Quality & Reliability Module.

Implements checks for:
- Signal Integrity (Dropout, Noise, Range).
- Protocol Compliance (Ramp Linearity, Step Duration).
- Automatic suppression of metrics when data is unreliable.
"""

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd


def check_signal_quality(
    series: pd.Series, metric_name: str = "Metric", valid_range: Tuple[float, float] = (0, 1000)
) -> Dict[str, Any]:
    """
    Check the quality of a single time-series signal.

    Args:
        series: The data series to check.
        metric_name: Name for reporting (e.g. "SmO2").
        valid_range: Tuple of (min, max) physiologically valid values.

    Returns:
        Dict with quality score (0.0-1.0), status, and issues list.
    """
    if series is None or series.empty:
        return {"score": 0.0, "is_valid": False, "issues": [f"{metric_name}: No data"]}

    issues = []
    score = 1.0

    # 1. Check Dropouts (NaNs or Zeros/Negatives if strictly positive)
    n_total = len(series)
    n_nans = series.isna().sum()
    pct_nan = (n_nans / n_total) * 100

    if pct_nan > 20:
        score -= 0.5
        issues.append(f"{metric_name}: High dropout rate ({pct_nan:.1f}% missing)")
    elif pct_nan > 5:
        score -= 0.1
        issues.append(f"{metric_name}: Moderate dropouts ({pct_nan:.1f}%)")

    # 2. Check Range
    # Filter valid to check range on existing data
    valid_data = series.dropna()
    if valid_data.empty:
        return {"score": 0.0, "is_valid": False, "issues": [f"{metric_name}: All Empty"]}

    min_val, max_val = valid_range
    n_out_range = ((valid_data < min_val) | (valid_data > max_val)).sum()
    pct_out = (n_out_range / len(valid_data)) * 100

    if pct_out > 10:
        score -= 0.3
        issues.append(f"{metric_name}: Values out of range ({pct_out:.1f}%)")

    # 3. Check Noise (Rapid fluctuations)
    # Calculate rolling std dev or diff
    # Simple metric: Mean of absolute adjacent differences
    diffs = np.abs(np.diff(valid_data))
    mean_diff = np.mean(diffs)
    data_range = valid_data.max() - valid_data.min()

    # Heuristic: If avg step is > 5% of range, it's very noisy
    if data_range > 0:
        noise_ratio = mean_diff / data_range
        if noise_ratio > 0.05:  # > 5% jump per second on average
            score -= 0.3
            issues.append(f"{metric_name}: High Signal Noise")

    # Clean up score
    score = max(0.0, min(1.0, score))

    return {"score": round(score, 2), "is_valid": score > 0.5, "issues": issues}
