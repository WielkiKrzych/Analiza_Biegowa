"""
Common types and dataclasses for threshold detection.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

@dataclass
class TransitionZone:
    """Represents a transition zone (intensity range) instead of a single point.
    
    Thresholds are not single values - they represent a physiological
    transition that occurs over a range of intensities.
    """
    range_watts: Tuple[float, float]                    # (min, max) power range
    range_hr: Optional[Tuple[float, float]] = None      # (min, max) HR range
    midpoint_ve: Optional[float] = None                 # Midpoint VE (L/min)
    range_ve: Optional[List[float]] = None              # (min, max) VE range
    confidence: float = 0.0                             # 0.0-1.0 detection confidence
    stability_score: float = 0.0                        # 0.0-1.0 temporal stability
    method: str = ""                                    # Detection method used
    description: str = ""                               # Human-readable description
    detection_sources: List[str] = field(default_factory=list)  # ["VE", "SmO2", "HR"]
    variability_watts: float = 0.0                      # Std dev of detections
    
    @property
    def midpoint_watts(self) -> float:
        """Get the midpoint of the power range."""
        return (self.range_watts[0] + self.range_watts[1]) / 2
    
    @property
    def range_width_watts(self) -> float:
        """Get the width of the power range."""
        return self.range_watts[1] - self.range_watts[0]
    
    @property
    def midpoint_hr(self) -> Optional[float]:
        """Get the midpoint of the HR range if available."""
        if self.range_hr:
            return (self.range_hr[0] + self.range_hr[1]) / 2
        return None
    
    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        """Check if confidence exceeds threshold."""
        return self.confidence >= threshold
    
    def is_stable(self, threshold: float = 0.7) -> bool:
        """Check if stability score exceeds threshold."""
        return self.stability_score >= threshold

@dataclass
class ThresholdResult:
    """Result of threshold detection (Legacy/Simple)."""
    zone_name: str
    zone_type: str  # info, success, warning, error
    description: str
    slope_value: float
    power_at_threshold: Optional[float] = None
    hr_at_threshold: Optional[float] = None

@dataclass
class HysteresisResult:
    """Result of directional analysis (hysteresis)."""
    vt1_inc_zone: Optional[TransitionZone] = None
    vt1_dec_zone: Optional[TransitionZone] = None
    vt2_inc_zone: Optional[TransitionZone] = None
    vt2_dec_zone: Optional[TransitionZone] = None
    
    vt1_shift_watts: Optional[float] = None
    vt2_shift_watts: Optional[float] = None
    
    warnings: List[str] = field(default_factory=list)

@dataclass
class SensitivityResult:
    """Result of sensitivity/stability analysis."""
    vt1_stability_score: float = 0.0
    vt2_stability_score: float = 0.0
    vt1_variability_watts: float = 0.0
    vt2_variability_watts: float = 0.0
    is_vt1_unreliable: bool = False
    is_vt2_unreliable: bool = False
    details: List[str] = field(default_factory=list)

@dataclass
class StepTestResult:
    """Complete result of step test analysis."""
    vt1_watts: Optional[float] = None
    vt2_watts: Optional[float] = None
    lt1_watts: Optional[float] = None
    lt2_watts: Optional[float] = None
    vt1_zone: Optional[TransitionZone] = None
    vt2_zone: Optional[TransitionZone] = None
    hysteresis: Optional[HysteresisResult] = None
    sensitivity: Optional[SensitivityResult] = None
    vt1_hr: Optional[float] = None
    vt2_hr: Optional[float] = None
    steps_analyzed: int = 0
    analysis_notes: List[str] = field(default_factory=list)
    step_ve_analysis: List[dict] = field(default_factory=list)
    vt1_ve: Optional[float] = None
    vt1_br: Optional[float] = None
    vt2_ve: Optional[float] = None
    vt2_br: Optional[float] = None
    smo2_1_watts: Optional[float] = None
    smo2_2_watts: Optional[float] = None
    smo2_1_hr: Optional[float] = None
    smo2_2_hr: Optional[float] = None
    smo2_1_value: Optional[float] = None
    smo2_2_value: Optional[float] = None
    step_smo2_analysis: List[dict] = field(default_factory=list)
    step_range: Optional['StepTestRange'] = None

@dataclass
class DetectedStep:
    """Represents a detected step in the step test."""
    step_number: int
    start_time: float
    end_time: float
    duration_sec: float
    avg_power: float
    power_diff_from_prev: float = 0.0

@dataclass
class StepTestRange:
    """Detected range of a valid step test."""
    start_time: float
    end_time: float
    steps: List[DetectedStep]
    min_power: float
    max_power: float
    is_valid: bool = True
    notes: List[str] = field(default_factory=list)

@dataclass
class StepVTResult:
    """Result of step-by-step VT detection.
    
    NEW: vt1_zone and vt2_zone provide range-based thresholds with confidence.
    Legacy point fields (vt1_watts, vt2_watts) kept for backward compatibility.
    """
    # NEW: Range-based thresholds (preferred)
    vt1_zone: Optional[TransitionZone] = None
    vt2_zone: Optional[TransitionZone] = None
    
    # Legacy point values (for backward compatibility)
    vt1_watts: Optional[float] = None
    vt1_hr: Optional[float] = None
    vt1_ve: Optional[float] = None
    vt1_br: Optional[float] = None
    vt1_step_number: Optional[int] = None
    vt1_ve_slope: Optional[float] = None
    vt2_watts: Optional[float] = None
    vt2_hr: Optional[float] = None
    vt2_ve: Optional[float] = None
    vt2_br: Optional[float] = None
    vt2_step_number: Optional[int] = None
    vt2_ve_slope: Optional[float] = None
    step_analysis: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    
    # Confidence (derived from zones if available)
    @property
    def vt1_confidence(self) -> float:
        """Get VT1 confidence from zone or default."""
        return self.vt1_zone.confidence if self.vt1_zone else 0.5
    
    @property
    def vt2_confidence(self) -> float:
        """Get VT2 confidence from zone or default."""
        return self.vt2_zone.confidence if self.vt2_zone else 0.5

@dataclass
class StepSmO2Result:
    """Result of step-by-step SmO2 detection.
    
    IMPORTANT LIMITATIONS - SmO₂ is a LOCAL/REGIONAL signal:
    
    1. SmO₂ reflects oxygen saturation in ONE muscle group (e.g., vastus lateralis).
       It does NOT represent whole-body oxygen dynamics like VO₂ or VE.
       
    2. Sensor placement significantly affects readings:
       - Different muscles show different responses
       - Subcutaneous fat thickness affects signal
       - Movement artifacts are common
       
    3. SmO₂ thresholds should SUPPORT ventilatory thresholds (VT1/VT2), 
       NOT replace them. Use SmO₂ as confirmatory evidence only.
       
    4. Inter-individual variability is HIGH:
       - Baseline SmO₂ varies 60-80% between athletes
       - Response patterns differ based on training/fiber type
    
    Set is_supporting_only=True by default - SmO₂ should influence
    interpretation of other thresholds, never be the sole decision maker.
    """
    # NEW: Range-based thresholds (preferred)
    smo2_1_zone: Optional[TransitionZone] = None
    smo2_2_zone: Optional[TransitionZone] = None
    
    # Legacy point values (for backward compatibility)
    smo2_1_watts: Optional[float] = None
    smo2_1_hr: Optional[float] = None
    smo2_1_step_number: Optional[int] = None
    smo2_1_slope: Optional[float] = None
    smo2_2_watts: Optional[float] = None
    smo2_2_hr: Optional[float] = None
    smo2_2_step_number: Optional[int] = None
    smo2_2_slope: Optional[float] = None
    smo2_1_value: Optional[float] = None
    smo2_2_value: Optional[float] = None
    step_analysis: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    
    # LOCAL SIGNAL FLAGS - SmO2 is regional, not systemic
    signal_type: str = "LOCAL"  # LOCAL = muscle-specific, not whole-body
    is_supporting_only: bool = True  # Should NOT generate standalone decisions
    
    # Documented limitations for UI display
    limitations: List[str] = field(default_factory=lambda: [
        "SmO₂ odzwierciedla utlenowanie JEDNEGO mięśnia, nie całego ciała",
        "Pozycja sensora znacząco wpływa na odczyty",
        "Użyj SmO₂ do potwierdzenia VT1/VT2 z wentylacji, nie jako samodzielny próg",
        "Zmienność międzyosobnicza jest wysoka (baseline 60-80%)"
    ])
    
    def get_confidence_modifier(self) -> float:
        """Return confidence modifier for combined threshold detection.
        
        SmO₂ should only slightly boost confidence when it agrees with VT,
        not be used alone for threshold detection.
        """
        # SmO₂ alone = low confidence boost
        # Agreement with VT = moderate boost
        if self.smo2_1_watts is not None and self.smo2_2_watts is not None:
            return 0.15  # Both thresholds detected - moderate support
        elif self.smo2_1_watts is not None or self.smo2_2_watts is not None:
            return 0.10  # One threshold - weak support
        return 0.0  # No detection
    
    def get_interpretation_note(self) -> str:
        """Get interpretation guidance for UI."""
        if self.is_supporting_only:
            return "⚠️ SmO₂ to sygnał LOKALNY - używaj do potwierdzenia VT, nie jako samodzielny próg"
        return ""


# ============================================================
# Helper Functions for Confidence and Stability
# ============================================================

def calculate_detection_confidence(
    detections: List[float],
    agreement_threshold: float = 20.0
) -> Tuple[float, Tuple[float, float], float]:
    """
    Calculate confidence based on agreement between multiple detection methods.
    
    Confidence is higher when different methods agree on similar values.
    
    Args:
        detections: List of threshold values from different methods (e.g., VE, SmO2)
        agreement_threshold: Maximum W difference for perfect agreement (default: 20W)
    
    Returns:
        Tuple of (confidence 0-1, range_watts, variability)
    """
    if not detections or len(detections) == 0:
        return 0.0, (0.0, 0.0), 0.0
    
    valid_detections = [d for d in detections if d is not None and d > 0]
    
    if len(valid_detections) == 0:
        return 0.0, (0.0, 0.0), 0.0
    
    if len(valid_detections) == 1:
        # Single detection - moderate confidence
        val = valid_detections[0]
        return 0.5, (val - 10, val + 10), 0.0
    
    # Calculate range and variability
    min_val = min(valid_detections)
    max_val = max(valid_detections)
    range_width = max_val - min_val
    
    import numpy as np
    variability = float(np.std(valid_detections))
    
    # Calculate confidence based on agreement
    # Perfect agreement (range_width = 0) -> confidence = 1.0
    # Poor agreement (range_width > agreement_threshold) -> confidence decreases
    if range_width <= agreement_threshold:
        confidence = 1.0 - (range_width / agreement_threshold) * 0.4  # 1.0 to 0.6
    else:
        # Larger disagreement reduces confidence more
        excess = range_width - agreement_threshold
        confidence = max(0.2, 0.6 - excess / 100)
    
    # Boost confidence for more detection sources
    source_bonus = min(0.1, (len(valid_detections) - 1) * 0.05)
    confidence = min(1.0, confidence + source_bonus)
    
    return round(confidence, 2), (min_val, max_val), round(variability, 1)


def calculate_temporal_stability(
    threshold_history: List[float],
    max_cv_for_stable: float = 0.05
) -> Tuple[float, float]:
    """
    Calculate stability score based on historical threshold values.
    
    Uses coefficient of variation (CV) - lower CV means higher stability.
    
    Args:
        threshold_history: List of historical threshold values
        max_cv_for_stable: CV threshold for "stable" classification (default: 5%)
    
    Returns:
        Tuple of (stability_score 0-1, variability_watts)
    """
    if not threshold_history or len(threshold_history) < 2:
        return 0.0, 0.0
    
    valid_history = [v for v in threshold_history if v is not None and v > 0]
    
    if len(valid_history) < 2:
        return 0.0, 0.0
    
    import numpy as np
    mean_val = np.mean(valid_history)
    std_val = np.std(valid_history)
    
    if mean_val == 0:
        return 0.0, 0.0
    
    cv = std_val / mean_val
    
    # Convert CV to stability score
    # CV = 0 -> stability = 1.0
    # CV >= max_cv_for_stable -> stability decreases linearly
    if cv <= max_cv_for_stable:
        stability = 1.0 - (cv / max_cv_for_stable) * 0.3  # 1.0 to 0.7
    else:
        # Higher CV = lower stability
        stability = max(0.0, 0.7 - (cv - max_cv_for_stable) * 5)
    
    return round(stability, 2), round(float(std_val), 1)


def create_transition_zone(
    detections: List[float],
    detection_sources: List[str],
    hr_detections: Optional[List[float]] = None,
    historical_values: Optional[List[float]] = None,
    method: str = "multi-source",
    agreement_threshold: float = 20.0
) -> TransitionZone:
    """
    Create a TransitionZone from multiple detection sources.
    
    Args:
        detections: List of power threshold values from different methods
        detection_sources: Names of detection sources (e.g., ["VE", "SmO2"])
        hr_detections: Optional list of HR values at thresholds
        historical_values: Optional historical threshold values for stability
        method: Description of detection method
        agreement_threshold: Max W difference for agreement
    
    Returns:
        TransitionZone with confidence, stability, and range
    """
    # Calculate confidence and range
    confidence, range_watts, variability = calculate_detection_confidence(
        detections, agreement_threshold
    )
    
    # Calculate stability if historical data available
    stability_score = 0.0
    if historical_values and len(historical_values) >= 2:
        stability_score, _ = calculate_temporal_stability(historical_values)
    
    # Calculate HR range if available
    range_hr = None
    if hr_detections:
        valid_hr = [h for h in hr_detections if h is not None and h > 0]
        if valid_hr:
            range_hr = (min(valid_hr), max(valid_hr))
    
    # Create description
    sources_str = ", ".join(detection_sources) if detection_sources else "unknown"
    desc = f"Detected via {sources_str}"
    if confidence >= 0.8:
        desc += " (high confidence)"
    elif confidence >= 0.5:
        desc += " (moderate confidence)"
    else:
        desc += " (low confidence)"
    
    return TransitionZone(
        range_watts=range_watts,
        range_hr=range_hr,
        confidence=confidence,
        stability_score=stability_score,
        method=method,
        description=desc,
        detection_sources=detection_sources,
        variability_watts=variability
    )

