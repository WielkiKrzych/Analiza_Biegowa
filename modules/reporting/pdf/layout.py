"""
PDF Layout Module.

Defines page structure and content sections for Ramp Test PDF.
Each page is a separate function.
No physiological calculations - only layout and formatting.

Per specification: methodology/ramp_test/10_pdf_layout.md

This module re-exports from split submodules and contains remaining
page builder functions that have not yet been extracted.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, Spacer, Table, TableStyle

# Re-export from split modules for backward compatibility
from .layout_executive_summary import build_page_executive_summary  # noqa: F401
from .layout_executive_verdict import build_page_executive_verdict  # noqa: F401
from .layout_formatters import (  # noqa: F401
    build_colored_box,
    build_section_description,
)
from .layout_tables import (  # noqa: F401
    build_chapter_header,
    build_table_of_contents,
)
from .layout_title import (  # noqa: F401
    build_contact_footer,
    build_title_page,
)
from .styles import (
    COLORS,
    get_table_style,
)

__all__ = [
    # From layout_executive_summary
    "build_page_executive_summary",
    # From layout_executive_verdict
    "build_page_executive_verdict",
    # From layout_formatters
    "build_colored_box",
    "build_section_description",
    # From layout_tables
    "build_table_of_contents",
    "build_chapter_header",
    # From layout_title
    "build_title_page",
    "build_contact_footer",
    # Remaining functions defined below
    "build_page_cover",
    "build_page_test_profile",
    "build_page_thresholds",
    "build_page_smo2",
    "build_page_pdc",
    "build_page_interpretation",
    "build_page_cardiovascular",
    "build_page_ventilation",
    "build_page_metabolic_engine",
    "build_page_limiter_radar",
    "build_page_zones",
    "build_page_limitations",
    "build_page_theory",
    "build_page_protocol",
    "build_page_thermal",
    "build_page_biomech",
    "build_page_drift",
    "build_page_kpi_dashboard",
    "build_page_drift_kpi",
    "build_page_limiters",
    "build_page_extra",
]

# Setup logger
logger = logging.getLogger("Tri_Dashboard.PDFLayout")

# Premium color constants
PREMIUM_COLORS = {
    "navy": HexColor("#1A5276"),  # Recommendations/training
    "dark_glass": HexColor("#17252A"),  # Title page background
    "red": HexColor("#C0392B"),  # Warnings/limitations
    "green": HexColor("#27AE60"),  # Positives/strengths
    "white": HexColor("#FFFFFF"),
    "light_gray": HexColor("#BDC3C7"),
}


# ============================================================================
# PAGE 1: OKŁADKA / PODSUMOWANIE
# ============================================================================


def build_page_cover(
    metadata: Dict[str, Any],
    thresholds: Dict[str, Any],
    cp_model: Dict[str, Any],
    confidence: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict,
    is_conditional: bool = False,
    vt1_onset_watts: Optional[int] = None,
    rcp_onset_watts: Optional[int] = None,
) -> List:
    """Build Page 1: Cover / Summary.

    Contains:
    - Title and metadata
    - Confidence badge
    - Conditional warning (if applicable)
    - Key results table
    - Ramp profile chart
    """
    elements = []

    # === HEADER ===
    metadata.get("test_date", "Unknown")
    metadata.get("session_id", "")[:8]
    metadata.get("method_version", "1.0.0")

    elements.append(Paragraph("1. PODSUMOWANIE WYKONAWCZE", styles["title"]))
    elements.append(Paragraph("<font size='14'>1.1 RAPORT POTESTOWY</font>", styles["center"]))
    elements.append(Spacer(1, 8 * mm))

    # === CONFIDENCE BADGE REMOVED per user request ===
    elements.append(Spacer(1, 6 * mm))

    # === CONDITIONAL WARNING ===
    if is_conditional:
        warning_text = (
            "<b>⚠️ Test rozpoznany warunkowo</b><br/>"
            "Interpretacja obarczona zwiększoną niepewnością. "
            "Profil mocy lub czas kroków wykazują odchylenia od standardowego protokołu."
        )
        warning_table = Table([[Paragraph(warning_text, styles["body"])]], colWidths=[160 * mm])
        warning_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), COLORS["warning"]),
                    ("TEXTCOLOR", (0, 0), (-1, -1), COLORS["text"]),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("PADDING", (0, 0), (-1, -1), 10),
                    ("BOX", (0, 0), (-1, -1), 2, COLORS["warning"]),
                ]
            )
        )
        elements.append(warning_table)
        elements.append(Spacer(1, 6 * mm))

    # === KEY RESULTS TABLE ===
    elements.append(Paragraph("Kluczowe Wyniki", styles["heading"]))

    vt1_watts = thresholds.get("vt1_watts", "brak danych")
    vt2_watts = thresholds.get("vt2_watts", "brak danych")
    cp_watts = cp_model.get("cp_watts", "brak danych")
    w_prime_kj = cp_model.get("w_prime_kj", "brak danych")
    metadata.get("pmax_watts", "brak danych")

    # Calculate Upper Aerobic range (VT1_onset to RCP_onset) with W unit
    if vt1_onset_watts and rcp_onset_watts:
        upper_aerobic_range = f"{int(vt1_onset_watts)}–{int(rcp_onset_watts)} W"
    else:
        upper_aerobic_range = "brak danych"

    data = [
        ["Parametr", "Wartość", "Interpretacja"],
        ["VT1 (Próg tlenowy)", f"{vt1_watts} W", "Strefa komfortowa"],
        ["VT2 (Próg beztlenowy)", f"{vt2_watts} W", "Strefa wysiłku"],
        ["Zakres Upper Aerobic", upper_aerobic_range, "Strefa tempo/threshold"],
        ["Critical Power (CP)", f"{cp_watts} W", "Moc progowa"],
        ["W' (Rezerwa)", f"{w_prime_kj} kJ", "Rezerwa anaerobowa"],
    ]

    table = Table(data, colWidths=[55 * mm, 35 * mm, 55 * mm])
    table.setStyle(get_table_style())
    elements.append(table)
    elements.append(Spacer(1, 8 * mm))

    # === ZONES TABLE (integrated into 1.1) ===
    elements.append(Paragraph("Strefy Treningowe", styles["heading"]))
    elements.append(Spacer(1, 3 * mm))

    vt1_raw = thresholds.get("vt1_watts", "brak danych")
    vt2_raw = thresholds.get("vt2_watts", "brak danych")

    # Parse numbers for zone calculation
    try:
        vt1 = float(vt1_raw) if vt1_raw != "brak danych" else 0
        vt2 = float(vt2_raw) if vt2_raw != "brak danych" else 0
    except (ValueError, TypeError):
        vt1 = 0
        vt2 = 0

    # Calculate zones
    if vt1 and vt2:
        z1_max = int(vt1 * 0.8)
        z2_min = z1_max
        z2_max = int(vt1)
        z3_min = z2_max
        z3_max = int(vt2)
        z4_min = z3_max
        z4_max = int(vt2 * 1.05)
        z5_min = z4_max

        zones_data = [
            ["Strefa", "Zakres [W]", "Opis", "Cel treningowy"],
            ["Z1 Recovery", f"< {z1_max}", "Bardzo łatwy", "Regeneracja"],
            ["Z2 Endurance", f"{z2_min}–{z2_max}", "Komfortowy", "Baza tlenowa"],
            ["Z3 Tempo", f"{z3_min}–{z3_max}", "Umiarkowany", "Wytrzymałość"],
            ["Z4 Threshold", f"{z4_min}–{z4_max}", "Ciężki", "Próg"],
            ["Z5 VO₂max", f"> {z5_min}", "Maksymalny", "Pułap Tlenowy"],
        ]
    else:
        zones_data = [
            ["Strefa", "Zakres [W]", "Opis", "Cel treningowy"],
            ["Z1 Recovery", "-", "Bardzo łatwy", "Regeneracja"],
            ["Z2 Endurance", "-", "Komfortowy", "Baza tlenowa"],
            ["Z3 Tempo", "-", "Umiarkowany", "Wytrzymałość"],
            ["Z4 Threshold", "-", "Ciężki", "Próg"],
            ["Z5 VO₂max", "-", "Maksymalny", "Pułap Tlenowy"],
        ]

    zones_table = Table(zones_data, colWidths=[35 * mm, 35 * mm, 35 * mm, 40 * mm])
    zones_table.setStyle(get_table_style())
    elements.append(zones_table)
    elements.append(Spacer(1, 4 * mm))

    elements.append(
        Paragraph(
            "Powyższe strefy są obliczone automatycznie na podstawie wykrytych progów VT1 i VT2. "
            "Przed zastosowaniem skonsultuj je z trenerem, który może dostosować je do Twoich celów.",
            styles["small"],
        )
    )

    return elements


def build_page_test_profile(
    metadata: Dict[str, Any], figure_paths: Dict[str, str], styles: Dict
) -> List:
    """Build Page 1.2: Test Profile (chart and protocol description).

    Contains:
    - Ramp profile chart
    - Test protocol description
    """
    elements = []

    elements.append(Paragraph("<font size='14'>1.2 PRZEBIEG TESTU</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))

    # === RAMP PROFILE CHART ===
    if figure_paths and "ramp_profile" in figure_paths:
        elements.extend(_build_chart(figure_paths["ramp_profile"], "", styles))
        elements.append(Spacer(1, 4 * mm))

    # === TEST PROTOCOL DESCRIPTION ===
    # Extract protocol info from metadata (populated from UI manual inputs)
    test_start_power = metadata.get("test_start_power", "---")
    test_end_power = metadata.get("test_end_power", metadata.get("pmax_watts", "---"))
    test_duration = metadata.get("test_duration", "---")

    elements.append(
        Paragraph(
            "<font size='8' color='#7F8C8D'>"
            "Test wykonywany do odmowy, każdy interwał trwał 3 minuty. "
            "Zwiększenie obciążenia w każdym interwale +30W. "
            f"Początek testu rozpoczął się od wartości {test_start_power} W, "
            f"koniec testu nastąpił na wartości {test_end_power} W. "
            f"Test trwał łącznie {test_duration}."
            "</font>",
            styles["center"],
        )
    )

    return elements


# ============================================================================
# PAGE 2: SZCZEGÓŁY PROGÓW VT1/VT2
# ============================================================================


def build_page_thresholds(
    thresholds: Dict[str, Any], smo2: Dict[str, Any], figure_paths: Dict[str, str], styles: Dict
) -> List:
    """Build Page 2: Threshold Details.

    Contains:
    - VT1/VT2 explanation
    - Thresholds table with HR/VE
    - SmO2 vs Power chart
    - SmO2 supporting signal note
    """
    elements = []

    elements.append(Paragraph("2. PROGI METABOLICZNE", styles["title"]))
    elements.append(Paragraph("<font size='14'>2.1 SZCZEGÓŁY VT1 / VT2</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))

    # === EXPLANATION ===
    elements.append(
        Paragraph(
            "Progi zostały wykryte na podstawie zmian w wentylacji (oddychaniu) podczas testu.",
            styles["body"],
        )
    )
    elements.append(
        Paragraph(
            "<b>VT1 (Próg tlenowy):</b> Moment, gdy organizm zaczyna intensywniej pracować. "
            "Możesz jechać komfortowo przez wiele godzin.",
            styles["body"],
        )
    )
    elements.append(
        Paragraph(
            "<b>VT2 (Próg beztlenowy):</b> Punkt, powyżej którego wysiłek staje się bardzo ciężki. "
            "Oddychasz ciężko, nie możesz swobodnie mówić.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # === THRESHOLDS TABLE ===
    elements.append(Paragraph("Tabela Progów", styles["heading"]))

    vt1_watts = thresholds.get("vt1_watts", "brak danych")
    vt1_range = thresholds.get("vt1_range_watts", "brak danych")
    vt1_hr = thresholds.get("vt1_hr", "brak danych")
    vt1_ve = thresholds.get("vt1_ve", "brak danych")

    vt2_watts = thresholds.get("vt2_watts", "brak danych")
    vt2_range = thresholds.get("vt2_range_watts", "brak danych")
    vt2_hr = thresholds.get("vt2_hr", "brak danych")
    vt2_ve = thresholds.get("vt2_ve", "brak danych")

    def format_thresh(mid, rng):
        if mid == "brak danych":
            return mid
        if rng == "brak danych":
            return f"~{mid}"
        return f"{rng} (środek: {mid})"

    def fmt(val):
        if val == "brak danych":
            return val
        try:
            return f"{float(val):.0f}"
        except (ValueError, TypeError):
            return str(val)

    data = [
        ["Próg", "Moc [W]", "HR [bpm]", "VE [L/min]"],
        ["VT1 (Próg tlenowy)", format_thresh(vt1_watts, vt1_range), fmt(vt1_hr), fmt(vt1_ve)],
        ["VT2 (Próg beztlenowy)", format_thresh(vt2_watts, vt2_range), fmt(vt2_hr), fmt(vt2_ve)],
    ]

    table = Table(data, colWidths=[50 * mm, 50 * mm, 30 * mm, 30 * mm])
    table.setStyle(get_table_style())
    elements.append(table)
    # === EDUCATION BLOCK: VT1/VT2 ===
    elements.append(Spacer(1, 4 * mm))
    elements.extend(
        _build_education_block(
            "Dlaczego to ma znaczenie? (VT1 / VT2)",
            "Progi wentylacyjne to Twoje najważniejsze drogowskazy w planowaniu obciążeń. "
            "VT1 wyznacza granicę komfortu tlenowego i „przepalania” tłuszczy – to tu budujesz bazę na długie godziny. "
            "VT2 to Twój „szklany sufit” – powyżej niego kwas narasta szybciej niż organizm go utylizuje, "
            "co wymaga długiej regeneracji. Znajomość tych punktów pozwala unikać „strefy zgubnej” między progami, "
            "gdzie zmęczenie jest duże, a adaptacje nieoptymalne. Jako trener używam ich, by każda Twoja minuta "
            "na rowerze miała konkretny cel fizjologiczny. Dzięki temu nie trenujesz po prostu „ciężko”, "
            "ale trenujesz mądrze i precyzyjnie.",
            styles,
        )
    )

    return elements


# ============================================================================
# SmO2 PAGE HELPERS
# ============================================================================


def _classify_smo2_slope(slope: float) -> tuple:
    """Classify SmO2 desaturation slope rate.

    Returns:
        Tuple of (color_hex, label).
    """
    if slope < -6:
        return ("#E74C3C", "Szybka desaturacja")
    if slope < -3:
        return ("#F39C12", "Umiarkowana")
    return ("#2ECC71", "Stabilna")


def _classify_smo2_halftime(halftime: float) -> tuple:
    """Classify SmO2 reoxygenation half-time.

    Returns:
        Tuple of (color_hex, label).
    """
    if halftime > 60:
        return ("#E74C3C", "Wolna reoksygenacja")
    if halftime > 30:
        return ("#F39C12", "Umiarkowana")
    return ("#2ECC71", "Szybka")


def _classify_smo2_coupling(coupling: float) -> tuple:
    """Classify HR-SmO2 coupling strength.

    Returns:
        Tuple of (color_hex, label).
    """
    abs_c = abs(coupling)
    if abs_c > 0.6:
        return ("#3498DB", "Silna (centralna)")
    if abs_c > 0.3:
        return ("#F39C12", "Umiarkowana")
    return ("#2ECC71", "Słaba (lokalna)")


def _classify_smo2_data_quality(quality: str) -> tuple:
    """Classify SmO2 data quality.

    Returns:
        Tuple of (color_hex, label).
    """
    if quality == "good":
        return ("#2ECC71", "Wysoka")
    if quality == "low":
        return ("#F39C12", "Niska")
    return ("#7F8C8D", "Brak danych")


def _classify_smo2_slope_benchmark(slope: float) -> str:
    """Classify SmO2 slope for benchmark interpretation."""
    if slope < -4:
        return "Typowe dla limitu centralnego"
    if slope < -2:
        return "Umiarkowane - balans C/P"
    return "Stabilne - limit lokalny"


def _classify_smo2_halftime_benchmark(halftime: Optional[float]) -> str:
    """Classify SmO2 halftime for benchmark interpretation."""
    if halftime is None:
        return "Brak danych"
    if halftime < 25:
        return "Elite (<25s)"
    if halftime < 50:
        return "OK ale nie elite"
    return "Wolna - priorytet interwały"


def _classify_smo2_coupling_benchmark(coupling: float) -> str:
    """Classify HR-SmO2 coupling for benchmark interpretation."""
    abs_c = abs(coupling)
    if abs_c > 0.6:
        return "Silna dominacja serca (centralny)"
    if abs_c > 0.3:
        return "Zrównoważona"
    return "Dominacja obwodowa (lokalna)"


def _build_smo2_metric_card(
    title: str, value: str, unit: str, interpretation: str, color: str, styles: Dict
) -> Table:
    """Build a single metric card for SmO2 analysis."""
    card_content = [
        Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
        Paragraph(f"<font size='16' color='{color}'><b>{value}</b></font>", styles["center"]),
        Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
        Spacer(1, 1 * mm),
        Paragraph(f"<font size='8'>{interpretation}</font>", styles["center"]),
    ]
    card_table = Table([[card_content]], colWidths=[55 * mm])
    card_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return card_table


def _build_smo2_metric_cards(smo2_advanced: Dict[str, Any], styles: Dict) -> List:
    """Build metric cards row for SmO2 analysis page."""
    safe = smo2_advanced or {}
    slope = safe.get("slope_per_100w", 0)
    halftime = safe.get("halftime_reoxy_sec")
    coupling = safe.get("hr_coupling_r", 0)

    slope_color, slope_interp = _classify_smo2_slope(slope)
    card1 = _build_smo2_metric_card(
        "DESATURATION RATE", f"{slope:.1f}", "%/100W", slope_interp, slope_color, styles
    )

    if halftime:
        ht_color, ht_interp = _classify_smo2_halftime(halftime)
        card2 = _build_smo2_metric_card(
            "REOXY HALF-TIME", f"{halftime:.0f}", "sekund", ht_interp, ht_color, styles
        )
    else:
        card2 = _build_smo2_metric_card(
            "REOXY HALF-TIME", "---", "sekund", "Brak danych", "#7F8C8D", styles
        )

    coup_color, coup_interp = _classify_smo2_coupling(coupling)
    card3 = _build_smo2_metric_card(
        "HR COUPLING", f"{coupling:.2f}", "r-Pearson", coup_interp, coup_color, styles
    )

    cards_row = Table([[card1, card2, card3]], colWidths=[58 * mm, 58 * mm, 58 * mm])
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    return [cards_row, Spacer(1, 6 * mm)]


def _build_smo2_mechanism_panel(smo2_advanced: Dict[str, Any], styles: Dict) -> List:
    """Build oxygen delivery mechanism panel for SmO2 page."""
    safe = smo2_advanced or {}
    limiter_type = safe.get("limiter_type", "unknown")
    limiter_conf = safe.get("limiter_confidence", 0)
    interpretation_adv = safe.get("interpretation", "")

    mechanism_colors = {
        "local": "#3498DB",
        "central": "#E74C3C",
        "metabolic": "#F39C12",
        "unknown": "#7F8C8D",
    }
    mechanism_names = {
        "local": "OBWODOWY",
        "central": "CENTRALNY",
        "metabolic": "MIESZANY",
        "unknown": "NIEOKREŚLONY",
    }
    mechanism_icons = {"local": "💪", "central": "❤️", "metabolic": "🔥", "unknown": "❓"}

    mech_color = HexColor(mechanism_colors.get(limiter_type, "#7F8C8D"))
    mech_name = mechanism_names.get(limiter_type, "UNDEFINED")
    mech_icon = mechanism_icons.get(limiter_type, "❓")

    elements: List = []
    elements.append(Paragraph("<b>DOMINANT OXYGEN DELIVERY MECHANISM</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    verdict_content = [
        Paragraph(f"<font color='white'><b>{mech_icon} {mech_name}</b></font>", styles["center"]),
        Paragraph(
            f"<font size='10' color='white'>{limiter_conf:.0%} confidence</font>", styles["center"]
        ),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), mech_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(verdict_table)
    elements.append(Spacer(1, 3 * mm))

    if interpretation_adv:
        for line in interpretation_adv.split("\n")[:2]:
            elements.append(Paragraph(line, styles["body"]))
    elements.append(Spacer(1, 6 * mm))

    return elements


def _build_smo2_threshold_cards(smo2_manual: Dict[str, Any], styles: Dict) -> List:
    """Build SmO2 threshold cards (LT1/LT2)."""

    def fmt(val: Any) -> str:
        if val in ("brak danych", None, "---"):
            return "---"
        try:
            return f"{float(val):.0f}"
        except (ValueError, TypeError):
            return str(val)

    lt1 = smo2_manual.get("lt1_watts", "---")
    lt2 = smo2_manual.get("lt2_watts", "---")
    lt1_hr = smo2_manual.get("lt1_hr", "---")
    lt2_hr = smo2_manual.get("lt2_hr", "---")

    elements: List = []
    elements.append(Paragraph("<b>PROGI OKSYGENACJI MIĘŚNIOWEJ</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    lt1_card = [
        Paragraph("<font size='9' color='#7F8C8D'>SmO₂ LT1</font>", styles["center"]),
        Paragraph(f"<font size='14'><b>{fmt(lt1)} W</b></font>", styles["center"]),
        Paragraph(f"<font size='9'>@ {fmt(lt1_hr)} bpm</font>", styles["center"]),
    ]
    lt2_card = [
        Paragraph("<font size='9' color='#7F8C8D'>SmO₂ LT2</font>", styles["center"]),
        Paragraph(f"<font size='14'><b>{fmt(lt2)} W</b></font>", styles["center"]),
        Paragraph(f"<font size='9'>@ {fmt(lt2_hr)} bpm</font>", styles["center"]),
    ]

    lt1_table = Table([[lt1_card]], colWidths=[85 * mm])
    lt1_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#E8F6F3")),
                ("BOX", (0, 0), (-1, -1), 1, HexColor("#1ABC9C")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    lt2_table = Table([[lt2_card]], colWidths=[85 * mm])
    lt2_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FDEDEC")),
                ("BOX", (0, 0), (-1, -1), 1, HexColor("#E74C3C")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    thresh_row = Table([[lt1_table, lt2_table]], colWidths=[88 * mm, 88 * mm])
    elements.append(thresh_row)
    elements.append(Spacer(1, 6 * mm))
    return elements


def _build_smo2_recommendation_cards(
    smo2_advanced: Dict[str, Any], limiter_type: str, styles: Dict
) -> List:
    """Build training decision cards for SmO2 page."""
    safe = smo2_advanced or {}
    recommendations = safe.get("recommendations", [])

    if not recommendations:
        return []

    elements: List = []
    elements.append(
        Paragraph("<b>DECYZJE TRENINGOWE NA PODSTAWIE KINETYKI O₂</b>", styles["subheading"])
    )
    elements.append(Spacer(1, 3 * mm))

    expected = {
        "local": ["Wzrost bazowego SmO₂ o 2-4%", "Szybsza reoksygenacja", "Zmniejszenie slope"],
        "central": [
            "Wyższe SmO₂ przy tym samym HR",
            "Lepsza korelacja",
            "Stabilniejsza saturacja",
        ],
        "metabolic": ["Późniejszy drop point", "Mniejszy slope", "Lepsza tolerancja kwasu"],
    }
    exp_list = expected.get(
        limiter_type, ["Poprawa ogólna", "Stabilniejsza saturacja", "Lepszy klirens"]
    )

    for i, rec in enumerate(recommendations[:3]):
        exp_resp = exp_list[i] if i < len(exp_list) else "Poprawa wydolności"
        card_content = [
            Paragraph(f"<font size='10'><b>{i + 1}. {rec}</b></font>", styles["body"]),
            Paragraph(
                f"<font size='8' color='#27AE60'>Spodziewany efekt: {exp_resp}</font>",
                styles["body"],
            ),
        ]
        card_table = Table([[card_content]], colWidths=[170 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                    ("BOX", (0, 0), (-1, -1), 0.5, COLORS["border"]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(card_table)
        elements.append(Spacer(1, 2 * mm))

    return elements


def _build_smo2_benchmark_table(
    slope: float, halftime: Optional[float], coupling: float, styles: Dict
) -> List:
    """Build reference benchmark table for SmO2 page."""
    slope_interp = _classify_smo2_slope_benchmark(slope)
    ht_interp = _classify_smo2_halftime_benchmark(halftime)
    coup_interp = _classify_smo2_coupling_benchmark(coupling)

    elements: List = []
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("<b>REFERENCE BENCHMARK</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    ht_value = f"{halftime:.0f} s" if halftime else "---"
    bench_data = [
        ["Metryka", "Twoja wartość", "Interpretacja kliniczna"],
        ["SmO2 slope", f"{slope:.1f} %/100W", slope_interp],
        ["Reoxy half-time", ht_value, ht_interp],
        ["HR-SmO2 r", f"{coupling:.2f}", coup_interp],
    ]

    bench_table = Table(bench_data, colWidths=[40 * mm, 40 * mm, 85 * mm])
    bench_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1F77B4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
                ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "DejaVuSans-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#555555")),
                ("ROWHEIGHT", (0, 0), (-1, -1), 9 * mm),
                ("BACKGROUND", (0, 1), (-1, 1), HexColor("#f5f5f5")),
                ("TEXTCOLOR", (0, 1), (-1, 1), HexColor("#333333")),
                ("BACKGROUND", (0, 2), (-1, 2), HexColor("#e8e8e8")),
                ("TEXTCOLOR", (0, 2), (-1, 2), HexColor("#333333")),
                ("BACKGROUND", (0, 3), (-1, 3), HexColor("#f5f5f5")),
                ("TEXTCOLOR", (0, 3), (-1, 3), HexColor("#333333")),
            ]
        )
    )
    elements.append(bench_table)
    elements.append(Spacer(1, 6 * mm))
    return elements


def _build_smo2_conclusion_box(limiter_type: str, styles: Dict) -> List:
    """Build conclusive statement box for SmO2 page."""
    if limiter_type == "central":
        conclusion = (
            "<b>WNIOSEK:</b> Poprawa VO2max da realny wzrost mocy tylko jeśli utrzymasz "
            "niską okluzję mechaniczną. Priorytet: treningi Z2/Z3 + interwały <95% HR max."
        )
        conclusion_color = "#E74C3C"
    elif limiter_type == "local":
        conclusion = (
            "<b>WNIOSEK:</b> Perfuzja mięśniowa jest limitująca - poprawa siły lub kadencji "
            "może zredukować okluzję i zwolnić desaturację. Priorytet: Strength Endurance."
        )
        conclusion_color = "#3498DB"
    else:
        conclusion = (
            "<b>WNIOSEK:</b> Balans miedzy dostawa a zuzycie O2 jest dobry. "
            "Kontynuuj zroznicowany trening, monitorujac SmO2 w sesjach tempo."
        )
        conclusion_color = "#27AE60"

    conclusion_style = ParagraphStyle(
        "conclusion", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9
    )
    conclusion_box = Table([[Paragraph(conclusion, conclusion_style)]], colWidths=[165 * mm])
    conclusion_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(conclusion_color)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [conclusion_box]


def build_page_smo2(smo2_data, smo2_manual, figure_paths, styles):
    """Build SmO2 analysis page - PREMIUM MUSCLE OXYGENATION DIAGNOSTIC."""
    elements: List = []
    smo2_advanced = smo2_data.get("advanced_metrics", {}) or {}

    elements.append(
        Paragraph("<font size='14'>3.3 OKSYGENACJA MIĘŚNIOWA (SmO₂)</font>", styles["center"])
    )
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Kliniczna analiza dostawy i wykorzystania tlenu</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    elements.extend(_build_smo2_metric_cards(smo2_advanced, styles))
    elements.extend(_build_smo2_mechanism_panel(smo2_advanced, styles))
    elements.extend(_build_smo2_threshold_cards(smo2_manual, styles))

    limiter_type = smo2_advanced.get("limiter_type", "unknown")
    elements.extend(_build_smo2_recommendation_cards(smo2_advanced, limiter_type, styles))

    if figure_paths and "smo2_power" in figure_paths:
        elements.append(Spacer(1, 4 * mm))
        elements.extend(_build_chart(figure_paths["smo2_power"], "SmO₂ vs Power Profile", styles))

    data_quality = smo2_advanced.get("data_quality", "unknown")
    quality_color, quality_label = _classify_smo2_data_quality(data_quality)
    elements.append(Spacer(1, 4 * mm))
    elements.append(
        Paragraph(
            f"<font size='8' color='#7F8C8D'>Data Quality: </font>"
            f"<font size='8' color='{quality_color}'><b>{quality_label}</b></font>",
            styles["body"],
        )
    )

    slope = smo2_advanced.get("slope_per_100w", 0)
    halftime = smo2_advanced.get("halftime_reoxy_sec")
    coupling = smo2_advanced.get("hr_coupling_r", 0)
    elements.extend(_build_smo2_benchmark_table(slope, halftime, coupling, styles))
    elements.extend(_build_smo2_conclusion_box(limiter_type, styles))

    return elements


# ============================================================================
# PAGE 3: POWER-DURATION CURVE / CP
# ============================================================================


def build_page_pdc(
    cp_model: Dict[str, Any], metadata: Dict[str, Any], figure_paths: Dict[str, str], styles: Dict
) -> List:
    """Build Page 3: Power-Duration Curve and Critical Power.

    Contains:
    - PDC explanation
    - CP/W' table
    - PDC chart
    """
    elements = []

    elements.append(Paragraph("<font size='14'>2.5 KRZYWA MOCY (PDC)</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))

    # === EXPLANATION ===
    elements.append(
        Paragraph(
            "Krzywa mocy pokazuje, jak długo możesz utrzymać dany poziom wysiłku.", styles["body"]
        )
    )
    elements.append(
        Paragraph(
            "<b>CP (Critical Power)</b> to moc, którą teoretycznie możesz utrzymać bardzo długo. "
            "W praktyce oznacza to maksymalny wysiłek przez 30-60 minut.",
            styles["body"],
        )
    )
    elements.append(
        Paragraph(
            "<b>W' (W-prime)</b> to Twoja rezerwa energetyczna powyżej CP. "
            "Możesz ją „spalić” na ataki, podjazdy lub sprint.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # === CP/W' TABLE ===
    elements.append(Paragraph("Parametry CP", styles["heading"]))

    cp_watts = cp_model.get("cp_watts", "brak danych")
    w_prime_kj = cp_model.get("w_prime_kj", "brak danych")

    # Calculate CP/kg if weight available
    athlete_weight = metadata.get("athlete_weight_kg", 0)
    if athlete_weight and cp_watts != "brak danych":
        try:
            cp_per_kg = f"{float(cp_watts) / athlete_weight:.2f}"
        except (ValueError, TypeError):
            cp_per_kg = "brak danych"
    else:
        cp_per_kg = "brak danych"

    data = [
        ["Parametr", "Wartość", "Znaczenie"],
        ["CP", f"{cp_watts} W", "Moc „długotrwała”"],
        ["CP/kg", f"{cp_per_kg} W/kg", "Względna wydolność"],
        ["W'", f"{w_prime_kj} kJ", "Rezerwa anaerobowa"],
    ]

    table = Table(data, colWidths=[45 * mm, 45 * mm, 55 * mm])
    table.setStyle(get_table_style())
    elements.append(table)
    elements.append(Spacer(1, 8 * mm))

    # === PDC CHART ===
    if figure_paths and "pdc_curve" in figure_paths:
        elements.extend(_build_chart(figure_paths["pdc_curve"], "Power-Duration Curve", styles))

    # === EDUCATION BLOCK: CP/W' ===
    elements.append(Spacer(1, 6 * mm))
    elements.extend(
        _build_education_block(
            "Dlaczego to ma znaczenie? (CP / W')",
            "Model CP/W' to Twoja cyfrowa bateria, która mówi na co Cię stać w decydującym momencie wyścigu. "
            "Critical Power (CP) to Twoja najwyższa moc „długodystansowa”, utrzymywana bez wyczerpania rezerw. "
            "W' to Twój „bak paliwa” na ataki, krótkie podjazdy i sprinty powyżej mocy progowej. "
            "Każdy skok powyżej CP kosztuje konkretną ilość dżuli, a regeneracja następuje dopiero poniżej tego progu. "
            "Rozumienie tego balansu pozwala decydować, czy odpowiedzieć na atak, czy czekać na swoją szansę. "
            "To serce Twojej strategii, które mówi nam, jak optymalnie zarządzać Twoimi siłami.",
            styles,
        )
    )

    # Additional theory - FAKT / INTERPRETACJA / AKCJA structure
    elements.append(Spacer(1, 4 * mm))
    elements.append(
        Paragraph(
            "<font color='#3498DB'><b>● FAKT:</b></font> Każdy skok powyżej CP kosztuje konkretną ilość dżuli z W'. "
            "Przy W'=15kJ i mocy 50W powyżej CP, wystarczy na ~5 min powyżej progu.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            "<font color='#9B59B6'><b>● INTERPRETACJA:</b></font> Regeneracja W' zachodzi TYLKO poniżej CP. "
            "Im głębiej poniżej CP, tym szybsza regeneracja (ok. 1-2% W'/s przy głębokim Z2).",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            "<font color='#27AE60'><b>● AKCJA:</b></font> W ataku kalkuluj koszt: krótki intensywny atak (30s @ +100W) kosztuje ~3kJ. "
            "Czy masz rezerwę? Decyduj na podstawie danych, nie intuicji.",
            styles["body"],
        )
    )

    return elements


# ============================================================================
# PAGE 4: INTERPRETACJA WYNIKÓW
# ============================================================================


def build_page_interpretation(
    thresholds: Dict[str, Any], cp_model: Dict[str, Any], styles: Dict
) -> List:
    """Build Page 4: Results Interpretation.

    Contains:
    - VT1 explanation with values + CHO/metabolic info + example workouts
    - VT2 explanation with values + CHO/metabolic info + example workouts
    - Tempo zone explanation + substrate usage
    - CP practical usage + pacing examples
    """
    elements = []

    elements.append(
        Paragraph("<font size='14'>2.2 CO OZNACZAJĄ TE WYNIKI?</font>", styles["center"])
    )
    elements.append(Spacer(1, 6 * mm))

    vt1_watts_raw = thresholds.get("vt1_watts", "brak danych")
    vt2_watts_raw = thresholds.get("vt2_watts", "brak danych")
    cp_watts_raw = cp_model.get("cp_watts", "brak danych")

    # Convert to numeric values for calculations
    try:
        vt1_num = (
            float(vt1_watts_raw) if vt1_watts_raw not in [None, "brak danych", "---"] else None
        )
    except (ValueError, TypeError):
        vt1_num = None

    try:
        vt2_num = (
            float(vt2_watts_raw) if vt2_watts_raw not in [None, "brak danych", "---"] else None
        )
    except (ValueError, TypeError):
        vt2_num = None

    try:
        cp_num = float(cp_watts_raw) if cp_watts_raw not in [None, "brak danych", "---"] else None
    except (ValueError, TypeError):
        cp_num = None

    # Format display values
    vt1_watts = f"{vt1_num:.0f}" if vt1_num else "brak danych"
    vt2_watts = f"{vt2_num:.0f}" if vt2_num else "brak danych"
    cp_watts = f"{cp_num:.0f}" if cp_num else "brak danych"

    # === VT1 ===
    elements.append(Paragraph("Próg tlenowy (VT1)", styles["heading"]))
    elements.append(
        Paragraph(
            f"Twój próg tlenowy wynosi około <b>{vt1_watts} W</b>. "
            "To moc, przy której możesz jechać komfortowo przez wiele godzin. "
            "Oddychasz spokojnie, możesz swobodnie rozmawiać. "
            "Treningi poniżej VT1 budują bazę tlenową i służą regeneracji.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            "<b>Metabolizm:</b> Poniżej VT1 spalasz głównie tłuszcze (~60-70% energii z lipidów). "
            "Zużycie węglowodanów (CHO) wynosi ok. <b>30-50g/h</b>. "
            "To strefa idealna do długich treningów bez uzupełniania CHO.",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            f"<b>Przykładowe jednostki:</b> "
            f"• Regeneracja: 60-90 min @ {int(vt1_num * 0.65) if vt1_num else '?'}-{int(vt1_num * 0.75) if vt1_num else '?'} W | "
            f"• Baza aerobowa: 2-4h @ {int(vt1_num * 0.8) if vt1_num else '?'}-{vt1_watts} W",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # === VT2 ===
    elements.append(Paragraph("Próg beztlenowy (VT2)", styles["heading"]))
    elements.append(
        Paragraph(
            f"Twój próg beztlenowy wynosi około <b>{vt2_watts} W</b>. "
            "Powyżej tej mocy wysiłek staje się bardzo wymagający. "
            "Oddychasz ciężko, nie możesz swobodnie mówić. "
            "Treningi powyżej VT2 rozwijają VO₂max, ale wymagają pełnej regeneracji.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            "<b>Metabolizm:</b> Powyżej VT2 dominuje glikoliza beztlenowa. "
            "Zużycie CHO rośnie do <b>90-120g/h</b>. Akumulacja mleczanu prowadzi do szybkiego zmęczenia. "
            "Wysiłek powyżej VT2 można utrzymać max 20-60 min.",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            f"<b>Przykładowe jednostki:</b> "
            f"• VO₂max: 5×5 min @ {int(vt2_num * 1.05) if vt2_num else '?'}-{int(vt2_num * 1.15) if vt2_num else '?'} W (4 min odpoczynku) | "
            f"• Tolerancja mleczanu: 3×8 min @ {vt2_watts} W (5 min odpoczynku)",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # === TEMPO ZONE ===
    elements.append(Paragraph("Strefa Tempo", styles["heading"]))
    elements.append(
        Paragraph(
            f"Strefa między <b>{vt1_watts}</b> a <b>{vt2_watts} W</b> to Twoja strefa 'tempo'. "
            "Jest idealna do treningu wytrzymałościowego i poprawy progu. "
            "W tej strefie możesz spędzać znaczną część czasu treningowego bez nadmiernego zmęczenia.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            "<b>Metabolizm:</b> W strefie tempo następuje przejście z lipidów na CHO. "
            "Spalanie tłuszczów spada do ~30-40%, rośnie zużycie CHO (<b>60-80g/h</b>). "
            "To strefa kluczowa dla rozwoju FatMax i przesunięcia krzywej spalania.",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 2 * mm))

    tempo_mid = ""
    if vt1_num and vt2_num:
        tempo_mid = f"{int((vt1_num + vt2_num) / 2)}"

    elements.append(
        Paragraph(
            f"<b>Przykładowe jednostki:</b> "
            f"• Sweet Spot: 2×20 min @ {tempo_mid if tempo_mid else '?'}-{int(vt2_num * 0.94) if vt2_num else '?'} W | "
            f"• Tempo długie: 1×45-60 min @ {vt1_watts}-{tempo_mid if tempo_mid else '?'} W",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # === CP ===
    elements.append(Paragraph("Critical Power", styles["heading"]))
    elements.append(
        Paragraph(
            f"CP ({cp_watts} W) to matematyczne przybliżenie Twojej mocy progowej. "
            "Możesz używać tej wartości do planowania interwałów i wyznaczania stref treningowych. "
            "CP jest przydatne do pacing'u podczas zawodów i długich treningów.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            "<b>Praktyka:</b> CP reprezentuje moc możliwą do utrzymania przez ~30-60 min. "
            "Treningi @ CP rozwijają próg mleczanowy i wydolność tlenową. "
            "Używaj CP jako górnej granicy dla długich, rytmicznych interwałów.",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 2 * mm))
    elements.append(
        Paragraph(
            f"<b>Przykładowe jednostki:</b> "
            f"• Under/Over: 3×12 min (2 min @ {int(cp_num * 0.92) if cp_num else '?'} W / 1 min @ {int(cp_num * 1.08) if cp_num else '?'} W) | "
            f"• Threshold: 2×20 min @ {int(cp_num * 0.95) if cp_num else '?'}-{cp_watts} W",
            styles["small"],
        )
    )

    return elements


# ============================================================================
# PAGE: CARDIOVASCULAR COST DIAGNOSTIC (PREMIUM)
# ============================================================================


def build_page_cardiovascular(cardio_data: Dict[str, Any], styles: Dict) -> List:
    """Build Cardiovascular Cost Diagnostic page - PREMIUM."""
    from reportlab.lib.colors import HexColor

    elements = []

    # ==========================================================================
    # HEADER
    # ==========================================================================
    elements.append(
        Paragraph("<font size='14'>3.2 UKŁAD SERCOWO-NACZYNIOWY</font>", styles["center"])
    )
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Diagnostyka kosztu sercowego generowania mocy</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # Extract metrics
    pp = cardio_data.get("pulse_power", 0)
    ef = cardio_data.get("efficiency_factor", 0)
    drift = cardio_data.get("hr_drift_pct", 0)
    recovery = cardio_data.get("hr_recovery_1min")
    cci = cardio_data.get("cci_avg", 0)
    cci_bp = cardio_data.get("cci_breakpoint_watts")
    status = cardio_data.get("efficiency_status", "unknown")
    confidence = cardio_data.get("efficiency_confidence", 0)
    interpretation = cardio_data.get("interpretation", "")
    recommendations = cardio_data.get("recommendations", [])

    # ==========================================================================
    # 1. METRIC CARDS
    # ==========================================================================

    def build_card(title, value, unit, interp, color):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='16' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
            Spacer(1, 1 * mm),
            Paragraph(f"<font size='8'>{interp}</font>", styles["center"]),
        ]
        card_table = Table([[card_content]], colWidths=[42 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return card_table

    # Pulse Power
    pp_color = "#2ECC71" if pp > 2.0 else ("#F39C12" if pp > 1.5 else "#E74C3C")
    pp_interp = "Efektywny" if pp > 2.0 else ("Umiarkowany" if pp > 1.5 else "Niski")
    card1 = build_card("MOC PULSOWA", f"{pp:.2f}", "W/bpm", pp_interp, pp_color)

    # Efficiency Factor
    ef_color = "#2ECC71" if ef > 1.8 else ("#F39C12" if ef > 1.4 else "#E74C3C")
    ef_interp = "Wysoki" if ef > 1.8 else ("Średni" if ef > 1.4 else "Niski")
    card2 = build_card("WSP. EFEKTYWNOŚCI", f"{ef:.2f}", "W/bpm", ef_interp, ef_color)

    # HR Drift
    drift_color = "#2ECC71" if drift < 3 else ("#F39C12" if drift < 6 else "#E74C3C")
    drift_interp = "Stabilny" if drift < 3 else ("Drift" if drift < 6 else "Wysoki Drift")
    card3 = build_card("DRYF HR", f"{drift:.1f}", "%", drift_interp, drift_color)

    # HR Recovery or CCI
    if recovery:
        rec_color = "#2ECC71" if recovery > 25 else ("#F39C12" if recovery > 15 else "#E74C3C")
        rec_interp = "Szybki" if recovery > 25 else ("Średni" if recovery > 15 else "Wolny")
        card4 = build_card("REGENERACJA HR", f"{recovery:.0f}", "bpm/min", rec_interp, rec_color)
    else:
        cci_color = "#2ECC71" if cci < 0.15 else ("#F39C12" if cci < 0.25 else "#E74C3C")
        cci_interp = "Efektywny" if cci < 0.15 else ("Średni" if cci < 0.25 else "Wysoki koszt")
        card4 = build_card("CCI (avg)", f"{cci:.3f}", "bpm/W", cci_interp, cci_color)

    cards_row = Table([[card1, card2, card3, card4]], colWidths=[44 * mm] * 4)
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 2. CCI METRIC PANEL
    # ==========================================================================

    elements.append(
        Paragraph("<b>INDEKS KOSZTU SERCOWO-NACZYNIOWEGO (CCI)</b>", styles["subheading"])
    )
    elements.append(Spacer(1, 2 * mm))

    cci_text = f"<b>CCI = {cci:.4f}</b> bpm/W – koszt tętna na jednostkę mocy."
    if cci_bp:
        cci_text += f" <b>Breakpoint</b> przy {cci_bp:.0f}W – punkt załamania efektywności."
    elements.append(Paragraph(cci_text, styles["body"]))
    elements.append(Spacer(1, 4 * mm))

    # ==========================================================================
    # 3. EFFICIENCY VERDICT PANEL
    # ==========================================================================

    elements.append(
        Paragraph("<b>WERDYKT EFEKTYWNOŚCI SERCOWO-NACZYNIOWEJ</b>", styles["subheading"])
    )
    elements.append(Spacer(1, 2 * mm))

    status_colors = {
        "efficient": "#2ECC71",
        "compensating": "#F39C12",
        "decompensating": "#E74C3C",
        "unknown": "#7F8C8D",
    }
    status_names = {
        "efficient": "EFEKTYWNY",
        "compensating": "KOMPENSUJĄCY",
        "decompensating": "DEKOMPENSUJĄCY",
        "unknown": "NIEOKREŚLONY",
    }
    status_icons = {"efficient": "✓", "compensating": "⚠", "decompensating": "✗", "unknown": "?"}

    st_color = HexColor(status_colors.get(status, "#7F8C8D"))
    st_name = status_names.get(status, "NIEOKREŚLONY")
    st_icon = status_icons.get(status, "?")

    verdict_content = [
        Paragraph(f"<font color='white'><b>{st_icon} {st_name}</b></font>", styles["center"]),
        Paragraph(
            f"<font size='10' color='white'>pewność: {confidence:.0%}</font>", styles["center"]
        ),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), st_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(verdict_table)
    elements.append(Spacer(1, 3 * mm))

    # Interpretation
    if interpretation:
        for line in interpretation.split("\n")[:3]:
            elements.append(Paragraph(line, styles["body"]))
    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 4. DECISION CARDS
    # ==========================================================================

    if recommendations:
        elements.append(Paragraph("<b>DECYZJE TRENINGOWE I ŚRODOWISKOWE</b>", styles["subheading"]))
        elements.append(Spacer(1, 3 * mm))

        type_colors = {
            "TRENINGOWA": "#3498DB",
            "ŚRODOWISKOWA": "#9B59B6",
            "REGENERACJA": "#1ABC9C",
            "WYDAJNOŚĆ": "#2ECC71",
            "DIAGNOSTYCZNA": "#E74C3C",
        }

        for rec in recommendations[:3]:
            rec_type = rec.get("type", "TRENINGOWA")
            action = rec.get("action", "---")
            expected = rec.get("expected", "---")
            risk = rec.get("risk", "low")

            type_color = type_colors.get(rec_type, "#7F8C8D")
            risk_color = (
                "#2ECC71" if risk == "low" else ("#F39C12" if risk == "medium" else "#E74C3C")
            )
            risk_label = (
                "NISKIE" if risk == "low" else ("ŚREDNIE" if risk == "medium" else "WYSOKIE")
            )

            card_content = [
                Paragraph(
                    f"<font size='9' color='{type_color}'><b>[{rec_type}]</b></font> {action}",
                    styles["body"],
                ),
                Paragraph(
                    f"<font size='8' color='#27AE60'>Spodziewany efekt: {expected}</font> | <font size='8' color='{risk_color}'>Ryzyko: {risk_label}</font>",
                    styles["body"],
                ),
            ]
            card_table = Table([[card_content]], colWidths=[170 * mm])
            card_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                        ("BOX", (0, 0), (-1, -1), 0.5, COLORS["border"]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            elements.append(card_table)
            elements.append(Spacer(1, 2 * mm))

    return elements


# ============================================================================
# PAGE: BREATHING & METABOLIC CONTROL DIAGNOSTIC (PREMIUM)
# ============================================================================


def build_page_ventilation(vent_data: Dict[str, Any], styles: Dict) -> List:
    """Build Breathing & Metabolic Control Diagnostic page - PREMIUM."""
    from reportlab.lib.colors import HexColor

    elements = []

    # ==========================================================================
    # HEADER
    # ==========================================================================
    elements.append(Paragraph("3. DIAGNOSTYKA UKŁADÓW", styles["title"]))
    elements.append(Paragraph("<font size='14'>3.1 KONTROLA ODDYCHANIA</font>", styles["center"]))
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Diagnostyka wentylacji i kontroli metabolicznej</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # Extract metrics
    ve_avg = vent_data.get("ve_avg", 0)
    ve_max = vent_data.get("ve_max", 0)
    vent_data.get("rr_avg", 0)
    rr_max = vent_data.get("rr_max", 0)
    ve_rr = vent_data.get("ve_rr_ratio", 0)
    ve_slope = vent_data.get("ve_slope", 0)
    ve_bp = vent_data.get("ve_breakpoint_watts")
    pattern = vent_data.get("breathing_pattern", "unknown")
    status = vent_data.get("control_status", "unknown")
    confidence = vent_data.get("control_confidence", 0)
    interpretation = vent_data.get("interpretation", "")
    recommendations = vent_data.get("recommendations", [])

    # ==========================================================================
    # 1. METRIC CARDS
    # ==========================================================================

    def build_card(title, value, unit, interp, color):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='14' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
            Paragraph(f"<font size='7'>{interp}</font>", styles["center"]),
        ]
        card_table = Table([[card_content]], colWidths=[42 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return card_table

    # VE
    ve_color = "#2ECC71" if ve_max < 120 else ("#F39C12" if ve_max < 150 else "#E74C3C")
    card1 = build_card("VE MAX", f"{ve_max:.0f}", "L/min", f"avg: {ve_avg:.0f}", ve_color)

    # RR
    rr_color = "#2ECC71" if rr_max < 45 else ("#F39C12" if rr_max < 55 else "#E74C3C")
    rr_interp = "Ekonomiczny" if rr_max < 45 else ("Podwyższony" if rr_max < 55 else "Wysoki")
    card2 = build_card("RR MAX", f"{rr_max:.0f}", "/min", rr_interp, rr_color)

    # VE/RR
    verr_color = "#2ECC71" if ve_rr > 2.5 else ("#F39C12" if ve_rr > 1.5 else "#E74C3C")
    verr_interp = "Głęboki oddech" if ve_rr > 2.5 else ("Średni" if ve_rr > 1.5 else "Płytki")
    card3 = build_card("VE/RR RATIO", f"{ve_rr:.2f}", "L/breath", verr_interp, verr_color)

    # VE Slope
    slope_color = "#2ECC71" if ve_slope < 0.25 else ("#F39C12" if ve_slope < 0.4 else "#E74C3C")
    slope_interp = "Stabilny" if ve_slope < 0.25 else ("Rosnący" if ve_slope < 0.4 else "Stromy")
    card4 = build_card("VE SLOPE", f"{ve_slope:.2f}", "L/min/100W", slope_interp, slope_color)

    cards_row = Table([[card1, card2, card3, card4]], colWidths=[44 * mm] * 4)
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 2. BREATHING PATTERN
    # ==========================================================================

    pattern_colors = {
        "efficient": "#2ECC71",
        "shallow": "#E74C3C",
        "hyperventilation": "#F39C12",
        "mixed": "#7F8C8D",
        "unknown": "#7F8C8D",
    }
    pattern_names = {
        "efficient": "EFEKTYWNY ODDECH",
        "shallow": "PŁYTKI/PANIKA",
        "hyperventilation": "HIPERWENTYLACJA",
        "mixed": "WZÓR MIESZANY",
        "unknown": "NIEOKREŚLONY",
    }

    elements.append(Paragraph("<b>WYKRYWANIE WZORCA ODDECHOWEGO</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    pattern_badge = Paragraph(
        f"<font color='white'><b>{pattern_names.get(pattern, 'UNDEFINED')}</b></font>",
        styles["center"],
    )
    pattern_table = Table([[pattern_badge]], colWidths=[170 * mm])
    pattern_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(pattern_colors.get(pattern, "#7F8C8D"))),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(pattern_table)
    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 3. VE BREAKPOINT
    # ==========================================================================

    if ve_bp:
        elements.append(Paragraph("<b>PUNKT ZAŁAMANIA WENTYLACJI</b>", styles["subheading"]))
        elements.append(Spacer(1, 2 * mm))
        elements.append(
            Paragraph(
                f"Wentylacja przyspiesza gwałtownie powyżej <b>{ve_bp:.0f} W</b>. "
                "Powyżej tej mocy oddychasz coraz ciężej przy każdym dodatkowym wacie.",
                styles["body"],
            )
        )
        elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 4. CONTROL STATUS VERDICT
    # ==========================================================================

    control_colors = {
        "efficient": "#2ECC71",
        "compensating": "#F39C12",
        "decompensating": "#E74C3C",
        "unknown": "#7F8C8D",
    }
    control_names = {
        "efficient": "EFEKTYWNA KONTROLA",
        "compensating": "KONTROLA KOMPENSACYJNA",
        "decompensating": "UTRATA KONTROLI",
        "unknown": "NIEOKREŚLONY",
    }
    control_icons = {"efficient": "✓", "compensating": "⚠", "decompensating": "✗", "unknown": "?"}

    elements.append(Paragraph("<b>WERDYKT KONTROLI METABOLICZNEJ</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    ct_color = HexColor(control_colors.get(status, "#7F8C8D"))
    ct_name = control_names.get(status, "NIEOKREŚLONY")
    ct_icon = control_icons.get(status, "?")

    verdict_content = [
        Paragraph(f"<font color='white'><b>{ct_icon} {ct_name}</b></font>", styles["center"]),
        Paragraph(
            f"<font size='10' color='white'>pewność: {confidence:.0%}</font>", styles["center"]
        ),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ct_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(verdict_table)
    elements.append(Spacer(1, 3 * mm))

    if interpretation:
        for line in interpretation.split("\n")[:3]:
            elements.append(Paragraph(line, styles["body"]))
    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 5. DECISION CARDS
    # ==========================================================================

    if recommendations:
        elements.append(Paragraph("<b>DECYZJE TRENINGOWE</b>", styles["subheading"]))
        elements.append(Spacer(1, 3 * mm))

        for rec in recommendations[:3]:
            action = rec.get("action", "---")
            expected = rec.get("expected", "---")

            card_content = [
                Paragraph(f"<font size='10'><b>{action}</b></font>", styles["body"]),
                Paragraph(
                    f"<font size='8' color='#27AE60'>Spodziewany efekt: {expected}</font>",
                    styles["body"],
                ),
            ]
            card_table = Table([[card_content]], colWidths=[170 * mm])
            card_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                        ("BOX", (0, 0), (-1, -1), 0.5, COLORS["border"]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            elements.append(card_table)
            elements.append(Spacer(1, 2 * mm))

    return elements


# ============================================================================
# PAGE: METABOLIC ENGINE DIAGNOSTIC (PREMIUM)
# ============================================================================


def build_page_metabolic_engine(metabolic_data: Dict[str, Any], styles: Dict) -> List:
    """Build Metabolic Engine Diagnostic page - PREMIUM."""
    from reportlab.lib.colors import HexColor

    elements = []

    elements.append(Paragraph("<font size='14'>3.4 SILNIK METABOLICZNY</font>", styles["center"]))
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Analiza substratów energetycznych i efektywności utylizacji</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    fat_max = metabolic_data.get("fat_max_watts", 0)
    fat_max_pct = metabolic_data.get("fat_max_pct", 0)
    cho_cross = metabolic_data.get("cho_crossover_watts")
    zone_fat = metabolic_data.get("fat_burning_zone", {})
    zone_cho = metabolic_data.get("cho_zone", {})
    status = metabolic_data.get("metabolic_status", "unknown")
    confidence = metabolic_data.get("metabolic_confidence", 0)
    interpretation = metabolic_data.get("interpretation", "")
    recommendations = metabolic_data.get("recommendations", [])

    def build_card(title, value, unit, interp, color):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='14' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
            Paragraph(f"<font size='7'>{interp}</font>", styles["center"]),
        ]
        card_table = Table([[card_content]], colWidths=[42 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return card_table

    fat_color = "#2ECC71" if fat_max_pct > 60 else ("#F39C12" if fat_max_pct > 40 else "#E74C3C")
    card1 = build_card("FATMAX", f"{fat_max:.0f}", "W", f"{fat_max_pct:.0f}% tłuszczów", fat_color)

    if cho_cross:
        cho_color = "#2ECC71" if cho_cross > 200 else ("#F39C12" if cho_cross > 150 else "#E74C3C")
        cho_interp = (
            "Późny crossover"
            if cho_cross > 200
            else ("Wczesny" if cho_cross > 150 else "Bardzo wczesny")
        )
        card2 = build_card("CHO CROSSOVER", f"{cho_cross:.0f}", "W", cho_interp, cho_color)
    else:
        card2 = build_card("CHO CROSSOVER", "---", "W", "Brak danych", "#7F8C8D")

    fat_zone_str = f"{zone_fat.get('low', 0):.0f}–{zone_fat.get('high', 0):.0f}"
    card3 = build_card("STREFA TŁUSZCZÓW", fat_zone_str, "W", "Optimal fat burn", "#3498DB")

    cho_zone_str = f"{zone_cho.get('low', 0):.0f}–{zone_cho.get('high', 0):.0f}"
    card4 = build_card("STREFA CHO", cho_zone_str, "W", "Dominant CHO", "#E74C3C")

    cards_row = Table([[card1, card2, card3, card4]], colWidths=[44 * mm] * 4)
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))

    # Verdict
    status_colors = {
        "efficient": "#2ECC71",
        "compensating": "#F39C12",
        "decompensating": "#E74C3C",
        "unknown": "#7F8C8D",
    }
    status_names = {
        "efficient": "EFEKTYWNY",
        "compensating": "KOMPENSUJĄCY",
        "decompensating": "DEKOMPENSUJĄCY",
        "unknown": "NIEOKREŚLONY",
    }

    elements.append(Paragraph("<b>WERDYKT SILNIKA METABOLICZNEGO</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    st_color = HexColor(status_colors.get(status, "#7F8C8D"))
    st_name = status_names.get(status, "NIEOKREŚLONY")

    verdict_content = [
        Paragraph(f"<font color='white'><b>{st_name}</b></font>", styles["center"]),
        Paragraph(
            f"<font size='10' color='white'>pewność: {confidence:.0%}</font>", styles["center"]
        ),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), st_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(verdict_table)
    elements.append(Spacer(1, 3 * mm))

    if interpretation:
        for line in interpretation.split("\n")[:3]:
            elements.append(Paragraph(line, styles["body"]))
    elements.append(Spacer(1, 6 * mm))

    if recommendations:
        elements.append(Paragraph("<b>DECYZJE TRENINGOWE</b>", styles["subheading"]))
        elements.append(Spacer(1, 3 * mm))

        for rec in recommendations[:3]:
            action = rec.get("action", "---")
            expected = rec.get("expected", "---")

            card_content = [
                Paragraph(f"<font size='10'><b>{action}</b></font>", styles["body"]),
                Paragraph(
                    f"<font size='8' color='#27AE60'>Spodziewany efekt: {expected}</font>",
                    styles["body"],
                ),
            ]
            card_table = Table([[card_content]], colWidths=[170 * mm])
            card_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                        ("BOX", (0, 0), (-1, -1), 0.5, COLORS["border"]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            elements.append(card_table)
            elements.append(Spacer(1, 2 * mm))

    return elements


# ============================================================================
# PAGE: LIMITER RADAR
# ============================================================================


def build_page_limiter_radar(limiter_data: Dict[str, Any], styles: Dict) -> List:
    """Build Limiter Radar page."""
    elements = []

    elements.append(Paragraph("4. ANALIZA LIMITERÓW", styles["title"]))
    elements.append(Spacer(1, 6 * mm))

    limiters = limiter_data.get("limiters", [])

    if not limiters:
        elements.append(Paragraph("Brak danych o limiterach.", styles["body"]))
        return elements

    for limiter in limiters:
        name = limiter.get("name", "Unknown")
        score = limiter.get("score", 0)
        severity = limiter.get("severity", "medium")
        description = limiter.get("description", "")

        severity_colors = {"low": "#2ECC71", "medium": "#F39C12", "high": "#E74C3C"}
        color = severity_colors.get(severity, "#7F8C8D")

        card_content = [
            Paragraph(f"<b>{name}</b> — Score: {score:.0f}/100", styles["body"]),
            Paragraph(f"<font size='8'>{description}</font>", styles["body"]),
        ]
        card_table = Table([[card_content]], colWidths=[170 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(card_table)
        elements.append(Spacer(1, 3 * mm))

    return elements


# ============================================================================
# PAGE: ZONES
# ============================================================================


def build_page_zones(thresholds: Dict[str, Any], cp_model: Dict[str, Any], styles: Dict) -> List:
    """Build Training Zones page."""
    elements = []

    elements.append(Paragraph("STREFY TRENINGOWE", styles["title"]))
    elements.append(Spacer(1, 6 * mm))

    vt1 = thresholds.get("vt1_watts", 0)
    vt2 = thresholds.get("vt2_watts", 0)
    cp = cp_model.get("cp_watts", 0)

    try:
        vt1 = float(vt1)
    except (ValueError, TypeError):
        vt1 = 0
    try:
        vt2 = float(vt2)
    except (ValueError, TypeError):
        vt2 = 0
    try:
        cp = float(cp)
    except (ValueError, TypeError):
        cp = 0

    zones = [
        ("Z1 Recovery", 0, vt1 * 0.8 if vt1 else 0, "Regeneracja"),
        ("Z2 Endurance", vt1 * 0.8 if vt1 else 0, vt1, "Baza tlenowa"),
        ("Z3 Tempo", vt1, vt2, "Wytrzymałość progowa"),
        ("Z4 Threshold", vt2, vt2 * 1.05 if vt2 else 0, "Próg mleczanowy"),
        ("Z5 VO₂max", vt2 * 1.05 if vt2 else 0, 9999, "Pułap tlenowy"),
    ]

    data = [["Strefa", "Zakres [W]", "Opis"]]
    for name, low, high, desc in zones:
        high_str = f"{int(high)}" if high < 9999 else "+"
        data.append([name, f"{int(low)}–{high_str}", desc])

    table = Table(data, colWidths=[45 * mm, 45 * mm, 65 * mm])
    table.setStyle(get_table_style())
    elements.append(table)

    return elements


# ============================================================================
# PAGE: LIMITATIONS
# ============================================================================


def build_page_limitations(limitations_data: Dict[str, Any], styles: Dict) -> List:
    """Build Limitations page."""
    elements = []

    elements.append(Paragraph("5. OGRANICZENIA I UWAGI", styles["title"]))
    elements.append(Spacer(1, 6 * mm))

    limitations = limitations_data.get("limitations", [])

    if not limitations:
        elements.append(Paragraph("Brak zidentyfikowanych ograniczeń.", styles["body"]))
        return elements

    for lim in limitations:
        title = lim.get("title", "")
        severity = lim.get("severity", "info")
        description = lim.get("description", "")

        severity_colors = {"info": "#3498DB", "warning": "#F39C12", "error": "#E74C3C"}
        color = severity_colors.get(severity, "#7F8C8D")

        card_content = [
            Paragraph(f"<b>{title}</b>", styles["body"]),
            Paragraph(f"<font size='8'>{description}</font>", styles["body"]),
        ]
        card_table = Table([[card_content]], colWidths=[170 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(card_table)
        elements.append(Spacer(1, 3 * mm))

    return elements


# ============================================================================
# INTERNAL HELPERS
# ============================================================================


def _build_chart(chart_path: str, title: str, styles: Dict) -> List:
    """Build a chart image element with error handling."""
    elements = []
    try:
        if os.path.exists(chart_path):
            img = Image(chart_path, width=170 * mm, height=95 * mm)
            elements.append(img)
            if title:
                elements.append(Spacer(1, 2 * mm))
        else:
            logger.warning(f"PDF Layout: Chart file missing for '{title}' at path: {chart_path}")
            if title:
                elements.append(Paragraph(f"<i>{title} — brak wykresu</i>", styles["small"]))
    except (OSError, IOError) as e:
        logger.error(f"PDF Layout: Error embedding chart '{title}' from {chart_path}: {e}")
        elements.append(Paragraph(f"<i>{title} — błąd wczytywania</i>", styles["small"]))
    return elements


def _build_education_block(title: str, content: str, styles: Dict) -> List:
    """Build an education/theory block with styled box."""
    elements = []
    box_content = [
        Paragraph(f"<b>{title}</b>", styles["subheading"]),
        Spacer(1, 2 * mm),
        Paragraph(content, styles["small"]),
    ]
    box_table = Table([[box_content]], colWidths=[170 * mm])
    box_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                ("BOX", (0, 0), (-1, -1), 0.5, COLORS["border"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(box_table)
    return elements


# ============================================================================
# PAGE: THEORY
# ============================================================================


def build_page_theory(styles: Dict) -> List:
    """Build Theory/Education page."""
    elements = []

    elements.append(Paragraph("TEORIA I METODOLOGIA", styles["title"]))
    elements.append(Spacer(1, 6 * mm))

    elements.extend(
        _build_education_block(
            "Model CP/W' — Teoria",
            "Model Critical Power (CP) i W' (W-prime) został opracowany przez H. Monoda i H. Scherrera w 1965 roku. "
            "CP reprezentuje najwyższą moc, jaką sportowiec może utrzymać przez dłuższy czas bez wyczerpania rezerw anaerobowych. "
            "W' to finite work capacity above CP — rezerwa energii dostępna na wysiłki powyżej CP.",
            styles,
        )
    )
    elements.append(Spacer(1, 4 * mm))

    elements.extend(
        _build_education_block(
            "Progi Wentylacyjne — VT1 i VT2",
            "VT1 (First Ventilatory Threshold) to punkt, w którym wentylacja zaczyna rosnąć nieliniowo względem mocy. "
            "VT2 (Second Ventilatory Threshold / RCP) to punkt, w którym wentylacja przyspiesza gwałtownie "
            "z powodu kompensacji kwasu mlekowego (respiratory compensation point). "
            "Te dwa progi są kluczowymi markerami intensywności treningowej.",
            styles,
        )
    )
    elements.append(Spacer(1, 4 * mm))

    elements.extend(
        _build_education_block(
            "Określanie Stref Treningowych",
            "Strefy treningowe są wyznaczane na podstawie VT1, VT2 i CP. "
            "Z1 (Recovery): poniżej 80% VT1 — regeneracja. "
            "Z2 (Endurance): 80% VT1 do VT1 — baza tlenowa. "
            "Z3 (Tempo): VT1 do VT2 — wytrzymałość progowa. "
            "Z4 (Threshold): VT2 do 105% VT2 — tolerancja mleczanowa. "
            "Z5 (VO₂max): powyżej 105% VT2 — rozwój pułapu tlenowego.",
            styles,
        )
    )

    return elements


# ============================================================================
# PAGE: PROTOCOL
# ============================================================================


def build_page_protocol(metadata: Dict[str, Any] = None, styles: Dict = None) -> List:
    """Build Test Protocol page."""
    elements = []

    elements.append(Paragraph("PROTOKÓŁ TESTU", styles["title"]))
    elements.append(Spacer(1, 6 * mm))

    if metadata and styles:
        test_type = metadata.get("test_type", "Ramp Test")
        start_power = metadata.get("test_start_power", "---")
        end_power = metadata.get("test_end_power", "---")
        step_duration = metadata.get("step_duration", "3 min")
        step_increment = metadata.get("step_increment", "30 W")
        test_duration = metadata.get("test_duration", "---")

        elements.append(Paragraph(f"<b>Typ testu:</b> {test_type}", styles["body"]))
        elements.append(Paragraph(f"<b>Moc początkowa:</b> {start_power} W", styles["body"]))
        elements.append(Paragraph(f"<b>Moc końcowa:</b> {end_power} W", styles["body"]))
        elements.append(Paragraph(f"<b>Czas kroku:</b> {step_duration}", styles["body"]))
        elements.append(Paragraph(f"<b>Przyrost:</b> {step_increment}", styles["body"]))
        elements.append(Paragraph(f"<b>Całkowity czas:</b> {test_duration}", styles["body"]))
    else:
        elements.append(Paragraph("Brak metadanych protokołu.", styles["body"]))

    return elements


# ============================================================================
# PAGE: THERMAL
# ============================================================================


def build_page_thermal(
    thermal_data: Dict[str, Any], figure_paths: Dict[str, str], styles: Dict
) -> List:
    """Build Thermal Analysis page."""
    elements = []

    elements.append(Paragraph("<font size='14'>3.5 ANALIZA TERMICZNA</font>", styles["center"]))
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Monitorowanie temperatury rdzeniowej i stresu cieplnego</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    core_temp_avg = thermal_data.get("core_temp_avg", 0)
    core_temp_max = thermal_data.get("core_temp_max", 0)
    thermal_data.get("skin_temp_avg", 0)
    heat_strain_index = thermal_data.get("heat_strain_index", 0)
    thermal_drift_rate = thermal_data.get("thermal_drift_rate", 0)
    thermal_data.get("thermal_status", "unknown")

    def build_card(title, value, unit, interp, color):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='14' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
            Paragraph(f"<font size='7'>{interp}</font>", styles["center"]),
        ]
        card_table = Table([[card_content]], colWidths=[42 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return card_table

    ct_color = (
        "#2ECC71" if core_temp_max < 38.5 else ("#F39C12" if core_temp_max < 39.0 else "#E74C3C")
    )
    card1 = build_card(
        "TEMP. RDZENIOWA", f"{core_temp_max:.1f}", "°C", f"avg: {core_temp_avg:.1f}°C", ct_color
    )

    hsi_color = (
        "#2ECC71" if heat_strain_index < 3 else ("#F39C12" if heat_strain_index < 5 else "#E74C3C")
    )
    hsi_interp = (
        "Niski" if heat_strain_index < 3 else ("Średni" if heat_strain_index < 5 else "Wysoki")
    )
    card2 = build_card("HEAT STRAIN INDEX", f"{heat_strain_index:.1f}", "", hsi_interp, hsi_color)

    drift_color = (
        "#2ECC71"
        if abs(thermal_drift_rate) < 0.1
        else ("#F39C12" if abs(thermal_drift_rate) < 0.3 else "#E74C3C")
    )
    drift_interp = (
        "Stabilna"
        if abs(thermal_drift_rate) < 0.1
        else ("Umiarkowany" if abs(thermal_drift_rate) < 0.3 else "Wysoki")
    )
    card3 = build_card(
        "DRYF TERMICZNY", f"{thermal_drift_rate:.2f}", "°C/h", drift_interp, drift_color
    )

    cards_row = Table([[card1, card2, card3]], colWidths=[58 * mm] * 3)
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))

    if figure_paths and "thermal_profile" in figure_paths:
        elements.extend(_build_chart(figure_paths["thermal_profile"], "Profil Termiczny", styles))

    return elements


# ============================================================================
# PAGE: BIOMECH
# ============================================================================


def build_page_biomech(
    biomech_data: Dict[str, Any], figure_paths: Dict[str, str], styles: Dict
) -> List:
    """Build Biomechanics Analysis page."""
    elements = []

    elements.append(Paragraph("<font size='14'>3.6 BIOMECHANIKA</font>", styles["center"]))
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Analiza dynamiki biegu i asymetrii</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    gct = biomech_data.get("gct_avg", 0)
    biomech_data.get("gct_left", 0)
    biomech_data.get("gct_right", 0)
    balance = biomech_data.get("stance_balance", 50.0)
    vo = biomech_data.get("vertical_oscillation", 0)
    biomech_data.get("vertical_ratio", 0)
    biomech_data.get("step_length", 0)
    biomech_data.get("gct_asymmetry", 0)

    def build_card(title, value, unit, interp, color):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='14' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
            Paragraph(f"<font size='7'>{interp}</font>", styles["center"]),
        ]
        card_table = Table([[card_content]], colWidths=[42 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return card_table

    gct_color = "#2ECC71" if gct < 250 else ("#F39C12" if gct < 300 else "#E74C3C")
    gct_interp = "Krótki kontakt" if gct < 250 else ("Średni" if gct < 300 else "Długi kontakt")
    card1 = build_card("GCT", f"{gct:.0f}", "ms", gct_interp, gct_color)

    bal_color = (
        "#2ECC71" if abs(balance - 50) < 2 else ("#F39C12" if abs(balance - 50) < 5 else "#E74C3C")
    )
    bal_interp = (
        "Symetryczny"
        if abs(balance - 50) < 2
        else ("Lekka asymetria" if abs(balance - 50) < 5 else "Asymetria")
    )
    card2 = build_card("BALANS L/P", f"{balance:.1f}", "%", bal_interp, bal_color)

    vo_color = "#2ECC71" if vo < 8 else ("#F39C12" if vo < 10 else "#E74C3C")
    vo_interp = "Niska" if vo < 8 else ("Średnia" if vo < 10 else "Wysoka")
    card3 = build_card("OSCYLACJA PION.", f"{vo:.1f}", "cm", vo_interp, vo_color)

    cards_row = Table([[card1, card2, card3]], colWidths=[58 * mm] * 3)
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))

    if figure_paths and "biomech_profile" in figure_paths:
        elements.extend(
            _build_chart(figure_paths["biomech_profile"], "Profil Biomechaniczny", styles)
        )

    return elements


# ============================================================================
# PAGE: DRIFT
# ============================================================================


def build_page_drift(
    drift_data: Dict[str, Any], figure_paths: Dict[str, str], styles: Dict
) -> List:
    """Build Drift Analysis page."""
    elements = []

    elements.append(Paragraph("<font size='14'>4.1 DRYF I DECOUPLING</font>", styles["center"]))
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Analiza stabilności tętna i mocy w czasie</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    hr_drift = drift_data.get("hr_drift_pct", 0)
    drift_data.get("power_drift_pct", 0)
    decoupling = drift_data.get("decoupling", 0)
    drift_data.get("drift_status", "unknown")

    def build_card(title, value, unit, interp, color):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='14' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
            Paragraph(f"<font size='7'>{interp}</font>", styles["center"]),
        ]
        card_table = Table([[card_content]], colWidths=[55 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return card_table

    drift_color = (
        "#2ECC71" if abs(hr_drift) < 3 else ("#F39C12" if abs(hr_drift) < 6 else "#E74C3C")
    )
    drift_interp = (
        "Stabilny" if abs(hr_drift) < 3 else ("Dryf" if abs(hr_drift) < 6 else "Wysoki dryf")
    )
    card1 = build_card("DRYF HR", f"{hr_drift:.1f}", "%", drift_interp, drift_color)

    dec_color = (
        "#2ECC71" if abs(decoupling) < 5 else ("#F39C12" if abs(decoupling) < 10 else "#E74C3C")
    )
    dec_interp = (
        "Stabilny" if abs(decoupling) < 5 else ("Umiarkowany" if abs(decoupling) < 10 else "Wysoki")
    )
    card2 = build_card("DECOUPLING", f"{decoupling:.1f}", "%", dec_interp, dec_color)

    cards_row = Table([[card1, card2]], colWidths=[88 * mm] * 2)
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))

    if figure_paths and "drift_hr" in figure_paths:
        elements.extend(_build_chart(figure_paths["drift_hr"], "Moc vs Tętno (Dryf)", styles))

    return elements


# ============================================================================
# PAGE: KPI DASHBOARD
# ============================================================================


def build_page_kpi_dashboard(kpi: Dict[str, Any], styles: Dict) -> List:
    """Build KPI Dashboard page."""
    elements = []

    elements.append(Paragraph("<font size='14'>5.1 WSKAŹNIKI KPI</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))

    metrics = kpi.get("metrics", [])

    if not metrics:
        elements.append(Paragraph("Brak danych KPI.", styles["body"]))
        return elements

    # Build KPI cards in rows of 3
    for i in range(0, len(metrics), 3):
        row = metrics[i : i + 3]
        cards = []

        for m in row:
            name = m.get("name", "")
            value = m.get("value", "---")
            unit = m.get("unit", "")
            interpretation = m.get("interpretation", "")
            color = m.get("color", "#7F8C8D")

            card_content = [
                Paragraph(f"<font size='8' color='#7F8C8D'>{name}</font>", styles["center"]),
                Paragraph(
                    f"<font size='16' color='{color}'><b>{value}</b></font>", styles["center"]
                ),
                Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
                Paragraph(f"<font size='8'>{interpretation}</font>", styles["center"]),
            ]
            card_table = Table([[card_content]], colWidths=[55 * mm])
            card_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                        ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            cards.append(card_table)

        if cards:
            cards_row = Table([cards], colWidths=[58 * mm] * len(cards))
            cards_row.setStyle(
                TableStyle(
                    [("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]
                )
            )
            elements.append(cards_row)
            elements.append(Spacer(1, 4 * mm))

    return elements


# ============================================================================
# PAGE: DRIFT KPI
# ============================================================================


def build_page_drift_kpi(kpi: Dict[str, Any], styles: Dict) -> List:
    """Build Drift KPI summary."""
    elements = []

    elements.append(Paragraph("<font size='14'>5.3 DRYF — PODSUMOWANIE</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))

    drift_metrics = kpi.get("drift", {})
    if drift_metrics:
        hr_drift = drift_metrics.get("hr_drift_pct", "---")
        power_drift = drift_metrics.get("power_drift_pct", "---")
        decoupling = drift_metrics.get("decoupling", "---")

        data = [
            ["Metryka", "Wartość"],
            ["Dryf HR", f"{hr_drift} %"],
            ["Dryf Mocy", f"{power_drift} %"],
            ["Decoupling", f"{decoupling} %"],
        ]

        table = Table(data, colWidths=[60 * mm, 60 * mm])
        table.setStyle(get_table_style())
        elements.append(table)
    else:
        elements.append(Paragraph("Brak danych o dryfie.", styles["body"]))

    return elements


# ============================================================================
# PAGE: LIMITERS
# ============================================================================


def build_page_limiters(limiter_data: Dict[str, Any], styles: Dict) -> List:
    """Build Limiters Summary page."""
    elements = []

    elements.append(Paragraph("<font size='14'>5.2 ANALIZA LIMITERÓW</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))

    limiters = limiter_data.get("limiters", [])

    if not limiters:
        elements.append(Paragraph("Brak danych o limiterach.", styles["body"]))
        return elements

    for limiter in limiters:
        name = limiter.get("name", "Unknown")
        score = limiter.get("score", 0)
        severity = limiter.get("severity", "medium")

        severity_colors = {"low": "#2ECC71", "medium": "#F39C12", "high": "#E74C3C"}
        color = severity_colors.get(severity, "#7F8C8D")

        card_content = [
            Paragraph(f"<b>{name}</b> — {score:.0f}/100", styles["body"]),
        ]
        card_table = Table([[card_content]], colWidths=[170 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(card_table)
        elements.append(Spacer(1, 3 * mm))

    return elements


# ============================================================================
# PAGE: EXTRA
# ============================================================================


def build_page_extra(figure_paths: Dict[str, str], styles: Dict) -> List:
    """Build Page 8: Extra Analytics (Ventilation & Drift)."""
    elements = []

    elements.append(Paragraph("Zaawansowana Analityka", styles["title"]))
    elements.append(Spacer(1, 6 * mm))

    # Vent Full
    if figure_paths and "vent_full" in figure_paths:
        elements.extend(
            _build_chart(figure_paths["vent_full"], "Dynamika Wentylacji (VE) vs Moc", styles)
        )
        elements.append(Spacer(1, 6 * mm))

    # Drift Maps
    elements.append(Paragraph("Mapy Dryfu i Decoupling", styles["heading"]))

    if figure_paths and "drift_hr" in figure_paths:
        elements.extend(_build_chart(figure_paths["drift_hr"], "Moc vs Tętno", styles))
        elements.append(Spacer(1, 4 * mm))

    # PAGE BREAK FOR SECOND DRIFT MAP
    elements.append(PageBreak())

    if figure_paths and "drift_smo2" in figure_paths:
        # Title moved to new page
        elements.append(Paragraph("Moc vs Saturacja Mięśniowa", styles["title"]))
        elements.append(Spacer(1, 6 * mm))
        elements.extend(_build_chart(figure_paths["drift_smo2"], "Decoupling Mięśniowy", styles))

    return elements
