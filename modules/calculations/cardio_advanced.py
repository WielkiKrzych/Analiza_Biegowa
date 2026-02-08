"""
Cardiovascular Cost Diagnostics Module.

Calculates advanced cardiac cost metrics for efficiency analysis:
- Pulse Power (W/bpm)
- Efficiency Factor (W/bpm)
- HR Drift / Pa:Hr (%)
- Cardiovascular Cost Index (CCI)

Classifies cardiovascular efficiency:
- Efficient
- Compensating
- Decompensating
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("Tri_Dashboard.CardioAdvanced")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CardiovascularMetrics:
    """Container for cardiovascular cost metrics."""
    # Core metrics
    pulse_power: float = 0.0              # W/bpm average
    efficiency_factor: float = 0.0        # EF = NP / HR_avg
    hr_drift_pct: float = 0.0             # Pa:Hr cardiac decoupling %
    hr_recovery_1min: Optional[float] = None  # HR drop in 1st min of recovery
    
    # CCI - Cardiovascular Cost Index
    cci_avg: float = 0.0                  # Average CCI during test
    cci_breakpoint_watts: Optional[float] = None  # Power at CCI breakpoint
    cci_breakpoint_hr: Optional[float] = None     # HR at breakpoint
    
    # Classification
    efficiency_status: str = "unknown"    # efficient, compensating, decompensating
    efficiency_confidence: float = 0.0
    
    # Interpretation
    interpretation: str = ""
    recommendations: List[Dict[str, str]] = field(default_factory=list)
    
    # CCI profile for charting
    cci_profile: List[Dict[str, float]] = field(default_factory=list)


# =============================================================================
# METRIC CALCULATIONS
# =============================================================================

def calculate_pulse_power(
    df: pd.DataFrame,
    power_col: str = "watts",
    hr_col: str = "hr"
) -> Tuple[float, pd.Series]:
    """
    Calculate Pulse Power (W/bpm) - power generated per heartbeat.
    
    Returns:
        (average_pulse_power, pulse_power_series)
    """
    if power_col not in df.columns or hr_col not in df.columns:
        return 0.0, pd.Series()
    
    # Filter valid data
    mask = (df[power_col] > 50) & (df[hr_col] > 80)
    if mask.sum() < 10:
        return 0.0, pd.Series()
    
    filtered = df.loc[mask].copy()
    
    # Pulse Power = Power / HR
    pp = filtered[power_col] / filtered[hr_col]
    
    return float(pp.mean()), pp


def calculate_efficiency_factor(
    df: pd.DataFrame,
    power_col: str = "watts",
    hr_col: str = "hr"
) -> float:
    """
    Calculate Efficiency Factor (NP / avg HR).
    
    For ramp tests, we use average power instead of NP.
    """
    if power_col not in df.columns or hr_col not in df.columns:
        return 0.0
    
    mask = (df[power_col] > 50) & (df[hr_col] > 80)
    if mask.sum() < 10:
        return 0.0
    
    filtered = df.loc[mask]
    
    avg_power = filtered[power_col].mean()
    avg_hr = filtered[hr_col].mean()
    
    if avg_hr > 0:
        return float(avg_power / avg_hr)
    return 0.0


def calculate_hr_drift(
    df: pd.DataFrame,
    power_col: str = "watts",
    hr_col: str = "hr",
    window_pct: float = 0.5
) -> float:
    """
    Calculate HR Drift (Pa:Hr) - cardiac decoupling percentage.
    
    Compares HR/Power ratio in first half vs second half.
    """
    if power_col not in df.columns or hr_col not in df.columns:
        return 0.0
    
    # Filter valid power
    mask = df[power_col] > 100
    if mask.sum() < 20:
        return 0.0
    
    filtered = df.loc[mask].copy()
    n = len(filtered)
    mid = int(n * window_pct)
    
    # First half
    first_half = filtered.iloc[:mid]
    first_ratio = first_half[hr_col].mean() / first_half[power_col].mean()
    
    # Second half
    second_half = filtered.iloc[mid:]
    second_ratio = second_half[hr_col].mean() / second_half[power_col].mean()
    
    if first_ratio > 0:
        drift = ((second_ratio - first_ratio) / first_ratio) * 100
        return float(drift)
    
    return 0.0


def calculate_hr_recovery(
    df: pd.DataFrame,
    hr_col: str = "hr",
    power_col: str = "watts",
    recovery_window_sec: int = 60
) -> Optional[float]:
    """
    Calculate HR Recovery - drop in HR in first minute after peak.
    """
    if hr_col not in df.columns or power_col not in df.columns:
        return None
    
    # Find peak power index
    peak_idx = df[power_col].idxmax()
    peak_hr = df.loc[peak_idx, hr_col]
    
    # Get recovery segment
    recovery_df = df.loc[peak_idx:].head(recovery_window_sec)
    
    if len(recovery_df) < 30:
        return None
    
    # HR at end of recovery window
    end_hr = recovery_df[hr_col].iloc[-1]
    
    recovery = peak_hr - end_hr
    return float(recovery) if recovery > 0 else None


def calculate_cci(
    df: pd.DataFrame,
    power_col: str = "watts",
    hr_col: str = "hr",
    window: int = 30
) -> Tuple[float, Optional[float], Optional[float], List[Dict[str, float]]]:
    """
    Calculate Cardiovascular Cost Index (CCI).
    
    CCI = d(HR) / d(Power) - rate of HR increase per watt
    Lower is better (more efficient).
    
    Returns:
        (avg_cci, breakpoint_watts, breakpoint_hr, cci_profile)
    """
    if power_col not in df.columns or hr_col not in df.columns:
        return 0.0, None, None, []
    
    # Filter to ramp portion
    mask = df[power_col] > 100
    if mask.sum() < 50:
        return 0.0, None, None, []
    
    filtered = df.loc[mask].copy()
    
    # Smooth data
    power_smooth = filtered[power_col].rolling(window=window, min_periods=1).mean()
    hr_smooth = filtered[hr_col].rolling(window=window, min_periods=1).mean()
    
    # Calculate CCI as derivative
    d_hr = hr_smooth.diff()
    d_power = power_smooth.diff()
    
    # CCI = dHR / dPower (bpm/W)
    cci = d_hr / d_power.replace(0, np.nan)
    cci = cci.replace([np.inf, -np.inf], np.nan).dropna()
    
    if len(cci) < 20:
        return 0.0, None, None, []
    
    avg_cci = float(cci.mean())
    
    # Build profile
    profile = []
    for i in range(0, len(filtered), 10):
        if i < len(power_smooth) and i < len(cci):
            profile.append({
                "power": float(power_smooth.iloc[i]),
                "hr": float(hr_smooth.iloc[i]),
                "cci": float(cci.iloc[i]) if i < len(cci) else avg_cci
            })
    
    # Find breakpoint (where CCI increases significantly)
    breakpoint_watts = None
    breakpoint_hr = None
    
    # Use rolling CCI to find inflection
    cci_rolling = cci.rolling(window=20, min_periods=1).mean()
    threshold = avg_cci * 1.5  # 50% increase from average
    
    for i, val in enumerate(cci_rolling):
        if val > threshold:
            idx = cci.index[i]
            breakpoint_watts = float(power_smooth.loc[idx])
            breakpoint_hr = float(hr_smooth.loc[idx])
            break
    
    return avg_cci, breakpoint_watts, breakpoint_hr, profile


# =============================================================================
# EFFICIENCY CLASSIFICATION
# =============================================================================

def classify_cardiovascular_efficiency(metrics: CardiovascularMetrics) -> Tuple[str, float, str]:
    """
    Classify cardiovascular efficiency status.
    
    Returns:
        (status, confidence, interpretation)
    """
    scores = {"efficient": 0.0, "compensating": 0.0, "decompensating": 0.0}
    
    pp = metrics.pulse_power
    ef = metrics.efficiency_factor
    drift = metrics.hr_drift_pct
    cci = metrics.cci_avg
    
    # --- PULSE POWER ANALYSIS ---
    if pp > 2.0:
        scores["efficient"] += 2.0
    elif pp > 1.5:
        scores["efficient"] += 1.0
        scores["compensating"] += 0.5
    elif pp > 1.0:
        scores["compensating"] += 1.5
    else:
        scores["decompensating"] += 2.0
    
    # --- EFFICIENCY FACTOR ANALYSIS ---
    if ef > 1.8:
        scores["efficient"] += 2.0
    elif ef > 1.4:
        scores["efficient"] += 1.0
    elif ef > 1.0:
        scores["compensating"] += 1.5
    else:
        scores["decompensating"] += 1.5
    
    # --- HR DRIFT ANALYSIS ---
    if drift < 3:
        scores["efficient"] += 2.0
    elif drift < 5:
        scores["compensating"] += 1.5
    elif drift < 8:
        scores["decompensating"] += 1.0
    else:
        scores["decompensating"] += 2.5
    
    # --- CCI ANALYSIS ---
    if cci < 0.15:
        scores["efficient"] += 1.5
    elif cci < 0.25:
        scores["compensating"] += 1.0
    else:
        scores["decompensating"] += 1.5
    
    # Determine winner
    total = sum(scores.values()) or 1.0
    max_score = max(scores.values())
    status = max(scores, key=scores.get)
    confidence = max_score / total
    
    # Generate interpretation
    interpretation = _generate_cardio_interpretation(status, metrics, scores)
    
    return status, confidence, interpretation


def _generate_cardio_interpretation(
    status: str,
    metrics: CardiovascularMetrics,
    scores: Dict[str, float]
) -> str:
    """Generate coach-oriented interpretation text."""
    
    pp = metrics.pulse_power
    ef = metrics.efficiency_factor
    drift = metrics.hr_drift_pct
    breakpoint = metrics.cci_breakpoint_watts
    
    if status == "efficient":
        base = "EFFICIENT – Układ krążenia pracuje optymalnie"
        detail = (
            f"Pulse Power {pp:.2f} W/bpm i EF {ef:.2f} wskazują na efektywne wykorzystanie rzutu serca. "
            f"Cardiac Drift {drift:.1f}% w normie. "
        )
        if breakpoint:
            detail += f"Punkt załamania CCI przy {breakpoint:.0f}W – to Twój próg efektywności krążeniowej."
    
    elif status == "compensating":
        base = "COMPENSATING – Serce kompensuje ograniczenia"
        detail = (
            f"Umiarkowany Pulse Power ({pp:.2f} W/bpm) i Drift {drift:.1f}% sugerują, "
            "że serce musi pracować ciężej, by utrzymać moc. "
        )
        if drift > 5:
            detail += "Rozważ strategię nawodnienia i chłodzenia. "
    
    else:  # decompensating
        base = "DECOMPENSATING – Nieefektywność krążeniowa"
        detail = (
            f"Niski Pulse Power ({pp:.2f} W/bpm) i wysoki Drift ({drift:.1f}%) wskazują na "
            "narastający koszt sercowy. "
            "Priorytet: budowa bazy aerobowej i/lub adaptacja termiczna."
        )
    
    return f"{base}\n{detail}"


def generate_cardio_recommendations(
    status: str,
    metrics: CardiovascularMetrics
) -> List[Dict[str, str]]:
    """Generate training and environmental recommendations."""
    
    recommendations = []
    
    if status == "efficient":
        recommendations = [
            {
                "type": "TRENINGOWA",
                "action": "Utrzymanie treningu spolaryzowanego 80/20",
                "expected": "Stabilizacja PP i EF na obecnym poziomie",
                "risk": "low"
            },
            {
                "type": "PERFORMANCE",
                "action": "Można zwiększyć intensywność interwałów",
                "expected": "Wzrost PP o 5-10% w 4-6 tygodni",
                "risk": "low"
            }
        ]
    elif status == "compensating":
        recommendations = [
            {
                "type": "TRENINGOWA",
                "action": "Więcej objętości Z2 (3-4h sesje)",
                "expected": "Poprawa PP o 0.1-0.2 W/bpm",
                "risk": "low"
            },
            {
                "type": "ŚRODOWISKOWA",
                "action": "Nawadnianie 500-750ml/h + elektrolity",
                "expected": "Redukcja Drift o 2-3%",
                "risk": "low"
            },
            {
                "type": "RECOVERY",
                "action": "Dłuższe przerwy między sesjami intensywnymi",
                "expected": "Lepsza adaptacja sercowa",
                "risk": "low"
            }
        ]
    else:  # decompensating
        recommendations = [
            {
                "type": "TRENINGOWA",
                "action": "Redukcja TSS o 20-30%, focus na Z2",
                "expected": "Spadek Drift poniżej 5%",
                "risk": "medium"
            },
            {
                "type": "ŚRODOWISKOWA",
                "action": "Adaptacja termiczna (10-14 dni w cieple)",
                "expected": "Spadek HR o 10-15 bpm w cieple",
                "risk": "medium"
            },
            {
                "type": "DIAGNOSTYCZNA",
                "action": "Rozważ badanie kardiologiczne (EKG, echo)",
                "expected": "Wykluczenie patologii",
                "risk": "high"
            }
        ]
    
    return recommendations


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def analyze_cardiovascular(
    df: pd.DataFrame,
    power_col: str = "watts",
    hr_col: str = "hr"
) -> CardiovascularMetrics:
    """
    Perform complete cardiovascular cost analysis.
    """
    metrics = CardiovascularMetrics()
    
    if hr_col not in df.columns:
        metrics.interpretation = "Brak danych HR."
        return metrics
    
    if power_col not in df.columns:
        metrics.interpretation = "Brak danych mocy."
        return metrics
    
    # Calculate metrics
    metrics.pulse_power, _ = calculate_pulse_power(df, power_col, hr_col)
    metrics.efficiency_factor = calculate_efficiency_factor(df, power_col, hr_col)
    metrics.hr_drift_pct = calculate_hr_drift(df, power_col, hr_col)
    metrics.hr_recovery_1min = calculate_hr_recovery(df, hr_col, power_col)
    
    # Calculate CCI
    cci_avg, bp_watts, bp_hr, profile = calculate_cci(df, power_col, hr_col)
    metrics.cci_avg = cci_avg
    metrics.cci_breakpoint_watts = bp_watts
    metrics.cci_breakpoint_hr = bp_hr
    metrics.cci_profile = profile
    
    # Classify efficiency
    status, confidence, interpretation = classify_cardiovascular_efficiency(metrics)
    metrics.efficiency_status = status
    metrics.efficiency_confidence = confidence
    metrics.interpretation = interpretation
    
    # Generate recommendations
    metrics.recommendations = generate_cardio_recommendations(status, metrics)
    
    return metrics


def format_cardio_metrics_for_report(metrics: CardiovascularMetrics) -> Dict[str, Any]:
    """Format metrics for inclusion in JSON/PDF reports."""
    return {
        "pulse_power": round(metrics.pulse_power, 3),
        "efficiency_factor": round(metrics.efficiency_factor, 3),
        "hr_drift_pct": round(metrics.hr_drift_pct, 2),
        "hr_recovery_1min": round(metrics.hr_recovery_1min, 0) if metrics.hr_recovery_1min else None,
        "cci_avg": round(metrics.cci_avg, 4),
        "cci_breakpoint_watts": round(metrics.cci_breakpoint_watts, 0) if metrics.cci_breakpoint_watts else None,
        "cci_breakpoint_hr": round(metrics.cci_breakpoint_hr, 0) if metrics.cci_breakpoint_hr else None,
        "efficiency_status": metrics.efficiency_status,
        "efficiency_confidence": round(metrics.efficiency_confidence, 2),
        "interpretation": metrics.interpretation,
        "recommendations": metrics.recommendations,
        "cci_profile": metrics.cci_profile[:20]  # Limit for JSON size
    }


__all__ = [
    "CardiovascularMetrics",
    "analyze_cardiovascular",
    "calculate_pulse_power",
    "calculate_efficiency_factor",
    "calculate_hr_drift",
    "calculate_cci",
    "classify_cardiovascular_efficiency",
    "format_cardio_metrics_for_report",
]
