"""
Conflict Detection for Ramp Test Analysis.

Per methodology/ramp_test/06_signal_conflicts.md:
- Conflicts are INFORMATIVE, not errors
- Each conflict has physiological interpretation
- Conflicts reduce confidence but do NOT "resolve" algorithmically

This module DETECTS and DESCRIBES conflicts.
It does NOT attempt to resolve them.
"""
import pandas as pd
from typing import List, Optional

from models.results import (
    ConflictReport, SignalConflict, ConflictType, ConflictSeverity
)
from modules.calculations.threshold_types import (
    StepVTResult, StepSmO2Result
)


# ============================================================
# CONFLICT DESCRIPTIONS (per methodology/06_signal_conflicts.md)
# ============================================================

CONFLICT_DESCRIPTIONS = {
    ConflictType.CARDIAC_DRIFT: {
        "name": "Cardiac Drift",
        "description": "HR rośnie przy stałej mocy",
        "interpretation": "Termoregulacja, odwodnienie lub zmęczenie - HR może nie odzwierciedlać obciążenia",
        "recommendation": "Używaj mocy, nie HR, do definiowania stref",
        "penalty": 0.1
    },
    ConflictType.HR_PLATEAU: {
        "name": "HR Plateau",
        "description": "HR przestaje rosnąć mimo wzrostu mocy",
        "interpretation": "Osiągnięcie limitu chronotropowego - potwierdza zbliżenie do maksimum",
        "recommendation": "Może wskazywać na osiągnięcie VT2",
        "penalty": 0.0  # This is informative, not problematic
    },
    ConflictType.HR_LAG: {
        "name": "HR Lag",
        "description": "HR opóźnione względem mocy",
        "interpretation": "Wolna kinetyka sercowa lub zbyt szybka rampa",
        "recommendation": "Rozważ korektę czasową lub wolniejszy protokół",
        "penalty": 0.05
    },
    ConflictType.SMO2_FLAT: {
        "name": "SmO₂ Flat",
        "description": "SmO₂ nie wykazuje spadku mimo wzrostu mocy",
        "interpretation": "Wysoka kapilaryzacja mięśnia, problem z sensorem, lub nieaktywny mięsień pod sensorem",
        "recommendation": "SmO₂ nie może potwierdzić VT - używaj tylko sygnałów systemowych",
        "penalty": 0.1
    },
    ConflictType.SMO2_EARLY: {
        "name": "SmO₂ Early",
        "description": "SmO₂ reaguje WCZEŚNIEJ niż VT",
        "interpretation": "Niska kapilaryzacja mięśnia pod sensorem - limit lokalny przed systemowym",
        "recommendation": "VT prawidłowe, SmO₂ wskazuje na potencjał poprawy kapilaryzacji",
        "penalty": 0.1
    },
    ConflictType.SMO2_LATE: {
        "name": "SmO₂ Late",
        "description": "SmO₂ reaguje PÓŹNIEJ niż VT",
        "interpretation": "Wysoka rezerwa ekstrakcyjna mięśnia - dobry znak wytrenowania",
        "recommendation": "VT prawidłowe, SmO₂ wskazuje na dobrą lokalną adaptację",
        "penalty": 0.05  # Lower penalty - positive finding
    },
    ConflictType.DFA_ANOMALY: {
        "name": "DFA Anomaly",
        "description": "DFA α1 > 1.0 przy wysokim HR",
        "interpretation": "Artefakty w sygnale RR - ektopie lub problemy z detekcją R-peaks",
        "recommendation": "Wyklucz DFA z analizy VT",
        "penalty": 0.15
    },
    ConflictType.DFA_STABLE: {
        "name": "DFA Stable",
        "description": "DFA nie wykazuje typowego spadku",
        "interpretation": "Bardzo wysoki próg lub niewystarczające obciążenie testu",
        "recommendation": "Rozważ dłuższy test lub wyższe obciążenie",
        "penalty": 0.1
    },
    ConflictType.DFA_FAST_DROP: {
        "name": "DFA Fast Drop",
        "description": "DFA spada szybciej niż oczekiwano na podstawie HR",
        "interpretation": "Wysoka wrażliwość autonomiczna - VT może być niższe niż sugeruje HR",
        "recommendation": "Uwzględnij wcześniejszy próg niż wskazuje HR",
        "penalty": 0.05
    }
}


# ============================================================
# CONFLICT DETECTION FUNCTIONS
# ============================================================

def detect_conflicts(
    vt_result: Optional[StepVTResult],
    smo2_result: Optional[StepSmO2Result],
    df: Optional[pd.DataFrame] = None,
    power_column: str = 'watts',
    hr_column: str = 'hr',
    time_column: str = 'time'
) -> ConflictReport:
    """
    Detect all conflicts in Ramp Test data.
    
    DOES NOT RESOLVE conflicts - only DETECTS and DESCRIBES them.
    Each conflict includes:
    - Type (enum)
    - Description
    - Physiological interpretation
    - Confidence penalty
    
    Args:
        vt_result: VT detection result (from VE)
        smo2_result: SmO₂ analysis result
        df: Optional DataFrame for HR/Power analysis
        
    Returns:
        ConflictReport with all detected conflicts
    """
    report = ConflictReport(signals_analyzed=[])
    
    # Track which signals we analyzed
    if vt_result and vt_result.vt1_zone:
        report.signals_analyzed.append("VE")
    if smo2_result:
        report.signals_analyzed.append("SmO2 (LOCAL)")
    if df is not None and hr_column in df.columns:
        report.signals_analyzed.append("HR")
    
    # Detect SmO₂ vs VT conflicts
    smo2_conflicts = _detect_smo2_vs_vt_conflicts(vt_result, smo2_result)
    report.conflicts.extend(smo2_conflicts)
    
    # Detect HR vs Power conflicts (if data available)
    if df is not None:
        hr_conflicts = _detect_hr_vs_power_conflicts(df, power_column, hr_column, time_column)
        report.conflicts.extend(hr_conflicts)
    
    # Calculate agreement score
    total_penalty = sum(c.confidence_penalty for c in report.conflicts)
    report.agreement_score = max(0.0, 1.0 - total_penalty)
    
    # Generate recommendations
    report.recommendations = _generate_recommendations(report.conflicts)
    
    return report


def _detect_smo2_vs_vt_conflicts(
    vt_result: Optional[StepVTResult],
    smo2_result: Optional[StepSmO2Result]
) -> List[SignalConflict]:
    """Detect conflicts between SmO₂ and VT."""
    conflicts = []
    
    if not vt_result or not vt_result.vt1_zone:
        return conflicts
    if not smo2_result:
        return conflicts
    
    vt1_mid = vt_result.vt1_zone.midpoint_watts
    
    # Check if SmO₂ shows no drop (FLAT)
    if smo2_result.smo2_1_zone is None:
        info = CONFLICT_DESCRIPTIONS[ConflictType.SMO2_FLAT]
        conflicts.append(SignalConflict(
            conflict_type=ConflictType.SMO2_FLAT,
            severity=ConflictSeverity.WARNING,
            signal_a="SmO2 (LOCAL)",
            signal_b="VE",
            description=info["description"],
            physiological_interpretation=info["interpretation"],
            confidence_penalty=info["penalty"]
        ))
        return conflicts
    
    # Check SmO₂ timing vs VT
    smo2_mid = smo2_result.smo2_1_zone.midpoint_watts
    deviation = smo2_mid - vt1_mid
    
    if deviation < -20:  # SmO₂ drops >20W BEFORE VT
        info = CONFLICT_DESCRIPTIONS[ConflictType.SMO2_EARLY]
        conflicts.append(SignalConflict(
            conflict_type=ConflictType.SMO2_EARLY,
            severity=ConflictSeverity.WARNING,
            signal_a="SmO2 (LOCAL)",
            signal_b="VE",
            description=f"{info['description']} ({abs(deviation):.0f} W wcześniej)",
            physiological_interpretation=info["interpretation"],
            magnitude=abs(deviation),
            confidence_penalty=info["penalty"]
        ))
    elif deviation > 20:  # SmO₂ drops >20W AFTER VT
        info = CONFLICT_DESCRIPTIONS[ConflictType.SMO2_LATE]
        conflicts.append(SignalConflict(
            conflict_type=ConflictType.SMO2_LATE,
            severity=ConflictSeverity.INFO,  # Positive finding
            signal_a="SmO2 (LOCAL)",
            signal_b="VE",
            description=f"{info['description']} ({deviation:.0f} W później)",
            physiological_interpretation=info["interpretation"],
            magnitude=deviation,
            confidence_penalty=info["penalty"]
        ))
    
    return conflicts


def _detect_hr_vs_power_conflicts(
    df: pd.DataFrame,
    power_column: str,
    hr_column: str,
    time_column: str
) -> List[SignalConflict]:
    """Detect conflicts between HR and Power."""
    conflicts = []
    
    if power_column not in df.columns or hr_column not in df.columns:
        return conflicts
    
    # Cardiac Drift detection (HR rises at constant power)
    # Look for segments where power is stable but HR increases
    drift = _detect_cardiac_drift(df, power_column, hr_column, time_column)
    if drift is not None:
        info = CONFLICT_DESCRIPTIONS[ConflictType.CARDIAC_DRIFT]
        conflicts.append(SignalConflict(
            conflict_type=ConflictType.CARDIAC_DRIFT,
            severity=ConflictSeverity.WARNING,
            signal_a="HR",
            signal_b="Power",
            description=f"{info['description']} (+{drift:.0f} bpm)",
            physiological_interpretation=info["interpretation"],
            magnitude=drift,
            confidence_penalty=info["penalty"]
        ))
    
    # HR Plateau detection (HR stops rising)
    plateau = _detect_hr_plateau(df, power_column, hr_column, time_column)
    if plateau is not None:
        info = CONFLICT_DESCRIPTIONS[ConflictType.HR_PLATEAU]
        conflicts.append(SignalConflict(
            conflict_type=ConflictType.HR_PLATEAU,
            severity=ConflictSeverity.INFO,  # Informative, not problematic
            signal_a="HR",
            signal_b="Power",
            description=f"{info['description']} (przy {plateau:.0f} W)",
            physiological_interpretation=info["interpretation"],
            magnitude=plateau,
            confidence_penalty=info["penalty"]
        ))
    
    return conflicts


def _detect_cardiac_drift(
    df: pd.DataFrame,
    power_column: str,
    hr_column: str,
    time_column: str,
    min_duration_sec: int = 60,
    power_tolerance: float = 10.0,
    drift_threshold_bpm: float = 5.0
) -> Optional[float]:
    """
    Detect cardiac drift: HR rising at constant power.
    
    Returns drift in bpm if detected, else None.
    """
    # Look at the middle portion of the test (avoid warmup/cooldown)
    n = len(df)
    if n < 120:
        return None
    
    mid_start = n // 4
    mid_end = 3 * n // 4
    mid_df = df.iloc[mid_start:mid_end]
    
    # Find stable power segments
    power = mid_df[power_column].values
    hr = mid_df[hr_column].values
    
    # Simple check: look for periods where power std is low but HR trend is positive
    window_size = min(60, len(power) // 4)
    if window_size < 30:
        return None
    
    max_drift = 0.0
    for i in range(0, len(power) - window_size, window_size // 2):
        segment_power = power[i:i+window_size]
        segment_hr = hr[i:i+window_size]
        
        # Check if power is stable
        if segment_power.std() < power_tolerance:
            # Check if HR is drifting up
            hr_start = segment_hr[:10].mean()
            hr_end = segment_hr[-10:].mean()
            drift = hr_end - hr_start
            if drift > max_drift:
                max_drift = drift
    
    if max_drift >= drift_threshold_bpm:
        return max_drift
    return None


def _detect_hr_plateau(
    df: pd.DataFrame,
    power_column: str,
    hr_column: str,
    time_column: str,
    plateau_threshold: float = 3.0
) -> Optional[float]:
    """
    Detect HR plateau: HR stops rising despite power increase.
    
    Returns power at plateau if detected, else None.
    """
    n = len(df)
    if n < 120:
        return None
    
    # Look at the last portion of the test
    end_portion = df.iloc[-n//4:]
    
    power = end_portion[power_column].values
    hr = end_portion[hr_column].values
    
    # Check if power is still rising but HR is flat
    power_diff = power[-10:].mean() - power[:10].mean()
    hr_diff = hr[-10:].mean() - hr[:10].mean()
    
    if power_diff > 20 and abs(hr_diff) < plateau_threshold:
        return power[-1]
    
    return None


def _generate_recommendations(conflicts: List[SignalConflict]) -> List[str]:
    """Generate recommendations based on detected conflicts."""
    recommendations = []
    
    for conflict in conflicts:
        if conflict.conflict_type in CONFLICT_DESCRIPTIONS:
            info = CONFLICT_DESCRIPTIONS[conflict.conflict_type]
            recommendations.append(info["recommendation"])
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for r in recommendations:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    
    return unique


# ============================================================
# CONFIDENCE CALCULATION
# ============================================================

def calculate_conflict_adjusted_confidence(
    base_confidence: float,
    conflicts: ConflictReport
) -> float:
    """
    Adjust confidence based on detected conflicts.
    
    Each conflict reduces confidence by its penalty.
    Does NOT attempt to resolve conflicts.
    
    Args:
        base_confidence: Starting confidence (0-1)
        conflicts: Detected conflicts
    
    Returns:
        Adjusted confidence (0-1)
    """
    total_penalty = conflicts.total_confidence_penalty()
    adjusted = base_confidence - total_penalty
    return max(0.1, min(1.0, adjusted))


def get_conflict_summary(conflicts: ConflictReport) -> str:
    """
    Generate human-readable summary of conflicts.
    
    For report display.
    """
    if not conflicts.has_conflicts:
        return "✅ Brak konfliktów między sygnałami"
    
    n = len(conflicts.conflicts)
    critical = len(conflicts.critical_conflicts)
    
    if critical > 0:
        return f"⛔ {n} konflikt(ów), w tym {critical} krytyczny(ch)"
    else:
        return f"⚠️ {n} konflikt(ów) - patrz szczegóły"


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'detect_conflicts',
    'calculate_conflict_adjusted_confidence',
    'get_conflict_summary',
    'CONFLICT_DESCRIPTIONS',
]
