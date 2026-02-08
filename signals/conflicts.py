"""
Signal Conflict Detection Module

Detects conflicts and disagreements between physiological signals:
- HR vs Power (cardiac drift, decoupling)
- SmO₂ vs Power (O2 kinetics mismatch)
- DFA-a1 anomalies (correlation with intensity)
- Phase mismatches (lag between signals)

When signals disagree, results MUST communicate this clearly.
NO STREAMLIT OR UI DEPENDENCIES ALLOWED.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import numpy as np
import pandas as pd


class ConflictSeverity(str, Enum):
    """Severity levels for signal conflicts."""
    MINOR = "minor"       # Small disagreement, may be noise
    MAJOR = "major"       # Significant disagreement, affects interpretation
    CRITICAL = "critical" # Signals fundamentally disagree


class ConflictType(str, Enum):
    """Types of signal conflicts."""
    CARDIAC_DRIFT = "cardiac_drift"           # HR/Power ratio increases
    PHASE_MISMATCH = "phase_mismatch"         # Timing lag between signals
    DIRECTION_CONFLICT = "direction_conflict" # Signals moving opposite ways
    DFA_ANOMALY = "dfa_anomaly"               # DFA-a1 unexpected values
    DECOUPLING = "decoupling"                 # Loss of correlation
    RANGE_MISMATCH = "range_mismatch"         # Different intensity ranges


@dataclass
class SignalConflict:
    """A single conflict between two signals."""
    signal_a: str                   # e.g., "HR"
    signal_b: str                   # e.g., "Power"
    conflict_type: ConflictType
    severity: ConflictSeverity
    description: str
    affected_zones: List[str] = field(default_factory=list)  # ["VT1", "VT2"]
    details: Dict = field(default_factory=dict)
    
    def __str__(self) -> str:
        emoji = {"minor": "🟡", "major": "🟠", "critical": "🔴"}.get(self.severity.value, "")
        return f"{emoji} {self.signal_a} vs {self.signal_b}: {self.description}"


@dataclass
class ConflictAnalysisResult:
    """Complete result of conflict analysis between signals."""
    has_conflicts: bool
    conflicts: List[SignalConflict] = field(default_factory=list)
    agreement_score: float = 1.0    # 0-1, higher = more agreement
    recommendations: List[str] = field(default_factory=list)
    signals_analyzed: List[str] = field(default_factory=list)
    
    def get_critical_conflicts(self) -> List[SignalConflict]:
        """Get only critical conflicts."""
        return [c for c in self.conflicts if c.severity == ConflictSeverity.CRITICAL]
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        if not self.has_conflicts:
            return "✅ Wszystkie sygnały są zgodne"
        
        n_critical = len(self.get_critical_conflicts())
        n_major = len([c for c in self.conflicts if c.severity == ConflictSeverity.MAJOR])
        n_minor = len([c for c in self.conflicts if c.severity == ConflictSeverity.MINOR])
        
        parts = []
        if n_critical > 0:
            parts.append(f"🔴 {n_critical} krytycznych")
        if n_major > 0:
            parts.append(f"🟠 {n_major} poważnych")
        if n_minor > 0:
            parts.append(f"🟡 {n_minor} drobnych")
        
        return f"⚠️ Wykryto konflikty: {', '.join(parts)}"


# ============================================================
# Conflict Detection Functions
# ============================================================

def detect_cardiac_drift(
    hr_data: pd.Series,
    power_data: pd.Series,
    threshold_pct: float = 0.05
) -> Optional[SignalConflict]:
    """
    Detect cardiac drift (HR increasing while power stable).
    
    Cardiac drift typically indicates fatigue, dehydration, or heat stress.
    
    Args:
        hr_data: Heart rate series
        power_data: Power series
        threshold_pct: Threshold for drift detection (default: 5%)
    
    Returns:
        SignalConflict if drift detected, None otherwise
    """
    if hr_data is None or power_data is None:
        return None
    if len(hr_data) < 60 or len(power_data) < 60:
        return None
    
    # Calculate HR/Power ratio (efficiency)
    valid_mask = (power_data > 50) & (hr_data > 60)
    if valid_mask.sum() < 30:
        return None
    
    hr_valid = hr_data[valid_mask].values
    power_valid = power_data[valid_mask].values
    
    efficiency = hr_valid / power_valid
    
    # Split into first and second half
    mid = len(efficiency) // 2
    first_half = efficiency[:mid]
    second_half = efficiency[mid:]
    
    mean_first = np.nanmean(first_half)
    mean_second = np.nanmean(second_half)
    
    if mean_first == 0:
        return None
    
    drift_pct = (mean_second - mean_first) / mean_first
    
    if drift_pct > threshold_pct:
        severity = ConflictSeverity.MINOR if drift_pct < 0.1 else (
            ConflictSeverity.MAJOR if drift_pct < 0.15 else ConflictSeverity.CRITICAL
        )
        return SignalConflict(
            signal_a="HR",
            signal_b="Power",
            conflict_type=ConflictType.CARDIAC_DRIFT,
            severity=severity,
            description=f"Dryft tętna: +{drift_pct:.1%} (HR rośnie przy stałej mocy)",
            details={"drift_pct": round(drift_pct * 100, 1)}
        )
    
    return None


def detect_smo2_power_conflict(
    smo2_data: pd.Series,
    power_data: pd.Series,
    window: int = 60
) -> Optional[SignalConflict]:
    """
    Detect conflict between SmO2 and Power trends.
    
    Normally SmO2 should decrease with increasing power.
    
    Args:
        smo2_data: SmO2 series (%)
        power_data: Power series
        window: Window for trend calculation
    
    Returns:
        SignalConflict if conflict detected, None otherwise
    """
    if smo2_data is None or power_data is None:
        return None
    if len(smo2_data) < window or len(power_data) < window:
        return None
    
    # Calculate rolling trends
    smo2_trend = smo2_data.diff(window).dropna()
    power_trend = power_data.diff(window).dropna()
    
    if len(smo2_trend) == 0 or len(power_trend) == 0:
        return None
    
    # Align lengths
    min_len = min(len(smo2_trend), len(power_trend))
    smo2_trend = smo2_trend.iloc[:min_len]
    power_trend = power_trend.iloc[:min_len]
    
    # Check for direction conflict
    # Power up + SmO2 up = unusual (should go down)
    conflict_mask = (power_trend > 10) & (smo2_trend > 2)
    conflict_ratio = conflict_mask.sum() / len(conflict_mask)
    
    if conflict_ratio > 0.1:
        severity = ConflictSeverity.MINOR if conflict_ratio < 0.2 else (
            ConflictSeverity.MAJOR if conflict_ratio < 0.3 else ConflictSeverity.CRITICAL
        )
        return SignalConflict(
            signal_a="SmO2",
            signal_b="Power",
            conflict_type=ConflictType.DIRECTION_CONFLICT,
            severity=severity,
            description=f"SmO2 rośnie przy rosnącej mocy ({conflict_ratio:.0%} czasu)",
            affected_zones=["VT1", "VT2"],
            details={"conflict_ratio": round(conflict_ratio * 100, 1)}
        )
    
    return None


def detect_dfa_anomaly(
    dfa_data: pd.Series,
    power_data: pd.Series,
    high_power_threshold: float = 0.7  # % of max power
) -> Optional[SignalConflict]:
    """
    Detect DFA-a1 anomalies at high intensity.
    
    At high intensity, DFA-a1 should be ~0.5-0.75 (uncorrelated).
    Values > 1.0 at high intensity suggest measurement issues.
    
    Args:
        dfa_data: DFA Alpha-1 series
        power_data: Power series
        high_power_threshold: Threshold for "high power" (% of max)
    
    Returns:
        SignalConflict if anomaly detected, None otherwise
    """
    if dfa_data is None or power_data is None:
        return None
    if len(dfa_data) < 10 or len(power_data) < 10:
        return None
    
    max_power = power_data.max()
    if max_power <= 0:
        return None
    
    high_power_mask = power_data > (max_power * high_power_threshold)
    
    if high_power_mask.sum() < 5:
        return None
    
    # Get DFA values at high power (need to align indices)
    common_idx = dfa_data.index.intersection(power_data[high_power_mask].index)
    if len(common_idx) == 0:
        return None
    
    dfa_high = dfa_data.loc[common_idx]
    
    # Check for anomalous values
    anomaly_mask = dfa_high > 1.0
    anomaly_ratio = anomaly_mask.sum() / len(dfa_high)
    
    if anomaly_ratio > 0.2:
        severity = ConflictSeverity.MAJOR if anomaly_ratio < 0.5 else ConflictSeverity.CRITICAL
        return SignalConflict(
            signal_a="DFA-a1",
            signal_b="Power",
            conflict_type=ConflictType.DFA_ANOMALY,
            severity=severity,
            description=f"DFA-a1 > 1.0 przy wysokiej intensywności ({anomaly_ratio:.0%})",
            affected_zones=["VT2"],
            details={"anomaly_ratio": round(anomaly_ratio * 100, 1)}
        )
    
    return None


def detect_decoupling(
    signal_a: pd.Series,
    signal_b: pd.Series,
    signal_a_name: str,
    signal_b_name: str,
    correlation_threshold: float = 0.5
) -> Optional[SignalConflict]:
    """
    Detect decoupling (loss of correlation) between two signals.
    
    Args:
        signal_a: First signal
        signal_b: Second signal
        signal_a_name: Name of first signal
        signal_b_name: Name of second signal
        correlation_threshold: Minimum expected correlation
    
    Returns:
        SignalConflict if decoupling detected, None otherwise
    """
    if signal_a is None or signal_b is None:
        return None
    if len(signal_a) < 30 or len(signal_b) < 30:
        return None
    
    # Align signals
    common_idx = signal_a.index.intersection(signal_b.index)
    if len(common_idx) < 30:
        return None
    
    a = signal_a.loc[common_idx].dropna()
    b = signal_b.loc[common_idx].dropna()
    
    common_idx2 = a.index.intersection(b.index)
    if len(common_idx2) < 30:
        return None
    
    # Calculate correlation
    correlation = a.loc[common_idx2].corr(b.loc[common_idx2])
    
    if np.isnan(correlation):
        return None
    
    # Check for low correlation
    if abs(correlation) < correlation_threshold:
        severity = ConflictSeverity.MINOR if abs(correlation) > 0.3 else (
            ConflictSeverity.MAJOR if abs(correlation) > 0.1 else ConflictSeverity.CRITICAL
        )
        return SignalConflict(
            signal_a=signal_a_name,
            signal_b=signal_b_name,
            conflict_type=ConflictType.DECOUPLING,
            severity=severity,
            description=f"Niska korelacja między {signal_a_name} i {signal_b_name} (r={correlation:.2f})",
            details={"correlation": round(correlation, 2)}
        )
    
    return None


# ============================================================
# Main Conflict Detection Function
# ============================================================

def detect_signal_conflicts(
    df: pd.DataFrame,
    hr_column: str = 'heartrate',
    power_column: str = 'watts',
    smo2_column: str = 'smo2',
    dfa_column: str = 'alpha1',
    time_column: str = 'time'
) -> ConflictAnalysisResult:
    """
    Perform complete conflict analysis between physiological signals.
    
    Detects conflicts between HR, Power, SmO2, and DFA-a1.
    When signals disagree, this MUST be communicated clearly.
    
    Args:
        df: DataFrame with signal columns
        hr_column: Column name for heart rate
        power_column: Column name for power
        smo2_column: Column name for SmO2
        dfa_column: Column name for DFA Alpha-1
        time_column: Column name for time
    
    Returns:
        ConflictAnalysisResult with conflicts, agreement score, recommendations
    """
    conflicts = []
    signals_analyzed = []
    recommendations = []
    
    # Get available signals
    hr_data = df[hr_column] if hr_column in df.columns else None
    power_data = df[power_column] if power_column in df.columns else None
    smo2_data = df[smo2_column] if smo2_column in df.columns else None
    dfa_data = df[dfa_column] if dfa_column in df.columns else None
    
    if hr_data is not None:
        signals_analyzed.append("HR")
    if power_data is not None:
        signals_analyzed.append("Power")
    if smo2_data is not None:
        signals_analyzed.append("SmO2")
    if dfa_data is not None:
        signals_analyzed.append("DFA-a1")
    
    # Check cardiac drift (HR vs Power)
    if hr_data is not None and power_data is not None:
        drift = detect_cardiac_drift(hr_data, power_data)
        if drift:
            conflicts.append(drift)
            recommendations.append("⚠️ Rozważ czynniki: nawodnienie, temperatura, zmęczenie")
        
        # Check HR-Power decoupling
        decoupling = detect_decoupling(hr_data, power_data, "HR", "Power")
        if decoupling:
            conflicts.append(decoupling)
            recommendations.append("⚠️ HR i Power nie są skorelowane - sprawdź jakość danych")
    
    # Check SmO2 vs Power
    if smo2_data is not None and power_data is not None:
        smo2_conflict = detect_smo2_power_conflict(smo2_data, power_data)
        if smo2_conflict:
            conflicts.append(smo2_conflict)
            recommendations.append("⚠️ SmO2 zachowuje się nietypowo - sprawdź pozycje sensora")
    
    # Check DFA anomalies
    if dfa_data is not None and power_data is not None:
        dfa_anomaly = detect_dfa_anomaly(dfa_data, power_data)
        if dfa_anomaly:
            conflicts.append(dfa_anomaly)
            recommendations.append("⚠️ DFA-a1 > 1.0 przy wysokiej mocy - możliwe artefakty RR")
    
    # Calculate agreement score
    n_signals = len(signals_analyzed)
    n_possible_pairs = n_signals * (n_signals - 1) // 2 if n_signals > 1 else 1
    
    conflict_weight = sum(
        0.1 if c.severity == ConflictSeverity.MINOR else (
            0.25 if c.severity == ConflictSeverity.MAJOR else 0.4
        )
        for c in conflicts
    )
    
    agreement_score = max(0.0, 1.0 - conflict_weight)
    
    return ConflictAnalysisResult(
        has_conflicts=len(conflicts) > 0,
        conflicts=conflicts,
        agreement_score=round(agreement_score, 2),
        recommendations=recommendations,
        signals_analyzed=signals_analyzed
    )


__all__ = [
    # Enums
    'ConflictSeverity',
    'ConflictType',
    # Dataclasses
    'SignalConflict',
    'ConflictAnalysisResult',
    # Functions
    'detect_cardiac_drift',
    'detect_smo2_power_conflict',
    'detect_dfa_anomaly',
    'detect_decoupling',
    'detect_signal_conflicts',
]
