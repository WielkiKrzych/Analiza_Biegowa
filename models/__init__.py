"""
Models Module - Data Models and Complex Computations

This module contains data models, dataclasses, and complex ML models.
NO STREAMLIT OR UI DEPENDENCIES ALLOWED.

Sub-modules:
- session: Session data model
- pdc: Power Duration Curve model
- training: Training load models
- results: Calculation result objects
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd

# Re-export data classes from modules.calculations
from modules.calculations.threshold_types import (
    TransitionZone,
    ThresholdResult,
    StepTestResult,
    HysteresisResult,
    SensitivityResult,
)


# ============================================================
# Calculation Result Dataclasses
# ============================================================

@dataclass
class NormalizedPowerResult:
    """Result of Normalized Power calculation."""
    value: float
    rolling_window_sec: int
    samples_count: int
    data_quality: float  # 0.0-1.0 based on missing/outlier data
    
    def __float__(self) -> float:
        """Allow using result as float for backward compatibility."""
        return self.value


@dataclass
class PulsePowerResult:
    """Result of Pulse Power (cardiac efficiency) calculation."""
    avg_pulse_power: float
    trend_drop_pct: float
    df_filtered: pd.DataFrame
    # Parameters used
    min_watts: float
    min_hr: float
    min_samples_trend: int
    # Quality metrics
    samples_count: int
    data_quality: float


@dataclass
class DFAResult:
    """Result of DFA Alpha-1 (HRV) calculation.
    
    ⚠️ DFA-a1 is HIGHLY SENSITIVE to artifacts in RR data.
    
    Uncertainty conditions:
    1. Window < min_window_sec (default 120s) → uncertain
    2. Data quality < 0.9 (>10% artifacts) → uncertain
    3. Alpha1 outside [0.5, 1.5] at moderate intensity → uncertain
    """
    df_results: Optional[pd.DataFrame]
    mean_alpha1: Optional[float]
    alpha1_range: Tuple[float, float]  # (min, max)
    # Parameters used
    window_sec: int
    step_sec: int
    min_samples_hrv: int
    # Quality metrics
    samples_count: int
    windows_analyzed: int
    data_quality: float
    error: Optional[str] = None
    
    # NEW: Uncertainty and quality
    is_uncertain: bool = False
    uncertainty_reasons: List[str] = field(default_factory=list)
    quality_grade: str = "A"  # A=excellent, B=good, C=acceptable, D=poor, F=unusable
    
    # NEW: Minimum window validation
    min_window_sec: int = 120  # 2 min minimum for reliable DFA
    window_meets_minimum: bool = True
    
    # NEW: Artifact sensitivity warning
    artifact_sensitivity_note: str = field(default_factory=lambda: 
        "⚠️ DFA-a1 jest BARDZO wrażliwy na artefakty. "
        "Nawet 1-2% błędnych wartości RR może znacząco wpłynąć na wynik."
    )
    
    def get_interpretation(self) -> str:
        """Get interpretation of the result."""
        if self.is_uncertain:
            reasons = "; ".join(self.uncertainty_reasons)
            return f"❓ NIEPEWNY: {reasons}"
        if self.quality_grade in ["A", "B"]:
            return "✅ Wynik wiarygodny"
        elif self.quality_grade == "C":
            return "⚠️ Wynik akceptowalny, ale z ograniczeniami"
        else:
            return "❌ Wynik niewiarygodny"


@dataclass
class RecoveryScoreResult:
    """Result of W' recovery score calculation."""
    score: float
    w_pct: float  # W' percentage
    time_bonus: float
    # Parameters used
    tau_seconds: float
    time_bonus_max: float
    # Interpretation
    recommendation: Tuple[str, str]  # (emoji+label, description)


@dataclass
class SessionRecord:
    """Session data record for storage."""
    filename: str
    timestamp: str
    duration_sec: int
    avg_power: float
    np_power: float
    tss: float
    intensity_factor: float
    avg_hr: Optional[float] = None
    avg_smo2: Optional[float] = None
    extra_metrics: Optional[Dict[str, Any]] = None


@dataclass  
class AthleteProfile:
    """Athlete profile with physiological parameters."""
    weight_kg: float
    ftp: float
    max_hr: int
    lthr: Optional[int] = None
    vo2max: Optional[float] = None
    w_prime: Optional[float] = None


__all__ = [
    # Threshold models
    'TransitionZone',
    'ThresholdResult',
    'StepTestResult',
    'HysteresisResult',
    'SensitivityResult',
    # Result models
    'NormalizedPowerResult',
    'PulsePowerResult',
    'DFAResult',
    'RecoveryScoreResult',
    # Session models
    'SessionRecord',
    'AthleteProfile',
]

