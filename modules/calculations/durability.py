"""Aerobic decoupling from speed and heart rate."""

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# --- Constants ---
STOPPED_PACE_THRESHOLD = 900  # s/km; above this the runner is stopped
MIN_SAMPLES = 20
DECOUPLING_THRESHOLDS = {"excellent": 3.0, "good": 5.0, "moderate": 8.0}
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
        return {
            "decoupling_pct": np.nan,
            "ef_first_half": np.nan,
            "ef_second_half": np.nan,
            "classification": "insufficient_data",
            "interpretation": "Not enough data for analysis.",
        }

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
        return {
            "onset_time_sec": None,
            "onset_distance_m": None,
            "ef_at_onset": np.nan,
            "ef_series": pd.Series(dtype=float),
            "drift_series": pd.Series(dtype=float),
        }

    speed = _pace_to_speed(pace)

    # Rolling EF with given window, then smooth with 60-sample mean
    rolling_ef = (
        speed.rolling(window=window_sec, min_periods=window_sec // 2).mean()
        / hr.rolling(window=window_sec, min_periods=window_sec // 2).mean()
    )
    smoothed_ef = rolling_ef.rolling(window=60, min_periods=30).mean()

    initial_ef = smoothed_ef.dropna().iloc[0] if not smoothed_ef.dropna().empty else np.nan
    if np.isnan(initial_ef) or initial_ef == 0:
        return {
            "onset_time_sec": None,
            "onset_distance_m": None,
            "ef_at_onset": np.nan,
            "ef_series": rolling_ef,
            "drift_series": pd.Series(dtype=float),
        }

    drift_pct = (initial_ef - smoothed_ef) / initial_ef * 100

    # Onset = first point where drift > 3% sustained for > DRIFT_ONSET_HOLD_SEC
    above = drift_pct > DRIFT_ONSET_PCT
    onset_idx = None
    run_start = None
    for i, (_idx, val) in enumerate(above.items()):
        if val:
            if run_start is None:
                run_start = i
            if (i - run_start) >= DRIFT_ONSET_HOLD_SEC:
                onset_idx = run_start
                break
        else:
            run_start = None

    onset_time = int(pace.index[onset_idx]) if onset_idx is not None else None
    ef_at_onset = float(smoothed_ef.iloc[onset_idx]) if onset_idx is not None else np.nan

    return {
        "onset_time_sec": onset_time,
        "onset_distance_m": None,
        "ef_at_onset": round(ef_at_onset, 6) if not np.isnan(ef_at_onset) else np.nan,
        "ef_series": rolling_ef,
        "drift_series": drift_pct,
    }
