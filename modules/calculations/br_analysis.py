"""Breathing rate (BR) analysis for running performance.

Based on:
- npj Digital Medicine 2024: BR-based ventilatory threshold detection
- Nicolo & Bhatt 2017: BR as exercise intensity marker

All functions are pure/immutable - no mutation of input data.
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Optional, Dict

# BR zone boundaries (breaths/min)
_BR_ZONES = (
    ("Z1_Recovery", 0, 20),
    ("Z2_Easy", 20, 30),
    ("Z3_Moderate", 30, 40),
    ("Z4_Threshold", 40, 50),
    ("Z5_VO2max", 50, float("inf")),
)

_SMOOTHING_WINDOW = 30  # seconds
_VT1_SLOPE_THRESHOLD = 2.0  # breaths/min^2
_VT2_SLOPE_THRESHOLD = 4.0  # breaths/min^2
_DECOUPLING_SIGNIFICANT_PCT = 5.0


def classify_br_zone(br_value: float) -> str:
    """Classify a single BR value into a training zone.

    Args:
        br_value: Breathing rate in breaths/min.

    Returns:
        Zone name string (e.g. "Z2_Easy").
    """
    if not np.isfinite(br_value):
        return "Unknown"
    for name, low, high in _BR_ZONES:
        if low <= br_value < high:
            return name
    return "Unknown"


def calculate_br_zones_time(
    br_series: pd.Series, sample_rate_hz: float = 1.0
) -> Dict[str, float]:
    """Calculate time spent in each BR zone.

    Args:
        br_series: Breathing rate values over time.
        sample_rate_hz: Sampling frequency in Hz.

    Returns:
        Dict mapping zone names to seconds spent in each zone.
    """
    sample_interval = 1.0 / sample_rate_hz
    clean = br_series.dropna()
    zones = clean.map(classify_br_zone)
    counts = zones.value_counts()
    return {
        name: counts.get(name, 0) * sample_interval
        for name, _, _ in _BR_ZONES
    }


def _segmented_regression(x: np.ndarray, y: np.ndarray):
    """Fit 2-breakpoint segmented regression. Returns (bp1, bp2, confidence)."""
    n = len(x)
    if n < 10:
        return None, None, 0.0
    best_rss, best_bp1, best_bp2 = np.inf, None, None
    step = max(1, n // 50)
    for i in range(n // 5, 2 * n // 5, step):
        for j in range(3 * n // 5, 4 * n // 5, step):
            if j - i < 5:
                continue
            s1, s2, s3 = stats.linregress(x[:i], y[:i]), stats.linregress(x[i:j], y[i:j]), stats.linregress(x[j:], y[j:])
            rss = (np.sum((y[:i] - (s1.slope * x[:i] + s1.intercept)) ** 2)
                   + np.sum((y[i:j] - (s2.slope * x[i:j] + s2.intercept)) ** 2)
                   + np.sum((y[j:] - (s3.slope * x[j:] + s3.intercept)) ** 2))
            if rss < best_rss:
                best_rss, best_bp1, best_bp2 = rss, i, j
    tss = np.sum((y - np.mean(y)) ** 2)
    seg_r2 = max(0.0, min(1.0, 1.0 - best_rss / tss)) if tss > 0 else 0.0
    single_r2 = stats.linregress(x, y).rvalue ** 2 if tss > 0 else 0.0
    confidence = max(0.0, min(1.0, (seg_r2 - single_r2) / max(1.0 - single_r2, 1e-9)))
    return best_bp1, best_bp2, confidence


def detect_vt_from_br(
    br_series: pd.Series,
    time_series: Optional[pd.Series] = None,
    pace_series: Optional[pd.Series] = None,
    hr_series: Optional[pd.Series] = None,
) -> Dict:
    """Detect ventilatory thresholds (VT1, VT2) from breathing rate.

    Uses segmented regression on smoothed BR data, falling back to
    slope-change detection when regression yields low confidence.

    Reference: npj Digital Medicine 2024.
    """
    _empty = {"vt1_time_sec": None, "vt1_br": None, "vt1_hr": None, "vt1_pace": None,
              "vt2_time_sec": None, "vt2_br": None, "vt2_hr": None, "vt2_pace": None,
              "confidence": 0.0, "method": "none"}
    result = dict(_empty)
    clean_br = br_series.dropna()
    if len(clean_br) < 60:
        return result
    smoothed = clean_br.rolling(window=_SMOOTHING_WINDOW, min_periods=1, center=True).median()
    t = (time_series.loc[smoothed.index].values.astype(float)
         if time_series is not None else np.arange(len(smoothed), dtype=float))
    x, y = t - t[0], smoothed.values

    bp1, bp2, seg_conf = _segmented_regression(x, y)
    if bp1 is not None and bp2 is not None and seg_conf > 0.15:
        result.update(method="segmented_regression", confidence=round(float(seg_conf), 3),
                      vt1_time_sec=int(x[bp1]), vt1_br=round(float(y[bp1]), 1),
                      vt2_time_sec=int(x[bp2]), vt2_br=round(float(y[bp2]), 1))
    else:
        dt = np.diff(x); dt[dt == 0] = 1.0
        dbr_smooth = pd.Series(np.diff(y) / dt).rolling(window=_SMOOTHING_WINDOW, min_periods=1).mean().values
        vt1_idx = next((i for i in range(len(dbr_smooth)) if dbr_smooth[i] > _VT1_SLOPE_THRESHOLD), None)
        start = (vt1_idx + _SMOOTHING_WINDOW) if vt1_idx is not None else len(dbr_smooth) // 2
        vt2_idx = next((i for i in range(start, len(dbr_smooth)) if dbr_smooth[i] > _VT2_SLOPE_THRESHOLD), None)
        result["method"] = "slope_change"
        result["confidence"] = round(0.4 if vt1_idx and vt2_idx else 0.2, 3)
        if vt1_idx is not None:
            result.update(vt1_time_sec=int(x[vt1_idx]), vt1_br=round(float(y[vt1_idx]), 1))
        if vt2_idx is not None:
            result.update(vt2_time_sec=int(x[vt2_idx]), vt2_br=round(float(y[vt2_idx]), 1))

    for prefix, t_sec in [("vt1", result["vt1_time_sec"]), ("vt2", result["vt2_time_sec"])]:
        if t_sec is None:
            continue
        idx = int(np.argmin(np.abs(x - t_sec)))
        orig = smoothed.index[idx]
        if hr_series is not None and orig in hr_series.index:
            result[f"{prefix}_hr"] = round(float(hr_series.loc[orig]), 1)
        if pace_series is not None and orig in pace_series.index:
            result[f"{prefix}_pace"] = round(float(pace_series.loc[orig]), 2)
    return result


def calculate_br_hr_ratio(br_series: pd.Series, hr_series: pd.Series) -> pd.Series:
    """Calculate ventilatory efficiency as BR/HR ratio (30s rolling mean).

    Higher values indicate less efficient breathing relative to cardiac output.
    """
    aligned = pd.DataFrame({"br": br_series, "hr": hr_series}).dropna()
    if aligned.empty:
        return pd.Series(dtype=float)

    raw_ratio = aligned["br"] / aligned["hr"].replace(0, np.nan)
    return raw_ratio.rolling(window=_SMOOTHING_WINDOW, min_periods=1, center=True).mean()


def calculate_br_decoupling(
    br_series: pd.Series,
    hr_series: pd.Series,
    pace_series: Optional[pd.Series] = None,
) -> Dict[str, object]:
    """Compute BR/HR decoupling between first and second half of activity.

    Decoupling > 5% suggests cardiovascular or ventilatory drift.
    """
    ratio = calculate_br_hr_ratio(br_series, hr_series).dropna()
    if len(ratio) < 2:
        return {"decoupling_pct": 0.0, "is_significant": False, "interpretation": "Insufficient data"}

    mid = len(ratio) // 2
    mean_first = ratio.iloc[:mid].mean()
    mean_second = ratio.iloc[mid:].mean()

    if mean_first == 0:
        return {"decoupling_pct": 0.0, "is_significant": False, "interpretation": "Invalid first-half ratio"}

    decoupling = (mean_second - mean_first) / mean_first * 100.0
    is_significant = abs(decoupling) > _DECOUPLING_SIGNIFICANT_PCT

    if not is_significant:
        interpretation = "Stable ventilatory efficiency throughout the activity"
    elif decoupling > 0:
        interpretation = "Ventilatory drift detected: breathing became less efficient in the second half"
    else:
        interpretation = "Improved ventilatory efficiency in the second half"

    return {
        "decoupling_pct": round(float(decoupling), 2),
        "is_significant": is_significant,
        "interpretation": interpretation,
    }
