"""
SmO2 core analysis: metrics calculation and limiter classification.

Calculates advanced muscle oxygenation metrics for limiter classification:
- SmO2 Slope [%/100W]
- Half-Time Reoxygenation [s]
- SmO2-HR Coupling Index [r]

Classifies limiters:
- Local (capillarization / occlusion)
- Central (cardiac output)
- Metabolic (high glycolysis)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from ._smo2_utils import logger


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class SmO2AdvancedMetrics:
    """Container for advanced SmO2 metrics."""

    # Core metrics
    slope_per_100w: float = 0.0  # SmO2 drop per 100W [%/100W]
    halftime_reoxy_sec: Optional[float] = None  # Half-time to reoxygenation [s]
    hr_coupling_r: float = 0.0  # Correlation SmO2 vs HR changes
    drift_pct: float = 0.0  # SmO2 drift first half vs second half [%]

    # Limiter classification
    limiter_type: str = "unknown"  # local, central, metabolic, balanced
    limiter_confidence: float = 0.0  # 0-1

    # Interpretation
    interpretation: str = ""
    recommendations: List[str] = field(default_factory=list)

    # Raw data for debugging
    slope_r2: float = 0.0
    data_quality: str = "unknown"


# =============================================================================
# METRIC CALCULATIONS
# =============================================================================


def calculate_smo2_slope(
    df: pd.DataFrame, smo2_col: str = "SmO2", power_col: str = "watts", min_power: float = 100.0
) -> Tuple[float, float]:
    """
    Calculate SmO2 slope per 100W of power increase.

    Returns:
        (slope_per_100w, r_squared)
    """
    # Filter to valid power range
    mask = df[power_col] >= min_power
    if mask.sum() < 10:
        return 0.0, 0.0

    filtered = df.loc[mask, [power_col, smo2_col]].dropna()
    if len(filtered) < 10:
        return 0.0, 0.0

    # Linear regression
    slope, intercept, r, p, se = stats.linregress(filtered[power_col], filtered[smo2_col])

    # Convert to per 100W
    slope_per_100w = slope * 100
    r_squared = r**2

    return slope_per_100w, r_squared


def calculate_halftime_reoxygenation(
    df: pd.DataFrame,
    smo2_col: str = "SmO2",
    time_col: str = "seconds",
    power_col: str = "watts",
    power_threshold: float = 50.0,
) -> Optional[float]:
    """
    Calculate half-time for SmO2 reoxygenation after ramp ends.

    Finds the point where power drops (end of ramp) and measures
    how long it takes for SmO2 to recover 50% of its drop.

    Returns:
        Half-time in seconds, or None if not detectable.
    """
    # Find end of ramp (power drops significantly)
    if power_col not in df.columns or smo2_col not in df.columns:
        return None

    # Get power and SmO2
    power = df[power_col].values
    smo2 = df[smo2_col].values

    # Check for time column
    if time_col in df.columns:
        time = df[time_col].values
    elif "time" in df.columns:
        # Try to parse time strings
        try:
            time = pd.to_timedelta(df["time"]).dt.total_seconds().values
        except Exception:
            time = np.arange(len(df))
    else:
        time = np.arange(len(df))

    # Find peak power index
    peak_idx = np.argmax(power)
    if peak_idx >= len(power) - 30:  # Not enough recovery data
        return None

    # Get SmO2 at peak and minimum before peak
    smo2_at_peak = smo2[peak_idx]
    smo2_min_during_ramp = np.min(smo2[:peak_idx])

    # Look for recovery after peak
    recovery_smo2 = smo2[peak_idx:]
    recovery_time = time[peak_idx:]

    if len(recovery_smo2) < 30:
        return None

    # Calculate baseline from first 30s of low-intensity data (not just smo2[0])
    low_power_mask = power < power_threshold
    if low_power_mask.any():
        baseline_smo2 = float(np.mean(smo2[low_power_mask][:30]))
    else:
        # Fallback: mean of first 30 samples
        baseline_smo2 = float(np.mean(smo2[: min(30, len(smo2))]))

    # Calculate 50% recovery target
    drop = baseline_smo2 - smo2_min_during_ramp  # Baseline - minimum
    if drop <= 0:
        return None

    half_recovery_target = smo2_min_during_ramp + (drop * 0.5)

    # Find when SmO2 reaches 50% recovery
    for i, val in enumerate(recovery_smo2):
        if val >= half_recovery_target:
            halftime = recovery_time[i] - recovery_time[0]
            return float(halftime)

    return None  # Did not reach 50% recovery in data


def calculate_hr_coupling_index(
    df: pd.DataFrame, smo2_col: str = "SmO2", hr_col: str = "hr", window: int = 30
) -> float:
    """
    Calculate dynamic coupling index between SmO2 and HR changes.

    Uses rate-of-change (first differences) instead of absolute levels.
    Correlating absolute SmO2 vs HR gives spurious strong negatives in ramp
    tests (both trend monotonically) regardless of physiological mechanism.

    By correlating d(SmO2)/dt vs d(HR)/dt we measure whether changes in HR
    and SmO2 co-vary, which is the true coupling signal.

    High negative correlation = Central limiter (HR rises → SmO2 drops)
    Low/no correlation = Local limiter (SmO2 changes independently of HR)

    Returns:
        Pearson correlation coefficient (-1 to 1)
    """
    if hr_col not in df.columns or smo2_col not in df.columns:
        return 0.0

    # Smooth first to reduce noise
    smo2_smooth = df[smo2_col].rolling(window=window, min_periods=1).mean()
    hr_smooth = df[hr_col].rolling(window=window, min_periods=1).mean()

    # Rate of change (first differences)
    smo2_delta = smo2_smooth.diff()
    hr_delta = hr_smooth.diff()

    # Drop NaN from diff()
    valid = pd.DataFrame({"smo2_d": smo2_delta, "hr_d": hr_delta}).dropna()
    if len(valid) < 30:
        return 0.0

    # Remove zero-change periods (standstill)
    valid = valid[(valid["smo2_d"].abs() > 0.001) | (valid["hr_d"].abs() > 0.01)]
    if len(valid) < 20:
        return 0.0

    r, p = stats.pearsonr(valid["smo2_d"], valid["hr_d"])

    return float(r)


# =============================================================================
# LIMITER CLASSIFICATION
# =============================================================================

LIMITER_THRESHOLDS = {
    "slope_severe": -8.0,  # SmO2 drop > 8%/100W = severe local
    "slope_moderate": -4.0,  # SmO2 drop > 4%/100W = moderate local
    "halftime_fast": 30.0,  # < 30s = good capillarization
    "halftime_slow": 90.0,  # > 90s = poor capillarization
    "coupling_strong": -0.7,  # Strong negative = central driver
    "coupling_weak": -0.3,  # Weak = local driver
}


def classify_smo2_limiter(metrics: SmO2AdvancedMetrics) -> Tuple[str, float, str]:
    """
    Classify the primary limiter based on SmO2 metrics.

    Returns:
        (limiter_type, confidence, interpretation)
    """
    scores = {"local": 0.0, "central": 0.0, "metabolic": 0.0}

    slope = metrics.slope_per_100w
    halftime = metrics.halftime_reoxy_sec
    coupling = metrics.hr_coupling_r

    # --- SLOPE ANALYSIS ---
    if slope < LIMITER_THRESHOLDS["slope_severe"]:
        scores["local"] += 3.0
        scores["metabolic"] += 1.0
    elif slope < LIMITER_THRESHOLDS["slope_moderate"]:
        scores["local"] += 1.5
    else:
        scores["central"] += 1.0  # Low slope = supply keeping up

    # --- HALFTIME ANALYSIS ---
    if halftime is not None:
        if halftime > LIMITER_THRESHOLDS["halftime_slow"]:
            scores["local"] += 2.0  # Poor capillary refill
        elif halftime < LIMITER_THRESHOLDS["halftime_fast"]:
            scores["central"] += 1.5  # Good capillaries, central limit
        else:
            scores["metabolic"] += 1.0  # Moderate = metabolic

    # --- COUPLING ANALYSIS ---
    if coupling < LIMITER_THRESHOLDS["coupling_strong"]:
        scores["central"] += 2.5  # Strong HR-SmO2 link = central driver
    elif coupling > LIMITER_THRESHOLDS["coupling_weak"]:
        scores["local"] += 2.0  # Weak link = local independence
    else:
        scores["metabolic"] += 1.5

    # Determine winner
    total = sum(scores.values()) or 1.0
    max_score = max(scores.values())
    limiter_type = max(scores, key=scores.get)
    confidence = max_score / total

    # Generate interpretation
    interpretation = _generate_interpretation(limiter_type, metrics, scores)

    return limiter_type, confidence, interpretation


def _generate_interpretation(
    limiter_type: str, metrics: SmO2AdvancedMetrics, scores: Dict[str, float]
) -> str:
    """Generate coach-oriented interpretation text."""

    slope = metrics.slope_per_100w
    halftime = metrics.halftime_reoxy_sec
    coupling = metrics.hr_coupling_r

    if limiter_type == "local":
        base = "LIMIT OBWODOWY (KAPILARYZACJA)"
        detail = f"SmO₂ spada o {abs(slope):.1f}%/100W – mięsień szybko wyczerpuje tlen lokalnie. "
        if halftime and halftime > 60:
            detail += f"Powolna reoksygenacja ({halftime:.0f}s) potwierdza słabą kapilaryzację. "
        if coupling > -0.5:
            detail += "Niska korelacja z HR wskazuje na niezależność od układu centralnego. "

        recommendations = [
            "Trening Sweet Spot (2×20min) dla rozbudowy kapilar",
            "Siłowy na rowerze (4×8min @ 50rpm) dla rekrutacji włókien",
            "Objętość Z2 (3-4h) dla gęstości naczyń",
        ]

    elif limiter_type == "central":
        base = "LIMIT CENTRALNY (RZUT SERCA)"
        detail = (
            f"Silna korelacja SmO₂-HR (r={coupling:.2f}) wskazuje, że serce dyktuje dostawę tlenu. "
        )
        if abs(slope) < 4:
            detail += f"Umiarkowany spadek SmO₂ ({abs(slope):.1f}%/100W) potwierdza wystarczającą kapilaryzację. "
        if halftime and halftime < 45:
            detail += f"Szybka reoksygenacja ({halftime:.0f}s) – mięśnie sprawnie odbierają tlen. "

        recommendations = [
            "Interwały VO₂max (4-6×4min) dla wzrostu rzutu serca",
            "Tempo długie (60-90min) dla adaptacji sercowej",
            "Budowa bazy Z2 (4-5h) dla objętości wyrzutowej",
        ]

    else:  # metabolic
        base = "LIMIT METABOLICZNY (GLIKOLIZA)"
        detail = (
            f"Profil mieszany: spadek SmO₂ {abs(slope):.1f}%/100W przy umiarkowanej korelacji z HR. "
            "Sugeruje wysoką produkcję mleczanu (VLaMax) jako główny czynnik."
        )
        if halftime and 45 < halftime < 90:
            detail += (
                f" Umiarkowana reoksygenacja ({halftime:.0f}s) potwierdza stres metaboliczny. "
            )

        recommendations = [
            "Długie jazdy Z2 (4-5h) na obniżenie VLaMax",
            "Treningi na czczo dla optymalizacji FatMax",
            "Tempo pod LT1 dla efektywności metabolicznej",
        ]

    full_interpretation = f"{base}\n{detail}"

    return full_interpretation


def get_recommendations_for_limiter(limiter_type: str) -> List[str]:
    """Get training recommendations for a given limiter type."""
    recommendations = {
        "local": [
            "Sweet Spot 2×20min @ 88-94% FTP",
            "Siłowy 4×8min @ 50-60rpm pod LT1",
            "Objętość Z2 3-4h ciągła",
        ],
        "central": [
            "VO₂max 4-6×4min @ 106-120% FTP",
            "Tempo 60-90min @ 80-90% FTP",
            "Z2 długie 4-5h",
        ],
        "metabolic": [
            "Z2 bardzo długie 4-5h @ 60-70% FTP",
            "Treningi na czczo 1.5-2h",
            "Tempo pod LT1 2×30min",
        ],
    }
    return recommendations.get(limiter_type, ["Trening zrównoważony"])


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================


def analyze_smo2_advanced(
    df: pd.DataFrame,
    smo2_col: str = "SmO2",
    power_col: str = "watts",
    hr_col: str = "hr",
    time_col: str = "seconds",
) -> SmO2AdvancedMetrics:
    """
    Perform complete advanced SmO2 analysis.

    Args:
        df: DataFrame with SmO2, power, HR, time columns
        smo2_col: Name of SmO2 column
        power_col: Name of power column
        hr_col: Name of HR column
        time_col: Name of time column

    Returns:
        SmO2AdvancedMetrics with all calculated values
    """
    metrics = SmO2AdvancedMetrics()

    # Check data quality
    if smo2_col not in df.columns:
        metrics.data_quality = "no_smo2"
        metrics.interpretation = "Brak danych SmO₂."
        return metrics

    if power_col not in df.columns:
        metrics.data_quality = "no_power"
        metrics.interpretation = "Brak danych mocy."
        return metrics

    # Calculate metrics
    metrics.slope_per_100w, metrics.slope_r2 = calculate_smo2_slope(df, smo2_col, power_col)

    metrics.halftime_reoxy_sec = calculate_halftime_reoxygenation(df, smo2_col, time_col, power_col)

    metrics.hr_coupling_r = calculate_hr_coupling_index(df, smo2_col, hr_col)

    # Classify limiter
    limiter_type, confidence, interpretation = classify_smo2_limiter(metrics)
    metrics.limiter_type = limiter_type
    metrics.limiter_confidence = confidence
    metrics.interpretation = interpretation
    metrics.recommendations = get_recommendations_for_limiter(limiter_type)

    metrics.data_quality = "good" if metrics.slope_r2 > 0.3 else "low"

    # Calculate SmO2 drift (first half vs second half)
    metrics.drift_pct = calculate_smo2_drift(df, smo2_col, power_col)

    return metrics


def calculate_smo2_drift(
    df: pd.DataFrame, smo2_col: str = "SmO2", power_col: str = "watts", min_power: float = 100.0
) -> float:
    """
    Calculate SmO2 drift as percentage change from first half to second half.

    Positive drift = SmO2 increased (recovery)
    Negative drift = SmO2 decreased (fatigue)

    Returns:
        Drift percentage (e.g., -7.5 means 7.5% drop)
    """
    if smo2_col not in df.columns or power_col not in df.columns:
        return 0.0

    # Filter to ramp portion (power > threshold)
    mask = df[power_col] > min_power
    if mask.sum() < 20:
        return 0.0

    filtered = df.loc[mask, smo2_col].dropna()
    if len(filtered) < 20:
        return 0.0

    n = len(filtered)
    mid = n // 2

    first_half_avg = filtered.iloc[:mid].mean()
    second_half_avg = filtered.iloc[mid:].mean()

    if first_half_avg == 0:
        return 0.0

    drift_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100

    return float(drift_pct)


def format_smo2_metrics_for_report(metrics: SmO2AdvancedMetrics) -> Dict[str, Any]:
    """Format metrics for inclusion in JSON/PDF reports."""
    return {
        "slope_per_100w": round(metrics.slope_per_100w, 2),
        "halftime_reoxy_sec": round(metrics.halftime_reoxy_sec, 1)
        if metrics.halftime_reoxy_sec
        else None,
        "hr_coupling_r": round(metrics.hr_coupling_r, 3),
        "drift_pct": round(metrics.drift_pct, 2),
        "limiter_type": metrics.limiter_type,
        "limiter_confidence": round(metrics.limiter_confidence, 2),
        "interpretation": metrics.interpretation,
        "recommendations": metrics.recommendations,
        "data_quality": metrics.data_quality,
    }


__all__ = [
    "SmO2AdvancedMetrics",
    "analyze_smo2_advanced",
    "calculate_smo2_slope",
    "calculate_halftime_reoxygenation",
    "calculate_hr_coupling_index",
    "calculate_smo2_drift",
    "classify_smo2_limiter",
    "format_smo2_metrics_for_report",
    "LIMITER_THRESHOLDS",
    "get_recommendations_for_limiter",
]
