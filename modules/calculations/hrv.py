"""
SRP: Moduł odpowiedzialny za analizę HRV i DFA Alpha-1.
"""

from typing import Optional, Tuple, List
import numpy as np
import pandas as pd
from numba import jit

from .common import ensure_pandas


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
                    results_sdnn.append(sdnn)
                    results_mean_rr.append(mean_rr)

        curr_t += step_sec
    return results_time, results_alpha, results_rmssd, results_sdnn, results_mean_rr


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


# Cache for DFA results to avoid recomputation
dfa_cache = {}


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


def calculate_dynamic_dfa_v2(
    df_pl,
    window_sec: int = 300,
    step_sec: int = 30,
    min_samples_hrv: int = 100,
    alpha1_clip_range: Tuple[float, float] = (0.2, 1.8),
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Calculate HRV metrics (RMSSD, SDNN, Alpha-1) in a sliding window.
    Optimized version with Numba and caching.
    V2: Robust column detection, cache-busting, and data cleaning.

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
        print(f"[DEBUG] Using cached DFA results for key: {cache_key[:16]}...")
        return dfa_cache[cache_key]

    print(f"[DEBUG] Executing calculate_dynamic_dfa_v2 logic...")
    df = ensure_pandas(df_pl)

    # Robust column detection (case-insensitive)
    search_terms = ["rr", "rr_interval", "hrv", "ibi", "r-r", "rr_ms"]
    rr_col = next(
        (c for c in df.columns if any(x == c.lower().strip() for x in search_terms)), None
    )

    # If not found, try partial match (e.g. "HRV (ms)")
    if rr_col is None:
        rr_col = next((c for c in df.columns if any(x in c.lower() for x in search_terms)), None)

    if rr_col is None:
        return None, f"Missing R-R/HRV data column. Available: {list(df.columns)}"

    rr_data = df[["time", rr_col]].dropna()

    # Clean HRV data - handle Excel time format (HH:MM:SS) and other invalid formats
    def clean_rr_value(val):
        """Convert various RR formats to milliseconds."""
        if pd.isna(val):
            return np.nan

        # If already numeric, validate range
        if isinstance(val, (int, float)):
            if 300 <= val <= 2000:  # Normal RR range in ms
                return float(val)
            elif 0.3 <= val <= 2.0:  # Seconds
                return float(val * 1000)
            elif 300000 <= val <= 2000000:  # Microseconds
                return float(val / 1000)
            else:
                return np.nan  # Out of range

        # Handle string formats (e.g., "648", "681:07:00")
        if isinstance(val, str):
            val = val.strip()
            # Try parsing as simple number first
            try:
                num_val = float(val)
                return clean_rr_value(num_val)
            except ValueError:
                pass

            # Handle HH:MM:SS format (Excel time export artifact)
            if ":" in val:
                parts = val.split(":")
                if len(parts) == 3:
                    try:
                        hours = float(parts[0])
                        minutes = float(parts[1])
                        seconds = float(parts[2])
                        total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
                        # Validate: if result is > 10 seconds, it's likely an error
                        if 300 <= total_ms <= 2000:
                            return total_ms
                    except ValueError:
                        pass

        return np.nan

    # Apply cleaning
    rr_data[rr_col] = rr_data[rr_col].apply(clean_rr_value)
    rr_data = rr_data.dropna()
    rr_data = rr_data[rr_data[rr_col] > 0]

    if len(rr_data) < min_samples_hrv:
        return None, f"Za mało danych R-R ({len(rr_data)} < {min_samples_hrv})"

    # Outlier removal using IQR method
    q1 = rr_data[rr_col].quantile(0.25)
    q3 = rr_data[rr_col].quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    # Keep only values within IQR bounds (but minimum 300ms, max 2000ms)
    valid_mask = (rr_data[rr_col] >= max(300, lower_bound)) & (
        rr_data[rr_col] <= min(2000, upper_bound)
    )
    rr_data = rr_data[valid_mask]

    if len(rr_data) < min_samples_hrv:
        return (
            None,
            f"Za mało danych R-R po usunięciu artefaktów ({len(rr_data)} < {min_samples_hrv})",
        )

    # Automatic unit detection (already cleaned to ms)
    mean_val = rr_data[rr_col].mean()
    if mean_val < 2.0:  # Seconds -> ms
        rr_data[rr_col] = rr_data[rr_col] * 1000
    elif mean_val > 2000:  # Microseconds -> ms
        rr_data[rr_col] = rr_data[rr_col] / 1000

    rr_values = rr_data[rr_col].values.astype(np.float64)
    time_values = rr_data["time"].values.astype(np.float64)

    try:
        r_time, r_alpha, r_rmssd, r_sdnn, r_mean_rr = _fast_dfa_loop(
            time_values, rr_values, float(window_sec), float(step_sec)
        )

        if not r_time:
            return None, "Brak wyników (zbyt mało danych w oknach?)"

        results = pd.DataFrame(
            {
                "time": r_time,
                "alpha1": r_alpha,
                "rmssd": r_rmssd,
                "sdnn": r_sdnn,
                "mean_rr": r_mean_rr,
            }
        )

        # Store in cache
        dfa_cache[cache_key] = (results, None)

        return results, None

    except Exception as e:
        return None, f"Błąd obliczeń Numba: {e}"
