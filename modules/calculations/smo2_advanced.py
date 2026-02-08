"""
Advanced SmO2 Metrics Module.

Calculates advanced muscle oxygenation metrics for limiter classification:
- SmO2 Slope [%/100W]
- Half-Time Reoxygenation [s]
- SmO2-HR Coupling Index [r]

Classifies limiters:
- Local (capillarization / occlusion)
- Central (cardiac output)
- Metabolic (high glycolysis)
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from scipy import stats
import logging

try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Create dummy decorator if numba not available
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

logger = logging.getLogger("Tri_Dashboard.SmO2Advanced")


# =============================================================================
# NUMBA-OPTIMIZED FUNCTIONS
# =============================================================================

if NUMBA_AVAILABLE:
    @jit(nopython=True, cache=True)
    def _fast_gradient(smo2_vals, power_vals):
        """Fast gradient calculation using Numba."""
        n = len(smo2_vals)
        grad = np.zeros(n)
        for i in range(1, n - 1):
            dp = power_vals[i + 1] - power_vals[i - 1]
            if dp != 0:
                grad[i] = (smo2_vals[i + 1] - smo2_vals[i - 1]) / dp
        grad[0] = grad[1] if n > 1 else 0
        grad[-1] = grad[-2] if n > 1 else 0
        return grad

    @jit(nopython=True, cache=True)
    def _fast_curvature(smo2_vals, power_vals):
        """Fast curvature calculation using Numba."""
        n = len(smo2_vals)
        grad = _fast_gradient(smo2_vals, power_vals)
        curv = np.zeros(n)
        for i in range(1, n - 1):
            dp = power_vals[i + 1] - power_vals[i - 1]
            if dp != 0:
                curv[i] = (grad[i + 1] - grad[i - 1]) / dp
        curv[0] = curv[1] if n > 1 else 0
        curv[-1] = curv[-2] if n > 1 else 0
        return curv
else:
    def _fast_gradient(smo2_vals, power_vals):
        """Fallback gradient calculation."""
        return np.gradient(smo2_vals, power_vals)

    def _fast_curvature(smo2_vals, power_vals):
        """Fallback curvature calculation."""
        grad = np.gradient(smo2_vals, power_vals)
        return np.gradient(grad, power_vals)

logger = logging.getLogger("Tri_Dashboard.SmO2Advanced")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SmO2AdvancedMetrics:
    """Container for advanced SmO2 metrics."""
    # Core metrics
    slope_per_100w: float = 0.0           # SmO2 drop per 100W [%/100W]
    halftime_reoxy_sec: Optional[float] = None  # Half-time to reoxygenation [s]
    hr_coupling_r: float = 0.0            # Correlation SmO2 vs HR changes
    drift_pct: float = 0.0                # SmO2 drift first half vs second half [%]
    
    # Limiter classification
    limiter_type: str = "unknown"         # local, central, metabolic, balanced
    limiter_confidence: float = 0.0       # 0-1
    
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
    df: pd.DataFrame,
    smo2_col: str = "SmO2",
    power_col: str = "watts",
    min_power: float = 100.0
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
    slope, intercept, r, p, se = stats.linregress(
        filtered[power_col], 
        filtered[smo2_col]
    )
    
    # Convert to per 100W
    slope_per_100w = slope * 100
    r_squared = r ** 2
    
    return slope_per_100w, r_squared


def calculate_halftime_reoxygenation(
    df: pd.DataFrame,
    smo2_col: str = "SmO2",
    time_col: str = "seconds",
    power_col: str = "watts",
    power_threshold: float = 50.0
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
        except:
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
    
    # Calculate 50% recovery target
    drop = smo2[0] - smo2_min_during_ramp  # Baseline - minimum
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
    df: pd.DataFrame,
    smo2_col: str = "SmO2",
    hr_col: str = "hr",
    window: int = 30
) -> float:
    """
    Calculate coupling index between SmO2 and HR.
    
    High negative correlation = Central limiter (HR rises, SmO2 drops proportionally)
    Low correlation = Local limiter (SmO2 drops independently of HR)
    
    Returns:
        Pearson correlation coefficient (-1 to 1)
    """
    if hr_col not in df.columns or smo2_col not in df.columns:
        return 0.0
    
    # Calculate rolling changes
    smo2_smooth = df[smo2_col].rolling(window=window, min_periods=1).mean()
    hr_smooth = df[hr_col].rolling(window=window, min_periods=1).mean()
    
    # Drop NaN
    valid = pd.DataFrame({"smo2": smo2_smooth, "hr": hr_smooth}).dropna()
    if len(valid) < 30:
        return 0.0
    
    # Correlation
    r, p = stats.pearsonr(valid["smo2"], valid["hr"])
    
    return float(r)


# =============================================================================
# LIMITER CLASSIFICATION
# =============================================================================

LIMITER_THRESHOLDS = {
    "slope_severe": -8.0,      # SmO2 drop > 8%/100W = severe local
    "slope_moderate": -4.0,    # SmO2 drop > 4%/100W = moderate local
    "halftime_fast": 30.0,     # < 30s = good capillarization
    "halftime_slow": 90.0,     # > 90s = poor capillarization
    "coupling_strong": -0.7,   # Strong negative = central driver
    "coupling_weak": -0.3,     # Weak = local driver
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
    limiter_type: str,
    metrics: SmO2AdvancedMetrics,
    scores: Dict[str, float]
) -> str:
    """Generate coach-oriented interpretation text."""
    
    slope = metrics.slope_per_100w
    halftime = metrics.halftime_reoxy_sec
    coupling = metrics.hr_coupling_r
    
    if limiter_type == "local":
        base = "LIMIT OBWODOWY (KAPILARYZACJA)"
        detail = (
            f"SmO₂ spada o {abs(slope):.1f}%/100W – mięsień szybko wyczerpuje tlen lokalnie. "
        )
        if halftime and halftime > 60:
            detail += f"Powolna reoksygenacja ({halftime:.0f}s) potwierdza słabą kapilaryzację. "
        if coupling > -0.5:
            detail += "Niska korelacja z HR wskazuje na niezależność od układu centralnego. "
        
        recommendations = [
            "Trening Sweet Spot (2×20min) dla rozbudowy kapilar",
            "Siłowy na rowerze (4×8min @ 50rpm) dla rekrutacji włókien",
            "Objętość Z2 (3-4h) dla gęstości naczyń"
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
            "Budowa bazy Z2 (4-5h) dla objętości wyrzutowej"
        ]
    
    else:  # metabolic
        base = "LIMIT METABOLICZNY (GLIKOLIZA)"
        detail = (
            f"Profil mieszany: spadek SmO₂ {abs(slope):.1f}%/100W przy umiarkowanej korelacji z HR. "
            "Sugeruje wysoką produkcję mleczanu (VLaMax) jako główny czynnik."
        )
        if halftime and 45 < halftime < 90:
            detail += f" Umiarkowana reoksygenacja ({halftime:.0f}s) potwierdza stres metaboliczny. "
        
        recommendations = [
            "Długie jazdy Z2 (4-5h) na obniżenie VLaMax",
            "Treningi na czczo dla optymalizacji FatMax",
            "Tempo pod LT1 dla efektywności metabolicznej"
        ]
    
    full_interpretation = f"{base}\n{detail}"
    
    return full_interpretation


def get_recommendations_for_limiter(limiter_type: str) -> List[str]:
    """Get training recommendations for a given limiter type."""
    recommendations = {
        "local": [
            "Sweet Spot 2×20min @ 88-94% FTP",
            "Siłowy 4×8min @ 50-60rpm pod LT1",
            "Objętość Z2 3-4h ciągła"
        ],
        "central": [
            "VO₂max 4-6×4min @ 106-120% FTP",
            "Tempo 60-90min @ 80-90% FTP",
            "Z2 długie 4-5h"
        ],
        "metabolic": [
            "Z2 bardzo długie 4-5h @ 60-70% FTP",
            "Treningi na czczo 1.5-2h",
            "Tempo pod LT1 2×30min"
        ]
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
    time_col: str = "seconds"
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
    metrics.slope_per_100w, metrics.slope_r2 = calculate_smo2_slope(
        df, smo2_col, power_col
    )
    
    metrics.halftime_reoxy_sec = calculate_halftime_reoxygenation(
        df, smo2_col, time_col, power_col
    )
    
    metrics.hr_coupling_r = calculate_hr_coupling_index(
        df, smo2_col, hr_col
    )
    
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
    df: pd.DataFrame,
    smo2_col: str = "SmO2",
    power_col: str = "watts",
    min_power: float = 100.0
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
        "halftime_reoxy_sec": round(metrics.halftime_reoxy_sec, 1) if metrics.halftime_reoxy_sec else None,
        "hr_coupling_r": round(metrics.hr_coupling_r, 3),
        "drift_pct": round(metrics.drift_pct, 2),
        "limiter_type": metrics.limiter_type,
        "limiter_confidence": round(metrics.limiter_confidence, 2),
        "interpretation": metrics.interpretation,
        "recommendations": metrics.recommendations,
        "data_quality": metrics.data_quality
    }


# =============================================================================
# 3-POINT SmO2 THRESHOLD DETECTION MODEL
# =============================================================================

@dataclass
class SmO2ThresholdResult:
    """Result of 3-point SmO2 threshold detection (T1, T2_onset, T2_steady)."""
    
    # T1 (LT1 analog - onset of desaturation)
    t1_watts: Optional[int] = None
    t1_hr: Optional[int] = None
    t1_smo2: Optional[float] = None
    t1_gradient: Optional[float] = None  # dSmO2/dP
    t1_trend: Optional[float] = None     # dSmO2/dt (%/min)
    t1_sd: Optional[float] = None        # Variability
    t1_step: Optional[int] = None
    
    # T2_onset (Heavy→Severe transition)
    t2_onset_watts: Optional[int] = None
    t2_onset_hr: Optional[int] = None
    t2_onset_smo2: Optional[float] = None
    t2_onset_gradient: Optional[float] = None
    t2_onset_curvature: Optional[float] = None
    t2_onset_sd: Optional[float] = None
    t2_onset_step: Optional[int] = None
    
    # T2_steady (MLSS_local / RCP_steady analog)
    t2_steady_watts: Optional[int] = None
    t2_steady_hr: Optional[int] = None
    t2_steady_smo2: Optional[float] = None
    t2_steady_gradient: Optional[float] = None
    t2_steady_trend: Optional[float] = None  # dSmO2/dt (%/min)
    t2_steady_sd: Optional[float] = None
    t2_steady_step: Optional[int] = None
    
    # Legacy compatibility (map to primary thresholds)
    t2_watts: Optional[int] = None  # Maps to t2_onset_watts
    t2_hr: Optional[int] = None
    t2_smo2: Optional[float] = None
    t2_gradient: Optional[float] = None
    t2_step: Optional[int] = None
    
    # Zones
    zones: List[Dict] = field(default_factory=list)
    
    # Validation
    vt1_correlation_watts: Optional[int] = None
    rcp_onset_correlation_watts: Optional[int] = None
    rcp_steady_correlation_watts: Optional[int] = None
    physiological_agreement: str = "not_checked"
    
    # Analysis info
    analysis_notes: List[str] = field(default_factory=list)
    method: str = "moxy_3point"
    step_data: List[Dict] = field(default_factory=list)


def detect_smo2_thresholds_moxy(
    df: pd.DataFrame,
    step_duration_sec: int = 180,
    smo2_col: str = "smo2",
    power_col: str = "watts",
    hr_col: str = "hr",
    time_col: str = "time",
    cp_watts: Optional[int] = None,
    hr_max: Optional[int] = None,
    vt1_watts: Optional[int] = None,
    rcp_onset_watts: Optional[int] = None,
    rcp_steady_watts: Optional[int] = None
) -> SmO2ThresholdResult:
    """
    RAMP TEST SmO₂ THRESHOLD DETECTION (Senior Physiologist + Signal Processing):
    
    CRITICAL: Only 2 breakpoints valid in ramp test:
    - SmO2_T1 (LT1 analog)
    - SmO2_T2_onset (RCP / Heavy→Severe)
    
    T2_steady (MLSS_local) MUST NOT be detected in ramp tests.
    
    Pipeline:
    1. Median smoothing 30-45s
    2. Remove last 1 step (ischemic crash)
    3. Reject CV > 6% (motion artefact)
    4. T1: dSmO2/dt < -0.4%/min ≥2 consecutive steps, CV < 4%, VT1±15%
    5. T2_onset: max global curvature, dSmO2/dt < -1.5%/min, osc ↑30%, T1+20%, VT2±15%
    6. 4-domain zones
    7. Confidence score
    """
    
    result = SmO2ThresholdResult()
    
    # Normalize columns
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    smo2_col = smo2_col.lower()
    power_col = power_col.lower()
    hr_col = hr_col.lower() if hr_col else None
    time_col = time_col.lower()
    
    if smo2_col not in df.columns:
        result.analysis_notes.append("❌ Brak kolumny SmO2")
        return result
    
    if power_col not in df.columns:
        result.analysis_notes.append("❌ Brak kolumny mocy")
        return result
    
    # =========================================================================
    # 1. PREPROCESSING: MEDIAN SMOOTHING (30-45s)
    # =========================================================================
    
    window = min(45, max(30, len(df) // 40))
    if window % 2 == 0:
        window += 1
    
    df['smo2_smooth'] = df[smo2_col].rolling(window=window, center=True, min_periods=1).median()
    
    if time_col in df.columns:
        df['step'] = (df[time_col] // step_duration_sec).astype(int)
    else:
        df['step'] = (df.index // step_duration_sec).astype(int)
    
    max_power = df[power_col].max()
    has_hr = hr_col and hr_col in df.columns
    
    if hr_max is None and has_hr:
        hr_max = int(df[hr_col].max())
    
    # =========================================================================
    # 2. AGGREGATE BY STEP
    # =========================================================================
    
    # OPTIMIZED: Vectorized step aggregation using groupby
    all_steps = sorted(df['step'].unique())
    
    # REMOVE LAST 1 STEP (ischemic crash zone)
    if len(all_steps) > 1:
        last_step = all_steps[-1]
    else:
        last_step = None
    
    # Filter steps with at least 30 samples
    step_counts = df.groupby('step').size()
    valid_steps = step_counts[step_counts >= 30].index.tolist()
    
    if not valid_steps:
        result.analysis_notes.append("⚠️ Za mało danych w stopniach")
        return result
    
    # Vectorized aggregation per step
    def aggregate_step(step_num):
        step_df = df[df['step'] == step_num]
        last_90 = step_df.tail(90) if len(step_df) >= 90 else step_df
        last_60 = step_df.tail(60) if len(step_df) >= 60 else step_df
        
        avg_power = last_60[power_col].mean()
        avg_smo2 = last_60['smo2_smooth'].mean()
        avg_hr = last_60[hr_col].mean() if has_hr else None
        end_time = last_60[time_col].iloc[-1] if time_col in last_60.columns else None
        
        # CV in 90s window
        sd_smo2 = last_90['smo2_smooth'].std()
        cv_smo2 = (sd_smo2 / avg_smo2 * 100) if avg_smo2 > 0 else 0
        
        # Oscillation amplitude (peak-to-peak)
        osc_amp = last_60['smo2_smooth'].max() - last_60['smo2_smooth'].min()
        
        # Trend (dSmO2/dt in %/min)
        trend = 0
        if len(last_90) >= 60 and time_col in last_90.columns:
            time_range = last_90[time_col].iloc[-1] - last_90[time_col].iloc[0]
            if time_range > 0:
                smo2_change = last_90['smo2_smooth'].iloc[-1] - last_90['smo2_smooth'].iloc[0]
                trend = smo2_change / (time_range / 60)
        
        # HR slope (linear check)
        hr_slope = None
        if has_hr and len(last_90) >= 30:
            hr_vals = last_90[hr_col].values
            time_vals = np.arange(len(hr_vals))
            if len(hr_vals) > 2:
                hr_slope = np.polyfit(time_vals, hr_vals, 1)[0]
        
        return {
            'step': step_num,
            'power': avg_power,
            'smo2': avg_smo2,
            'hr': avg_hr,
            'end_time': end_time,
            'sd': sd_smo2,
            'cv': cv_smo2,
            'osc_amp': osc_amp,
            'trend': trend,
            'hr_slope': hr_slope,
            'is_last_step': step_num == last_step
        }
    
    # Use list comprehension for better performance
    step_data = [aggregate_step(step) for step in valid_steps]
    
    if len(step_data) < 4:
        result.analysis_notes.append(f"⚠️ Za mało stopni ({len(step_data)})")
        return result
    
    step_df = pd.DataFrame(step_data)
    
    # =========================================================================
    # 3. CALCULATE DERIVATIVES
    # =========================================================================
    
    # Use Numba-optimized functions if available
    smo2_vals = step_df['smo2'].values
    power_vals = step_df['power'].values
    step_df['gradient'] = _fast_gradient(smo2_vals, power_vals)
    step_df['curvature'] = _fast_curvature(smo2_vals, power_vals)
    
    # =========================================================================
    # 4. SmO₂_T1 DETECTION (LT1 analog)
    # =========================================================================
    # Criteria: dSmO2/dt < -0.4%/min for ≥2 consecutive steps, CV < 4%, VT1±15%
    
    t1_idx = None
    t1_is_systemic = False
    t1_confidence = 0
    
    # Power window for T1: VT1 ± 15%
    t1_power_min = vt1_watts * 0.85 if vt1_watts else 0
    t1_power_max = vt1_watts * 1.15 if vt1_watts else max_power
    
    for i in range(1, len(step_df) - 1):
        row = step_df.iloc[i]
        next_row = step_df.iloc[i + 1]
        
        # Skip last step (ischemic)
        if row['is_last_step'] or next_row['is_last_step']:
            continue
        
        # ARTEFACT REJECTION: CV > 6%
        if row['cv'] > 6.0:
            result.analysis_notes.append(f"❌ Step {row['step']} rejected: CV={row['cv']:.1f}% > 6%")
            continue
        
        # Power window check
        if vt1_watts:
            if not (t1_power_min <= row['power'] <= t1_power_max):
                continue
        
        # T1 CRITERIA:
        # dSmO2/dt < -0.4%/min for ≥2 consecutive steps
        trend_ok = row['trend'] < -0.4 and next_row['trend'] < -0.4
        
        # CV < 4%
        cv_ok = row['cv'] < 4.0
        
        # HR slope remains linear (not accelerating excessively)
        hr_linear = True
        if row['hr_slope'] is not None:
            hr_linear = row['hr_slope'] > 0  # HR should be increasing
        
        if trend_ok and cv_ok and hr_linear:
            t1_idx = i
            
            # Check VT1 validation
            if vt1_watts:
                pct_diff = abs(row['power'] - vt1_watts) / vt1_watts * 100
                if pct_diff <= 10:
                    t1_is_systemic = True
                    t1_confidence += 30
                    result.analysis_notes.append(f"✓ T1 zgodny z VT1 ±{pct_diff:.0f}%")
                elif pct_diff <= 15:
                    t1_confidence += 15
                    result.analysis_notes.append(f"⚠️ T1 w zakresie VT1 ±{pct_diff:.0f}%")
            else:
                t1_confidence += 20
            
            # Additional confidence from signal quality
            if row['cv'] < 2.0:
                t1_confidence += 10
            if abs(row['trend']) > 0.6:
                t1_confidence += 10
            
            break
    
    if t1_idx is None:
        result.analysis_notes.append("⚠️ T1 nie wykryto")
    else:
        row = step_df.iloc[t1_idx]
        result.t1_watts = int(row['power'])
        result.t1_smo2 = round(row['smo2'], 1)
        result.t1_hr = int(row['hr']) if pd.notna(row['hr']) else None
        result.t1_gradient = round(row['gradient'], 4)
        result.t1_trend = round(row['trend'], 2)
        result.t1_sd = round(row['sd'], 2)
        result.t1_step = int(row['step'])
        flag = "🟢 Systemic" if t1_is_systemic else "🟡 Local"
        result.analysis_notes.append(
            f"SmO₂ T1: {result.t1_watts}W @ {result.t1_smo2}% "
            f"(slope={result.t1_trend}%/min, CV={row['cv']:.1f}%) [{flag}]"
        )
    
    # =========================================================================
    # 5. SmO₂_T2_onset DETECTION (RCP analog)
    # =========================================================================
    # Criteria: max global curvature, dSmO2/dt < -1.5%/min, osc ↑30%, T1+20%, VT2±15%
    
    t2_onset_idx = None
    t2_onset_is_systemic = False
    t2_confidence = 0
    
    # Power constraints
    min_t2_power = (result.t1_watts * 1.20) if result.t1_watts else (vt1_watts * 1.20 if vt1_watts else 0)
    t2_power_min = rcp_onset_watts * 0.85 if rcp_onset_watts else min_t2_power
    t2_power_max = rcp_onset_watts * 1.15 if rcp_onset_watts else max_power
    
    search_start = t1_idx + 1 if t1_idx is not None else 2
    
    # Get baseline oscillation amplitude
    t1_osc = step_df.iloc[t1_idx]['osc_amp'] if t1_idx else step_df['osc_amp'].median()
    
    # Find max global curvature in valid range
    valid_rows = []
    for i in range(search_start, len(step_df)):
        row = step_df.iloc[i]
        
        # Skip last step (ischemic)
        if row['is_last_step']:
            continue
        
        # Power constraints
        if row['power'] < min_t2_power:
            continue
        if rcp_onset_watts:
            if not (t2_power_min <= row['power'] <= t2_power_max):
                continue
        
        # ARTEFACT REJECTION: CV > 6%
        if row['cv'] > 6.0:
            result.analysis_notes.append(f"❌ Step {row['step']} rejected: CV={row['cv']:.1f}% > 6%")
            continue
        
        valid_rows.append({'idx': i, 'row': row})
    
    if valid_rows:
        # Find max curvature (global peak)
        max_curv_item = max(valid_rows, key=lambda x: abs(x['row']['curvature']))
        best_row = max_curv_item['row']
        best_idx = max_curv_item['idx']
        
        # Check T2_onset criteria
        trend_severe = best_row['trend'] < -1.5
        osc_increasing = best_row['osc_amp'] > t1_osc * 1.3  # ≥30% increase
        
        if trend_severe or abs(best_row['curvature']) > 0.0003:
            t2_onset_idx = best_idx
            
            # Confidence from trend
            if trend_severe:
                t2_confidence += 20
            
            # Confidence from oscillation
            if osc_increasing:
                t2_confidence += 15
            
            # Confidence from curvature magnitude
            if abs(best_row['curvature']) > 0.0005:
                t2_confidence += 15
            elif abs(best_row['curvature']) > 0.0003:
                t2_confidence += 10
            
            # Check VT2/RCP validation
            if rcp_onset_watts:
                pct_diff = abs(best_row['power'] - rcp_onset_watts) / rcp_onset_watts * 100
                if pct_diff <= 10:
                    t2_onset_is_systemic = True
                    t2_confidence += 30
                    result.analysis_notes.append(f"✓ T2_onset zgodny z VT2/RCP ±{pct_diff:.0f}%")
                elif pct_diff <= 15:
                    t2_confidence += 15
                    result.analysis_notes.append(f"⚠️ T2_onset w zakresie VT2/RCP ±{pct_diff:.0f}%")
                else:
                    result.analysis_notes.append(f"❌ T2_onset poza VT2/RCP ±15%: Local Perfusion Limitation")
            else:
                t2_confidence += 20
    
    if t2_onset_idx is None:
        result.analysis_notes.append("⚠️ T2_onset nie wykryto")
    else:
        row = step_df.iloc[t2_onset_idx]
        result.t2_onset_watts = int(row['power'])
        result.t2_onset_smo2 = round(row['smo2'], 1)
        result.t2_onset_hr = int(row['hr']) if pd.notna(row['hr']) else None
        result.t2_onset_gradient = round(row['gradient'], 4)
        result.t2_onset_curvature = round(row['curvature'], 5)
        result.t2_onset_sd = round(row['sd'], 2)
        result.t2_onset_step = int(row['step'])
        
        result.t2_watts = result.t2_onset_watts
        result.t2_hr = result.t2_onset_hr
        result.t2_smo2 = result.t2_onset_smo2
        result.t2_gradient = result.t2_onset_gradient
        result.t2_step = result.t2_onset_step
        
        flag = "🟢 Systemic" if t2_onset_is_systemic else "🟡 Local"
        result.analysis_notes.append(
            f"SmO₂ T2_onset: {result.t2_onset_watts}W @ {result.t2_onset_smo2}% "
            f"(slope={row['trend']:.1f}%/min, curv={row['curvature']:.5f}) [{flag}]"
        )
    
    # =========================================================================
    # 6. NO T2_STEADY FOR RAMP TESTS
    # =========================================================================
    # CRITICAL: T2_steady (MLSS_local) MUST NOT be detected in ramp tests
    
    result.analysis_notes.append(
        "ℹ️ T2_steady N/A w teście rampowym (brak plateau do detekcji MLSS_local)"
    )
    
    # =========================================================================
    # 7. HIERARCHICAL VALIDATION + CONFIDENCE SCORE
    # =========================================================================
    
    # Check T1 < T2_onset
    if result.t1_watts and result.t2_onset_watts:
        if result.t1_watts >= result.t2_onset_watts:
            result.analysis_notes.append("⚠️ Hierarchy violated: T1 >= T2_onset")
            result.t1_watts = None
            t1_confidence = 0
    
    # Correlation with CPET
    if vt1_watts and result.t1_watts:
        result.vt1_correlation_watts = abs(result.t1_watts - vt1_watts)
    
    if rcp_onset_watts and result.t2_onset_watts:
        result.rcp_onset_correlation_watts = abs(result.t2_onset_watts - rcp_onset_watts)
    
    # Overall confidence score (0-100)
    total_confidence = t1_confidence + t2_confidence
    if result.t1_watts and result.t2_onset_watts:
        total_confidence += 20  # Both thresholds detected
    
    # Cap at 100
    total_confidence = min(100, total_confidence)
    
    # Determine agreement level
    systemic_count = sum([t1_is_systemic, t2_onset_is_systemic])
    
    if systemic_count >= 2:
        result.physiological_agreement = "high"
        result.analysis_notes.append(f"🟢 High systemic agreement (confidence: {total_confidence}%)")
    elif systemic_count == 1:
        result.physiological_agreement = "moderate"
        result.analysis_notes.append(f"🟡 Moderate agreement (confidence: {total_confidence}%)")
    else:
        result.physiological_agreement = "low"
        result.analysis_notes.append(f"🔴 Low agreement - Local Perfusion Limitation (confidence: {total_confidence}%)")
    
    # =========================================================================
    # 8. BUILD 4-DOMAIN ZONES
    # =========================================================================
    
    max_power_int = int(max_power)
    zones = []
    
    # Zone 1: Stable aerobic extraction (< T1)
    if result.t1_watts:
        zones.append({
            'zone': 1, 'name': 'Stable Aerobic',
            'power_min': 0, 'power_max': result.t1_watts,
            'description': '<T1 - stable O₂ extraction',
            'training': 'Endurance / Recovery'
        })
    
    # Zone 2: Heavy domain, progressive extraction (T1 → T2)
    t2_w = result.t2_onset_watts
    if result.t1_watts and t2_w:
        zones.append({
            'zone': 2, 'name': 'Progressive Extraction',
            'power_min': result.t1_watts, 'power_max': t2_w,
            'description': 'T1→T2 - progressive O₂ extraction',
            'training': 'Tempo / Threshold'
        })
    
    # Zone 3: Severe domain, non-steady ischemic (T2 → end)
    if t2_w:
        zones.append({
            'zone': 3, 'name': 'Non-Steady Severe',
            'power_min': t2_w, 'power_max': max_power_int,
            'description': 'T2→end - compensatory desaturation',
            'training': 'VO₂max intervals'
        })
    
    # Zone 4: Post-failure ischemic collapse (artefact, not training zone)
    zones.append({
        'zone': 4, 'name': 'Ischemic Collapse',
        'power_min': max_power_int, 'power_max': max_power_int,
        'description': 'Post-failure artefact',
        'training': 'N/A'
    })
    
    result.zones = zones
    result.step_data = step_df.to_dict('records')
    
    result.analysis_notes.append(
        f"Ramp Test Pipeline: T1+T2_onset only, no T2_steady. Confidence: {total_confidence}%."
    )
    
    return result


__all__ = [
    "SmO2AdvancedMetrics",
    "analyze_smo2_advanced",
    "calculate_smo2_slope",
    "calculate_halftime_reoxygenation",
    "calculate_hr_coupling_index",
    "classify_smo2_limiter",
    "format_smo2_metrics_for_report",
    "SmO2ThresholdResult",
    "detect_smo2_thresholds_moxy",
]
