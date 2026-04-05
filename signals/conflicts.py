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
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class ConflictSeverity(str, Enum):
    """Severity levels for signal conflicts."""

    MINOR = "minor"  # Small disagreement, may be noise
    MAJOR = "major"  # Significant disagreement, affects interpretation
    CRITICAL = "critical"  # Signals fundamentally disagree


class ConflictType(str, Enum):
    """Types of signal conflicts."""

    CARDIAC_DRIFT = "cardiac_drift"  # HR/Power ratio increases
    PHASE_MISMATCH = "phase_mismatch"  # Timing lag between signals
    DIRECTION_CONFLICT = "direction_conflict"  # Signals moving opposite ways
    DFA_ANOMALY = "dfa_anomaly"  # DFA-a1 unexpected values
    DECOUPLING = "decoupling"  # Loss of correlation
    RANGE_MISMATCH = "range_mismatch"  # Different intensity ranges


@dataclass
class SignalConflict:
    """A single conflict between two signals."""

    signal_a: str  # e.g., "HR"
    signal_b: str  # e.g., "Power"
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
    agreement_score: float = 1.0  # 0-1, higher = more agreement
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
    hr_data: pd.Series, power_data: pd.Series, threshold_pct: float = 0.05
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
        severity = (
            ConflictSeverity.MINOR
            if drift_pct < 0.1
            else (ConflictSeverity.MAJOR if drift_pct < 0.15 else ConflictSeverity.CRITICAL)
        )
        return SignalConflict(
            signal_a="HR",
            signal_b="Power",
            conflict_type=ConflictType.CARDIAC_DRIFT,
            severity=severity,
            description=f"Dryft tętna: +{drift_pct:.1%} (HR rośnie przy stałej mocy)",
            details={"drift_pct": round(drift_pct * 100, 1)},
        )

    return None


def detect_smo2_power_conflict(
    smo2_data: pd.Series, power_data: pd.Series, window: int = 60
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
        severity = (
            ConflictSeverity.MINOR
            if conflict_ratio < 0.2
            else (ConflictSeverity.MAJOR if conflict_ratio < 0.3 else ConflictSeverity.CRITICAL)
        )
        return SignalConflict(
            signal_a="SmO2",
            signal_b="Power",
            conflict_type=ConflictType.DIRECTION_CONFLICT,
            severity=severity,
            description=f"SmO2 rośnie przy rosnącej mocy ({conflict_ratio:.0%} czasu)",
            affected_zones=["VT1", "VT2"],
            details={"conflict_ratio": round(conflict_ratio * 100, 1)},
        )

    return None


def detect_dfa_anomaly(
    dfa_data: pd.Series,
    power_data: pd.Series,
    high_power_threshold: float = 0.7,  # % of max power
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
            details={"anomaly_ratio": round(anomaly_ratio * 100, 1)},
        )

    return None


def detect_decoupling(
    signal_a: pd.Series,
    signal_b: pd.Series,
    signal_a_name: str,
    signal_b_name: str,
    correlation_threshold: float = 0.5,
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
        severity = (
            ConflictSeverity.MINOR
            if abs(correlation) > 0.3
            else (ConflictSeverity.MAJOR if abs(correlation) > 0.1 else ConflictSeverity.CRITICAL)
        )
        return SignalConflict(
            signal_a=signal_a_name,
            signal_b=signal_b_name,
            conflict_type=ConflictType.DECOUPLING,
            severity=severity,
            description=f"Niska korelacja między {signal_a_name} i {signal_b_name} (r={correlation:.2f})",
            details={"correlation": round(correlation, 2)},
        )

    return None


# ============================================================
# Main Conflict Detection Function
# ============================================================


def _extract_signal(df: pd.DataFrame, column: str) -> Optional[pd.Series]:
    """Extract a signal column from DataFrame if it exists."""
    return df[column] if column in df.columns else None


def _collect_signal_names(
    hr_data: Optional[pd.Series],
    power_data: Optional[pd.Series],
    smo2_data: Optional[pd.Series],
    dfa_data: Optional[pd.Series],
) -> List[str]:
    """Build list of available signal names."""
    names: List[str] = []
    if hr_data is not None:
        names.append("HR")
    if power_data is not None:
        names.append("Power")
    if smo2_data is not None:
        names.append("SmO2")
    if dfa_data is not None:
        names.append("DFA-a1")
    return names


def _check_hr_power_conflicts(
    hr_data: Optional[pd.Series],
    power_data: Optional[pd.Series],
) -> Tuple[List[SignalConflict], List[str]]:
    """Detect cardiac drift and HR-Power decoupling conflicts."""
    if hr_data is None or power_data is None:
        return [], []

    conflicts: List[SignalConflict] = []
    recommendations: List[str] = []

    drift = detect_cardiac_drift(hr_data, power_data)
    if drift:
        conflicts.append(drift)
        recommendations.append("⚠️ Rozważ czynniki: nawodnienie, temperatura, zmęczenie")

    decoupling = detect_decoupling(hr_data, power_data, "HR", "Power")
    if decoupling:
        conflicts.append(decoupling)
        recommendations.append("⚠️ HR i Power nie są skorelowane - sprawdź jakość danych")

    return conflicts, recommendations


def _check_signal_pair(
    signal_data: Optional[pd.Series],
    power_data: Optional[pd.Series],
    detect_fn: Callable[[pd.Series, pd.Series], Optional[SignalConflict]],
    warning_msg: str,
) -> Tuple[List[SignalConflict], List[str]]:
    """Run a pairwise signal-vs-power conflict check."""
    if signal_data is None or power_data is None:
        return [], []

    conflict = detect_fn(signal_data, power_data)
    if conflict:
        return [conflict], [warning_msg]
    return [], []


def _calculate_agreement_score(conflicts: List[SignalConflict]) -> float:
    """Calculate agreement score from conflict severities."""
    conflict_weight = sum(
        0.1
        if c.severity == ConflictSeverity.MINOR
        else (0.25 if c.severity == ConflictSeverity.MAJOR else 0.4)
        for c in conflicts
    )
    return round(max(0.0, 1.0 - conflict_weight), 2)


def detect_signal_conflicts(
    df: pd.DataFrame,
    hr_column: str = "heartrate",
    power_column: str = "watts",
    smo2_column: str = "smo2",
    dfa_column: str = "alpha1",
    time_column: str = "time",
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
    conflicts: List[SignalConflict] = []
    recommendations: List[str] = []

    hr_data = _extract_signal(df, hr_column)
    power_data = _extract_signal(df, power_column)
    smo2_data = _extract_signal(df, smo2_column)
    dfa_data = _extract_signal(df, dfa_column)

    signals_analyzed = _collect_signal_names(hr_data, power_data, smo2_data, dfa_data)

    # HR vs Power pair (cardiac drift + decoupling)
    pair_conflicts, pair_recs = _check_hr_power_conflicts(hr_data, power_data)
    conflicts.extend(pair_conflicts)
    recommendations.extend(pair_recs)

    # SmO2 vs Power
    smo2_c, smo2_r = _check_signal_pair(
        smo2_data,
        power_data,
        detect_smo2_power_conflict,
        "⚠️ SmO2 zachowuje się nietypowo - sprawdź pozycje sensora",
    )
    conflicts.extend(smo2_c)
    recommendations.extend(smo2_r)

    # DFA anomalies
    dfa_c, dfa_r = _check_signal_pair(
        dfa_data,
        power_data,
        detect_dfa_anomaly,
        "⚠️ DFA-a1 > 1.0 przy wysokiej mocy - możliwe artefakty RR",
    )
    conflicts.extend(dfa_c)
    recommendations.extend(dfa_r)

    return ConflictAnalysisResult(
        has_conflicts=len(conflicts) > 0,
        conflicts=conflicts,
        agreement_score=_calculate_agreement_score(conflicts),
        recommendations=recommendations,
        signals_analyzed=signals_analyzed,
    )

    agreement_score = max(0.0, 1.0 - conflict_weight)

    return ConflictAnalysisResult(
        has_conflicts=len(conflicts) > 0,
        conflicts=conflicts,
        agreement_score=round(agreement_score, 2),
        recommendations=recommendations,
        signals_analyzed=signals_analyzed,
    )


__all__ = [
    # Enums
    "ConflictSeverity",
    "ConflictType",
    # Dataclasses
    "SignalConflict",
    "ConflictAnalysisResult",
    # Functions
    "detect_cardiac_drift",
    "detect_smo2_power_conflict",
    "detect_dfa_anomaly",
    "detect_decoupling",
    "detect_signal_conflicts",
]
