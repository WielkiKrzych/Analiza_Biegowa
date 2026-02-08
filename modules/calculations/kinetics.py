"""
VO2/SmO2 Kinetics Module.

Implements kinetics analysis for oxygen consumption and muscle oxygenation.
Inspired by INSCYD O2 Deficit and academic VO2 kinetics research.
Refactored to support Relative SmO2 analysis (normalization and trend classification).
Includes Context-Aware Analysis (Power/HR/Cadence fusion).
Includes Resaturation Analysis (Recovery Kinetics).
Includes Cross-Correlation Analysis (Signal Lag).
Includes State-Based Physiological Modeling.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, List
from scipy.optimize import curve_fit
from scipy import stats, signal


def normalize_smo2_series(series: pd.Series) -> pd.Series:
    """
    Normalize SmO2 series to 0.0 - 1.0 (0-100%) range based on session min/max.
    Uses 5th and 95th percentiles to be robust against artifacts/outliers.

    Args:
        series: Pandas Series with raw SmO2 values

    Returns:
        Normalized Pandas Series (0.0 to 1.0)
    """
    if series.empty:
        return series

    # Robust min/max
    val_min = series.quantile(0.02)  # 2nd percentile as physiological min
    val_max = series.quantile(0.98)  # 98th percentile as physiological max

    if val_max <= val_min:
        return series.apply(lambda x: 0.5)  # Flat line if no range

    normalized = (series - val_min) / (val_max - val_min)
    return normalized.clip(0.0, 1.0)


def detect_smo2_trend(time_series: pd.Series, smo2_series: pd.Series) -> Dict[str, any]:
    """
    Detect SmO2 trend (Slope) and classify kinetics state.

    Args:
        time_series: Time in seconds
        smo2_series: SmO2 values (can be raw or normalized)

    Returns:
        Dictionary with slope, interpretation, and category.
    """
    if len(time_series) < 10:
        return {
            "slope": 0.0,
            "category": "Niewystarczające dane",
            "description": "Za mało punktów danych",
        }

    slope, _, _, _, std_err = stats.linregress(time_series, smo2_series)

    # Classification thresholds (assuming %/s for raw, or unit/s for norm)
    # If raw SmO2 (0-100), slope is %/s.

    category = "Stabilny"
    description = "Równowaga (Stan stały)"

    if slope < -0.05:
        category = "Szybka deoksygenacja"
        description = "Wysoka intensywność (>> CP). Bardzo szybka ekstrakcja O2."
    elif slope < -0.01:
        category = "Deoksygenacja"
        description = "Stan niestały (> CP). Dług tlenowy kumuluje się."
    elif slope <= 0.01:
        category = "Równowaga"
        description = "Stan stały. Podaż równa się popytowi."
    elif slope > 0.05:
        category = "Szybka reoksygenacja"
        description = "Regeneracja / Reperfuzja."
    else:  # > 0.01
        category = "Reoksygenacja"
        description = "Podaż przewyższa popyt (Regeneracja)."

    return {"slope": slope, "std_err": std_err, "category": category, "description": description}


def classify_smo2_context(
    df_window: pd.DataFrame, smo2_trend_result: Dict[str, any]
) -> Dict[str, str]:
    """
    Infer the physiological cause of the SmO2 trend using concurrent signals.

    Args:
        df_window: DataFrame with 'time', 'watts', 'hr', 'cadence' (optional)
        smo2_trend_result: Result from detect_smo2_trend

    Returns:
        Dict with 'cause', 'explanation', 'confidence'
    """
    category = smo2_trend_result.get("category", "")
    slope_smo2 = smo2_trend_result.get("slope", 0)

    if "Niewystarczaj" in category:
        return {"cause": "Nieznana", "explanation": "Niewystarczające dane"}

    # Calculate trends for other metrics
    time = df_window["time"]

    # Power Trend
    if "watts" in df_window.columns:
        slope_watts, _, _, _, _ = stats.linregress(time, df_window["watts"])
    else:
        slope_watts = 0

    # HR Trend
    if "hr" in df_window.columns:
        slope_hr, _, _, _, _ = stats.linregress(time, df_window["hr"])
    else:
        slope_hr = 0

    # Cadence Stats
    avg_cadence = df_window["cadence"].mean() if "cadence" in df_window.columns else 90

    # === HEURISTICS ===

    # 1. DEOXYGENATION CASES (Slope < -0.01)
    if slope_smo2 < -0.01:
        # A. Mechanical Occlusion (Grinding)
        # Low cadence + Stable/Rising Torque implies high muscle tension restricting flow
        if avg_cadence < 65 and avg_cadence > 10:  # >10 to ignore coasting
            return {
                "cause": "Okluzja mechaniczna",
                "explanation": f"Niska kadencja ({avg_cadence:.0f} rpm) tworzy wysokie napięcie mięśniowe, fizycznie ograniczając przepływ krwi.",
                "type": "mechanical",
            }

        # B. Demand Driven
        # Power is rising significantly
        if slope_watts > 0.5:  # Rising by >0.5 W/s
            return {
                "cause": "Napędzany popytem",
                "explanation": "Normalna odpowiedź na rosnącą moc wyjściową.",
                "type": "normal",
            }

        # C. Efficiency Loss (Fading)
        # Power is dropping but we are STILL desaturating? Very bad sign.
        if slope_watts < -0.5:
            return {
                "cause": "Utrata efektywności",
                "explanation": "Desaturacja kontynuuje się mimo spadającej mocy. Wskazuje na poważne zmęczenie metaboliczne lub rozjechanie.",
                "type": "warning",
            }

        # D. Delivery Limitation (Supply constrained)
        # Power is steady, but we are desaturating.
        # Check HR. If HR is flat/maxed, it might be cardiac limit.
        if abs(slope_watts) <= 0.5:
            return {
                "cause": "Ograniczenie dostawy",
                "explanation": "Desaturacja przy stałej mocy. Podaż tlenu nie może zaspokoić stałego popytu.",
                "type": "limit",
            }

        return {
            "cause": "Stres metaboliczny",
            "explanation": "Ogólne zużycie przewyższa podaż.",
            "type": "normal",
        }

    # 2. EQUILIBRIUM / STABLE
    elif abs(slope_smo2) <= 0.01:
        return {
            "cause": "Stan stały",
            "explanation": "Podaż tlenu równa się popytowi.",
            "type": "success",
        }

    # 3. REOXYGENATION
    else:  # > 0.01
        if slope_watts < -0.5:
            return {
                "cause": "Regeneracja",
                "explanation": "Normalna regeneracja z powodu zmniejszonego obciążenia.",
                "type": "success",
            }
        else:
            return {
                "cause": "Przesterowanie / Rozgrzewka",
                "explanation": "Podaż przewyższa popyt mimo stałego/rosnącego obciążenia (efekt rozgrzewki).",
                "type": "success",
            }


def calculate_resaturation_metrics(
    time_series: pd.Series, smo2_series: pd.Series
) -> Dict[str, float]:
    """
    Calculate Resaturation (Recovery) Metrics: T1/2, Tau, Rate.

    Args:
        time_series: Time inputs (seconds)
        smo2_series: SmO2 values (absolute or normalized)

    Returns:
        Dict with T_half, Tau, Resat_Rate, Score
    """
    if len(time_series) < 10:
        return {}

    # Zero time
    t = time_series.values - time_series.values[0]
    y = smo2_series.values

    # 1. Basic Stats
    min_val = np.min(y)
    max_val = np.max(y)
    range_val = max_val - min_val

    if range_val <= 0.0:
        return {"t_half": 0, "tau": 0, "rate": 0, "score": 0}

    # 2. T1/2 (Time to 50% recovery)
    target_50 = min_val + (range_val * 0.5)

    # Find first index where y >= target_50
    # Assuming generally increasing for resaturation
    idx_50 = np.argmax(y >= target_50)
    if y[idx_50] < target_50:  # If never reached (argmax returns 0 if all False)
        # Check if 0 is actually >= target (unlikely for min) or if max < target
        if max_val < target_50:
            t_half = t[-1]  # Never reached, assume > window
        else:
            t_half = t[idx_50]
    else:
        t_half = t[idx_50]

    # 3. Resaturation Rate (Slope of first 30s or 50% of window)
    window_limit_idx = np.searchsorted(t, 30.0)  # Look at first 30s
    if window_limit_idx < 5:
        window_limit_idx = len(t)  # If window short, use all

    slope, _, _, _, _ = stats.linregress(t[:window_limit_idx], y[:window_limit_idx])

    # 4. Tau Interpretation (Score)
    # Estimate Tau ~ T_half / ln(2) approx for mono-exponential
    tau_est = t_half / 0.693 if t_half > 0 else 0

    # Simple score: Tau < 30s = 100, Tau > 90s = 0
    score = max(0, min(100, 100 - (tau_est - 30) * (100 / 60)))
    if tau_est < 30:
        score = 100

    return {
        "t_half": float(t_half),
        "tau_est": float(tau_est),
        "resat_rate": float(slope),
        "recovery_score": float(score),
    }


def calculate_signal_lag(
    reference_series: pd.Series, target_series: pd.Series, max_lag: int = 60
) -> float:
    """
    Calculate the cross-correlation lag between two signals.
    Determine how much 'target' lags behind 'reference'.

    Args:
        reference_series: The leading signal (usually Power)
        target_series: The following signal (HR, SmO2)
        max_lag: Maximum expected lag in seconds to search

    Returns:
        Lag in seconds. Positive means Target LAGS Reference.
    """
    if len(reference_series) != len(target_series):
        # Must be same length
        min_len = min(len(reference_series), len(target_series))
        reference_series = reference_series.iloc[:min_len]
        target_series = target_series.iloc[:min_len]

    if len(reference_series) < max_lag * 2:
        return 0.0  # Too short for meaningful correlation

    # Normalize signals (Z-score) to focus on shape not magnitude
    ref = (reference_series - reference_series.mean()) / (reference_series.std() + 1e-9)
    tgt = (target_series - target_series.mean()) / (target_series.std() + 1e-9)

    # Cross-correlate
    # mode='full' returns correlation at all lags
    corr = signal.correlate(tgt, ref, mode="full")
    lags = signal.correlation_lags(len(tgt), len(ref), mode="full")

    # Find max correlation within valid window (-max_lag to +max_lag)
    mask = (lags >= -max_lag) & (lags <= max_lag)

    if not np.any(mask):
        return 0.0

    valid_lags = lags[mask]
    valid_corr = corr[mask]

    # Argmax
    peak_idx = np.argmax(valid_corr)
    best_lag = valid_lags[peak_idx]

    return float(best_lag)


def analyze_temporal_sequence(df_window: pd.DataFrame) -> Dict[str, float]:
    """
    Analyze time lags for HR and SmO2 relative to Power.
    Builds a picture of the response sequence.

    Args:
        df_window: DataFrame with 'watts', 'hr', 'smo2' (or 'smo2_norm')

    Returns:
        Dict with lags for HR, SmO2, etc.
    """
    results = {}

    if "watts" not in df_window.columns:
        return results

    # Reference
    watts = df_window["watts"]

    # Check HR Lag
    if "hr" in df_window.columns:
        lag_hr = calculate_signal_lag(watts, df_window["hr"], max_lag=90)
        results["hr_lag"] = lag_hr

    # Check SmO2 Lag (Note: SmO2 often INVERSELY correlates with Power increase)
    # We should correlate Power with -SmO2 if we want positive peak for deoxygenation?
    # Or just use raw and expect negative correlation peak?
    # Standard approach: Correlation of Power and SmO2 usually yields a negative peak.
    # To find lag, we multiply SmO2 by -1 (since power UP = SmO2 DOWN)
    if "smo2" in df_window.columns:
        # Invert SmO2 for correlation with Power
        # (Assuming Deoxygenation is the response to Load)
        lag_smo2 = calculate_signal_lag(watts, -df_window["smo2"], max_lag=60)
        results["smo2_lag"] = lag_smo2

    return results


def detect_physiological_state(df_window: pd.DataFrame, smo2_col: str = "smo2") -> Dict[str, any]:
    """
    Detects the physiological state based on signal trends in the window.

    States:
    - RECOVERY: Power < Low, HR Dropping/Low, SmO2 Rising
    - STEADY_STATE: Power Stable, HR Stable (Slope ~0), SmO2 Stable
    - NON_STEADY: Power Stable/High, HR Rising, SmO2 Dropping
    - FATIGUE: Power Dropping, HR Flat/high, SmO2 Dropping (Efficiency Loss)

    Args:
        df_window: DataFrame window (e.g. 30s)
        smo2_col: Column name for SmO2

    Returns:
        Dict with 'state', 'confidence', 'details'
    """
    if len(df_window) < 10:
        return {"state": "NIEZNANY", "confidence": 0.0}

    time = df_window["time"]

    # Calculate Slopes
    slope_watts = 0
    if "watts" in df_window.columns:
        slope_watts, _, _, _, _ = stats.linregress(time, df_window["watts"])

    slope_hr = 0
    if "hr" in df_window.columns:
        slope_hr, _, _, _, _ = stats.linregress(time, df_window["hr"])

    slope_smo2 = 0
    if smo2_col in df_window.columns:
        slope_smo2, _, _, _, _ = stats.linregress(time, df_window[smo2_col])

    # Thresholds
    # Slopes are per second

    # STATE LOGIC

    # 1. RECOVERY
    # SmO2 Rising (>0.05), Watts Dropping or Low
    if slope_smo2 > 0.05:
        confidence = min(1.0, slope_smo2 * 10)  # Higher slope = higher confidence
        return {"state": "RECOVERY", "confidence": confidence, "details": "SmO2 rising"}

    # 2. NON-STEADY (Deoxygenation)
    # SmO2 Dropping (<-0.05)
    if slope_smo2 < -0.05:
        if slope_watts < -0.5:
            return {
                "state": "FATIGUE",
                "confidence": 0.8,
                "details": "Power dropping, SmO2 dropping",
            }
        else:
            return {"state": "NON_STEADY", "confidence": 0.9, "details": "High demand (Deox)"}

    # 3. STEADY STATE vs DRIFT
    # SmO2 Stable (-0.05 to 0.05)
    else:
        # Check HR drift
        if slope_hr > 0.05:  # HR Rising significantly (>3 bpm/min)
            return {"state": "NON_STEADY", "confidence": 0.7, "details": "HR drift detected"}
        elif slope_watts > 0.5:
            return {"state": "RAMP_UP", "confidence": 0.8, "details": "Power rising"}
        else:
            return {"state": "STEADY_STATE", "confidence": 0.9, "details": "All signals stable"}


def generate_state_timeline(
    df: pd.DataFrame, window_size_sec: int = 30, step_sec: int = 10
) -> List[Dict[str, any]]:
    """
    Generate a timeline of physiological states using a sliding window.
    Merges consecutive same states.

    Args:
        df: Full session DataFrame
        window_size_sec: Size of analysis window
        step_sec: Step size for sliding

    Returns:
        List of segments dict(start, end, state, confidence)
    """
    if "time" not in df.columns:
        return []

    segments = []

    t_min = df["time"].min()
    t_max = df["time"].max()

    current_state = None
    current_segment_start = t_min
    current_confidences = []

    for t_start in np.arange(t_min, t_max - window_size_sec, step_sec):
        t_end = t_start + window_size_sec

        # Slice window
        mask = (df["time"] >= t_start) & (df["time"] < t_end)
        window = df.loc[mask]

        if len(window) < 5:
            continue

        res = detect_physiological_state(window)
        state = res["state"]
        conf = res["confidence"]

        if current_state is None:
            current_state = state
            current_segment_start = t_start
            current_confidences = [conf]

        elif state != current_state:
            # State changed, close previous segment
            avg_conf = sum(current_confidences) / len(current_confidences)
            segments.append(
                {
                    "start": float(current_segment_start),
                    "end": float(t_start),
                    "state": current_state,
                    "confidence": float(avg_conf),
                }
            )

            # Start new
            current_state = state
            current_segment_start = t_start
            current_confidences = [conf]
        else:
            # Same state, extend
            current_confidences.append(conf)

    # Close last segment
    if current_state:
        avg_conf = sum(current_confidences) / len(current_confidences)
        segments.append(
            {
                "start": float(current_segment_start),
                "end": float(t_max),
                "state": current_state,
                "confidence": float(avg_conf),
            }
        )

    return segments


def _mono_exponential(t: np.ndarray, a: float, tau: float, td: float) -> np.ndarray:
    """Mono-exponential model: y = a * (1 - exp(-(t-td)/tau))"""
    result = np.zeros_like(t, dtype=float)
    mask = t > td
    result[mask] = a * (1 - np.exp(-(t[mask] - td) / tau))
    return result


def fit_smo2_kinetics(
    df: pd.DataFrame, start_idx: int, end_idx: int, column: str = "smo2"
) -> Optional[dict]:
    """Fit mono-exponential model to SmO2 response."""
    if column not in df.columns or "time" not in df.columns:
        return None

    if end_idx <= start_idx or end_idx > len(df):
        return None

    # Extract window
    window = df.iloc[start_idx:end_idx].copy()

    if len(window) < 30:  # Need minimum data points
        return None

    # Normalize time to start from 0
    t = window["time"].values - window["time"].values[0]
    y = window[column].values

    # Remove NaNs
    mask = ~np.isnan(y) & ~np.isnan(t)
    t = t[mask]
    y = y[mask]

    if len(t) < 30:
        return None

    try:
        # Initial guesses
        amplitude_guess = y[-1] - y[0]
        tau_guess = 30.0
        td_guess = 5.0

        # Fit the model
        popt, pcov = curve_fit(
            _mono_exponential,
            t,
            y - y[0],  # Fit delta from baseline
            p0=[amplitude_guess, tau_guess, td_guess],
            bounds=(
                [-100, 1, 0],  # Lower bounds
                [100, 120, 30],  # Upper bounds
            ),
            maxfev=5000,
        )

        amplitude, tau, td = popt

        # Calculate R² for goodness of fit
        y_pred = _mono_exponential(t, amplitude, tau, td) + y[0]
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "amplitude": round(amplitude, 2),
            "tau": round(tau, 1),
            "time_delay": round(td, 1),
            "r_squared": round(r_squared, 3),
            "baseline": round(y[0], 1),
            "steady_state": round(y[0] + amplitude, 1),
        }

    except (RuntimeError, ValueError):
        return None


def get_tau_interpretation(tau: float) -> str:
    """Get interpretation of SmO2 time constant (tau)."""
    if tau < 15:
        return "⚡ Bardzo szybka kinetyka - doskonały system tlenowy"
    elif tau < 25:
        return "🟢 Szybka kinetyka - dobra wydolność tlenowa"
    elif tau < 40:
        return "🟡 Umiarkowana kinetyka - przeciętna adaptacja"
    elif tau < 60:
        return "🟠 Wolna kinetyka - ograniczona dostawa tlenu"
    else:
        return "🔴 Bardzo wolna kinetyka - wymagana praca nad bazą tlenową"


def calculate_o2_deficit(
    df: pd.DataFrame, interval_start: int, interval_end: int, steady_state_smo2: float
) -> Optional[float]:
    """Calculate oxygen deficit during interval onset."""
    if "smo2" not in df.columns:
        return None

    window = df.iloc[interval_start:interval_end]

    if window.empty:
        return None

    # O2 deficit = integral of (steady_state - actual) over time
    smo2_values = window["smo2"].values

    # Calculate deficit (area where actual < steady state)
    deficit = np.sum(np.maximum(0, steady_state_smo2 - smo2_values))

    return round(deficit, 1)


def detect_smo2_breakpoints(
    df: pd.DataFrame, window_size: int = 60, threshold: float = 0.5
) -> list:
    """Detect breakpoints in SmO2 response."""
    if "smo2" not in df.columns:
        return []

    smo2 = df["smo2"].values

    # Calculate smoothed derivative
    smo2_smooth = pd.Series(smo2).rolling(window=10).mean().values
    derivative = np.gradient(smo2_smooth)

    # Find points where derivative changes sign significantly
    breakpoints = []

    for i in range(window_size, len(derivative) - window_size):
        # Check for significant change in derivative
        before = np.mean(derivative[i - window_size : i])
        after = np.mean(derivative[i : i + window_size])

        if abs(after - before) > threshold:
            breakpoints.append(i)

    # Merge nearby breakpoints (within 30 seconds)
    if breakpoints:
        merged = [breakpoints[0]]
        for bp in breakpoints[1:]:
            if bp - merged[-1] > 30:
                merged.append(bp)
        return merged

    return []
