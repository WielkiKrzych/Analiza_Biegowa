"""
Interpretation & Prescription Engine.

Translates physiological metrics into actionable training advice.
NEW: Interprets result OBJECTS (not raw numbers), cites uncertainty and conflicts,
avoids definitive recommendations when data quality is low.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class InterpretationResult:
    """Quality-aware interpretation result."""
    diagnostics: List[str] = field(default_factory=list)
    prescriptions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    uncertainties: List[str] = field(default_factory=list)  # NEW: Cited uncertainties
    conflicts: List[str] = field(default_factory=list)       # NEW: Cited conflicts
    data_quality_note: str = ""                              # NEW: Overall quality assessment
    is_valid: bool = True
    confidence_level: str = "high"  # high, medium, low
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        if self.confidence_level == "low":
            return "❓ Interpretacja niepewna - dane niskiej jakości"
        elif self.confidence_level == "medium":
            return "⚠️ Interpretacja z zastrzeżeniami"
        return "✅ Interpretacja wiarygodna"


def interpret_results(
    thresholds: Optional[Any] = None,  # StepTestResult
    dfa_result: Optional[Any] = None,  # DFAResult
    smo2_result: Optional[Any] = None,  # StepSmO2Result
    conflicts: Optional[Any] = None,    # ConflictAnalysisResult
    metrics: Optional[Dict[str, Any]] = None  # Legacy fallback
) -> InterpretationResult:
    """
    Generate quality-aware interpretation from result objects.
    
    CRITICAL: This function:
    1. Interprets result OBJECTS, not raw numbers
    2. CITES uncertainty when present
    3. CITES conflicts between signals
    4. AVOIDS definitive recommendations at low data quality
    
    Args:
        thresholds: StepTestResult with VT1/VT2 zones
        dfa_result: DFAResult with HRV analysis
        smo2_result: StepSmO2Result (LOCAL signal)
        conflicts: ConflictAnalysisResult from signal conflicts
        metrics: Legacy dict fallback for backward compatibility
    
    Returns:
        InterpretationResult with quality-aware diagnosis
    """
    result = InterpretationResult()
    overall_quality = 1.0
    quality_issues = []
    
    # =========================================================
    # 1. EXTRACT AND CITE CONFLICTS
    # =========================================================
    if conflicts is not None and hasattr(conflicts, 'has_conflicts'):
        if conflicts.has_conflicts:
            result.conflicts.append("⚠️ Wykryto konflikty między sygnałami:")
            for c in conflicts.conflicts:
                result.conflicts.append(f"  • {c}")
            
            # Lower confidence based on conflicts
            overall_quality *= conflicts.agreement_score
            quality_issues.append(f"Zgoda sygnałów: {conflicts.agreement_score:.0%}")
    
    # =========================================================
    # 2. EXTRACT AND CITE UNCERTAINTIES
    # =========================================================
    
    # Check DFA uncertainty
    if dfa_result is not None:
        if hasattr(dfa_result, 'is_uncertain') and dfa_result.is_uncertain:
            reasons = getattr(dfa_result, 'uncertainty_reasons', [])
            result.uncertainties.append(f"❓ DFA-a1 niepewny: {'; '.join(reasons)}")
            overall_quality *= 0.7
            quality_issues.append("DFA niepewny")
        
        # Cite artifact sensitivity
        if hasattr(dfa_result, 'artifact_sensitivity_note'):
            result.warnings.append(dfa_result.artifact_sensitivity_note)
    
    # Check SmO2 local signal limitation
    if smo2_result is not None:
        if hasattr(smo2_result, 'is_supporting_only') and smo2_result.is_supporting_only:
            result.uncertainties.append("⚠️ SmO₂ = sygnał LOKALNY, używany tylko jako potwierdzenie")
        
        if hasattr(smo2_result, 'get_interpretation_note'):
            note = smo2_result.get_interpretation_note()
            if note:
                result.warnings.append(note)
    
    # Check threshold zone confidence
    if thresholds is not None:
        # VT1 zone
        vt1_zone = getattr(thresholds, 'vt1_zone', None)
        if vt1_zone is not None and hasattr(vt1_zone, 'confidence'):
            if vt1_zone.confidence < 0.7:
                result.uncertainties.append(
                    f"❓ VT1 niska pewność ({vt1_zone.confidence:.0%})"
                )
                overall_quality *= vt1_zone.confidence
        
        # VT2 zone
        vt2_zone = getattr(thresholds, 'vt2_zone', None)
        if vt2_zone is not None and hasattr(vt2_zone, 'confidence'):
            if vt2_zone.confidence < 0.7:
                result.uncertainties.append(
                    f"❓ VT2 niska pewność ({vt2_zone.confidence:.0%})"
                )
                overall_quality *= vt2_zone.confidence
    
    # =========================================================
    # 3. DETERMINE CONFIDENCE LEVEL
    # =========================================================
    if overall_quality < 0.5:
        result.confidence_level = "low"
        result.data_quality_note = (
            "⛔ NISKA JAKOŚĆ DANYCH - unikam jednoznacznych zaleceń. "
            f"Problemy: {', '.join(quality_issues)}"
        )
    elif overall_quality < 0.8:
        result.confidence_level = "medium"
        result.data_quality_note = (
            f"⚠️ Średnia jakość danych. {', '.join(quality_issues)}"
        )
    else:
        result.confidence_level = "high"
        result.data_quality_note = "✅ Dane wysokiej jakości"
    
    # =========================================================
    # 4. GENERATE DIAGNOSTICS (with confidence qualifiers)
    # =========================================================
    vt1_watts = _get_threshold_value(thresholds, 'vt1_watts', metrics)
    vt2_watts = _get_threshold_value(thresholds, 'vt2_watts', metrics)
    
    if vt1_watts and vt2_watts and vt2_watts > 0:
        ratio = vt1_watts / vt2_watts
        
        # Add confidence qualifier
        qualifier = _get_confidence_qualifier(result.confidence_level)
        
        if ratio < 0.65:
            result.diagnostics.append(
                f"{qualifier}Deficyt aerobowy: VT1 jest niski względem VT2 (<65%)."
            )
            if result.confidence_level != "low":
                result.prescriptions.append(
                    "Sugestia: Budowanie bazy - duża objętość Strefy 2 (LSD)."
                )
            else:
                result.prescriptions.append(
                    "⚠️ Zalecenie niepewne z powodu niskiej jakości danych."
                )
        elif ratio > 0.85:
            result.diagnostics.append(
                f"{qualifier}Wysoka baza aerobowa: VT1 blisko VT2 (>85%). Profil 'Diesel'."
            )
            if result.confidence_level != "low":
                result.prescriptions.append(
                    "Sugestia: Trening spolaryzowany - interwały VO2max."
                )
            else:
                result.prescriptions.append(
                    "⚠️ Zalecenie niepewne z powodu niskiej jakości danych."
                )
        else:
            result.diagnostics.append(
                f"{qualifier}Zrównoważony profil aerobowy (VT1 = 65-85% VT2)."
            )
    
    # =========================================================
    # 5. DFA-BASED DIAGNOSTICS (with uncertainty citation)
    # =========================================================
    if dfa_result is not None:
        mean_alpha = getattr(dfa_result, 'mean_alpha1', None)
        if mean_alpha is not None:
            is_uncertain = getattr(dfa_result, 'is_uncertain', False)
            uncertainty_marker = " ❓" if is_uncertain else ""
            
            if mean_alpha > 1.0:
                result.diagnostics.append(
                    f"DFA-a1 = {mean_alpha:.2f}{uncertainty_marker} - strefa aerobowa/regeneracja"
                )
            elif mean_alpha > 0.75:
                result.diagnostics.append(
                    f"DFA-a1 = {mean_alpha:.2f}{uncertainty_marker} - strefa progowa"
                )
            else:
                result.diagnostics.append(
                    f"DFA-a1 = {mean_alpha:.2f}{uncertainty_marker} - strefa VO2max"
                )
    
    if not result.diagnostics:
        result.diagnostics.append("Profil normalny. Brak zidentyfikowanych limitów.")
    
    return result


def _get_threshold_value(
    thresholds: Optional[Any],
    attr_name: str,
    metrics: Optional[Dict]
) -> Optional[float]:
    """Extract threshold value from object or legacy dict."""
    if thresholds is not None:
        # Try zone midpoint first
        zone_attr = attr_name.replace('_watts', '_zone')
        zone = getattr(thresholds, zone_attr, None)
        if zone is not None and hasattr(zone, 'midpoint_watts'):
            return zone.midpoint_watts
        # Fallback to direct attribute
        return getattr(thresholds, attr_name, None)
    
    if metrics is not None:
        return metrics.get(attr_name)
    
    return None


def _get_confidence_qualifier(level: str) -> str:
    """Get qualifier prefix based on confidence level."""
    if level == "low":
        return "❓ [NIEPEWNE] "
    elif level == "medium":
        return "⚠️ [MOŻLIWE] "
    return ""


# Legacy compatibility
def generate_training_advice(
    metrics: Dict[str, Any],
    quality_report: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    
    DEPRECATED: Use interpret_results() with result objects instead.
    """
    if not quality_report.get('is_valid', True):
        return {
            "diagnostics": [],
            "prescriptions": [],
            "warnings": ["Data Unreliable: " + "; ".join(quality_report.get('issues', []))],
            "is_valid": False
        }
    
    result = interpret_results(metrics=metrics)
    
    return {
        "diagnostics": result.diagnostics,
        "prescriptions": result.prescriptions,
        "warnings": result.warnings + result.uncertainties + result.conflicts,
        "is_valid": result.is_valid
    }


def get_feedback_style(severity: str) -> str:
    """Return styling color/icon for severity."""
    if severity == 'high':
        return "🔴"
    elif severity == 'medium':
        return "🟠"
    return "🟢"
