"""
Ramp Test Report Generator.

Per methodology/ramp_test/07_report_structure.md:
- Every result has confidence
- Uncertainty is explicit
- Language is non-categorical
- No absolute statements

This module generates human-readable reports from RampTestResult.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from models.results import (
    RampTestResult, ThresholdRange, ValidityLevel, ConfidenceLevel,
    ConflictReport, TestValidity
)


# ============================================================
# LANGUAGE MAPPINGS (per methodology/07_report_structure.md)
# ============================================================

# Confidence → Language qualifier
CONFIDENCE_LANGUAGE = {
    ConfidenceLevel.HIGH: "",               # "znajduje się w"
    ConfidenceLevel.MEDIUM: "prawdopodobnie ",  # "prawdopodobnie w okolicach"
    ConfidenceLevel.LOW: "może "            # "może znajdować się"
}

# Confidence → Recommendation qualifier
RECOMMENDATION_LANGUAGE = {
    ConfidenceLevel.HIGH: "Sugeruję",
    ConfidenceLevel.MEDIUM: "Rozważ",
    ConfidenceLevel.LOW: "Dane niepewne — unikam jednoznacznych zaleceń"
}

# Validity → Header
VALIDITY_HEADERS = {
    ValidityLevel.VALID: "✅ **Test metodologicznie wiarygodny**",
    ValidityLevel.CONDITIONAL: "⚠️ **Test ważny z zastrzeżeniami**",
    ValidityLevel.INVALID: "⛔ **Test metodologicznie nieważny**"
}


# ============================================================
# REPORT SECTIONS
# ============================================================

@dataclass
class ReportSection:
    """A section of the report."""
    title: str
    content: str
    confidence: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class RampTestReport:
    """Complete Ramp Test report."""
    summary: str
    validity: ReportSection
    vt1_section: Optional[ReportSection] = None
    vt2_section: Optional[ReportSection] = None
    smo2_section: Optional[ReportSection] = None
    conflicts_section: Optional[ReportSection] = None
    recommendations_section: Optional[ReportSection] = None
    methodology_disclaimer: str = ""
    overall_confidence: float = 0.0


# ============================================================
# REPORT GENERATOR
# ============================================================

def generate_report(result: RampTestResult) -> RampTestReport:
    """
    Generate human-readable report from RampTestResult.
    
    Every result has confidence.
    Uncertainty is explicit.
    Language is non-categorical.
    """
    report = RampTestReport(
        summary=_generate_summary(result),
        validity=_generate_validity_section(result.validity),
        overall_confidence=result.overall_confidence,
        methodology_disclaimer=_generate_disclaimer()
    )
    
    # VT1 section
    if result.vt1:
        report.vt1_section = _generate_threshold_section(
            result.vt1, "Próg Aerobowy (VT1)"
        )
    
    # VT2 section
    if result.vt2:
        report.vt2_section = _generate_threshold_section(
            result.vt2, "Próg Anaerobowy (VT2)"
        )
    
    # SmO2 section (LOCAL signal)
    if result.smo2_lt1 or result.smo2_interpretation:
        report.smo2_section = _generate_smo2_section(result)
    
    # Conflicts section
    if result.conflicts.has_conflicts:
        report.conflicts_section = _generate_conflicts_section(result.conflicts)
    
    # Recommendations
    report.recommendations_section = _generate_recommendations_section(result)
    
    return report


def _generate_summary(result: RampTestResult) -> str:
    """Generate executive summary."""
    lines = []
    
    # Validity status
    validity_text = {
        ValidityLevel.VALID: "Test przeprowadzony poprawnie.",
        ValidityLevel.CONDITIONAL: "Test przeprowadzony z zastrzeżeniami.",
        ValidityLevel.INVALID: "Test nieważny — wymagana powtórka."
    }
    lines.append(validity_text[result.validity.validity])
    
    # VT1/VT2 summary with confidence qualifiers
    if result.vt1:
        qualifier = _get_language_qualifier(result.vt1.confidence)
        lines.append(
            f"VT1 {qualifier}w okolicach **{result.vt1.lower_watts:.0f}–{result.vt1.upper_watts:.0f} W** "
            f"(pewność: {result.vt1.confidence:.0%})."
        )
    else:
        lines.append("VT1 nie wykryto.")
    
    if result.vt2:
        qualifier = _get_language_qualifier(result.vt2.confidence)
        lines.append(
            f"VT2 {qualifier}w okolicach **{result.vt2.lower_watts:.0f}–{result.vt2.upper_watts:.0f} W** "
            f"(pewność: {result.vt2.confidence:.0%})."
        )
    
    # Overall confidence
    overall_level = _get_confidence_level(result.overall_confidence)
    lines.append(f"\nOgólna pewność wyników: **{result.overall_confidence:.0%}** ({overall_level}).")
    
    return " ".join(lines)


def _generate_validity_section(validity: TestValidity) -> ReportSection:
    """Generate validity section."""
    header = VALIDITY_HEADERS[validity.validity]
    
    content_lines = [header, ""]
    
    if validity.issues:
        content_lines.append("**Zastrzeżenia:**")
        for issue in validity.issues:
            content_lines.append(f"- {issue}")
    else:
        content_lines.append("Wszystkie kryteria jakości spełnione.")
    
    return ReportSection(
        title="Ważność Testu",
        content="\n".join(content_lines),
        confidence=1.0 if validity.validity == ValidityLevel.VALID else 0.7
    )


def _generate_threshold_section(threshold: ThresholdRange, title: str) -> ReportSection:
    """Generate section for a threshold (VT1 or VT2)."""
    qualifier = _get_language_qualifier(threshold.confidence)
    
    # Range format (never a point!)
    range_text = f"{threshold.lower_watts:.0f}–{threshold.upper_watts:.0f} W"
    midpoint_text = f"~{threshold.midpoint_watts:.0f} W"
    
    # HR range if available
    hr_text = ""
    if threshold.lower_hr and threshold.upper_hr:
        hr_text = f"\n- Zakres HR: ~{threshold.lower_hr:.0f}–{threshold.upper_hr:.0f} bpm"
    
    # Confidence visualization
    confidence_bar = _confidence_bar(threshold.confidence)
    
    content = f"""**Przedział mocy:** {qualifier}{range_text}
**Wartość centralna:** {midpoint_text}{hr_text}

**Pewność detekcji:** {confidence_bar} ({threshold.confidence:.0%})
**Źródła:** {', '.join(threshold.sources)}"""

    # Add warning if low confidence
    warnings = []
    if threshold.confidence < 0.5:
        warnings.append(
            f"⚠️ Pewność NISKA — przedział {range_text} wymaga ostrożnej interpretacji"
        )
    
    return ReportSection(
        title=title,
        content=content,
        confidence=threshold.confidence,
        warnings=warnings
    )


def _generate_smo2_section(result: RampTestResult) -> ReportSection:
    """Generate SmO₂ section (LOCAL signal)."""
    content_lines = [
        "ℹ️ **Uwaga:** SmO₂ jest sygnałem LOKALNYM mierzącym jeden mięsień.",
        "Wyniki tej sekcji stanowią dodatkowy kontekst, NIE samodzielny próg.",
        ""
    ]
    
    if result.smo2_lt1:
        qualifier = _get_language_qualifier(result.smo2_lt1.confidence)
        content_lines.append(
            f"**Punkt spadku SmO₂:** {qualifier}~{result.smo2_lt1.midpoint_watts:.0f} W"
        )
    
    if result.smo2_deviation_from_vt is not None:
        deviation = result.smo2_deviation_from_vt
        if deviation < 0:
            diff_text = f"{abs(deviation):.0f} W wcześniej niż VT"
        elif deviation > 0:
            diff_text = f"{deviation:.0f} W później niż VT"
        else:
            diff_text = "zgodny z VT"
        content_lines.append(f"**Różnica vs VT:** {diff_text}")
    
    if result.smo2_interpretation:
        content_lines.append(f"\n**Interpretacja:** {result.smo2_interpretation}")
    
    return ReportSection(
        title="SmO₂ — Sygnał Lokalny",
        content="\n".join(content_lines),
        confidence=result.smo2_lt1.confidence if result.smo2_lt1 else 0.3,
        warnings=["SmO₂ jest sygnałem LOKALNYM — nie zastępuje VT"]
    )


def _generate_conflicts_section(conflicts: ConflictReport) -> ReportSection:
    """Generate conflicts section."""
    content_lines = [
        "**Zaobserwowane rozbieżności:**",
        ""
    ]
    
    for i, conflict in enumerate(conflicts.conflicts, 1):
        content_lines.append(f"{i}. **{conflict.signal_a}** vs **{conflict.signal_b}**")
        content_lines.append(f"   {conflict.description}")
        content_lines.append(f"   *Interpretacja: {conflict.physiological_interpretation}*")
        content_lines.append("")
    
    content_lines.append(f"**Ogólna zgodność sygnałów:** {conflicts.agreement_score:.0%}")
    
    return ReportSection(
        title="Konflikty i Zastrzeżenia",
        content="\n".join(content_lines),
        confidence=conflicts.agreement_score
    )


def _generate_recommendations_section(result: RampTestResult) -> ReportSection:
    """Generate recommendations with confidence-appropriate language."""
    confidence_level = _get_confidence_level(result.overall_confidence)
    
    # Get language qualifier
    if result.overall_confidence >= 0.7:
        prefix = "Sugeruję"
    elif result.overall_confidence >= 0.5:
        prefix = "Rozważ"
    else:
        prefix = "⚠️ Dane niepewne — poniższe sugestie traktuj z ostrożnością"
    
    content_lines = [f"**{prefix}:**", ""]
    
    # Only provide recommendations if confidence is sufficient
    if result.overall_confidence >= 0.3 and result.vt1:
        vt1_mid = result.vt1.midpoint_watts
        content_lines.append(f"- Trening Z2 (wytrzymałość): do ~{vt1_mid - 10:.0f} W")
        content_lines.append(f"- Trening Z3 (tempo): ~{vt1_mid - 5:.0f}–{vt1_mid + 15:.0f} W")
        
        if result.vt2:
            vt2_mid = result.vt2.midpoint_watts
            content_lines.append(f"- Trening Z4 (próg): ~{vt1_mid + 10:.0f}–{vt2_mid - 10:.0f} W")
    
    if result.overall_confidence < 0.5:
        content_lines.append("")
        content_lines.append("*Zalecam powtórzenie testu dla większej pewności.*")
    
    return ReportSection(
        title="Sugestie Treningowe",
        content="\n".join(content_lines),
        confidence=result.overall_confidence
    )


def _generate_disclaimer() -> str:
    """Generate methodology disclaimer."""
    return """---

**Nota metodologiczna:**

1. Niniejszy raport NIE stanowi diagnozy medycznej.
2. Progi wentylacyjne (VT1, VT2) są szacowane bez bezpośredniej analizy gazowej.
3. SmO₂ jest sygnałem LOKALNYM i nie zastępuje pomiarów systemowych.
4. Wyniki mogą różnić się o 5–15 W między testami (naturalna zmienność).
5. Przed zmianą treningu skonsultuj się z trenerem.
"""


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _get_language_qualifier(confidence: float) -> str:
    """Get language qualifier based on confidence."""
    if confidence >= 0.7:
        return ""  # No qualifier needed
    elif confidence >= 0.5:
        return "prawdopodobnie "
    else:
        return "może "


def _get_confidence_level(confidence: float) -> str:
    """Get human-readable confidence level."""
    if confidence >= 0.8:
        return "wysoka"
    elif confidence >= 0.5:
        return "średnia"
    else:
        return "niska"


def _confidence_bar(confidence: float, width: int = 10) -> str:
    """Generate visual confidence bar."""
    filled = int(confidence * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def format_report_markdown(report: RampTestReport) -> str:
    """Format report as Markdown string."""
    sections = [
        "# Raport Ramp Test",
        "",
        "## Podsumowanie",
        report.summary,
        "",
    ]
    
    # Validity
    sections.extend([
        f"## {report.validity.title}",
        report.validity.content,
        ""
    ])
    
    # VT1
    if report.vt1_section:
        sections.extend([
            f"## {report.vt1_section.title}",
            report.vt1_section.content,
            ""
        ])
        for warning in report.vt1_section.warnings:
            sections.append(f"> {warning}")
            sections.append("")
    
    # VT2
    if report.vt2_section:
        sections.extend([
            f"## {report.vt2_section.title}",
            report.vt2_section.content,
            ""
        ])
    
    # SmO2
    if report.smo2_section:
        sections.extend([
            f"## {report.smo2_section.title}",
            report.smo2_section.content,
            ""
        ])
    
    # Conflicts
    if report.conflicts_section:
        sections.extend([
            f"## {report.conflicts_section.title}",
            report.conflicts_section.content,
            ""
        ])
    
    # Recommendations
    if report.recommendations_section:
        sections.extend([
            f"## {report.recommendations_section.title}",
            report.recommendations_section.content,
            ""
        ])
    
    # Disclaimer
    sections.append(report.methodology_disclaimer)
    
    return "\n".join(sections)


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'generate_report',
    'format_report_markdown',
    'RampTestReport',
    'ReportSection',
    'CONFIDENCE_LANGUAGE',
]
