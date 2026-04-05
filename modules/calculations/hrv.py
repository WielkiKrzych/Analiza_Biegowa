"""
SRP: Moduł odpowiedzialny za analizę HRV i DFA Alpha-1.
"""

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from numba import jit

from .common import ensure_pandas

# FIX: Add logger to avoid NameError on lines 273, 276
logger = logging.getLogger(__name__)


@jit(nopython=True)
def _calc_alpha1_numba(rr_values: np.ndarray) -> float:
    """True DFA Alpha-1 calculation for short-term fractal correlation (Rogers et al. methodology)."""
    if len(rr_values) < 20:
        return np.nan

    # Scale range for Alpha-1 (short-range correlations)
    scales = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], dtype=np.float64)

    # Standardize and Integrate signal
    y = np.cumsum(rr_values - np.mean(rr_values))

    fluctuations = np.zeros(len(scales))

    for idx_n, n in enumerate(scales):
        n_int = int(n)
        num_windows = len(y) // n_int
        if num_windows == 0:
            continue

        rms_sum = 0.0
        # Indices for linear fit optimization: 0...n-1
        x_indices = np.arange(n_int).astype(np.float64)
        x_mean = (n_int - 1.0) / 2.0
        x_var = np.sum((x_indices - x_mean) ** 2)

        for i in range(num_windows):
            start = i * n_int
            seg = y[start : start + n_int]

            # Fast Linear Regression in Numba
            seg_mean = np.mean(seg)
            slope = np.sum((x_indices - x_mean) * (seg - seg_mean)) / x_var
            intercept = seg_mean - slope * x_mean

            # Residual Sum of Squares
            fit = slope * x_indices + intercept
            rms_sum += np.sum((seg - fit) ** 2)

        fluctuations[idx_n] = np.sqrt(rms_sum / (num_windows * n_int))

    # Linear regression in log-log space (Alpha = slope)
    log_scales = np.log(scales)
    log_flucts = np.log(fluctuations)

    # Filter out invalid logs
    mask = ~(np.isnan(log_flucts) | np.isinf(log_flucts))
    if np.sum(mask) < 4:
        return np.nan

    ls = log_scales[mask]
    lf = log_flucts[mask]

    ls_mean = np.mean(ls)
    lf_mean = np.mean(lf)
    alpha = np.sum((ls - ls_mean) * (lf - lf_mean)) / np.sum((ls - ls_mean) ** 2)

    return alpha


@jit(nopython=True)
def _fast_dfa_loop(time_values, rr_values, window_sec, step_sec):
    """Szybka pętla DFA z użyciem Numba - sliding window analysis."""
    n = len(time_values)
    results_time = []
    results_alpha = []
    results_rmssd = []
    results_pnn50 = []  # FIX: Add pNN50 results
    results_sdnn = []
    results_mean_rr = []
    start_t = time_values[0]
    end_t = time_values[-1]

    curr_t = start_t + window_sec

    left_idx = 0
    right_idx = 0

    while curr_t < end_t:
        while right_idx < n and time_values[right_idx] <= curr_t:
            right_idx += 1

        win_start = curr_t - window_sec
        while left_idx < right_idx and time_values[left_idx] < win_start:
            left_idx += 1

        window_len = right_idx - left_idx

        if window_len >= 30:
            window_rr = rr_values[left_idx:right_idx]

            # IQR Outlier Removal
            q25 = np.nanpercentile(window_rr, 25)
            q75 = np.nanpercentile(window_rr, 75)
            iqr = q75 - q25
            lower = q25 - 1.5 * iqr
            upper = q75 + 1.5 * iqr

            clean_rr = window_rr[(window_rr > lower) & (window_rr < upper)]

            if len(clean_rr) >= 20:
                # RMSSD
                diffs_sq_sum = 0.0
                for k in range(len(clean_rr) - 1):
                    d = clean_rr[k + 1] - clean_rr[k]
                    diffs_sq_sum += d * d
                rmssd = np.sqrt(diffs_sq_sum / (len(clean_rr) - 1))

                # FIX: pNN50 - percentage of RR intervals differing by >50ms
                nn50_count = 0
                for k in range(len(clean_rr) - 1):
                    if abs(clean_rr[k + 1] - clean_rr[k]) > 50:
                        nn50_count += 1
                pnn50 = (nn50_count / (len(clean_rr) - 1)) * 100 if len(clean_rr) > 1 else 0.0

                # SDNN
                sdnn = np.std(clean_rr)
                mean_rr = np.mean(clean_rr)

                # Real True Alpha1
                alpha1 = _calc_alpha1_numba(clean_rr)

                if not np.isnan(alpha1):
                    # Clip to sensible physiology
                    alpha1 = max(0.2, min(1.8, alpha1))

                    results_time.append(curr_t)
                    results_alpha.append(alpha1)
                    results_rmssd.append(rmssd)
                    results_pnn50.append(pnn50)
                    results_sdnn.append(sdnn)
                    results_mean_rr.append(mean_rr)

        curr_t += step_sec
    return results_time, results_alpha, results_rmssd, results_pnn50, results_sdnn, results_mean_rr


# ============================================================
# DFA Quality Validation
# ============================================================


def validate_dfa_quality(
    window_sec: int,
    data_quality: float,
    mean_alpha1: Optional[float],
    windows_analyzed: int,
    min_window_sec: int = 120,
) -> Tuple[bool, List[str], str]:
    """
    Validate DFA-a1 result quality and determine uncertainty.

    DFA-a1 is HIGHLY SENSITIVE to artifacts in RR data.
    If conditions are not met, result should be marked as "uncertain".

    Args:
        window_sec: Window size used for DFA
        data_quality: Ratio of valid samples (0-1)
        mean_alpha1: Mean Alpha-1 value
        windows_analyzed: Number of windows analyzed
        min_window_sec: Minimum required window (default: 120s)

    Returns:
        Tuple of (is_uncertain, uncertainty_reasons, quality_grade)
    """
    is_uncertain = False
    reasons = []
    quality_grade = "A"

    # Check 1: Minimum window length
    if window_sec < min_window_sec:
        is_uncertain = True
        reasons.append(f"Okno {window_sec}s < minimum {min_window_sec}s")
        quality_grade = "D"

    # Check 2: Data quality (artifacts)
    if data_quality < 0.9:
        is_uncertain = True
        reasons.append(f"Jakość danych {data_quality:.0%} < 90% (za dużo artefaktów)")
        quality_grade = "D" if quality_grade != "D" else "F"
    elif data_quality < 0.95:
        reasons.append(f"Jakość danych {data_quality:.0%} - umiarkowana ilość artefaktów")
        quality_grade = max("C", quality_grade)

    # Check 3: Alpha1 range at moderate intensity
    if mean_alpha1 is not None:
        if mean_alpha1 < 0.5 or mean_alpha1 > 1.5:
            is_uncertain = True
            reasons.append(f"Alpha1 = {mean_alpha1:.2f} poza typowym zakresem [0.5-1.5]")
            quality_grade = "D"

    # Check 4: Minimum windows analyzed
    if windows_analyzed < 3:
        is_uncertain = True
        reasons.append(f"Za mało okien ({windows_analyzed} < 3)")
        quality_grade = "F"

    # Determine final grade if not already set
    if not is_uncertain and quality_grade == "A":
        if data_quality >= 0.98 and windows_analyzed >= 10:
            quality_grade = "A"
        elif data_quality >= 0.95:
            quality_grade = "B"
        else:
            quality_grade = "C"

    return is_uncertain, reasons, quality_grade


# Cache for DFA results with max size to prevent memory leak
from collections import OrderedDict


class LRUCache(OrderedDict):
    """LRU Cache with max size limit."""

    def __init__(self, maxsize: int = 10):
        super().__init__()
        self.maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            self.popitem(last=False)


dfa_cache = LRUCache(maxsize=10)


def _generate_cache_key(
    df_pl, window_sec: int, step_sec: int, min_samples_hrv: int, alpha1_clip_range: tuple
) -> str:
    """Generate a unique cache key based on input parameters and data hash."""
    import hashlib

    df = ensure_pandas(df_pl)

    # Create a hash of the data
    data_str = f"{df.shape}{df.columns.tolist()}{df.head(1).to_string()}{df.tail(1).to_string()}"
    data_hash = hashlib.md5(data_str.encode()).hexdigest()[:16]

    # Include parameters in key
    key = f"{data_hash}_{window_sec}_{step_sec}_{min_samples_hrv}_{alpha1_clip_range}"
    return key


def _find_rr_column(df: pd.DataFrame) -> Optional[str]:
    """Find the R-R/HRV column name using case-insensitive matching.

    Searches for exact matches first, then falls back to partial matches
    (e.g. 'HRV (ms)').

    Args:
        df: DataFrame whose columns to search.

    Returns:
        Column name string if found, else None.
    """
    search_terms = ["rr", "rr_interval", "hrv", "ibi", "r-r", "rr_ms"]

    # Exact match (case-insensitive, trimmed)
    col = next(
        (c for c in df.columns if any(x == c.lower().strip() for x in search_terms)),
        None,
    )
    if col is not None:
        return col

    # Partial match (e.g. "HRV (ms)")
    return next(
        (c for c in df.columns if any(x in c.lower() for x in search_terms)),
        None,
    )


def _normalize_numeric_rr(val: float) -> float:
    """Normalize a numeric RR value to milliseconds.

    Accepts ms (300-2000), seconds (0.3-2.0), and μs (300000-2000000).
    Returns np.nan for out-of-range values.
    """
    if 300 <= val <= 2000:
        return float(val)
    if 0.3 <= val <= 2.0:
        return float(val * 1000)
    if 300000 <= val <= 2000000:
        return float(val / 1000)
    return np.nan


def _parse_colon_separated_rr(val: str) -> float:
    """Parse colon-separated RR intervals ('493:490') or HH:MM:SS into ms.

    Returns np.nan if the format cannot be parsed or the result is out of
    the 300-2000 ms physiological range.
    """
    parts = val.split(":")
    if not parts:
        return np.nan

    # Try interpreting all parts as RR intervals (Intervals.icu format)
    try:
        rr_vals = [float(p) for p in parts if p.strip()]
        mean_rr = float(np.mean(rr_vals))
        if 300 <= mean_rr <= 2000:
            return mean_rr
    except ValueError:
        pass

    # Fallback: HH:MM:SS interpretation (only for exactly 3 parts)
    if len(parts) == 3:
        try:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
            if 300 <= total_ms <= 2000:
                return total_ms
        except ValueError:
            pass

    return np.nan


def _clean_rr_value(val: object) -> float:
    """Convert various RR formats to milliseconds.

    Handles:
    - Numeric values in ms, seconds, or microseconds
    - String numbers ("648")
    - Colon-separated intervals ("493:490", "455:465:451")
    - HH:MM:SS Excel time artifacts ("0:01:05")

    Returns np.nan for unparseable or out-of-range values.
    """
    if pd.isna(val):
        return np.nan

    if isinstance(val, (int, float)):
        return _normalize_numeric_rr(float(val))

    if isinstance(val, str):
        val = val.strip()
        # Try simple numeric parse first
        try:
            return _normalize_numeric_rr(float(val))
        except ValueError:
            pass

        # Colon-separated formats
        if ":" in val:
            return _parse_colon_separated_rr(val)

    return np.nan


def _remove_rr_outliers(
    rr_data: pd.DataFrame,
    rr_col: str,
) -> pd.DataFrame:
    """Remove RR outliers using IQR method, clamped to 300-2000 ms.

    Args:
        rr_data: DataFrame with 'time' and *rr_col* columns.
        rr_col: Name of the RR interval column.

    Returns:
        Filtered DataFrame with outliers removed.
    """
    q1 = rr_data[rr_col].quantile(0.25)
    q3 = rr_data[rr_col].quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    valid_mask = (rr_data[rr_col] >= max(300, lower_bound)) & (
        rr_data[rr_col] <= min(2000, upper_bound)
    )
    return rr_data[valid_mask].copy()


def calculate_dynamic_dfa_v2(
    df_pl,
    window_sec: int = 300,
    step_sec: int = 30,
    min_samples_hrv: int = 100,
    alpha1_clip_range: Tuple[float, float] = (0.2, 1.8),
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Calculate HRV metrics (RMSSD, pNN50, SDNN, Alpha-1) in a sliding window.
    Optimized version with Numba and caching.
    V2: Robust column detection, cache-busting, and data cleaning.
    FIX: Added pNN50 (percentage of NN intervals >50ms different).

    Args:
        df_pl: DataFrame with RR data
        window_sec: Window size in seconds (default: 300)
        step_sec: Step size in seconds (default: 30)
        min_samples_hrv: Minimum RR samples required (default: 100)
        alpha1_clip_range: Min/max range for alpha1 clipping (default: 0.2-1.8)

    Returns:
        Tuple of (results DataFrame, error message or None)
    """
    # Check cache first
    cache_key = _generate_cache_key(df_pl, window_sec, step_sec, min_samples_hrv, alpha1_clip_range)
    if cache_key in dfa_cache:
        logger.debug(f"Using cached DFA results for key: {cache_key[:16]}...")
        return dfa_cache[cache_key]

    logger.debug("Executing calculate_dynamic_dfa_v2 logic...")
    df = ensure_pandas(df_pl)

    rr_col = _find_rr_column(df)
    if rr_col is None:
        return None, f"Missing R-R/HRV data column. Available: {list(df.columns)}"

    rr_data = df[["time", rr_col]].dropna().copy()

    # Clean and validate RR values
    rr_data[rr_col] = rr_data[rr_col].apply(_clean_rr_value)
    rr_data = rr_data.dropna()
    rr_data = rr_data[rr_data[rr_col] > 0]

    if len(rr_data) < min_samples_hrv:
        return None, f"Za mało danych R-R ({len(rr_data)} < {min_samples_hrv})"

    # Outlier removal using IQR method
    rr_data = _remove_rr_outliers(rr_data, rr_col)

    if len(rr_data) < min_samples_hrv:
        return (
            None,
            f"Za mało danych R-R po usunięciu artefaktów ({len(rr_data)} < {min_samples_hrv})",
        )

    # Data is already cleaned to ms by _clean_rr_value (300-2000ms range).
    # No secondary unit conversion needed — the cleaning step handles all
    # unit normalization. Removed dead code that could cause latent bugs.

    rr_values = rr_data[rr_col].values.astype(np.float64)
    time_values = rr_data["time"].values.astype(np.float64)

    try:
        r_time, r_alpha, r_rmssd, r_pnn50, r_sdnn, r_mean_rr = _fast_dfa_loop(
            time_values, rr_values, float(window_sec), float(step_sec)
        )

        if not r_time:
            return None, "Brak wyników (zbyt mało danych w oknach?)"

        results = pd.DataFrame(
            {
                "time": r_time,
                "alpha1": r_alpha,
                "rmssd": r_rmssd,
                "pnn50": r_pnn50,  # FIX: Add pNN50 column
                "sdnn": r_sdnn,
                "mean_rr": r_mean_rr,
            }
        )

        # Store in cache
        dfa_cache[cache_key] = (results, None)

        return results, None

    except (ValueError, TypeError, RuntimeError) as e:  # noqa: BLE001
        return None, f"Błąd obliczeń Numba: {e}"


# ============================================================
# Dynamical DFA (DDFA) — time-varying DFA alpha1
# Reference: Frontiers in Physiology 2023 (DDFA), Rogers et al. 2021
# ============================================================


def _classify_alpha1_zone(alpha1: float) -> str:
    """Classify a single alpha1 value into an intensity zone."""
    if alpha1 > 1.0:
        return "correlated"
    if alpha1 > 0.75:
        return "moderate"
    if alpha1 > 0.5:
        return "transition"
    return "uncorrelated"


def calculate_ddfa(
    rr_intervals: np.ndarray,
    window_beats: int = 120,
    step_beats: int = 10,
) -> dict:
    """
    Dynamical DFA (DDFA) — compute time-varying DFA alpha1 over a sliding window.

    Args:
        rr_intervals: 1-D array of RR intervals in ms.
        window_beats: Number of RR intervals per window (default 120).
        step_beats: Stride in beats between successive windows (default 10).

    Returns:
        Dictionary with alpha1 time series, zone classification, and
        HRVT1/HRVT2 beat indices (first sustained downward crossings
        of 0.75 and 0.50 respectively).
    """
    rr = np.asarray(rr_intervals, dtype=np.float64)
    n = len(rr)

    if n < window_beats:
        return {
            "alpha1_series": np.array([]),
            "time_indices": np.array([], dtype=np.int64),
            "mean_alpha1": np.nan,
            "hrvt1_beat_idx": None,
            "hrvt2_beat_idx": None,
            "zone_classification": [],
        }

    alpha1_list: list[float] = []
    center_list: list[int] = []

    start = 0
    while start + window_beats <= n:
        window = rr[start : start + window_beats]
        a1 = float(_calc_alpha1_numba(window))
        if not np.isnan(a1):
            a1 = max(0.2, min(1.8, a1))
        alpha1_list.append(a1)
        center_list.append(start + window_beats // 2)
        start += step_beats

    alpha1_series = np.array(alpha1_list)
    time_indices = np.array(center_list, dtype=np.int64)
    zones = [_classify_alpha1_zone(a) for a in alpha1_list]

    # Detect first downward crossing of a threshold
    def _first_crossing(series: np.ndarray, indices: np.ndarray, threshold: float):
        for i, val in enumerate(series):
            if not np.isnan(val) and val < threshold:
                return int(indices[i])
        return None

    valid = alpha1_series[~np.isnan(alpha1_series)]
    mean_a1 = float(np.mean(valid)) if len(valid) > 0 else np.nan

    return {
        "alpha1_series": alpha1_series,
        "time_indices": time_indices,
        "mean_alpha1": mean_a1,
        "hrvt1_beat_idx": _first_crossing(alpha1_series, time_indices, 0.75),
        "hrvt2_beat_idx": _first_crossing(alpha1_series, time_indices, 0.50),
        "zone_classification": zones,
    }


def _find_sustained_crossing(
    alpha1_series: np.ndarray,
    time_indices: np.ndarray,
    time_stamps: np.ndarray,
    threshold: float,
    sustained_sec: float = 60.0,
) -> Tuple[Optional[int], Optional[float]]:
    """Return beat index and time where alpha1 stays below threshold for >= sustained_sec."""
    candidate_idx: Optional[int] = None
    candidate_time: Optional[float] = None

    for a1, beat_idx in zip(alpha1_series, time_indices, strict=False):
        if np.isnan(a1):
            candidate_idx = None
            continue
        t = float(time_stamps[min(beat_idx, len(time_stamps) - 1)])
        if a1 < threshold:
            if candidate_idx is None:
                candidate_idx = int(beat_idx)
                candidate_time = t
            elif t - candidate_time >= sustained_sec:
                return candidate_idx, candidate_time
        else:
            candidate_idx = None
            candidate_time = None
    return None, None


def _lookup_hrv_value(beat_idx: Optional[int], source: Optional[np.ndarray]) -> Optional[float]:
    """Look up a physiological value at the given beat index."""
    if beat_idx is None or source is None:
        return None
    return float(source[min(beat_idx, len(source) - 1)])


def detect_hrv_thresholds(
    rr_intervals: np.ndarray,
    time_stamps: Optional[np.ndarray] = None,
    hr_series: Optional[np.ndarray] = None,
    pace_series: Optional[np.ndarray] = None,
) -> dict:
    """
    Detect HRVT1 and HRVT2 from DFA alpha1 trend.

    HRVT1 = time where alpha1 consistently drops below 0.75 (sustained >60 s).
    HRVT2 = time where alpha1 consistently drops below 0.50 (sustained >60 s).

    Args:
        rr_intervals: 1-D array of RR intervals in ms.
        time_stamps: Optional cumulative time in seconds for each beat.
        hr_series: Optional HR values aligned to beats.
        pace_series: Optional pace values (min/km) aligned to beats.

    Returns:
        Dictionary with threshold times, HR, pace, alpha1 series and confidence.

    Reference: Rogers et al. 2021 (Frontiers in Physiology).
    """
    rr = np.asarray(rr_intervals, dtype=np.float64)
    ddfa = calculate_ddfa(rr, window_beats=120, step_beats=10)

    if time_stamps is None:
        time_stamps = np.cumsum(rr) / 1000.0

    empty_result = {
        "hrvt1_time_sec": None,
        "hrvt1_hr": None,
        "hrvt1_pace": None,
        "hrvt2_time_sec": None,
        "hrvt2_hr": None,
        "hrvt2_pace": None,
        "alpha1_series": ddfa["alpha1_series"],
        "confidence": 0.0,
    }

    if len(ddfa["alpha1_series"]) == 0:
        return empty_result

    hrvt1_beat, hrvt1_t = _find_sustained_crossing(
        ddfa["alpha1_series"], ddfa["time_indices"], time_stamps, 0.75
    )
    hrvt2_beat, hrvt2_t = _find_sustained_crossing(
        ddfa["alpha1_series"], ddfa["time_indices"], time_stamps, 0.50
    )

    valid_count = int(np.sum(~np.isnan(ddfa["alpha1_series"])))
    total = len(ddfa["alpha1_series"])
    confidence = valid_count / total if total > 0 else 0.0

    return {
        "hrvt1_time_sec": int(hrvt1_t) if hrvt1_t is not None else None,
        "hrvt1_hr": _lookup_hrv_value(hrvt1_beat, hr_series),
        "hrvt1_pace": _lookup_hrv_value(hrvt1_beat, pace_series),
        "hrvt2_time_sec": int(hrvt2_t) if hrvt2_t is not None else None,
        "hrvt2_hr": _lookup_hrv_value(hrvt2_beat, hr_series),
        "hrvt2_pace": _lookup_hrv_value(hrvt2_beat, pace_series),
        "alpha1_series": ddfa["alpha1_series"],
        "confidence": round(confidence, 3),
    }
