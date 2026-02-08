"""
Ramp Test Result Objects.

Designed according to methodology/ramp_test/*.md documents.
Each object represents a physiological concept with quality awareness.

NO LOGIC IMPLEMENTED — structure only.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime


# ============================================================
# ENUMS
# ============================================================

class ValidityLevel(str, Enum):
    """Test validity classification per methodology/04_test_validity.md."""
    INVALID = "invalid"       # 🔴 Test odrzucony
    CONDITIONAL = "conditional"  # 🟡 Ważny z zastrzeżeniami  
    VALID = "valid"           # 🟢 W pełni wiarygodny


class ConfidenceLevel(str, Enum):
    """Confidence level for threshold detection."""
    HIGH = "high"       # ≥ 0.8 — "znajduje się w"
    MEDIUM = "medium"   # 0.5–0.8 — "prawdopodobnie w okolicach"
    LOW = "low"         # < 0.5 — "może znajdować się"


class ConflictType(str, Enum):
    """Types of signal conflicts per methodology/06_signal_conflicts.md."""
    CARDIAC_DRIFT = "cardiac_drift"       # HR rośnie przy stałej Power
    HR_PLATEAU = "hr_plateau"             # HR przestaje rosnąć
    HR_LAG = "hr_lag"                     # HR opóźnione vs Power
    SMO2_FLAT = "smo2_flat"               # SmO₂ nie spada
    SMO2_EARLY = "smo2_early"             # SmO₂ spadek przed VT
    SMO2_LATE = "smo2_late"               # SmO₂ spadek po VT
    DFA_ANOMALY = "dfa_anomaly"           # DFA α1 > 1.0 przy wysokim HR
    DFA_STABLE = "dfa_stable"             # DFA nie spada
    DFA_FAST_DROP = "dfa_fast_drop"       # DFA szybki spadek


class ConflictSeverity(str, Enum):
    """Severity of detected conflict."""
    INFO = "info"           # Informacyjne
    WARNING = "warning"     # Obniża pewność
    CRITICAL = "critical"   # Podważa wynik


# ============================================================
# SIGNAL QUALITY
# ============================================================

@dataclass
class SignalQuality:
    """
    Quality assessment for a single signal.
    
    Physiological meaning:
    - Represents how reliable this signal's data is for threshold detection
    - Captures artifacts, gaps, and noise level
    
    Report connection:
    - Used in "Ważność testu" section
    - Affects confidence score of detected thresholds
    - Cited in warnings if quality is poor
    """
    signal_name: str                    # e.g. "HR", "SmO2", "Power"
    
    # Quality metrics (0.0 – 1.0)
    quality_score: float = 1.0          # Overall quality (1.0 = perfect)
    artifact_ratio: float = 0.0         # % of samples that are artifacts
    gap_ratio: float = 0.0              # % of recording with gaps > 5s
    noise_level: float = 0.0            # Normalized noise (std/mean)
    
    # Counts
    total_samples: int = 0
    valid_samples: int = 0
    gaps_detected: int = 0              # Number of gaps > 5s
    
    # Flags
    is_usable: bool = True              # Can be used for threshold detection
    reasons_unusable: List[str] = field(default_factory=list)
    
    def get_grade(self) -> str:
        """Return A/B/C/D/F grade based on quality_score."""
        if self.quality_score >= 0.95:
            return "A"
        elif self.quality_score >= 0.85:
            return "B"
        elif self.quality_score >= 0.70:
            return "C"
        elif self.quality_score >= 0.50:
            return "D"
        return "F"
    
    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export."""
        return {
            "signal_name": self.signal_name,
            "quality_score": self.quality_score,
            "artifact_ratio": self.artifact_ratio,
            "gap_ratio": self.gap_ratio,
            "total_samples": self.total_samples,
            "valid_samples": self.valid_samples,
            "is_usable": self.is_usable,
            "grade": self.get_grade()
        }


# ============================================================
# THRESHOLD RANGE
# ============================================================

@dataclass
class ThresholdRange:
    """
    A threshold expressed as a range with confidence.
    
    Per methodology/05_threshold_as_range.md:
    - Threshold is NOT a point, it's a transition zone
    - Must have lower/upper bounds
    - Must have confidence score
    - Must cite detection sources
    
    Physiological meaning:
    - lower_watts: First power where any signal shows change
    - upper_watts: Power where change is confirmed in all signals
    - midpoint: Best estimate (center or max agreement point)
    
    Report connection:
    - Displayed as "VT1: 180–195 W (środek: ~188 W)"
    - Confidence affects language: "znajduje się" vs "może znajdować się"
    """
    # Range definition (REQUIRED)
    lower_watts: float                  # Lower bound of transition zone
    upper_watts: float                  # Upper bound of transition zone
    
    # Central value (best estimate)
    midpoint_watts: float               # Center or max agreement point
    
    # Confidence (0.0 – 1.0)
    confidence: float = 0.5             # Detection confidence
    
    # HR equivalent (optional)
    lower_hr: Optional[float] = None
    upper_hr: Optional[float] = None
    midpoint_hr: Optional[float] = None
    
    # VE equivalent (optional)
    midpoint_ve: Optional[float] = None
    range_ve: Optional[List[float]] = None
    
    # Detection metadata
    sources: List[str] = field(default_factory=list)  # ["VE", "HR", "SmO2"]
    method: str = ""                    # Detection method used
    
    # Stability (optional)
    stability_score: Optional[float] = None  # From sensitivity analysis
    variability_watts: Optional[float] = None  # Std dev across methods
    
    @property
    def width_watts(self) -> float:
        """Width of the transition zone in watts."""
        return self.upper_watts - self.lower_watts
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Convert confidence score to level."""
        if self.confidence >= 0.8:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.5:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
    
    def format_for_report(self) -> str:
        """Format threshold for report display."""
        level = self.confidence_level.value
        if level == "high":
            prefix = ""
        elif level == "medium":
            prefix = "prawdopodobnie "
        else:
            prefix = "może "
        
        return f"{prefix}{self.lower_watts:.0f}–{self.upper_watts:.0f} W (środek: ~{self.midpoint_watts:.0f} W)"
    
    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export per canonical spec."""
        return {
            "range_watts": [self.lower_watts, self.upper_watts],
            "midpoint_watts": self.midpoint_watts,
            "range_hr": [self.lower_hr, self.upper_hr] if self.lower_hr and self.upper_hr else None,
            "midpoint_hr": self.midpoint_hr,
            "midpoint_ve": self.midpoint_ve,
            "range_ve": self.range_ve,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "sources": self.sources,
            "method": self.method,
            "stability_score": self.stability_score,
            "variability_watts": self.variability_watts
        }


# ============================================================
# CONFLICT REPORT
# ============================================================

@dataclass
class SignalConflict:
    """
    A detected conflict between two signals.
    
    Per methodology/06_signal_conflicts.md:
    - Conflicts are INFORMATIVE, not errors
    - Each conflict has physiological interpretation
    - Affects confidence score
    
    Physiological meaning:
    - Signals disagree about threshold location or response pattern
    - May indicate measurement issue OR genuine physiological phenomenon
    
    Report connection:
    - Listed in "Konflikty i zastrzeżenia" section
    - Each conflict includes interpretation
    """
    conflict_type: ConflictType
    severity: ConflictSeverity
    
    signal_a: str                       # e.g. "HR"
    signal_b: str                       # e.g. "Power"
    
    description: str                    # Human-readable description
    physiological_interpretation: str   # Why this might happen
    
    # Quantification (optional)
    magnitude: Optional[float] = None   # e.g. drift in bpm, difference in W
    
    # Impact
    confidence_penalty: float = 0.0     # How much to reduce confidence (0–0.3)
    
    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export."""
        return {
            "type": self.conflict_type.value,
            "severity": self.severity.value,
            "signal_a": self.signal_a,
            "signal_b": self.signal_b,
            "description": self.description,
            "physiological_interpretation": self.physiological_interpretation,
            "magnitude_watts": self.magnitude,
            "confidence_penalty": self.confidence_penalty
        }


@dataclass
class ConflictReport:
    """
    Aggregated report of all detected conflicts.
    
    Per methodology/06_signal_conflicts.md:
    - Conflicts lower overall confidence
    - Should be transparently reported
    
    Report connection:
    - Feeds into "Konflikty i zastrzeżenia" section
    - Affects final confidence of VT1/VT2
    """
    conflicts: List[SignalConflict] = field(default_factory=list)
    
    # Aggregated metrics
    agreement_score: float = 1.0        # 1.0 = no conflicts, 0.0 = major disagreement
    
    # Signals analyzed
    signals_analyzed: List[str] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    @property
    def has_conflicts(self) -> bool:
        """Check if any conflicts were detected."""
        return len(self.conflicts) > 0
    
    @property
    def critical_conflicts(self) -> List[SignalConflict]:
        """Return only critical conflicts."""
        return [c for c in self.conflicts if c.severity == ConflictSeverity.CRITICAL]
    
    def total_confidence_penalty(self) -> float:
        """Sum of all confidence penalties."""
        return sum(c.confidence_penalty for c in self.conflicts)
    
    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export per canonical spec."""
        return {
            "agreement_score": self.agreement_score,
            "signals_analyzed": self.signals_analyzed,
            "detected": [c.to_dict() for c in self.conflicts],
            "recommendations": self.recommendations
        }


# ============================================================
# TEST VALIDITY
# ============================================================

@dataclass
class TestValidity:
    """
    Assessment of overall test validity.
    
    Per methodology/04_test_validity.md:
    - INVALID: Test rejected, must repeat
    - CONDITIONAL: Valid with caveats
    - VALID: Fully reliable
    
    Physiological meaning:
    - Captures whether the test protocol was executed correctly
    - Checks data quality across all signals
    - Validates subject behavior (exhaustion, breaks)
    
    Report connection:
    - Displayed prominently at top of report
    - If INVALID: "Test metodologicznie nieważny"
    - If CONDITIONAL: "Test ważny z zastrzeżeniami"
    """
    validity: ValidityLevel = ValidityLevel.VALID
    
    # Test duration
    ramp_duration_sec: int = 0
    ramp_duration_sufficient: bool = True  # ≥ 8 min for VALID
    
    # Power range
    power_range_watts: float = 0.0      # max - min
    power_range_sufficient: bool = True  # ≥ 150 W for VALID
    
    # Exhaustion
    exhaustion_reached: bool = True     # RPE 10/10 or HR plateau
    rpe_final: Optional[float] = None
    
    # Data quality per signal
    signal_qualities: Dict[str, SignalQuality] = field(default_factory=dict)
    
    # Issues detected
    issues: List[str] = field(default_factory=list)
    
    # Breaks/stops
    breaks_count: int = 0
    longest_break_sec: float = 0.0
    
    # Warmup
    warmup_duration_sec: int = 0
    warmup_adequate: bool = True        # ≥ 5 min for VALID
    
    def get_report_header(self) -> str:
        """Generate report header for validity section."""
        if self.validity == ValidityLevel.VALID:
            return "✅ **Test metodologicznie wiarygodny**"
        elif self.validity == ValidityLevel.CONDITIONAL:
            return "⚠️ **Test ważny z zastrzeżeniami**"
        else:
            return "⛔ **Test metodologicznie nieważny**"
    
    def get_issues_summary(self) -> str:
        """Format issues for report."""
        if not self.issues:
            return "Wszystkie kryteria jakości spełnione."
        return "\n".join(f"- {issue}" for issue in self.issues)
    
    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export per canonical spec."""
        return {
            "status": self.validity.value,
            "issues": self.issues,
            "metrics": {
                "ramp_duration_sec": self.ramp_duration_sec,
                "power_range_watts": self.power_range_watts,
                "exhaustion_reached": self.exhaustion_reached,
                "rpe_final": self.rpe_final
            },
            "signal_quality": {
                name: sq.to_dict() for name, sq in self.signal_qualities.items()
            }
        }


# ============================================================
# AGGREGATED RAMP TEST RESULT
# ============================================================

@dataclass
class RampTestResult:
    """
    Complete result of Ramp Test analysis.
    
    Aggregates all detection results with quality awareness.
    This is the main output object passed to report generation.
    
    Per methodology/08_algorithm_map.md:
    - Output of ResultAggregator
    - Input to ReportGenerator
    """
    # Test validity (REQUIRED)
    validity: TestValidity = field(default_factory=TestValidity)
    
    # Thresholds as ranges
    vt1: Optional[ThresholdRange] = None
    vt2: Optional[ThresholdRange] = None
    
    # SmO2 context (local signal, supporting only)
    smo2_lt1: Optional[ThresholdRange] = None
    smo2_lt2: Optional[ThresholdRange] = None
    smo2_deviation_from_vt: Optional[float] = None  # Difference in W
    smo2_interpretation: str = ""
    
    # DFA context
    dfa_vt1_crossing: Optional[float] = None  # W at α1 ≈ 0.75
    dfa_vt2_crossing: Optional[float] = None  # W at α1 ≈ 0.50
    dfa_is_uncertain: bool = False
    
    # Conflicts
    conflicts: ConflictReport = field(default_factory=ConflictReport)
    
    # Overall confidence
    overall_confidence: float = 0.5
    
    # Notes and warnings
    analysis_notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Metadata
    protocol: str = ""
    test_date: str = ""
    
    # External Metrics (CP / Manual)
    cp_watts: Optional[float] = None
    w_prime_joules: Optional[float] = None
    smo2_manual_lt1: Optional[float] = None
    smo2_manual_lt2: Optional[float] = None
    smo2_manual_lt1_hr: Optional[float] = None
    smo2_manual_lt2_hr: Optional[float] = None
    
    # Power Duration Curve (MMP)
    mmp_curve: Optional[Dict[int, float]] = None
    
    # User Parameters
    rider_weight: Optional[float] = None
    max_hr: Optional[float] = None
    
    # Transient / Debug data (not for JSON)
    detailed_step_analysis: Optional[Dict] = field(default=None, repr=False)
    
    def can_generate_zones(self) -> bool:
        """Check if training zones can be calculated."""
        return (
            self.validity.validity != ValidityLevel.INVALID and
            self.vt1 is not None and
            self.vt2 is not None and
            self.overall_confidence >= 0.3
        )
    
    def get_confidence_language(self) -> str:
        """Get appropriate language qualifier for recommendations."""
        if self.overall_confidence >= 0.8:
            return "Sugeruję"
        elif self.overall_confidence >= 0.5:
            return "Rozważ"
        else:
            return "Dane niepewne — unikam jednoznacznych zaleceń"
    
    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export per canonical spec."""
        # Confidence level
        if self.overall_confidence >= 0.8:
            conf_level = "high"
        elif self.overall_confidence >= 0.5:
            conf_level = "medium"
        else:
            conf_level = "low"
        
        return {
            "test_validity": self.validity.to_dict(),
            "thresholds": {
                "vt1": self.vt1.to_dict() if self.vt1 else None,
                "vt2": self.vt2.to_dict() if self.vt2 else None
            },
            "smo2_context": {
                "signal_type": "LOCAL",
                "is_threshold_source": False,
                "drop_point": self.smo2_lt1.to_dict() if self.smo2_lt1 else None,
                "deviation_from_vt1_watts": self.smo2_deviation_from_vt,
                "interpretation": self.smo2_interpretation
            } if self.smo2_lt1 or self.smo2_interpretation else None,
            "cp_model": {
                "cp_watts": self.cp_watts,
                "w_prime_joules": self.w_prime_joules
            },
            "smo2_manual": {
                "lt1_watts": self.smo2_manual_lt1,
                "lt2_watts": self.smo2_manual_lt2,
                "lt1_hr": self.smo2_manual_lt1_hr,
                "lt2_hr": self.smo2_manual_lt2_hr
            },
            "power_duration_curve": {
                "durations_sec": list(self.mmp_curve.keys()) if self.mmp_curve else [],
                "powers_watts": list(self.mmp_curve.values()) if self.mmp_curve else []
            },
            "conflicts": self.conflicts.to_dict(),
            "interpretation": {
                "overall_confidence": self.overall_confidence,
                "confidence_level": conf_level,
                "can_generate_zones": self.can_generate_zones(),
                "warnings": self.warnings,
                "notes": self.analysis_notes
            },
            "metadata": {
                "test_date": self.test_date,
                "protocol": self.protocol,
                "processing_date": datetime.now().isoformat(),
                "method_version": "2.0 (Deepmind)",
                "rider_weight": self.rider_weight,
                "max_hr": self.max_hr
            }
        }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'ValidityLevel',
    'ConfidenceLevel',
    'ConflictType',
    'ConflictSeverity',
    # Dataclasses
    'SignalQuality',
    'ThresholdRange',
    'SignalConflict',
    'ConflictReport',
    'TestValidity',
    'RampTestResult',
]
