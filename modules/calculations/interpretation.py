"""
Interpretation & Prescription Engine.

Translates physiological metrics into actionable training advice.
NEW: Interprets result OBJECTS (not raw numbers), cites uncertainty and conflicts,
avoids definitive recommendations when data quality is low.
"""

import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InterpretationResult:
    """Quality-aware interpretation result."""

    diagnostics: List[str] = field(default_factory=list)
    prescriptions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    uncertainties: List[str] = field(default_factory=list)  # NEW: Cited uncertainties
    conflicts: List[str] = field(default_factory=list)  # NEW: Cited conflicts
    data_quality_note: str = ""  # NEW: Overall quality assessment
    is_valid: bool = True
    confidence_level: str = "high"  # high, medium, low

    def get_summary(self) -> str:
        """Get human-readable summary."""
        if self.confidence_level == "low":
            return "❓ Interpretacja niepewna - dane niskiej jakości"
        elif self.confidence_level == "medium":
            return "⚠️ Interpretacja z zastrzeżeniami"
        return "✅ Interpretacja wiarygodna"


def _extract_conflicts(
    conflicts: Optional[Any],
    result: InterpretationResult,
    overall_quality: float,
    quality_issues: List[str],
) -> float:
    if conflicts is None or not hasattr(conflicts, "has_conflicts"):
        return overall_quality
    if not conflicts.has_conflicts:
        return overall_quality

    result.conflicts.append("⚠️ Wykryto konflikty między sygnałami:")
    for c in conflicts.conflicts:
        result.conflicts.append(f"  • {c}")

    overall_quality *= conflicts.agreement_score
    quality_issues.append(f"Zgoda sygnałów: {conflicts.agreement_score:.0%}")
    return overall_quality


def _extract_dfa_uncertainties(
    dfa_result: Optional[Any],
    result: InterpretationResult,
    overall_quality: float,
    quality_issues: List[str],
) -> float:
    if dfa_result is None:
        return overall_quality

    if hasattr(dfa_result, "is_uncertain") and dfa_result.is_uncertain:
        reasons = getattr(dfa_result, "uncertainty_reasons", [])
        result.uncertainties.append(f"❓ DFA-a1 niepewny: {'; '.join(reasons)}")
        overall_quality *= 0.7
        quality_issues.append("DFA niepewny")

    if hasattr(dfa_result, "artifact_sensitivity_note"):
        result.warnings.append(dfa_result.artifact_sensitivity_note)

    return overall_quality


def _extract_smo2_uncertainties(
    smo2_result: Optional[Any],
    result: InterpretationResult,
) -> None:
    if smo2_result is None:
        return

    if hasattr(smo2_result, "is_supporting_only") and smo2_result.is_supporting_only:
        result.uncertainties.append("⚠️ SmO₂ = sygnał LOKALNY, używany tylko jako potwierdzenie")

    if hasattr(smo2_result, "get_interpretation_note"):
        note = smo2_result.get_interpretation_note()
        if note:
            result.warnings.append(note)


def _extract_threshold_uncertainties(
    thresholds: Optional[Any],
    result: InterpretationResult,
    overall_quality: float,
    quality_issues: List[str],
) -> float:
    if thresholds is None:
        return overall_quality

    for zone_name in ("vt1_zone", "vt2_zone"):
        zone = getattr(thresholds, zone_name, None)
        if zone is not None and hasattr(zone, "confidence"):
            if zone.confidence < 0.7:
                label = zone_name.split("_")[0].upper()
                result.uncertainties.append(f"❓ {label} niska pewność ({zone.confidence:.0%})")
                overall_quality *= zone.confidence

    return overall_quality


def _determine_confidence_level(
    overall_quality: float,
    quality_issues: List[str],
) -> tuple:
    if overall_quality < 0.5:
        return (
            "low",
            "⛔ NISKA JAKOŚĆ DANYCH - unikam jednoznacznych zaleceń. "
            f"Problemy: {', '.join(quality_issues)}",
        )
    if overall_quality < 0.8:
        return (
            "medium",
            f"⚠️ Średnia jakość danych. {', '.join(quality_issues)}",
        )
    return "high", "✅ Dane wysokiej jakości"


def _generate_threshold_diagnostics(
    vt1_watts: Optional[float],
    vt2_watts: Optional[float],
    confidence_level: str,
) -> tuple:
    diagnostics: List[str] = []
    prescriptions: List[str] = []

    if not vt1_watts or not vt2_watts or vt2_watts <= 0:
        return diagnostics, prescriptions

    ratio = vt1_watts / vt2_watts
    qualifier = _get_confidence_qualifier(confidence_level)

    if ratio < 0.65:
        diagnostics.append(f"{qualifier}Deficyt aerobowy: VT1 jest niski względem VT2 (<65%).")
        prescriptions.append(
            "Sugestia: Budowanie bazy - duża objętość Strefy 2 (LSD)."
            if confidence_level != "low"
            else "⚠️ Zalecenie niepewne z powodu niskiej jakości danych."
        )
    elif ratio > 0.85:
        diagnostics.append(
            f"{qualifier}Wysoka baza aerobowa: VT1 blisko VT2 (>85%). Profil 'Diesel'."
        )
        prescriptions.append(
            "Sugestia: Trening spolaryzowany - interwały VO2max."
            if confidence_level != "low"
            else "⚠️ Zalecenie niepewne z powodu niskiej jakości danych."
        )
    else:
        diagnostics.append(f"{qualifier}Zrównoważony profil aerobowy (VT1 = 65-85% VT2).")

    return diagnostics, prescriptions


def _generate_dfa_diagnostics(dfa_result: Optional[Any]) -> List[str]:
    if dfa_result is None:
        return []

    mean_alpha = getattr(dfa_result, "mean_alpha1", None)
    if mean_alpha is None:
        return []

    is_uncertain = getattr(dfa_result, "is_uncertain", False)
    marker = " ❓" if is_uncertain else ""

    if mean_alpha > 1.0:
        zone = "strefa aerobowa/regeneracja"
    elif mean_alpha > 0.75:
        zone = "strefa progowa"
    else:
        zone = "strefa VO2max"

    return [f"DFA-a1 = {mean_alpha:.2f}{marker} - {zone}"]


def interpret_results(
    thresholds: Optional[Any] = None,  # StepTestResult
    dfa_result: Optional[Any] = None,  # DFAResult
    smo2_result: Optional[Any] = None,  # StepSmO2Result
    conflicts: Optional[Any] = None,  # ConflictAnalysisResult
    metrics: Optional[Dict[str, Any]] = None,  # Legacy fallback
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
    quality_issues: List[str] = []

    # 1. Extract and cite conflicts
    overall_quality = _extract_conflicts(conflicts, result, overall_quality, quality_issues)

    # 2. Extract and cite uncertainties
    overall_quality = _extract_dfa_uncertainties(
        dfa_result, result, overall_quality, quality_issues
    )
    _extract_smo2_uncertainties(smo2_result, result)
    overall_quality = _extract_threshold_uncertainties(
        thresholds, result, overall_quality, quality_issues
    )

    # 3. Determine confidence level
    result.confidence_level, result.data_quality_note = _determine_confidence_level(
        overall_quality, quality_issues
    )

    # 4. Generate diagnostics (with confidence qualifiers)
    vt1_watts = _get_threshold_value(thresholds, "vt1_watts", metrics)
    vt2_watts = _get_threshold_value(thresholds, "vt2_watts", metrics)

    threshold_diag, threshold_rx = _generate_threshold_diagnostics(
        vt1_watts, vt2_watts, result.confidence_level
    )
    result.diagnostics.extend(threshold_diag)
    result.prescriptions.extend(threshold_rx)

    # 5. DFA-based diagnostics (with uncertainty citation)
    dfa_diag = _generate_dfa_diagnostics(dfa_result)
    result.diagnostics.extend(dfa_diag)

    if not result.diagnostics:
        result.diagnostics.append("Profil normalny. Brak zidentyfikowanych limitów.")

    return result


def _get_threshold_value(
    thresholds: Optional[Any], attr_name: str, metrics: Optional[Dict]
) -> Optional[float]:
    """Extract threshold value from object or legacy dict."""
    if thresholds is not None:
        # Try zone midpoint first
        zone_attr = attr_name.replace("_watts", "_zone")
        zone = getattr(thresholds, zone_attr, None)
        if zone is not None and hasattr(zone, "midpoint_watts"):
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
    metrics: Dict[str, Any], quality_report: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.

    DEPRECATED: Use interpret_results() with result objects instead.
    Will be removed in a future version.
    """
    warnings.warn(
        "generate_training_advice is deprecated. Use interpret_results() with result objects instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if not quality_report.get("is_valid", True):
        return {
            "diagnostics": [],
            "prescriptions": [],
            "warnings": ["Data Unreliable: " + "; ".join(quality_report.get("issues", []))],
            "is_valid": False,
        }

    result = interpret_results(metrics=metrics)

    return {
        "diagnostics": result.diagnostics,
        "prescriptions": result.prescriptions,
        "warnings": result.warnings + result.uncertainties + result.conflicts,
        "is_valid": result.is_valid,
    }


def get_feedback_style(severity: str) -> str:
    """Return styling color/icon for severity."""
    if severity == "high":
        return "🔴"
    elif severity == "medium":
        return "🟠"
    return "🟢"
