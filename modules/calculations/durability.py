"""
Durability and fatigue analysis for running.

References:
    - Hunter 2025 (Experimental Physiology) -- durability definition
    - Jones 2024 (Journal of Physiology) -- "fourth dimension" of endurance
    - Smyth et al. 2025 (Frontiers in Sports) -- marathon decoupling in 82K runners
    - TrainingPeaks Pa:HR methodology (Friel)
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# --- Constants ---
STOPPED_PACE_THRESHOLD = 900  # s/km; above this the runner is stopped
MIN_SAMPLES = 20
DECOUPLING_THRESHOLDS = {"excellent": 3.0, "good": 5.0, "moderate": 8.0}
DURABILITY_THRESHOLDS = {"elite": 85, "good": 70, "average": 55}
DRIFT_ONSET_PCT = 3.0
DRIFT_ONSET_HOLD_SEC = 120


def _filter_active(pace: pd.Series, hr: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Remove stopped periods; return copies (immutable)."""
    mask = (pace > 0) & (pace < STOPPED_PACE_THRESHOLD) & hr.notna() & (hr > 0)
    return pace.loc[mask].copy(), hr.loc[mask].copy()


def _pace_to_speed(pace: pd.Series) -> pd.Series:
    """Convert pace (s/km) to speed (km/s). Returns new Series."""
    return 1.0 / pace


def _classify_decoupling(pct: float) -> tuple[str, str]:
    if pct < DECOUPLING_THRESHOLDS["excellent"]:
        return "excellent", "Strong aerobic base; ready for longer efforts."
    if pct < DECOUPLING_THRESHOLDS["good"]:
        return "good", "Solid aerobic fitness; continue building volume."
    if pct < DECOUPLING_THRESHOLDS["moderate"]:
        return "moderate", "Some aerobic drift; add easy long runs to improve."
    return "poor", "Significant drift detected; prioritise aerobic base training."


def _classify_durability(score: float) -> tuple[str, str]:
    if score >= DURABILITY_THRESHOLDS["elite"]:
        return "elite", "Exceptional fatigue resistance across all metrics."
    if score >= DURABILITY_THRESHOLDS["good"]:
        return "good", "Solid durability; minor drift under prolonged load."
    if score >= DURABILITY_THRESHOLDS["average"]:
        return "average", "Moderate fatigue resistance; targeted long runs will help."
    return "developing", "Durability is a limiter; build aerobic volume progressively."


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def calculate_aerobic_decoupling(
    pace_series: pd.Series,
    hr_series: pd.Series,
    split_method: str = "half",
) -> Dict:
    """Pa:HR aerobic decoupling analysis (TrainingPeaks / Friel methodology)."""
    pace, hr = _filter_active(pace_series, hr_series)
    if len(pace) < MIN_SAMPLES:
        logger.warning("Too few active samples (%d) for decoupling.", len(pace))
        return {"decoupling_pct": np.nan, "ef_first_half": np.nan,
                "ef_second_half": np.nan, "classification": "insufficient_data",
                "interpretation": "Not enough data for analysis."}

    speed = _pace_to_speed(pace)
    n = len(speed)

    if split_method == "quarter":
        q = n // 4
        ef_first = speed.iloc[:q].mean() / hr.iloc[:q].mean()
        ef_second = speed.iloc[-q:].mean() / hr.iloc[-q:].mean()
    else:
        mid = n // 2
        ef_first = speed.iloc[:mid].mean() / hr.iloc[:mid].mean()
        ef_second = speed.iloc[mid:].mean() / hr.iloc[mid:].mean()

    decoupling = (ef_first - ef_second) / ef_first * 100 if ef_first != 0 else np.nan
    classification, interpretation = _classify_decoupling(decoupling)

    return {
        "decoupling_pct": round(decoupling, 2),
        "ef_first_half": round(ef_first, 6),
        "ef_second_half": round(ef_second, 6),
        "classification": classification,
        "interpretation": interpretation,
    }


def detect_decoupling_onset(
    pace_series: pd.Series,
    hr_series: pd.Series,
    window_sec: int = 300,
) -> Dict:
    """Find the time point where decoupling begins (Smyth et al. 2025)."""
    pace, hr = _filter_active(pace_series, hr_series)
    if len(pace) < MIN_SAMPLES:
        return {"onset_time_sec": None, "onset_distance_m": None,
                "ef_at_onset": np.nan, "ef_series": pd.Series(dtype=float),
                "drift_series": pd.Series(dtype=float)}

    speed = _pace_to_speed(pace)

    # Rolling EF with given window, then smooth with 60-sample mean
    rolling_ef = (speed.rolling(window=window_sec, min_periods=window_sec // 2).mean()
                  / hr.rolling(window=window_sec, min_periods=window_sec // 2).mean())
    smoothed_ef = rolling_ef.rolling(window=60, min_periods=30).mean()

    initial_ef = smoothed_ef.dropna().iloc[0] if not smoothed_ef.dropna().empty else np.nan
    if np.isnan(initial_ef) or initial_ef == 0:
        return {"onset_time_sec": None, "onset_distance_m": None,
                "ef_at_onset": np.nan, "ef_series": rolling_ef,
                "drift_series": pd.Series(dtype=float)}

    drift_pct = (initial_ef - smoothed_ef) / initial_ef * 100

    # Onset = first point where drift > 3% sustained for > DRIFT_ONSET_HOLD_SEC
    above = drift_pct > DRIFT_ONSET_PCT
    onset_idx = None
    run_start = None
    for i, (idx, val) in enumerate(above.items()):
        if val:
            if run_start is None:
                run_start = i
            if (i - run_start) >= DRIFT_ONSET_HOLD_SEC:
                onset_idx = run_start
                break
        else:
            run_start = None

    onset_time = int(onset_idx) if onset_idx is not None else None
    ef_at_onset = float(smoothed_ef.iloc[onset_idx]) if onset_idx is not None else np.nan

    return {
        "onset_time_sec": onset_time,
        "onset_distance_m": None,
        "ef_at_onset": round(ef_at_onset, 6) if not np.isnan(ef_at_onset) else np.nan,
        "ef_series": rolling_ef,
        "drift_series": drift_pct,
    }


def calculate_cardiac_drift_rate(
    hr_series: pd.Series,
    time_series: Optional[pd.Series] = None,
    window_sec: int = 600,
    pace_series: Optional[pd.Series] = None,
) -> Dict:
    """Rate of HR increase during steady-state running (linear regression, 2nd half)."""
    hr = hr_series.dropna().copy()
    if len(hr) < MIN_SAMPLES:
        return {"drift_bpm_per_min": np.nan, "drift_bpm_per_hour": np.nan,
                "is_steady_state": False, "r_squared": np.nan}

    time_sec = (
        time_series.loc[hr.index].copy() if time_series is not None
        else pd.Series(range(len(hr)), index=hr.index, dtype=float)
    )

    mid = len(hr) // 2
    hr_2nd = hr.iloc[mid:].values
    t_2nd = time_sec.iloc[mid:].values.astype(float)

    if len(hr_2nd) < 10:
        return {"drift_bpm_per_min": np.nan, "drift_bpm_per_hour": np.nan,
                "is_steady_state": False, "r_squared": np.nan}

    slope, _intercept, r_value, _p, _se = stats.linregress(t_2nd, hr_2nd)
    drift_per_sec = float(slope)
    drift_per_min = drift_per_sec * 60
    drift_per_hour = drift_per_min * 60
    r_sq = float(r_value ** 2)

    is_steady = False
    if pace_series is not None:
        active_pace, _ = _filter_active(pace_series, hr_series)
        if len(active_pace) > MIN_SAMPLES:
            cv = active_pace.std() / active_pace.mean() * 100
            is_steady = cv < 5.0

    return {
        "drift_bpm_per_min": round(drift_per_min, 4),
        "drift_bpm_per_hour": round(drift_per_hour, 2),
        "is_steady_state": is_steady,
        "r_squared": round(r_sq, 4),
    }


def calculate_durability_index(
    pace_series: pd.Series,
    hr_series: pd.Series,
    time_series: Optional[pd.Series] = None,
) -> Dict:
    """Comprehensive durability score (Jones 2024 'fourth dimension')."""
    W_DECOUPLING = 0.4
    W_PACE_CV = 0.3
    W_HR_DRIFT = 0.3

    decoupling_result = calculate_aerobic_decoupling(pace_series, hr_series)
    drift_result = calculate_cardiac_drift_rate(
        hr_series, time_series=time_series, pace_series=pace_series,
    )

    pace, _hr = _filter_active(pace_series, hr_series)
    pace_cv = float(pace.std() / pace.mean() * 100) if len(pace) > MIN_SAMPLES else np.nan

    dec_pct = decoupling_result["decoupling_pct"]
    drift_bpm = drift_result["drift_bpm_per_min"]

    # Convert each metric to a 0-100 sub-score (100 = perfect stability)
    dec_score = max(0.0, 100.0 - dec_pct * 10) if not np.isnan(dec_pct) else np.nan
    cv_score = max(0.0, 100.0 - pace_cv * 5) if not np.isnan(pace_cv) else np.nan
    drift_score = (
        max(0.0, 100.0 - abs(drift_bpm) * 30) if not np.isnan(drift_bpm) else np.nan
    )

    valid = [(dec_score, W_DECOUPLING), (cv_score, W_PACE_CV), (drift_score, W_HR_DRIFT)]
    valid = [(s, w) for s, w in valid if not np.isnan(s)]

    if not valid:
        durability = np.nan
    else:
        total_w = sum(w for _, w in valid)
        durability = sum(s * w for s, w in valid) / total_w

    durability = round(float(durability), 1) if not np.isnan(durability) else np.nan
    classification, interpretation = (
        _classify_durability(durability) if not np.isnan(durability)
        else ("insufficient_data", "Not enough data for analysis.")
    )

    return {
        "durability_score": durability,
        "decoupling_pct": round(dec_pct, 2) if not np.isnan(dec_pct) else np.nan,
        "pace_cv_pct": round(pace_cv, 2) if not np.isnan(pace_cv) else np.nan,
        "hr_drift_bpm_per_min": round(drift_bpm, 4) if not np.isnan(drift_bpm) else np.nan,
        "classification": classification,
        "interpretation": interpretation,
    }
