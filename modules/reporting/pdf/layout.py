"""
PDF Layout Module.

Defines page structure and content sections for Ramp Test PDF.
Each page is a separate function.
No physiological calculations - only layout and formatting.

Per specification: methodology/ramp_test/10_pdf_layout.md
"""
from reportlab.platypus import (
    Paragraph, Spacer, Table, Image, PageBreak, KeepTogether, TableStyle
)
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
import os
import logging
from typing import Dict, Any, List, Optional

from .styles import (
    COLORS, PAGE_WIDTH, MARGIN,
    get_table_style, FONT_FAMILY, FONT_FAMILY_BOLD, FONT_FAMILY_ITALIC,
)

from .layout_formatters import build_colored_box, build_section_description
from .layout_title import _add_fallback_title, build_contact_footer, build_title_page
from .layout_tables import build_chapter_header, build_table_of_contents
from .layout_executive import build_page_executive_summary, build_page_executive_verdict

# Setup logger
logger = logging.getLogger("Tri_Dashboard.PDFLayout")

# Premium color constants
PREMIUM_COLORS = {
    "navy": HexColor("#1A5276"),      # Recommendations/training
    "dark_glass": HexColor("#17252A"), # Title page background
    "red": HexColor("#C0392B"),        # Warnings/limitations
    "green": HexColor("#27AE60"),      # Positives/strengths
    "white": HexColor("#FFFFFF"),
    "light_gray": HexColor("#BDC3C7"),
}


# ============================================================================
# PREMIUM HELPER FUNCTIONS
# ============================================================================











# ============================================================================
# TABLE OF CONTENTS (SPIS TREŚCI) - HIERARCHICAL
# ============================================================================





# ============================================================================
# PAGE 0: EXECUTIVE PHYSIO SUMMARY (NEW FIRST PAGE)
# ============================================================================



# ============================================================================
# PAGE 2: EXECUTIVE VERDICT (1-PAGE DECISION SUMMARY)
# ============================================================================



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
    rcp_onset_watts: Optional[int] = None
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
    test_date = metadata.get("test_date", "Unknown")
    session_id = metadata.get("session_id", "")[:8]
    method_version = metadata.get("method_version", "1.0.0")
    
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
        warning_table = Table(
            [[Paragraph(warning_text, styles["body"])]],
            colWidths=[160 * mm]
        )
        warning_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLORS["warning"]),
            ("TEXTCOLOR", (0, 0), (-1, -1), COLORS["text"]),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 2, COLORS["warning"]),
        ]))
        elements.append(warning_table)
        elements.append(Spacer(1, 6 * mm))
    
    # === KEY RESULTS TABLE ===
    elements.append(Paragraph("Kluczowe Wyniki", styles["heading"]))
    
    vt1_watts = thresholds.get("vt1_watts", "brak danych")
    vt2_watts = thresholds.get("vt2_watts", "brak danych")
    cp_watts = cp_model.get("cp_watts", "brak danych")
    w_prime_kj = cp_model.get("w_prime_kj", "brak danych")
    pmax = metadata.get("pmax_watts", "brak danych")
    
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
        ["W' (Rezerwa)", f"{w_prime_kj} kJ", "Rezerwa anaerobowa"]
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
    
    elements.append(Paragraph(
        "Powyższe strefy są obliczone automatycznie na podstawie wykrytych progów VT1 i VT2. "
        "Przed zastosowaniem skonsultuj je z trenerem, który może dostosować je do Twoich celów.",
        styles["small"]
    ))
    
    return elements


def build_page_test_profile(
    metadata: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict
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
    
    elements.append(Paragraph(
        "<font size='8' color='#7F8C8D'>"
        "Test wykonywany do odmowy, każdy interwał trwał 3 minuty. "
        "Zwiększenie obciążenia w każdym interwale +30W. "
        f"Początek testu rozpoczął się od wartości {test_start_power} W, "
        f"koniec testu nastąpił na wartości {test_end_power} W. "
        f"Test trwał łącznie {test_duration}."
        "</font>",
        styles["center"]
    ))
    
    return elements


# ============================================================================
# PAGE 2: SZCZEGÓŁY PROGÓW VT1/VT2
# ============================================================================

def build_page_thresholds(
    thresholds: Dict[str, Any],
    smo2: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict
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
    elements.append(Paragraph(
        "Progi zostały wykryte na podstawie zmian w wentylacji (oddychaniu) podczas testu.",
        styles["body"]
    ))
    elements.append(Paragraph(
        "<b>VT1 (Próg tlenowy):</b> Moment, gdy organizm zaczyna intensywniej pracować. "
        "Możesz jechać komfortowo przez wiele godzin.",
        styles["body"]
    ))
    elements.append(Paragraph(
        "<b>VT2 (Próg beztlenowy):</b> Punkt, powyżej którego wysiłek staje się bardzo ciężki. "
        "Oddychasz ciężko, nie możesz swobodnie mówić.",
        styles["body"]
    ))
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
        if mid == "brak danych": return mid
        if rng == "brak danych": return f"~{mid}"
        return f"{rng} (środek: {mid})"
        
    def fmt(val):
        if val == "brak danych": return val
        try:
            return f"{float(val):.0f}"
        except Exception:
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
    elements.extend(_build_education_block(
        "Dlaczego to ma znaczenie? (VT1 / VT2)",
        "Progi wentylacyjne to Twoje najważniejsze drogowskazy w planowaniu obciążeń. "
        "VT1 wyznacza granicę komfortu tlenowego i „przepalania” tłuszczy – to tu budujesz bazę na długie godziny. "
        "VT2 to Twój „szklany sufit” – powyżej niego kwas narasta szybciej niż organizm go utylizuje, "
        "co wymaga długiej regeneracji. Znajomość tych punktów pozwala unikać „strefy zgubnej” między progami, "
        "gdzie zmęczenie jest duże, a adaptacje nieoptymalne. Jako trener używam ich, by każda Twoja minuta "
        "na rowerze miała konkretny cel fizjologiczny. Dzięki temu nie trenujesz po prostu „ciężko”, "
        "ale trenujesz mądrze i precyzyjnie.",
        styles
    ))
    
    return elements


def build_page_smo2(smo2_data, smo2_manual, figure_paths, styles):
    """Build SmO2 analysis page - PREMIUM MUSCLE OXYGENATION DIAGNOSTIC."""
    from reportlab.lib.colors import HexColor
    
    elements = []
    smo2_advanced = smo2_data.get("advanced_metrics", {})
    
    # ==========================================================================
    # HEADER
    # ==========================================================================
    elements.append(Paragraph(
        "<font size='14'>3.3 OKSYGENACJA MIĘŚNIOWA (SmO₂)</font>",
        styles['center']
    ))
    elements.append(Paragraph(
        "<font size='10' color='#7F8C8D'>Kliniczna analiza dostawy i wykorzystania tlenu</font>",
        styles['center']
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 1. METRIC CARDS ROW
    # ==========================================================================
    
    slope = smo2_advanced.get("slope_per_100w", 0) if smo2_advanced else 0
    halftime = smo2_advanced.get("halftime_reoxy_sec") if smo2_advanced else None
    coupling = smo2_advanced.get("hr_coupling_r", 0) if smo2_advanced else 0
    data_quality = smo2_advanced.get("data_quality", "unknown") if smo2_advanced else "unknown"
    
    def build_metric_card(title, value, unit, interpretation, color):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='16' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
            Spacer(1, 1 * mm),
            Paragraph(f"<font size='8'>{interpretation}</font>", styles["center"]),
        ]
        card_table = Table([[card_content]], colWidths=[55 * mm])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F8F9FA")),
            ('BOX', (0, 0), (-1, -1), 1, HexColor(color)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        return card_table
    
    slope_color = "#E74C3C" if slope < -6 else ("#F39C12" if slope < -3 else "#2ECC71")
    slope_interp = "Szybka desaturacja" if slope < -6 else ("Umiarkowana" if slope < -3 else "Stabilna")
    card1 = build_metric_card("DESATURATION RATE", f"{slope:.1f}", "%/100W", slope_interp, slope_color)
    
    if halftime:
        ht_color = "#E74C3C" if halftime > 60 else ("#F39C12" if halftime > 30 else "#2ECC71")
        ht_interp = "Wolna reoksygenacja" if halftime > 60 else ("Umiarkowana" if halftime > 30 else "Szybka")
        card2 = build_metric_card("REOXY HALF-TIME", f"{halftime:.0f}", "sekund", ht_interp, ht_color)
    else:
        card2 = build_metric_card("REOXY HALF-TIME", "---", "sekund", "Brak danych", "#7F8C8D")
    
    coup_color = "#3498DB" if abs(coupling) > 0.6 else ("#F39C12" if abs(coupling) > 0.3 else "#2ECC71")
    coup_interp = "Silna (centralna)" if abs(coupling) > 0.6 else ("Umiarkowana" if abs(coupling) > 0.3 else "Słaba (lokalna)")
    card3 = build_metric_card("HR COUPLING", f"{coupling:.2f}", "r-Pearson", coup_interp, coup_color)
    
    cards_row = Table([[card1, card2, card3]], colWidths=[58 * mm, 58 * mm, 58 * mm])
    cards_row.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 2. OXYGEN DELIVERY MECHANISM PANEL
    # ==========================================================================
    
    limiter_type = smo2_advanced.get("limiter_type", "unknown") if smo2_advanced else "unknown"
    limiter_conf = smo2_advanced.get("limiter_confidence", 0) if smo2_advanced else 0
    interpretation_adv = smo2_advanced.get("interpretation", "") if smo2_advanced else ""
    
    mechanism_colors = {"local": "#3498DB", "central": "#E74C3C", "metabolic": "#F39C12", "unknown": "#7F8C8D"}
    mechanism_names = {"local": "OBWODOWY", "central": "CENTRALNY", "metabolic": "MIESZANY", "unknown": "NIEOKREŚLONY"}
    mechanism_icons = {"local": "💪", "central": "❤️", "metabolic": "🔥", "unknown": "❓"}
    
    mech_color = HexColor(mechanism_colors.get(limiter_type, "#7F8C8D"))
    mech_name = mechanism_names.get(limiter_type, "UNDEFINED")
    mech_icon = mechanism_icons.get(limiter_type, "❓")
    
    elements.append(Paragraph("<b>DOMINANT OXYGEN DELIVERY MECHANISM</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    verdict_content = [
        Paragraph(f"<font color='white'><b>{mech_icon} {mech_name}</b></font>", styles["center"]),
        Paragraph(f"<font size='10' color='white'>{limiter_conf:.0%} confidence</font>", styles["center"]),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), mech_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 3 * mm))
    
    if interpretation_adv:
        for line in interpretation_adv.split('\n')[:2]:
            elements.append(Paragraph(line, styles["body"]))
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 3. SmO2 THRESHOLDS (compact cards)
    # ==========================================================================
    
    lt1 = smo2_manual.get("lt1_watts", "---")
    lt2 = smo2_manual.get("lt2_watts", "---")
    lt1_hr = smo2_manual.get("lt1_hr", "---")
    lt2_hr = smo2_manual.get("lt2_hr", "---")
    
    def fmt(val):
        if val in ("brak danych", None, "---"): return "---"
        try: return f"{float(val):.0f}"
        except Exception: return str(val)
    
    elements.append(Paragraph("<b>PROGI OKSYGENACJI MIĘŚNIOWEJ</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    lt1_card = [Paragraph("<font size='9' color='#7F8C8D'>SmO₂ LT1</font>", styles["center"]),
                Paragraph(f"<font size='14'><b>{fmt(lt1)} W</b></font>", styles["center"]),
                Paragraph(f"<font size='9'>@ {fmt(lt1_hr)} bpm</font>", styles["center"])]
    lt2_card = [Paragraph("<font size='9' color='#7F8C8D'>SmO₂ LT2</font>", styles["center"]),
                Paragraph(f"<font size='14'><b>{fmt(lt2)} W</b></font>", styles["center"]),
                Paragraph(f"<font size='9'>@ {fmt(lt2_hr)} bpm</font>", styles["center"])]
    
    lt1_table = Table([[lt1_card]], colWidths=[85 * mm])
    lt1_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor("#E8F6F3")), ('BOX', (0, 0), (-1, -1), 1, HexColor("#1ABC9C")), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    lt2_table = Table([[lt2_card]], colWidths=[85 * mm])
    lt2_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor("#FDEDEC")), ('BOX', (0, 0), (-1, -1), 1, HexColor("#E74C3C")), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    
    thresh_row = Table([[lt1_table, lt2_table]], colWidths=[88 * mm, 88 * mm])
    elements.append(thresh_row)
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 4. TRAINING DECISION CARDS
    # ==========================================================================
    
    recommendations = smo2_advanced.get("recommendations", []) if smo2_advanced else []
    if recommendations:
        elements.append(Paragraph("<b>DECYZJE TRENINGOWE NA PODSTAWIE KINETYKI O₂</b>", styles["subheading"]))
        elements.append(Spacer(1, 3 * mm))
        
        expected = {"local": ["Wzrost bazowego SmO₂ o 2-4%", "Szybsza reoksygenacja", "Zmniejszenie slope"],
                    "central": ["Wyższe SmO₂ przy tym samym HR", "Lepsza korelacja", "Stabilniejsza saturacja"],
                    "metabolic": ["Późniejszy drop point", "Mniejszy slope", "Lepsza tolerancja kwasu"]}
        exp_list = expected.get(limiter_type, ["Poprawa ogólna", "Stabilniejsza saturacja", "Lepszy klirens"])
        
        for i, rec in enumerate(recommendations[:3]):
            exp_resp = exp_list[i] if i < len(exp_list) else "Poprawa wydolności"
            card_content = [Paragraph(f"<font size='10'><b>{i+1}. {rec}</b></font>", styles["body"]),
                           Paragraph(f"<font size='8' color='#27AE60'>Spodziewany efekt: {exp_resp}</font>", styles["body"])]
            card_table = Table([[card_content]], colWidths=[170 * mm])
            card_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), COLORS["background"]), ('BOX', (0, 0), (-1, -1), 0.5, COLORS["border"]), ('LEFTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
            elements.append(card_table)
            elements.append(Spacer(1, 2 * mm))
    
    # Chart
    if figure_paths and "smo2_power" in figure_paths:
        elements.append(Spacer(1, 4 * mm))
        elements.extend(_build_chart(figure_paths["smo2_power"], "SmO₂ vs Power Profile", styles))
    
    # Data quality
    quality_color = "#2ECC71" if data_quality == "good" else ("#F39C12" if data_quality == "low" else "#7F8C8D")
    quality_label = "Wysoka" if data_quality == "good" else ("Niska" if data_quality == "low" else "Brak danych")
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(f"<font size='8' color='#7F8C8D'>Data Quality: </font><font size='8' color='{quality_color}'><b>{quality_label}</b></font>", styles["body"]))
    
    # ==========================================================================
    # 5. REFERENCE BENCHMARK TABLE (MINI-BENCHMARK)
    # ==========================================================================
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("<b>REFERENCE BENCHMARK</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    # Interpret metrics for benchmark
    slope_interp_full = "Typowe dla limitu centralnego" if slope < -4 else ("Umiarkowane - balans C/P" if slope < -2 else "Stabilne - limit lokalny")
    if halftime:
        ht_interp_full = "Elite (<25s)" if halftime < 25 else ("OK ale nie elite" if halftime < 50 else "Wolna - priorytet interwały")
    else:
        ht_interp_full = "Brak danych"
    coup_interp_full = "Silna dominacja serca (centralny)" if abs(coupling) > 0.6 else ("Zrównoważona" if abs(coupling) > 0.3 else "Dominacja obwodowa (lokalna)")
    
    bench_data = [
        ["Metryka", "Twoja wartość", "Interpretacja kliniczna"],
        ["SmO2 slope", f"{slope:.1f} %/100W", slope_interp_full],
        ["Reoxy half-time", f"{halftime:.0f} s" if halftime else "---", ht_interp_full],
        ["HR-SmO2 r", f"{coupling:.2f}", coup_interp_full],
    ]
    
    bench_table = Table(bench_data, colWidths=[40 * mm, 40 * mm, 85 * mm])
    bench_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor("#1F77B4")),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'DejaVuSans-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#555555")),
        ('ROWHEIGHT', (0, 0), (-1, -1), 9 * mm),
        ('BACKGROUND', (0, 1), (-1, 1), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 1), (-1, 1), HexColor("#333333")),
        ('BACKGROUND', (0, 2), (-1, 2), HexColor("#e8e8e8")),
        ('TEXTCOLOR', (0, 2), (-1, 2), HexColor("#333333")),
        ('BACKGROUND', (0, 3), (-1, 3), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 3), (-1, 3), HexColor("#333333")),
    ]))
    elements.append(bench_table)
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 6. CONCLUSIVE STATEMENT (Links SmO2 with Biomechanics)
    # ==========================================================================
    
    # Generate conclusive statement based on limiter type
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
    
    conclusion_style = ParagraphStyle('conclusion', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9)
    conclusion_box = Table(
        [[Paragraph(conclusion, conclusion_style)]],
        colWidths=[165 * mm]
    )
    conclusion_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(conclusion_color)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(conclusion_box)
    
    return elements



# ============================================================================
# PAGE 3: POWER-DURATION CURVE / CP
# ============================================================================

def build_page_pdc(
    cp_model: Dict[str, Any],
    metadata: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict
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
    elements.append(Paragraph(
        "Krzywa mocy pokazuje, jak długo możesz utrzymać dany poziom wysiłku.",
        styles["body"]
    ))
    elements.append(Paragraph(
        "<b>CP (Critical Power)</b> to moc, którą teoretycznie możesz utrzymać bardzo długo. "
        "W praktyce oznacza to maksymalny wysiłek przez 30-60 minut.",
        styles["body"]
    ))
    elements.append(Paragraph(
        "<b>W' (W-prime)</b> to Twoja rezerwa energetyczna powyżej CP. "
        "Możesz ją „spalić” na ataki, podjazdy lub sprint.",
        styles["body"]
    ))
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
    elements.extend(_build_education_block(
        "Dlaczego to ma znaczenie? (CP / W')",
        "Model CP/W' to Twoja cyfrowa bateria, która mówi na co Cię stać w decydującym momencie wyścigu. "
        "Critical Power (CP) to Twoja najwyższa moc „długodystansowa”, utrzymywana bez wyczerpania rezerw. "
        "W' to Twój „bak paliwa” na ataki, krótkie podjazdy i sprinty powyżej mocy progowej. "
        "Każdy skok powyżej CP kosztuje konkretną ilość dżuli, a regeneracja następuje dopiero poniżej tego progu. "
        "Rozumienie tego balansu pozwala decydować, czy odpowiedzieć na atak, czy czekać na swoją szansę. "
        "To serce Twojej strategii, które mówi nam, jak optymalnie zarządzać Twoimi siłami.",
        styles
    ))
    
    # Additional theory - FAKT / INTERPRETACJA / AKCJA structure
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(
        "<font color='#3498DB'><b>● FAKT:</b></font> Każdy skok powyżej CP kosztuje konkretną ilość dżuli z W'. "
        "Przy W'=15kJ i mocy 50W powyżej CP, wystarczy na ~5 min powyżej progu.",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<font color='#9B59B6'><b>● INTERPRETACJA:</b></font> Regeneracja W' zachodzi TYLKO poniżej CP. "
        "Im głębiej poniżej CP, tym szybsza regeneracja (ok. 1-2% W'/s przy głębokim Z2).",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<font color='#27AE60'><b>● AKCJA:</b></font> W ataku kalkuluj koszt: krótki intensywny atak (30s @ +100W) kosztuje ~3kJ. "
        "Czy masz rezerwę? Decyduj na podstawie danych, nie intuicji.",
        styles["body"]
    ))

    return elements


# ============================================================================
# PAGE 4: INTERPRETACJA WYNIKÓW
# ============================================================================

def build_page_interpretation(
    thresholds: Dict[str, Any],
    cp_model: Dict[str, Any],
    styles: Dict
) -> List:
    """Build Page 4: Results Interpretation.
    
    Contains:
    - VT1 explanation with values + CHO/metabolic info + example workouts
    - VT2 explanation with values + CHO/metabolic info + example workouts
    - Tempo zone explanation + substrate usage
    - CP practical usage + pacing examples
    """
    elements = []
    
    elements.append(Paragraph("<font size='14'>2.2 CO OZNACZAJĄ TE WYNIKI?</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))
    
    vt1_watts_raw = thresholds.get("vt1_watts", "brak danych")
    vt2_watts_raw = thresholds.get("vt2_watts", "brak danych")
    cp_watts_raw = cp_model.get("cp_watts", "brak danych")
    
    # Convert to numeric values for calculations
    try:
        vt1_num = float(vt1_watts_raw) if vt1_watts_raw not in [None, "brak danych", "---"] else None
    except (ValueError, TypeError):
        vt1_num = None
        
    try:
        vt2_num = float(vt2_watts_raw) if vt2_watts_raw not in [None, "brak danych", "---"] else None
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
    elements.append(Paragraph(
        f"Twój próg tlenowy wynosi około <b>{vt1_watts} W</b>. "
        "To moc, przy której możesz jechać komfortowo przez wiele godzin. "
        "Oddychasz spokojnie, możesz swobodnie rozmawiać. "
        "Treningi poniżej VT1 budują bazę tlenową i służą regeneracji.",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<b>Metabolizm:</b> Poniżej VT1 spalasz głównie tłuszcze (~60-70% energii z lipidów). "
        "Zużycie węglowodanów (CHO) wynosi ok. <b>30-50g/h</b>. "
        "To strefa idealna do długich treningów bez uzupełniania CHO.",
        styles["small"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"<b>Przykładowe jednostki:</b> "
        f"• Regeneracja: 60-90 min @ {int(vt1_num*0.65) if vt1_num else '?'}-{int(vt1_num*0.75) if vt1_num else '?'} W | "
        f"• Baza aerobowa: 2-4h @ {int(vt1_num*0.8) if vt1_num else '?'}-{vt1_watts} W",
        styles["small"]
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # === VT2 ===
    elements.append(Paragraph("Próg beztlenowy (VT2)", styles["heading"]))
    elements.append(Paragraph(
        f"Twój próg beztlenowy wynosi około <b>{vt2_watts} W</b>. "
        "Powyżej tej mocy wysiłek staje się bardzo wymagający. "
        "Oddychasz ciężko, nie możesz swobodnie mówić. "
        "Treningi powyżej VT2 rozwijają VO₂max, ale wymagają pełnej regeneracji.",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<b>Metabolizm:</b> Powyżej VT2 dominuje glikoliza beztlenowa. "
        "Zużycie CHO rośnie do <b>90-120g/h</b>. Akumulacja mleczanu prowadzi do szybkiego zmęczenia. "
        "Wysiłek powyżej VT2 można utrzymać max 20-60 min.",
        styles["small"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"<b>Przykładowe jednostki:</b> "
        f"• VO₂max: 5×5 min @ {int(vt2_num*1.05) if vt2_num else '?'}-{int(vt2_num*1.15) if vt2_num else '?'} W (4 min odpoczynku) | "
        f"• Tolerancja mleczanu: 3×8 min @ {vt2_watts} W (5 min odpoczynku)",
        styles["small"]
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # === TEMPO ZONE ===
    elements.append(Paragraph("Strefa Tempo", styles["heading"]))
    elements.append(Paragraph(
        f"Strefa między <b>{vt1_watts}</b> a <b>{vt2_watts} W</b> to Twoja strefa 'tempo'. "
        "Jest idealna do treningu wytrzymałościowego i poprawy progu. "
        "W tej strefie możesz spędzać znaczną część czasu treningowego bez nadmiernego zmęczenia.",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<b>Metabolizm:</b> W strefie tempo następuje przejście z lipidów na CHO. "
        "Spalanie tłuszczów spada do ~30-40%, rośnie zużycie CHO (<b>60-80g/h</b>). "
        "To strefa kluczowa dla rozwoju FatMax i przesunięcia krzywej spalania.",
        styles["small"]
    ))
    elements.append(Spacer(1, 2 * mm))
    
    tempo_mid = ""
    if vt1_num and vt2_num:
        tempo_mid = f"{int((vt1_num + vt2_num) / 2)}"
    
    elements.append(Paragraph(
        f"<b>Przykładowe jednostki:</b> "
        f"• Sweet Spot: 2×20 min @ {tempo_mid if tempo_mid else '?'}-{int(vt2_num*0.94) if vt2_num else '?'} W | "
        f"• Tempo długie: 1×45-60 min @ {vt1_watts}-{tempo_mid if tempo_mid else '?'} W",
        styles["small"]
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # === CP ===
    elements.append(Paragraph("Critical Power", styles["heading"]))
    elements.append(Paragraph(
        f"CP ({cp_watts} W) to matematyczne przybliżenie Twojej mocy progowej. "
        "Możesz używać tej wartości do planowania interwałów i wyznaczania stref treningowych. "
        "CP jest przydatne do pacing'u podczas zawodów i długich treningów.",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<b>Praktyka:</b> CP reprezentuje moc możliwą do utrzymania przez ~30-60 min. "
        "Treningi @ CP rozwijają próg mleczanowy i wydolność tlenową. "
        "Używaj CP jako górnej granicy dla długich, rytmicznych interwałów.",
        styles["small"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"<b>Przykładowe jednostki:</b> "
        f"• Under/Over: 3×12 min (2 min @ {int(cp_num*0.92) if cp_num else '?'} W / 1 min @ {int(cp_num*1.08) if cp_num else '?'} W) | "
        f"• Threshold: 2×20 min @ {int(cp_num*0.95) if cp_num else '?'}-{cp_watts} W",
        styles["small"]
    ))
    
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
    elements.append(Paragraph(
        "<font size='14'>3.2 UKŁAD SERCOWO-NACZYNIOWY</font>",
        styles['center']
    ))
    elements.append(Paragraph(
        "<font size='10' color='#7F8C8D'>Diagnostyka kosztu sercowego generowania mocy</font>",
        styles['center']
    ))
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
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F8F9FA")),
            ('BOX', (0, 0), (-1, -1), 1, HexColor(color)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
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
    cards_row.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 2. CCI METRIC PANEL
    # ==========================================================================
    
    elements.append(Paragraph("<b>INDEKS KOSZTU SERCOWO-NACZYNIOWEGO (CCI)</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    cci_text = f"<b>CCI = {cci:.4f}</b> bpm/W – koszt tętna na jednostkę mocy."
    if cci_bp:
        cci_text += f" <b>Breakpoint</b> przy {cci_bp:.0f}W – punkt załamania efektywności."
    elements.append(Paragraph(cci_text, styles["body"]))
    elements.append(Spacer(1, 4 * mm))
    
    # ==========================================================================
    # 3. EFFICIENCY VERDICT PANEL
    # ==========================================================================
    
    elements.append(Paragraph("<b>WERDYKT EFEKTYWNOŚCI SERCOWO-NACZYNIOWEJ</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    status_colors = {"efficient": "#2ECC71", "compensating": "#F39C12", "decompensating": "#E74C3C", "unknown": "#7F8C8D"}
    status_names = {"efficient": "EFEKTYWNY", "compensating": "KOMPENSUJĄCY", "decompensating": "DEKOMPENSUJĄCY", "unknown": "NIEOKREŚLONY"}
    status_icons = {"efficient": "✓", "compensating": "⚠", "decompensating": "✗", "unknown": "?"}
    
    st_color = HexColor(status_colors.get(status, "#7F8C8D"))
    st_name = status_names.get(status, "NIEOKREŚLONY")
    st_icon = status_icons.get(status, "?")
    
    verdict_content = [
        Paragraph(f"<font color='white'><b>{st_icon} {st_name}</b></font>", styles["center"]),
        Paragraph(f"<font size='10' color='white'>pewność: {confidence:.0%}</font>", styles["center"]),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), st_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 3 * mm))
    
    # Interpretation
    if interpretation:
        for line in interpretation.split('\n')[:3]:
            elements.append(Paragraph(line, styles["body"]))
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 4. DECISION CARDS
    # ==========================================================================
    
    if recommendations:
        elements.append(Paragraph("<b>DECYZJE TRENINGOWE I ŚRODOWISKOWE</b>", styles["subheading"]))
        elements.append(Spacer(1, 3 * mm))
        
        type_colors = {"TRENINGOWA": "#3498DB", "ŚRODOWISKOWA": "#9B59B6", "REGENERACJA": "#1ABC9C", "WYDAJNOŚĆ": "#2ECC71", "DIAGNOSTYCZNA": "#E74C3C"}
        
        for rec in recommendations[:3]:
            rec_type = rec.get("type", "TRENINGOWA")
            action = rec.get("action", "---")
            expected = rec.get("expected", "---")
            risk = rec.get("risk", "low")
            
            type_color = type_colors.get(rec_type, "#7F8C8D")
            risk_color = "#2ECC71" if risk == "low" else ("#F39C12" if risk == "medium" else "#E74C3C")
            risk_label = "NISKIE" if risk == "low" else ("ŚREDNIE" if risk == "medium" else "WYSOKIE")
            
            card_content = [
                Paragraph(f"<font size='9' color='{type_color}'><b>[{rec_type}]</b></font> {action}", styles["body"]),
                Paragraph(f"<font size='8' color='#27AE60'>Spodziewany efekt: {expected}</font> | <font size='8' color='{risk_color}'>Ryzyko: {risk_label}</font>", styles["body"]),
            ]
            card_table = Table([[card_content]], colWidths=[170 * mm])
            card_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), COLORS["background"]),
                ('BOX', (0, 0), (-1, -1), 0.5, COLORS["border"]),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
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
    elements.append(Paragraph(
        "3. DIAGNOSTYKA UKŁADÓW",
        styles['title']
    ))
    elements.append(Paragraph(
        "<font size='14'>3.1 KONTROLA ODDYCHANIA</font>",
        styles['center']
    ))
    elements.append(Paragraph(
        "<font size='10' color='#7F8C8D'>Diagnostyka wentylacji i kontroli metabolicznej</font>",
        styles['center']
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # Extract metrics
    ve_avg = vent_data.get("ve_avg", 0)
    ve_max = vent_data.get("ve_max", 0)
    rr_avg = vent_data.get("rr_avg", 0)
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
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F8F9FA")),
            ('BOX', (0, 0), (-1, -1), 1, HexColor(color)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
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
    cards_row.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 2. BREATHING PATTERN
    # ==========================================================================
    
    pattern_colors = {"efficient": "#2ECC71", "shallow": "#E74C3C", "hyperventilation": "#F39C12", "mixed": "#7F8C8D", "unknown": "#7F8C8D"}
    pattern_names = {"efficient": "EFEKTYWNY ODDECH", "shallow": "PŁYTKI/PANIKA", "hyperventilation": "HIPERWENTYLACJA", "mixed": "WZÓR MIESZANY", "unknown": "NIEOKREŚLONY"}
    
    elements.append(Paragraph("<b>WYKRYWANIE WZORCA ODDECHOWEGO</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    pattern_badge = Paragraph(
        f"<font color='white'><b>{pattern_names.get(pattern, 'UNDEFINED')}</b></font>",
        styles["center"]
    )
    pattern_table = Table([[pattern_badge]], colWidths=[170 * mm])
    pattern_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(pattern_colors.get(pattern, "#7F8C8D"))),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(pattern_table)
    elements.append(Spacer(1, 4 * mm))
    
    # ==========================================================================
    # 3. CONTROL VERDICT
    # ==========================================================================
    
    elements.append(Paragraph("<b>WERDYKT KONTROLI WENTYLACJI</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    status_colors = {"controlled": "#2ECC71", "compensatory": "#F39C12", "unstable": "#E74C3C", "unknown": "#7F8C8D"}
    status_names = {"controlled": "KONTROLOWANY", "compensatory": "KOMPENSACYJNY", "unstable": "NIESTABILNY", "unknown": "NIEOKREŚLONY"}
    status_icons = {"controlled": "✓", "compensatory": "⚠", "unstable": "✗", "unknown": "?"}
    
    st_color = HexColor(status_colors.get(status, "#7F8C8D"))
    st_name = status_names.get(status, "NIEOKREŚLONY")
    st_icon = status_icons.get(status, "?")
    
    verdict_content = [
        Paragraph(f"<font color='white'><b>{st_icon} {st_name}</b></font>", styles["center"]),
        Paragraph(f"<font size='10' color='white'>pewność: {confidence:.0%}</font>", styles["center"]),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), st_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 3 * mm))
    
    if interpretation:
        for line in interpretation.split('\n')[:2]:
            elements.append(Paragraph(line, styles["body"]))
    
    if ve_bp:
        elements.append(Paragraph(f"<b>VE Breakpoint:</b> {ve_bp:.0f}W – punkt załamania kontroli wentylacyjnej", styles["body"]))
    
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 4. DECISION CARDS
    # ==========================================================================
    
    if recommendations:
        elements.append(Paragraph("<b>DECYZJE TRENINGOWE WENTYLACJI</b>", styles["subheading"]))
        elements.append(Spacer(1, 3 * mm))
        
        type_colors = {"TRENINGOWA": "#3498DB", "TECHNICZNA": "#9B59B6", "WYDAJNOŚĆ": "#2ECC71", "INTENSYWNOŚĆ": "#1ABC9C", "PILNA": "#E74C3C", "DIAGNOSTYKA": "#F39C12", "MEDYCZNA": "#E74C3C"}
        
        for rec in recommendations[:3]:
            rec_type = rec.get("type", "TRENINGOWA")
            action = rec.get("action", "---")
            expected = rec.get("expected", "---")
            risk = rec.get("risk", "low")
            
            type_color = type_colors.get(rec_type, "#7F8C8D")
            risk_color = "#2ECC71" if risk == "low" else ("#F39C12" if risk == "medium" else "#E74C3C")
            risk_label = "NISKIE" if risk == "low" else ("ŚREDNIE" if risk == "medium" else "WYSOKIE")
            
            card_content = [
                Paragraph(f"<font size='9' color='{type_color}'><b>[{rec_type}]</b></font> {action}", styles["body"]),
                Paragraph(f"<font size='8' color='#27AE60'>Spodziewany efekt: {expected}</font> | <font size='8' color='{risk_color}'>Ryzyko: {risk_label}</font>", styles["body"]),
            ]
            card_table = Table([[card_content]], colWidths=[170 * mm])
            card_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), COLORS["background"]),
                ('BOX', (0, 0), (-1, -1), 0.5, COLORS["border"]),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(card_table)
            elements.append(Spacer(1, 2 * mm))
    
    return elements


# ============================================================================
# PAGE: METABOLIC ENGINE & TRAINING STRATEGY (PREMIUM)
# ============================================================================

def build_page_metabolic_engine(metabolic_data: Dict[str, Any], styles: Dict) -> List:
    """Build Metabolic Engine & Training Strategy page - PREMIUM."""
    from reportlab.lib.colors import HexColor
    
    elements = []
    
    profile = metabolic_data.get("profile", {})
    block = metabolic_data.get("training_block", {})
    
    # ==========================================================================
    # HEADER
    # ==========================================================================
    elements.append(Paragraph(
        "<font size='14'>2.4 SILNIK METABOLICZNY</font>",
        styles['center']
    ))
    elements.append(Paragraph(
        "<font size='10' color='#7F8C8D'>Profil metaboliczny i strategia 6-8 tygodni</font>",
        styles['center']
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 1. METABOLIC PROFILE PANEL
    # ==========================================================================
    
    vo2max = profile.get("vo2max", 0)
    vlamax = profile.get("vlamax", 0)
    cp = profile.get("cp_watts", 0)
    ratio = profile.get("vo2max_vlamax_ratio", 0)
    phenotype = profile.get("phenotype", "unknown")
    vo2max_source = profile.get("vo2max_source", "unknown")
    data_quality = profile.get("data_quality", "unknown")
    
    elements.append(Paragraph("<b>PROFIL METABOLICZNY</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    def build_metric_card(title, value, unit, color, subtitle=""):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='14' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
        ]
        if subtitle:
            card_content.append(Paragraph(f"<font size='7' color='#95A5A6'>{subtitle}</font>", styles["center"]))
        card_table = Table([[card_content]], colWidths=[42 * mm])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F8F9FA")),
            ('BOX', (0, 0), (-1, -1), 1, HexColor(color)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return card_table
    
    # VO2max card - handle n/a and show source
    if vo2max and vo2max > 0:
        vo2_color = "#2ECC71" if vo2max >= 60 else ("#F39C12" if vo2max >= 50 else "#E74C3C")
        vo2_val = f"{vo2max:.0f}"
        vo2_source_label = {"acsm_5min": "ACSM", "acsm_cp": "~CP", "metrics_direct": "test", "ramp_test_peak": "test", "intervals_api": "API"}.get(vo2max_source, "")
    else:
        vo2_color = "#7F8C8D"
        vo2_val = "n/a"
        vo2_source_label = "brak danych"
    
    card1 = build_metric_card("VO₂max", vo2_val, "ml/kg/min", vo2_color, vo2_source_label)
    
    vla_color = "#2ECC71" if vlamax < 0.4 else ("#F39C12" if vlamax < 0.6 else "#E74C3C")
    card2 = build_metric_card("VLaMax", f"{vlamax:.2f}", "mmol/L/s", vla_color, "estymowany")
    card3 = build_metric_card("CP / FTP", f"{cp:.0f}", "W", "#3498DB", "obliczone")
    
    # Ratio card - show n/a if insufficient data
    if ratio and ratio > 0 and vo2max > 0:
        ratio_color = "#2ECC71" if ratio > 130 else ("#F39C12" if ratio > 90 else "#E74C3C")
        ratio_val = f"{ratio:.0f}"
    else:
        ratio_color = "#7F8C8D"
        ratio_val = "n/a"
    card4 = build_metric_card("VO₂/VLa RATIO", ratio_val, "(ratio)", ratio_color, "oszacowane")
    
    cards_row = Table([[card1, card2, card3, card4]], colWidths=[44 * mm] * 4)
    cards_row.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Align cards to top for consistent height
    ]))
    elements.append(cards_row)
    elements.append(Spacer(1, 3 * mm))
    
    # Phenotype badge
    phenotype_colors = {"diesel": "#27AE60", "allrounder": "#3498DB", "puncher": "#F39C12", "sprinter": "#E74C3C"}
    phenotype_names = {"diesel": "DIESEL (Aerobic Dominant)", "allrounder": "ALLROUNDER", "puncher": "PUNCHER", "sprinter": "SPRINTER (Glycolytic)"}
    
    phenotype_badge = Paragraph(
        f"<font color='white'><b>PHENOTYPE: {phenotype_names.get(phenotype, phenotype.upper())}</b></font>",
        styles["center"]
    )
    phenotype_table = Table([[phenotype_badge]], colWidths=[170 * mm])
    phenotype_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(phenotype_colors.get(phenotype, "#7F8C8D"))),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(phenotype_table)
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 2. LIMITER DIAGNOSIS
    # ==========================================================================
    
    limiter = profile.get("limiter", "unknown")
    limiter_conf = profile.get("limiter_confidence", 0)
    
    elements.append(Paragraph("<b>DIAGNOZA OGRANICZEŃ</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    limiter_colors = {"aerobic": "#E74C3C", "glycolytic": "#F39C12", "mixed": "#3498DB", "unknown": "#7F8C8D"}
    limiter_names = {"aerobic": "WYDOLNOŚĆ TLENOWA", "glycolytic": "DOMINACJA GLIKOLITYCZNA", "mixed": "MIESZANY / ZBALANSOWANY", "unknown": "NIEOKREŚLONY"}
    
    limiter_content = [
        Paragraph(f"<font color='white'><b>{limiter_names.get(limiter, 'UNDEFINED')}</b></font>", styles["center"]),
        Paragraph(f"<font size='10' color='white'>{limiter_conf:.0%} confidence</font>", styles["center"]),
    ]
    limiter_table = Table([[limiter_content]], colWidths=[170 * mm])
    limiter_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(limiter_colors.get(limiter, "#7F8C8D"))),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(limiter_table)
    elements.append(Spacer(1, 4 * mm))
    
    # ==========================================================================
    # 3. STRATEGY VERDICT
    # ==========================================================================
    
    target = profile.get("adaptation_target", "unknown")
    strategy_interp = profile.get("strategy_interpretation", "")
    
    elements.append(Paragraph("<b>PRIMARY ADAPTATION TARGET</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    
    target_colors = {"increase_vo2max": "#E74C3C", "lower_vlamax": "#27AE60", "maintain_balance": "#3498DB"}
    target_names = {"increase_vo2max": "↑ ZWIĘKSZ VO₂max", "lower_vlamax": "↓ OBNIŻ VLaMax", "maintain_balance": "↔ UTRZYMAJ BALANS"}
    
    target_badge = Paragraph(
        f"<font color='white'><b>{target_names.get(target, target.upper())}</b></font>",
        styles["center"]
    )
    target_table = Table([[target_badge]], colWidths=[170 * mm])
    target_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(target_colors.get(target, "#7F8C8D"))),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(target_table)
    elements.append(Spacer(1, 3 * mm))
    
    if strategy_interp:
        # Skip first line which duplicates target name in badge above
        lines = strategy_interp.split('\n')
        for line in lines[1:4]:  # Start from line 2, take up to 3 lines
            elements.append(Paragraph(line, styles["body"]))
    elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # 4. TRAINING BLOCK
    # ==========================================================================
    
    sessions = block.get("sessions", [])
    block_name = block.get("name", "Training Block")
    weeks = block.get("duration_weeks", 6)
    
    elements.append(Paragraph(f"<b>BLOK TRENINGOWY: {block_name}</b>", styles["subheading"]))
    elements.append(Paragraph(f"<font size='9' color='#7F8C8D'>{weeks} tygodni | {block.get('primary_focus', '')}</font>", styles["body"]))
    elements.append(Spacer(1, 3 * mm))
    
    for i, session in enumerate(sessions[:4]):
        name = session.get("name", "---")
        power = session.get("power_range", "---")
        duration = session.get("duration", "---")
        goal = session.get("adaptation_goal", "---")
        freq = session.get("frequency", "---")
        failure = session.get("failure_criteria", "---")
        exp_smo2 = session.get("expected_smo2", "---")
        exp_hr = session.get("expected_hr", "---")
        
        session_content = [
            Paragraph(f"<font size='10'><b>{i+1}. {name}</b></font> <font size='9' color='#7F8C8D'>({freq})</font>", styles["body"]),
            Paragraph(f"<font size='9'><b>Moc:</b> {power} | <b>Czas:</b> {duration}</font>", styles["body"]),
            Paragraph(f"<font size='8'><b>Cel:</b> {goal}</font>", styles["body"]),
            Paragraph(f"<font size='8' color='#27AE60'>Spodziewany efekt: SmO₂ {exp_smo2}, HR {exp_hr}</font>", styles["body"]),
            Paragraph(f"<font size='8' color='#E74C3C'>⚠ Sygnał ostrz.: {failure}</font>", styles["body"]),
        ]
        
        session_table = Table([[session_content]], colWidths=[170 * mm])
        session_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLORS["background"]),
            ('BOX', (0, 0), (-1, -1), 0.5, COLORS["border"]),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(session_table)
        elements.append(Spacer(1, 2 * mm))
    
    # ==========================================================================
    # 5. KPI MONITORING
    # ==========================================================================
    
    kpi_progress = block.get("kpi_progress", [])
    kpi_regress = block.get("kpi_regress", [])
    
    if kpi_progress or kpi_regress:
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph("<b>KPI MONITORING</b>", styles["subheading"]))
        elements.append(Spacer(1, 2 * mm))
        
        # Progress KPIs
        if kpi_progress:
            elements.append(Paragraph("<font color='#27AE60'><b>✓ Sygnały postępu:</b></font>", styles["body"]))
            for kpi in kpi_progress[:3]:
                elements.append(Paragraph(f"<font size='9'>• {kpi}</font>", styles["body"]))
        
        # Regress KPIs
        if kpi_regress:
            elements.append(Spacer(1, 4 * mm))  # Extra spacing before regress section
            elements.append(Paragraph("<font color='#E74C3C'><b>✗ Sygnały regresu / overreaching:</b></font>", styles["body"]))
            for kpi in kpi_regress[:3]:
                elements.append(Paragraph(f"<font size='9'>• {kpi}</font>", styles["body"]))
    
    return elements


# ============================================================================
# PAGE: LIMITER RADAR (20 MIN FTP ANALYSIS)
# ============================================================================

def build_page_limiter_radar(
    limiter_data: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict
) -> List:
    """Build page for 20min FTP Limiter Radar analysis.
    
    Contains:
    - Diagnosis table (Serce, Płuca, Mięśnie, Moc percentages)
    - Limiting factor identification
    - Training suggestions
    """
    from reportlab.lib.colors import HexColor
    
    elements = []
    
    # Title
    elements.append(Paragraph("4. LIMITERY I OBCIĄŻENIE CIEPLNE", styles["title"]))
    elements.append(Paragraph("<font size='14'>4.1 RADAR OBCIĄŻENIA SYSTEMÓW</font>", styles["center"]))
    elements.append(Paragraph(
        "<font size='10' color='#7F8C8D'>Analiza limiterów fizjologicznych dla 20 min (FTP)</font>",
        styles["center"]
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # Extract data
    window = limiter_data.get("window", "20 min (FTP)")
    peak_power = limiter_data.get("peak_power", 0)
    pct_hr = limiter_data.get("pct_hr", 0)
    pct_ve = limiter_data.get("pct_ve", 0)
    pct_smo2 = limiter_data.get("pct_smo2_util", 0)
    pct_power = limiter_data.get("pct_power", 0)
    limiting_factor = limiter_data.get("limiting_factor", "unknown")
    interpretation = limiter_data.get("interpretation", {})
    
    # ==========================================================================
    # RADAR CHART (if available)
    # ==========================================================================
    
    if figure_paths and "limiter_radar" in figure_paths:
        elements.extend(_build_chart(figure_paths["limiter_radar"], f"Profil Obciążenia: {window} ({peak_power:.0f} W)", styles))
        elements.append(Spacer(1, 6 * mm))
    
    # ==========================================================================
    # DIAGNOSIS TABLE
    # ==========================================================================
    
    elements.append(Paragraph(f"<b>DIAGNOZA: {window}</b>", styles["heading"]))
    elements.append(Spacer(1, 2 * mm))
    
    # Determine status for each system
    def get_status(system):
        if limiting_factor == system:
            return f"<font color='#E74C3C'>●</font> Limiter", "#E74C3C"
        return f"<font color='#27AE60'>●</font> OK", "#27AE60"
    
    hr_status_str, hr_color = get_status("Serce")
    ve_status_str, ve_color = get_status("Płuca")
    smo2_status_str, smo2_color = get_status("Mięśnie")
    
    hr_status_para = Paragraph(hr_status_str, styles["center"])
    ve_status_para = Paragraph(ve_status_str, styles["center"])
    smo2_status_para = Paragraph(smo2_status_str, styles["center"])
    
    # Build diagnosis table
    header = ["System", "Wartość", "Interpretacja"]
    rows = [
        header,
        ["Serce", f"{pct_hr:.1f}% HRmax", hr_status_para],
        ["Płuca", f"{pct_ve:.1f}% VEmax", ve_status_para],
        ["Mięśnie", f"{pct_smo2:.1f}% Desat", smo2_status_para],
        ["Moc", f"{pct_power:.0f}% CP", "—"],
    ]
    
    table = Table(rows, colWidths=[50 * mm, 50 * mm, 70 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS["primary"]),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ('FONTNAME', (0, 0), (-1, 0), FONT_FAMILY_BOLD),
        ('FONTNAME', (0, 1), (-1, -1), FONT_FAMILY),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        # Color the Limiter row
        ('BACKGROUND', (0, 1), (0, 1), HexColor(hr_color) if limiting_factor == "Serce" else HexColor("#F8F9FA")),
        ('BACKGROUND', (0, 2), (0, 2), HexColor(ve_color) if limiting_factor == "Płuca" else HexColor("#F8F9FA")),
        ('BACKGROUND', (0, 3), (0, 3), HexColor(smo2_color) if limiting_factor == "Mięśnie" else HexColor("#F8F9FA")),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 4 * mm))
    
    # Main limiter
    elements.append(Paragraph(f"<b>Główny Limiter: {limiting_factor}</b>", styles["subheading"]))
    elements.append(Spacer(1, 4 * mm))
    
    # ==========================================================================
    # INTERPRETATION BOX
    # ==========================================================================
    
    title = interpretation.get("title", f"Ograniczenie: {limiting_factor}")
    description = interpretation.get("description", "")
    suggestions = interpretation.get("suggestions", [])
    
    # Color based on limiter type
    limiter_colors = {
        "Serce": "#E74C3C",
        "Płuca": "#3498DB", 
        "Mięśnie": "#F39C12"
    }
    box_color = limiter_colors.get(limiting_factor, "#7F8C8D")
    
    interp_content = f"<b>{title}</b><br/><br/>{description}<br/><br/><b>Sugestie:</b>"
    for s in suggestions:
        interp_content += f"<br/>• {s}"
    
    interp_style = ParagraphStyle('interp', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9)
    interp_box = Table(
        [[Paragraph(interp_content, interp_style)]],
        colWidths=[170 * mm]
    )
    interp_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(box_color)),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(interp_box)
    
    return elements


# ============================================================================
# PAGE 5: STREFY TRENINGOWE
# ============================================================================

def build_page_zones(
    thresholds: Dict[str, Any],
    styles: Dict
) -> List:
    """Build Page 5: Training Zones.
    
    Contains:
    - Zones table based on VT1/VT2
    - Zone descriptions
    """
    elements = []
    
    elements.append(Paragraph("<font size='14'>1.2 STREFY TRENINGOWE</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))
    
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
        
        data = [
            ["Strefa", "Zakres [W]", "Opis", "Cel treningowy"],
            ["Z1 Recovery", f"< {z1_max}", "Bardzo łatwy", "Regeneracja"],
            ["Z2 Endurance", f"{z2_min}–{z2_max}", "Komfortowy", "Baza tlenowa"],
            ["Z3 Tempo", f"{z3_min}–{z3_max}", "Umiarkowany", "Wytrzymałość"],
            ["Z4 Threshold", f"{z4_min}–{z4_max}", "Ciężki", "Próg"],
            ["Z5 VO₂max", f"> {z5_min}", "Maksymalny", "Pułap Tlenowy"],
        ]
    else:
        data = [
            ["Strefa", "Zakres [W]", "Opis", "Cel treningowy"],
            ["Z1 Recovery", "-", "Bardzo łatwy", "Regeneracja"],
            ["Z2 Endurance", "-", "Komfortowy", "Baza tlenowa"],
            ["Z3 Tempo", "-", "Umiarkowany", "Wytrzymałość"],
            ["Z4 Threshold", "-", "Ciężki", "Próg"],
            ["Z5 VO₂max", "-", "Maksymalny", "Pułap Tlenowy"],
        ]
    
    table = Table(data, colWidths=[35 * mm, 35 * mm, 35 * mm, 40 * mm])
    table.setStyle(get_table_style())
    elements.append(table)
    elements.append(Spacer(1, 8 * mm))
    
    # === USAGE NOTE ===
    elements.append(Paragraph(
        "Powyższe strefy są obliczone automatycznie na podstawie wykrytych progów VT1 i VT2. "
        "Przed zastosowaniem skonsultuj je z trenerem, który może dostosować je do Twoich celów.",
        styles["body"]
    ))
    
    return elements


# ============================================================================
# PAGE 6: OGRANICZENIA INTERPRETACJI
# ============================================================================

def build_page_limitations(
    styles: Dict,
    is_conditional: bool = False
) -> List:
    """Build Page 6: Interpretation Limitations.
    
    Contains:
    - All mandatory disclaimers
    - Conditional warning (if applicable)
    """
    elements = []
    
    elements.append(Paragraph("<font size='14'>5.5 OGRANICZENIA INTERPRETACJI</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))
    
    limitations = [
        ("<b>1. To nie jest badanie medyczne.</b>", 
         "Wyniki są szacunkami algorytmicznymi, nie pomiarami laboratoryjnymi. "
         "Nie służą do diagnozowania stanów zdrowotnych."),
        
        ("<b>2. Dokładność zależy od jakości danych.</b>", 
         "Niepoprawna kalibracja czujników, artefakty ruchu lub niestabilność sygnału "
         "mogą wpłynąć na wyniki."),
        
        ("<b>3. Progi są przybliżeniami.</b>", 
         "VT1/VT2 wykryte algorytmicznie mogą się różnić od wyników testu "
         "spirometrycznego w laboratorium."),
        
        ("<b>4. Wyniki są jednorazowe.</b>", 
         "Wydolność zmienia się w czasie – powtarzaj testy co 6-8 tygodni, "
         "aby śledzić postępy."),
        
        ("<b>5. SmO₂ to sygnał wspierający.</b>", 
         "LT1/LT2 z SmO₂ nie zastępują progów wentylacyjnych. "
         "Służą do dodatkowej walidacji."),
        
        ("<b>6. Skonsultuj się z trenerem.</b>", 
         "Przed wprowadzeniem zmian w treningu skonsultuj wyniki "
         "z wykwalifikowanym specjalistą."),
    ]
    
    for title, description in limitations:
        elements.append(Paragraph(title, styles["body"]))
        elements.append(Paragraph(description, styles["body"]))
        elements.append(Spacer(1, 3 * mm))
    
    # === CONDITIONAL WARNING ===
    if is_conditional:
        elements.append(Spacer(1, 4 * mm))
        warning_text = (
            "<b>⚠️ Ten raport został wygenerowany dla testu rozpoznanego warunkowo.</b><br/>"
            "Profil mocy lub czas kroków wykazują odchylenia od standardowego protokołu Ramp Test. "
            "Interpretacja jest obarczona zwiększoną niepewnością."
        )
        warning_table = Table(
            [[Paragraph(warning_text, styles["body"])]],
            colWidths=[160 * mm]
        )
        warning_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLORS["warning"]),
            ("TEXTCOLOR", (0, 0), (-1, -1), COLORS["text"]),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 2, COLORS["warning"]),
        ]))
        elements.append(warning_table)
    
    return elements


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _build_chart(chart_path: str, title: str, styles: Dict) -> List:
    """Build a chart section with image.
    
    Args:
        chart_path: Path to chart PNG file
        title: Section title
        styles: Paragraph styles dictionary
        
    Returns:
        List of flowables
    """
    from reportlab.platypus import KeepTogether
    
    chart_elements = []
    
    # Title for the chart
    chart_elements.append(Paragraph(title, styles["subheading"]))
    
    # 1. Check if file exists
    if not chart_path or not os.path.exists(chart_path):
        logger.warning(f"PDF Layout: Chart file missing for '{title}' at path: {chart_path}")
        chart_elements.append(Paragraph("Wykres niedostępny", styles["small"]))
        return [KeepTogether(chart_elements)]
    
    # 2. Embed image
    try:
        available_width = PAGE_WIDTH - 2 * MARGIN
        img = Image(chart_path)
        
        # Scale to fit width
        aspect = img.imageHeight / img.imageWidth
        img_width = min(available_width, 150 * mm)
        img_height = img_width * aspect
        
        # Limit height
        if img_height > 90 * mm:
            img_height = 90 * mm
            img_width = img_height / aspect
        
        img.drawWidth = img_width
        img.drawHeight = img_height
        
        chart_elements.append(img)
    except Exception as e:
        logger.error(f"PDF Layout: Error embedding chart '{title}' from {chart_path}: {e}")
    
    # Wrap in KeepTogether to prevent title/chart separation across pages
    return [KeepTogether(chart_elements)]


def _build_education_block(title: str, content: str, styles: Dict) -> List:
    """Helper to build a consistent education block with 'Dlaczego to ma znaczenie?'."""
    elements = []
    
    # Label
    label = Paragraph("", styles["small"])  # Removed educational label
    elements.append(label)
    
    # Title & Text in a subtle box
    inner_story = [
        Paragraph(f"<b>{title}</b>", styles["heading"]),
        Spacer(1, 1 * mm),
        Paragraph(content, styles["body_italic"])
    ]
    
    table = Table([[inner_story]], colWidths=[170 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLORS["light_grey"]),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, COLORS["grey"]),
        ('BOX', (0, 0), (-1, -1), 0.25, COLORS["grey"]),
        ('LEFTPADDING', (0, 0), (-1, -1), 4 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4 * mm),
        ('TOPPADDING', (0, 0), (-1, -1), 4 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4 * mm),
    ]))
    
    elements.append(table)
    return elements


# ============================================================================
# PAGE 5: TEORIA FIZJOLOGICZNA (INSCYD/WKO5)
# ============================================================================

def build_page_theory(styles: Dict) -> List:
    """Build Page: Model Metaboliczny (2.3)."""
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import TableStyle
    elements = []
    
    elements.append(Paragraph("<font size='14'>2.3 MODEL METABOLICZNY</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))
    
    # Intro
    elements.append(Paragraph(
        "Twoja wydajność zależy od interakcji trzech systemów energetycznych. "
        "Zrozumienie ich pozwala na precyzyjne dopasowanie treningu.",
        styles["body"]
    ))
    elements.append(Spacer(1, 4 * mm))
    
    # VO2max
    elements.append(Paragraph("VO₂max (System Tlenowy)", styles["heading"]))
    elements.append(Paragraph(
        "Maksymalna ilość tlenu, jaką Twój organizm może przyswoić. "
        "Jest to Twój „silnik diesla” – odpowiada za moc na długim dystansie. "
        "Wysokie VO₂max jest kluczowe dla każdego kolarza wytrzymałościowego.",
        styles["body"]
    ))
    
    # VLaMax
    elements.append(Paragraph("VLaMax (System Glikolityczny)", styles["heading"]))
    elements.append(Paragraph(
        "Maksymalne tempo produkcji mleczanu. To Twój „dopalacz turbo”. "
        "Wysokie VLaMax daje świetny sprint i ataki, ale powoduje szybkie zużycie węglowodanów (niskie FatMax) i obniża próg FTP. "
        "Niskie VLaMax zwiększa próg FTP i oszczędza glikogen (dobre dla Ironman/GC), ale ogranicza dynamikę.",
        styles["body"]
    ))
    
    # Interaction
    elements.append(Paragraph("Interakcja VO₂max ↔ VLaMax", styles["subheading"]))
    elements.append(Paragraph(
        "Twój próg FTP to wynik walki między tymi dwoma systemami. "
        "Aby podnieść FTP, możesz albo zwiększyć VO₂max (powiększyć silnik), albo obniżyć VLaMax (zmniejszyć spalanie). "
        "Wybór strategii zależy od Twojego typu zawodnika.",
        styles["body"]
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # FatMax explain
    elements.append(Paragraph("FatMax (Metabolizm Tłuszczowy)", styles["heading"]))
    elements.append(Paragraph(
        "Moc, przy której spalasz najwięcej tłuszczu (zwykle strefa Z2). "
        "Trening w tej strefie uczy organizm oszczędzania glikogenu.",
        styles["body"]
    ))
    elements.append(Spacer(1, 4 * mm))
    
    elements.append(Paragraph("Typy Zawodników i Strategie", styles["heading"]))
    data = [
        ["Typ", "VO2max", "VLaMax", "Charakterystyka"],
        ["Sprinter", "Średni", "Wysoki", "Dynamika, punch, sprinty"],
        ["Climber", "Wysoki", "Niski", "Długie wspinaczki, tempo"],
        ["Time Trialist", "Wysoki", "Niski", "Równe tempo, aerodynamika"],
        ["Puncheur", "Wysoki", "Średni", "Ataki, krótkie górki"]
    ]
    t = Table(data, colWidths=[30*mm, 30*mm, 30*mm, 80*mm])
    # Table should use DejaVuSans for Polish chars if needed, though ASCII used above
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor("#1F77B4")),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#555555")),
        ('ROWHEIGHT', (0, 0), (-1, -1), 8 * mm),
    ]))
    elements.append(t)
    
    return elements


# ============================================================================
# NEW PAGE: PROTOKÓŁ I HIERARCHIA SYGNAŁÓW (Page 20 simulation)
# ============================================================================

def build_page_protocol(
    styles: Dict
) -> List:
    """Build Page for Signal Hierarchy and Protocol information."""
    elements = []
    
    elements.append(Paragraph("<font size='14'>5.4 PROTOKÓŁ TESTU</font>", styles["center"]))
    elements.append(Spacer(1, 8 * mm))
    
    # Extensive Theory Section
    elements.append(Paragraph("<b>FUNDAMENT METODOLOGII</b>", styles["heading"]))
    elements.append(Spacer(1, 4 * mm))
    
    theory_text = (
        "Współczesna analiza fizjologiczna opiera się na integracji wielu sygnałów, "
        "jednak nie wszystkie mają taką samą wagę diagnostyczną. Kluczem do sukcesu "
        "jest zrozumienie 'opóźnienia' i 'reaktywności' każdego z nich.<br/><br/>"
        "<b>1. WENTYLACJA (VE):</b> Nasz główny sygnał (Golden Standard). Dlaczego? Ponieważ "
        "wentylacja reaguje niemal natychmiast na zmiany pH krwi i poziomu CO2. Jest to "
        "bezpośrednie odbicie metabolizmu całego organizmu.<br/><br/>"
        "<b>2. OKSYDACJA MIĘŚNIOWA (SmO2):</b> Sygnał o najwyższej reaktywności lokalnej. "
        "Pozwala zobaczyć co dzieje się bezpośrednio w pracującym mięśniu (dostawa vs zapotrzebowanie). "
        "SmO2 reaguje najszybciej na zmiany obciążenia, ale jest sygnałem punktowym.<br/><br/>"
        "<b>3. TĘTNO (HR):</b> Sygnał najbardziej opóźniony (Heart Rate Lag). HR jest sterowane "
        "częścią autonomiczną układu nerwowego i potrzebuje czasu, aby 'dogonić' zapotrzebowanie "
        "tlenowe. HR jest doskonałym wskaźnikiem kosztu ustrojowego, ale słabym narzędziem "
        "do precyzyjnej detekcji progów w krótkich interwałach."
    )
    elements.append(Paragraph(theory_text, styles["body"]))
    elements.append(Spacer(1, 10 * mm))
    
    elements.append(Paragraph("<b>ZNACZENIE PROTOKOŁU</b>", styles["heading"]))
    elements.append(Spacer(1, 4 * mm))
    
    protocol_text = (
        "Długość kroku (rampy) jest krytyczna. Standardowy protokół 1-minutowy często "
        "prowadzi do przeszacowania mocy progowej, ponieważ sygnały (szczególnie HR i VE) "
        "nie zdążą osiągnąć stanu stabilnego (Steady State).<br/><br/>"
        "W naszej analizie stosujemy matematyczną korektę opóźnień lub zalecamy protokoły "
        "o długości 2-3 minut na stopień, co pozwala na pełną stabilizację kinetyki gazowej "
        "i parametrów krążeniowych. Dzięki temu wyznaczone progi VT1/VT2 oraz SmO2-LT "
        "są powtarzalne i mają realne przełożenie na trening w terenie."
    )
    elements.append(Paragraph(protocol_text, styles["body"]))
    
    return elements


# ============================================================================
# PAGE 6: TERMOREGULACJA
# ============================================================================

def build_page_thermal(
    thermo_data: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict
) -> List:
    """Build Page 6: Thermal Analysis - Enhanced with metrics and recommendations."""
    from reportlab.lib.colors import HexColor
    # Removed redundant local import

    from reportlab.platypus import TableStyle
    
    elements = []
    
    elements.append(Paragraph("<font size='14'>4.3 TERMOREGULACJA</font>", styles["center"]))
    elements.append(Paragraph("<font size='10' color='#7F8C8D'>Dynamika temperatury, tolerancja cieplna, rekomendacje</font>", styles["body"]))
    elements.append(Spacer(1, 6 * mm))
    
    elements.append(Paragraph(
        "Ciepło jest cichym zabójcą wydajności. Wzrost temperatury głębokiej (Core Temp) "
        "powoduje przekierowanie krwi do skóry (chłodzenie), co zabiera tlen pracującym mięśniom.",
        styles["body"]
    ))
    elements.append(Spacer(1, 4 * mm))
    
    # Chart 1: Core Temp vs HSI
    if figure_paths and "thermal_hsi" in figure_paths:
        elements.extend(_build_chart(figure_paths["thermal_hsi"], "Temp. Głęboka vs Indeks Zmęczenia (HSI)", styles))
        elements.append(Spacer(1, 6 * mm))
    
    # === KEY NUMBERS TABLE (Thermoregulation) ===
    # thermo_data is now passed directly
    metrics = thermo_data.get("metrics", {})
    classification = thermo_data.get("classification", {})
    
    # Check if we have actual data (not empty/default)
    has_thermo_data = bool(metrics) and metrics.get("max_core_temp", 0) > 35
    
    # Get values with proper fallbacks
    if has_thermo_data:
        max_temp = metrics.get("max_core_temp", 0)
        delta_10min = metrics.get("delta_per_10min", 0)
        time_38_0 = metrics.get("time_to_38_0_min")
        time_38_5 = metrics.get("time_to_38_5_min")
        peak_hsi = metrics.get("peak_hsi", 0)
        
        max_temp_str = f"{max_temp:.1f} C"
        delta_str = f"{delta_10min:.2f} C"
        peak_hsi_str = f"{peak_hsi:.1f}"
    else:
        max_temp_str = "---"
        delta_str = "---"
        time_38_0 = None
        time_38_5 = None
        peak_hsi_str = "---"
    
    # Classification
    tolerance = classification.get("heat_tolerance", "unknown") if has_thermo_data else "unknown"
    tolerance_color = classification.get("color", "#808080") if has_thermo_data else "#808080"
    tolerance_label = {"good": "DOBRA", "moderate": "SREDNIA", "poor": "SLABA"}.get(tolerance, "BRAK DANYCH")
    
    elements.append(Paragraph("KLUCZOWE LICZBY", styles["heading"]))
    elements.append(Spacer(1, 2 * mm))
    
    key_data = [
        ["Metryka", "Wartość", "Interpretacja"],
        ["Max Core Temp", max_temp_str, "Szczytowa temperatura głęboka"],
        ["Delta Temp / 10 min", delta_str, f"Tolerancja: {tolerance_label}"],
        ["Czas do 38.0 C", f"{time_38_0:.0f} min" if time_38_0 else "---", "Prog ostrzegawczy"],
        ["Czas do 38.5 C", f"{time_38_5:.0f} min" if time_38_5 else "---", "Prog krytyczny"],
        ["Peak HSI", peak_hsi_str, "Indeks obciazenia cieplnego"],
    ]
    
    table = Table(key_data, colWidths=[45 * mm, 35 * mm, 85 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor("#1F77B4")),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'DejaVuSans-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#555555")),
        ('ROWHEIGHT', (0, 0), (-1, -1), 10 * mm),
        # Delta row gets classification color
        ('BACKGROUND', (0, 2), (-1, 2), HexColor(tolerance_color)),
        ('TEXTCOLOR', (0, 2), (-1, 2), HexColor("#FFFFFF")),
        # Other rows light
        ('BACKGROUND', (0, 1), (-1, 1), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 1), (-1, 1), HexColor("#333333")),
        ('BACKGROUND', (0, 3), (-1, 3), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 3), (-1, 3), HexColor("#333333")),
        ('BACKGROUND', (0, 4), (-1, 4), HexColor("#e8e8e8")),
        ('TEXTCOLOR', (0, 4), (-1, 4), HexColor("#333333")),
        ('BACKGROUND', (0, 5), (-1, 5), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 5), (-1, 5), HexColor("#333333")),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))
    
    # === CLASSIFICATION VERDICT ===
    if tolerance == "poor":
        verdict_text = (
            "<b>SLABA TOLERANCJA CIEPLNA</b><br/>"
            "Tempo narastania temperatury przekracza prog bezpieczny. "
            "Redystrybucja krwi do skory konkuruje z dostawa O2 do miesni. "
            "Ryzyko przegrzania jest wysokie."
        )
        verdict_color = "#E74C3C"
    elif tolerance == "moderate":
        verdict_text = (
            "<b>SREDNIA TOLERANCJA</b><br/>"
            "Uklad chlodzenia radzi sobie, ale istnieje margines do poprawy. "
            "Adaptacja cieplna nie jest pelna."
        )
        verdict_color = "#F39C12"
    else:
        verdict_text = (
            "<b>DOBRA TOLERANCJA</b><br/>"
            "Tempo narastania temperatury miesci sie w normie. "
            "Uklad termoregulacji skutecznie balansuje miedzy chlodzeniem a perfuzja."
        )
        verdict_color = "#27AE60"
    
    white_style = ParagraphStyle('thermo_verdict', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9)
    verdict_box = Table(
        [[Paragraph(verdict_text, white_style)]],
        colWidths=[165 * mm]
    )
    verdict_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(verdict_color)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(verdict_box)
    elements.append(Spacer(1, 6 * mm))
    
    # === HR/EF CONNECTION ===
    elements.append(PageBreak())
    elements.append(Paragraph("<b>POŁĄCZENIE Z DRYFEM HR I EF</b>", styles["heading"]))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<b>Mechanizm fizjologiczny:</b> Wysoka temperatura wymusza redystrybucję krwi do skóry "
        "w celu chłodzenia. Serce musi pompować większą objętość krwi, by utrzymać zarówno chłodzenie, "
        "jak i dostawę O₂ do mięśni. Efekt: wzrost HR przy stałej mocy (cardiac drift), "
        "spadek Efficiency Factor (EF). To jest kardynalny syndrom przegrzania.",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<b>Konsekwencje dla wydolności:</b> Każdy 1°C wzrostu temperatury rdzenia powoduje "
        "wzrost HR o 8-10 bpm oraz spadek VO₂max o 1.5-2%. Przy temperaturze >39°C następuje "
        "ochronne ograniczenie rekrutacji jednostek motorycznych przez OUN.",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "<b>Adaptacja cieplna:</b> Po 10-14 dniach treningu w cieple (60-90min @ Z2, temp >28°C) "
        "obserwuje się: wcześniejsze pocenie, niższy HR przy tej samej mocy, zmniejszony drift, "
        "oraz poprawę tolerancji cieplnej o 15-20%.",
        styles["body"]
    ))
    elements.append(Spacer(1, 4 * mm))
    
    # === TRAINING RECOMMENDATIONS ===
    elements.append(Paragraph("<b>REKOMENDACJE</b>", styles["heading"]))
    elements.append(Spacer(1, 2 * mm))
    
    if tolerance == "poor":
        recommendations = [
            "PRIORYTET: Trening w cieple (heat acclimation) - 10-14 dni, 60-90min @ Z2",
            "Pre-cooling: kamizelka lodowa przed startem",
            "Nawodnienie: 500-800ml/h + elektrolity",
            "Unikaj zawodow >28C do czasu adaptacji",
        ]
    elif tolerance == "moderate":
        recommendations = [
            "Rozwaz 5-7 dni treningu w cieple przed wazymi zawodami",
            "Chlodzenie zewnetrzne: woda na glowe co 15-20 min",
            "Kontroluj wage przed/po treningu (max -2%)",
        ]
    else:
        recommendations = [
            "Adaptacja wystarczajaca - mozesz startowac w cieple",
            "Utrzymuj nawodnienie 400-600ml/h",
            "Kontynuuj okresowy trening w cieple (1x/tyg)",
        ]
    
    white_rec_style = ParagraphStyle('rec_white', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9)
    rec_data = [[Paragraph(f"* {rec}", white_rec_style)] for rec in recommendations]
    rec_table = Table(rec_data, colWidths=[165 * mm])
    rec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor("#16213e")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(rec_table)
    
    # FORCE PAGE BREAK BEFORE CARDIAC DRIFT ANALYSIS
    elements.append(PageBreak())
    
    # ========================================================================
    # CARDIAC DRIFT ANALYSIS - PRO LAYOUT
    # ========================================================================
    elements.append(Paragraph("Analiza Dryfu Efektywności (Cardiac Drift)", styles["title"]))
    elements.append(Paragraph("<font size='10' color='#7F8C8D'>Dynamika EF, klasyfikacja dryfu, implikacje treningowe</font>", styles["body"]))
    elements.append(Spacer(1, 6 * mm))
    
    # Get drift data from thermo_data (will be populated by persistence.py)
    drift_data = thermo_data.get("cardiac_drift", {})
    drift_metrics = drift_data.get("metrics", {})
    drift_signals = drift_data.get("key_signals", {})
    drift_class = drift_data.get("classification", {})
    drift_interp = drift_data.get("interpretation", {})
    
    # Check if we have drift data
    has_drift_data = bool(drift_metrics) and drift_metrics.get("ef_start", 0) > 0
    
    if has_drift_data:
        ef_start = drift_metrics.get("ef_start", 0)
        ef_end = drift_metrics.get("ef_end", 0)
        delta_pct = drift_metrics.get("delta_ef_pct", 0)
        ef_slope = drift_metrics.get("ef_vs_temp_slope")
        hsi_peak = drift_signals.get("hsi_peak", 0)
        smo2_drift = drift_signals.get("smo2_drift_pct", 0)
        
        drift_level = drift_class.get("drift_level", "unknown")
        drift_type = drift_class.get("drift_type", "unknown")
        drift_color = drift_class.get("color", "#808080")
        
        # Status helpers
        def get_delta_status(d):
            if abs(d) < 5: return ("STABILNY", "#27AE60")
            elif abs(d) < 10: return ("UMIARKOWANY", "#F39C12")
            else: return ("WYSOKI", "#E74C3C")
        
        def get_hsi_status(h):
            if h < 5: return ("NISKI", "#27AE60")
            elif h < 8: return ("OSTRZEZENIE", "#F39C12")
            else: return ("KRYTYCZNY", "#E74C3C")
        
        def get_smo2_status(s):
            if abs(s) < 5: return ("STABILNY", "#27AE60")
            else: return ("DRYF OBWODOWY", "#F39C12")
        
        delta_status, delta_color = get_delta_status(delta_pct)
        hsi_status, hsi_color = get_hsi_status(hsi_peak)
        smo2_status, smo2_color = get_smo2_status(smo2_drift)
    else:
        ef_start = 0
        ef_end = 0
        delta_pct = 0
        ef_slope = None
        hsi_peak = 0
        smo2_drift = 0
        drift_level = "unknown"
        drift_type = "unknown"
        drift_color = "#808080"
        delta_status, delta_color = ("BRAK", "#808080")
        hsi_status, hsi_color = ("BRAK", "#808080")
        smo2_status, smo2_color = ("BRAK", "#808080")
    
    # === KEY SIGNALS BOX ===
    elements.append(Paragraph("KLUCZOWE SYGNAŁY", styles["heading"]))
    elements.append(Spacer(1, 2 * mm))
    
    key_signals_data = [
        ["Sygnał", "Wartość", "Status"],
        ["EF Start", f"{ef_start:.2f} W/bpm" if ef_start > 0 else "---", "BAZOWY"],
        ["EF End", f"{ef_end:.2f} W/bpm" if ef_end > 0 else "---", f"{delta_pct:+.1f}%" if has_drift_data else "---"],
        ["dEF / dC", f"{ef_slope:.3f} W/bpm/C" if ef_slope else "---", drift_type.upper() if has_drift_data else "---"],
        ["HSI Szczyt", f"{hsi_peak:.1f}" if hsi_peak > 0 else "---", hsi_status],
        ["SmO2 Dryf", f"{smo2_drift:+.1f}%" if has_drift_data else "---", smo2_status],
    ]
    
    signals_table = Table(key_signals_data, colWidths=[45 * mm, 50 * mm, 70 * mm])
    signals_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor("#1a1a2e")),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'DejaVuSans-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#555555")),
        ('ROWHEIGHT', (0, 0), (-1, -1), 9 * mm),
        # Row backgrounds
        ('BACKGROUND', (0, 1), (1, 1), HexColor("#e8f5e9")),
        ('TEXTCOLOR', (0, 1), (1, 1), HexColor("#333333")),
        ('BACKGROUND', (2, 1), (2, 1), HexColor("#3498DB")),
        ('TEXTCOLOR', (2, 1), (2, 1), HexColor("#FFFFFF")),
        # Delta row - color by status
        ('BACKGROUND', (0, 2), (1, 2), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 2), (1, 2), HexColor("#333333")),
        ('BACKGROUND', (2, 2), (2, 2), HexColor(delta_color)),
        ('TEXTCOLOR', (2, 2), (2, 2), HexColor("#FFFFFF")),
        # EF slope row
        ('BACKGROUND', (0, 3), (1, 3), HexColor("#e8e8e8")),
        ('TEXTCOLOR', (0, 3), (1, 3), HexColor("#333333")),
        ('BACKGROUND', (2, 3), (2, 3), HexColor(drift_color)),
        ('TEXTCOLOR', (2, 3), (2, 3), HexColor("#FFFFFF")),
        # HSI row
        ('BACKGROUND', (0, 4), (1, 4), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 4), (1, 4), HexColor("#333333")),
        ('BACKGROUND', (2, 4), (2, 4), HexColor(hsi_color)),
        ('TEXTCOLOR', (2, 4), (2, 4), HexColor("#FFFFFF")),
        # SmO2 row
        ('BACKGROUND', (0, 5), (1, 5), HexColor("#e8e8e8")),
        ('TEXTCOLOR', (0, 5), (1, 5), HexColor("#333333")),
        ('BACKGROUND', (2, 5), (2, 5), HexColor(smo2_color)),
        ('TEXTCOLOR', (2, 5), (2, 5), HexColor("#FFFFFF")),
    ]))
    elements.append(signals_table)
    elements.append(Spacer(1, 6 * mm))
    
    # === CLASSIFICATION VERDICT BOX ===
    if has_drift_data:
        mechanism = drift_interp.get("mechanism", "")
        verdict_text = f"{mechanism}"  # Removed duplicate title, just show mechanism
    else:
        verdict_text = "<b>BRAK DANYCH DRYFU</b><br/>Analiza drift wymaga danych EF (power/HR)."
        drift_color = "#808080"
    
    verdict_style = ParagraphStyle('verdict_white', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9)
    verdict_box = Table(
        [[Paragraph(verdict_text, verdict_style)]],
        colWidths=[165 * mm]
    )
    verdict_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(drift_color)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(verdict_box)
    elements.append(Spacer(1, 6 * mm))
    
    # === RACE CONSEQUENCE SIMULATION ===
    # Get core temp from thermo_data
    thermo_metrics = thermo_data.get("metrics", {})
    core_temp_peak = thermo_metrics.get("max_core_temp", 0)
    
    # Calculate expected power loss after 60 min
    # Threshold: dEF/dC exists AND core_temp > 38
    ef_slope_val = ef_slope if ef_slope else 0
    
    if abs(ef_slope_val) > 0.01 and core_temp_peak > 38.0:
        # Assume conservative: 1% EF loss ≈ 0.7% power loss
        # If we have delta_pct (change over test), extrapolate to 60 min
        # Use absolute delta_pct as base (already computed)
        power_loss_pct = abs(delta_pct) * 0.7
        
        # Clamp to reasonable range (2-15%)
        power_loss_pct = max(2.0, min(15.0, power_loss_pct))
        
        simulation_text = (
            f"<b>SYMULACJA KONSEKWENCJI WYŚCIGOWYCH:</b> Przy obecnym koszcie termicznym (temp. rd. {core_temp_peak:.1f}°C, "
            f"dryf EF {delta_pct:+.1f}%), oczekiwany spadek efektywnej mocy wynosi ~{power_loss_pct:.0f}% "
            "po 60 min w gorących warunkach."
        )
        sim_color = "#E74C3C" if power_loss_pct > 8 else "#F39C12"
    else:
        simulation_text = (
            "<b>SYMULACJA KONSEKWENCJI WYŚCIGOWYCH:</b> Obciążenie termiczne w akceptowalnych granicach. "
            "Brak przewidywanego znaczącego spadku mocy dla 60 min wysokości w bieżących warunkach."
        )
        sim_color = "#27AE60"
    
    sim_style = ParagraphStyle('sim_text', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9)
    sim_box = Table(
        [[Paragraph(simulation_text, sim_style)]],
        colWidths=[165 * mm]
    )
    sim_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor(sim_color)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(sim_box)
    elements.append(Spacer(1, 6 * mm))
    
    # Chart: EF vs Time/Temp
    if figure_paths and "thermal_efficiency" in figure_paths:
        elements.extend(_build_chart(figure_paths["thermal_efficiency"], "Efektywność vs Czas/Temperatura", styles))
        elements.append(Spacer(1, 4 * mm))
    
    
    # === TRAINING IMPLICATIONS BOX ===
    # UWAGA: Usunięto PageBreak aby zapobiec pustej stronie
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("IMPLIKACJE TRENINGOWE", styles["heading"]))
    elements.append(Spacer(1, 2 * mm))
    
    # Add extended introduction
    elements.append(Paragraph(
        "<b>Zastosowanie w praktyce:</b> Poniższe zalecenia treningowe wynikają bezpośrednio "
        "z analizy dryfu sercowego i termicznego. Dostosuj intensywność i strategię "
        "nawodnienia do warunków środowiskowych.",
        styles["body"]
    ))
    elements.append(Spacer(1, 2 * mm))
    
    if has_drift_data:
        implications = drift_interp.get("training_implications", [])[:4]  # Limit to 4 items
        # Add extra recommendations
        extra_implications = [
            "Monitoruj EF w czasie rzeczywistym podczas długich wysiłków >2h",
            "Stosuj pre-cooling przed zawodami w gorącu (kamizelka lodowa, zimny napój)",
            "Nawadniaj regularnie: 500-750ml/h + 500-1000mg Na+/h w gorącu"
        ]
        implications.extend(extra_implications[:2])  # Add 2 extra
    else:
        implications = [
            "Brak danych do wygenerowania rekomendacji",
            "Upewnij się, że plik źródłowy zawiera kolumny Power i HR",
        ]
    
    impl_style = ParagraphStyle('impl_white', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=8)
    impl_data = [[Paragraph(f"→ {impl}", impl_style)] for impl in implications]
    impl_table = Table(impl_data, colWidths=[165 * mm])
    impl_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor("#16213e")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(impl_table)
    
    return elements


# ============================================================================
# PAGE 7: PROFIL METABOLICZNY (LIMITERY)
# ============================================================================

# ============================================================================
# NEW PAGE: BIOMECHANIKA (Premium INSCYD/WKO Quality)
# ============================================================================

def build_page_biomech(
    figure_paths: Dict[str, str],
    styles: Dict,
    biomech_data: Optional[Dict[str, Any]] = None
) -> List:
    """Build Biomechanics & Occlusion Physiology page - INSCYD/WKO Quality."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    
    elements = []
    
    elements.append(Paragraph("<font size='14'>3.4 BIOMECHANIKA</font>", styles["center"]))
    elements.append(Paragraph("<font size='10' color='#7F8C8D'>Fizjologia okluzji i relacja siła–tlen</font>", styles["body"]))
    elements.append(Spacer(1, 6 * mm))
    
    # Chart 1: Torque vs Cadence
    if figure_paths and "biomech_summary" in figure_paths:
        elements.extend(_build_chart(figure_paths["biomech_summary"], "Moment Obrotowy vs Kadencja", styles))
        elements.append(Spacer(1, 4 * mm))
        
    # Chart 2: Torque vs SmO2 (Occlusion)
    if figure_paths and "biomech_torque_smo2" in figure_paths:
        elements.extend(_build_chart(figure_paths["biomech_torque_smo2"], "Fizjologia Okluzji (Siła vs Tlen)", styles))
        elements.append(Spacer(1, 6 * mm))
    
    # === KEY NUMBERS BOX ===
    if biomech_data and "metrics" in biomech_data:
        metrics = biomech_data["metrics"]
        classification = biomech_data.get("classification", {})
        
        elements.append(PageBreak())
        elements.append(Paragraph("KLUCZOWE LICZBY", styles["heading"]))
        elements.append(Spacer(1, 2 * mm))
        
        # Determine colors based on classification
        level = classification.get("level", "unknown")
        level_color = classification.get("color", "#808080")
        level_label = {"low": "NISKA", "moderate": "UMIARKOWANA", "high": "WYSOKA"}.get(level, "---")
        
        # Build metrics table
        occlusion_idx = metrics.get("occlusion_index", 0)
        slope = metrics.get("regression_slope", 0)
        r2 = metrics.get("regression_r2", 0)
        smo2_base = metrics.get("smo2_baseline", 0)
        torque_base = metrics.get("torque_at_baseline", 0)
        torque_10 = metrics.get("torque_at_minus_10")
        torque_20 = metrics.get("torque_at_minus_20")
        
        key_data = [
            ["Metryka", "Wartość", "Interpretacja"],
            ["INDEKS OKLUZJI", f"{occlusion_idx:.3f}", f"Okluzja: {level_label}"],
            ["Nachylenie SmO2/Torque", f"{slope:.4f} %/Nm", f"R² = {r2:.2f}"],
            ["SmO2 bazowe", f"{smo2_base:.1f} %", f"@ {torque_base:.0f} Nm"],
            ["Torque @ SmO2 -10%", f"{torque_10:.0f} Nm" if torque_10 else "---", "Próg umiarkowanej okluzji"],
            ["Torque @ SmO2 -20%", f"{torque_20:.0f} Nm" if torque_20 else "---", "Próg istotnej okluzji"],
        ]
        
        table = Table(key_data, colWidths=[50 * mm, 40 * mm, 75 * mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor("#1a1a2e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ('BACKGROUND', (0, 1), (-1, 1), HexColor(level_color)),  # OCCLUSION INDEX row
            ('TEXTCOLOR', (0, 1), (-1, 1), HexColor("#FFFFFF")),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),  # ALL cells
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'DejaVuSans-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#555555")),
            ('ROWHEIGHT', (0, 0), (-1, -1), 12 * mm),
            # Light backgrounds for data rows (except OCCLUSION INDEX row)
            ('BACKGROUND', (0, 2), (-1, 2), HexColor("#f5f5f5")),
            ('TEXTCOLOR', (0, 2), (-1, 2), HexColor("#333333")),
            ('BACKGROUND', (0, 3), (-1, 3), HexColor("#e8e8e8")),
            ('TEXTCOLOR', (0, 3), (-1, 3), HexColor("#333333")),
            ('BACKGROUND', (0, 4), (-1, 4), HexColor("#f5f5f5")),
            ('TEXTCOLOR', (0, 4), (-1, 4), HexColor("#333333")),
            ('BACKGROUND', (0, 5), (-1, 5), HexColor("#e8e8e8")),
            ('TEXTCOLOR', (0, 5), (-1, 5), HexColor("#333333")),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 6 * mm))
        
        # === SAFE TORQUE WINDOW ===
        elements.append(Paragraph("<b>BEZPIECZNE OKNO MOMENTU OBROTOWEGO</b>", styles["heading"]))
        elements.append(Spacer(1, 2 * mm))
        
        # Define zones
        safe_max = torque_10 if torque_10 else torque_base
        warning_min = torque_10 if torque_10 else 0
        warning_max = torque_20 if torque_20 else 0
        critical_min = torque_20 if torque_20 else 0
        
        # Build zone table
        zone_rows = [
            ["Strefa", "Zakres Momentu", "Status"],
            ["BEZPIECZNA", f"< {safe_max:.0f} Nm" if safe_max else "---", "Pełna dostawa tlenowa utrzymana"],
            ["OSTRZEŻENIE", f"{warning_min:.0f}–{warning_max:.0f} Nm" if warning_min and warning_max else "---", "Częściowa okluzja, SmO2 spada"],
            ["KRYTYCZNA", f"> {critical_min:.0f} Nm" if critical_min else "---", "Silna okluzja, szybka desaturacja"],
        ]
        
        zone_table = Table(zone_rows, colWidths=[35 * mm, 50 * mm, 80 * mm])
        zone_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor("#2C3E50")),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ('FONTNAME', (0, 0), (-1, -1), FONT_FAMILY),
            ('FONTNAME', (0, 0), (-1, 0), FONT_FAMILY_BOLD),
            ('FONTNAME', (0, 1), (0, -1), FONT_FAMILY_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#555555")),
            ('ROWHEIGHT', (0, 0), (-1, -1), 10 * mm),
            # Zone colors
            ('BACKGROUND', (0, 1), (0, 1), HexColor("#27AE60")),  # SAFE
            ('TEXTCOLOR', (0, 1), (0, 1), HexColor("#FFFFFF")),
            ('BACKGROUND', (0, 2), (0, 2), HexColor("#F39C12")),  # WARNING
            ('TEXTCOLOR', (0, 2), (0, 2), HexColor("#FFFFFF")),
            ('BACKGROUND', (0, 3), (0, 3), HexColor("#E74C3C")),  # CRITICAL
            ('TEXTCOLOR', (0, 3), (0, 3), HexColor("#FFFFFF")),
            # Data cells
            ('BACKGROUND', (1, 1), (-1, -1), HexColor("#f8f9fa")),
            ('TEXTCOLOR', (1, 1), (-1, -1), HexColor("#333333")),
        ]))
        elements.append(zone_table)
        elements.append(Spacer(1, 3 * mm))
        
        # Collapse verdict
        collapse_point = torque_20 if torque_20 else (torque_10 if torque_10 else 0)
        if collapse_point:
            collapse_text = f"Efektywna dostawa tlenowa załamuje się powyżej {collapse_point:.0f} Nm."
        else:
            collapse_text = "Progi momentu obrotowego niedostępne dla oceny okluzji."
        elements.append(Paragraph(collapse_text, styles["body"]))
        elements.append(Spacer(1, 6 * mm))
        
        # === VERDICT BOX ===
        elements.append(Paragraph("WERDYKT", styles["heading"]))
        elements.append(Spacer(1, 2 * mm))
        
        # Verdict based on classification
        if level == "high":
            verdict_text = (
                "<b>WYSOKA OKLUZJA MECHANICZNA</b><br/>"
                "Przy wysokich momentach obrotowych naczynia mięśniowe są mechanicznie "
                "kompresowane, ograniczając perfuzję mimo dostępnego VO₂ systemowego. "
                "Styl siłowy (niska kadencja) prowadzi do przedwczesnej hipoksji lokalnej."
            )
            verdict_color = "#E74C3C"
        elif level == "moderate":
            verdict_text = (
                "<b>UMIARKOWANA OKLUZJA</b><br/>"
                "Spadek SmO₂ jest proporcjonalny do wzrostu momentu obrotowego. "
                "Mięśnie wykazują pewną tolerancję na siły, ale istnieje wyraźna granica "
                "powyżej której desaturacja przyspiesza."
            )
            verdict_color = "#F39C12"
        else:
            verdict_text = (
                "<b>NISKA OKLUZJA</b><br/>"
                "Kapilaryzacja mięśniowa jest wystarczająca, aby utrzymać perfuzję "
                "nawet przy wysokich momentach obrotowych. Możliwość efektywnej pracy siłowej."
            )
            verdict_color = "#27AE60"
        
        verdict_box = Table(
            [[Paragraph(verdict_text, ParagraphStyle('verdict', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9))]],
            colWidths=[165 * mm]
        )
        verdict_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor(verdict_color)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BOX', (0, 0), (-1, -1), 1, HexColor(verdict_color)),
        ]))
        elements.append(verdict_box)
        elements.append(Spacer(1, 6 * mm))
        
        # === MECHANISM DESCRIPTION ===
        interpretation = biomech_data.get("interpretation", {})
        mechanism = interpretation.get("mechanism", "")
        riding_style = interpretation.get("riding_style", "")
        
        if mechanism:
            elements.append(Paragraph("<b>MECHANIZM FIZJOLOGICZNY</b>", styles["heading"]))
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph(mechanism, styles["body"]))
            elements.append(Spacer(1, 4 * mm))
        
        if riding_style:
            elements.append(Paragraph("<b>WPŁYW NA STYL JAZDY</b>", styles["heading"]))
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph(riding_style, styles["body"]))
            elements.append(Spacer(1, 4 * mm))
        
        # === TRAINING RECOMMENDATIONS ===
        recommendations = interpretation.get("recommendations", [])
        if recommendations:
            elements.append(Paragraph("<b>ZALECENIA TRENINGOWE</b>", styles["heading"]))
            elements.append(Spacer(1, 2 * mm))
            
            # Use white text style for visibility on dark background
            white_style = ParagraphStyle('white_body', parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9)
            rec_data = [[Paragraph(f"• {rec}", white_style)] for rec in recommendations]
            rec_table = Table(rec_data, colWidths=[165 * mm])
            rec_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), HexColor("#16213e")),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(rec_table)
    else:
        # Fallback for legacy data without biomech analysis
        elements.append(Paragraph(
            "<b>Interpretacja:</b> Spadek saturacji (SmO₂) przy wysokich momentach obrotowych "
            "może świadczyć o okluzji mechanicznej lub niskiej efektywności układu krążenia "
            "w warunkach wysokiego napięcia mięśniowego.",
            styles["body"]
        ))
    
    return elements


# ============================================================================
# NEW PAGE: DRYF FIZJOLOGICZNY
# ============================================================================

def build_page_drift(
    kpi: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict
) -> List:
    """Build Physiological Drift page (heatmaps only, no KPI table)."""
    elements = []
    
    elements.append(Paragraph("<font size='14'>4.2 DRYF FIZJOLOGICZNY</font>", styles["center"]))
    elements.append(Spacer(1, 6 * mm))
    
    # Heatmaps
    if figure_paths and "drift_heatmap_hr" in figure_paths:
        elements.extend(_build_chart(figure_paths["drift_heatmap_hr"], "Mapa Dryfu (HR vs Power)", styles))
        elements.append(Spacer(1, 4 * mm))
        
    if figure_paths and "drift_heatmap_smo2" in figure_paths:
        elements.extend(_build_chart(figure_paths["drift_heatmap_smo2"], "Mapa Oksydacji (SmO2 vs Power)", styles))
        elements.append(Spacer(1, 4 * mm))
    
    # Drift education block - EXPANDED
    elements.append(Spacer(1, 6 * mm))
    elements.extend(_build_education_block(
        "Dlaczego to ma znaczenie? (Cardiac Drift)",
        "Dryf tętna to sygnał ostrzegawczy Twojego układu chłodzenia, którego nie wolno ignorować. "
        "Jeśli przy stałej mocy tętno systematycznie rośnie, serce musi pracować ciężej, "
        "by przetłoczyć krew nie tylko do mięśni, ale i do skóry w celu ochłodzenia organizmu.",
        styles
    ))
    
    # Additional theory paragraphs
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(
        "<b>Fizjologia dryfu sercowego:</b> Wzrost temperatury rdzenia o każdy 1°C powoduje "
        "przyrost HR o 8-10 uderzeń/min oraz spadek VO₂max o 1.5-2%. Przy temperaturze "
        "rdzenia >39°C następuje ochronne ograniczenie rekrutacji jednostek motorycznych "
        "przez ośrodkowy układ nerwowy (central governor). Efektywność serca (EF) spada, "
        "ponieważ każdy wat mocy wymaga większego nakładu pracy serca.",
        styles["body"]
    ))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        "<b>Konsekwencje startowe:</b> W wyścigu przy wysokiej temperaturze otoczenia dryf "
        "HR >10% w ciągu pierwszych 30-45 min oznacza, że pacing musi być skorygowany w dół. "
        "Kontynuacja planowanej mocy przy rosnącym HR prowadzi do przedwczesnego wyczerpania "
        "glikogenu, kumulacji ciepła i potencjalnego DNF. Adaptacja cieplna (heat acclimation) "
        "redukuje dryf o 15-20% po 10-14 dniach ekspozycji.",
        styles["body"]
    ))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        "<b>Praktyczne zalecenia:</b> Monitoruj EF w czasie rzeczywistym. Jeśli EF spada >8% "
        "w pierwszych 45 min, zmniejsz moc o 3-5%. Stosuj pre-cooling przed startem "
        "(kamizelka lodowa, zimny napój 500ml). Nawadniaj 500-750ml/h + elektrolity (500-1000mg Na+/h).",
        styles["body"]
    ))
    
    return elements


# ============================================================================
# NEW PAGE: KLUCZOWE WSKAŹNIKI WYDAJNOŚCI (KPI) - PREMIUM DASHBOARD
# ============================================================================

def build_page_kpi_dashboard(
    kpi: Dict[str, Any],
    styles: Dict
) -> List:
    """Build dedicated KPI Dashboard page - premium quality."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import TableStyle
    
    elements = []
    
    elements.append(Paragraph("5. PODSUMOWANIE", styles["title"]))
    elements.append(Paragraph("<font size='14'>5.1 WSKAŹNIKI KPI</font>", styles["center"]))
    elements.append(Paragraph("<font size='10' color='#7F8C8D'>Dashboard stabilności układu krążenia i kosztu energetycznego</font>", styles["body"]))
    elements.append(Spacer(1, 8 * mm))
    
    # === HELPER FUNCTIONS ===
    def get_ef_status(val):
        """Efficiency Factor status."""
        if val is None: return ("n/a", "BRAK", "#808080")
        try:
            v = float(val)
            if v < 1.8: return (f"{v:.2f}", "SŁABO", "#E74C3C")
            elif v < 2.2: return (f"{v:.2f}", "OK", "#27AE60")
            else: return (f"{v:.2f}", "BARDZO DOBRZE", "#2ECC71")
        except Exception: return ("n/a", "BRAK", "#808080")
    
    def get_pahr_status(val):
        """Pa:Hr Decoupling status."""
        if val is None: return ("n/a", "BRAK", "#808080")
        try:
            v = float(val)
            if v < 5: return (f"{v:.1f}%", "STABILNY", "#27AE60")
            elif v < 8: return (f"{v:.1f}%", "OSTRZEŻENIE", "#F39C12")
            else: return (f"{v:.1f}%", "RYZYKO", "#E74C3C")
        except Exception: return ("n/a", "BRAK", "#808080")
    
    def get_smo2_drift_status(val):
        """SmO2 Drift status."""
        if val is None: return ("n/a", "BRAK", "#808080")
        try:
            v = float(val)
            if v < 5: return (f"{v:.1f}%", "STABILNY", "#27AE60")
            else: return (f"{v:.1f}%", "ZMĘCZENIE OBWODOWE", "#F39C12")
        except Exception: return ("n/a", "BRAK", "#808080")
    
    # === GET VALUES ===
    ef_val, ef_status, ef_color = get_ef_status(kpi.get("ef"))
    pahr_val, pahr_status, pahr_color = get_pahr_status(kpi.get("pa_hr"))
    smo2_val, smo2_status, smo2_color = get_smo2_drift_status(kpi.get("smo2_drift"))
    
    # VO2max from canonical source
    vo2max_raw = kpi.get("vo2max_est")
    vo2max_source = kpi.get("vo2max_source", "")
    if vo2max_raw and vo2max_raw != "brak danych":
        try:
            vo2max_val = f"{float(vo2max_raw):.1f} ml/kg"
            vo2max_status = "CANONICAL"
            vo2max_color = "#3498DB"
        except Exception:
            vo2max_val = "n/a"
            vo2max_status = "BRAK"
            vo2max_color = "#808080"
    else:
        vo2max_val = "n/a"
        vo2max_status = "BRAK"
        vo2max_color = "#808080"
    
    # === BUILD KPI TABLE - Polish chars with proper encoding ===
    header = ["Metryka", "Wartość", "Zakres Ref.", "Status"]
    
    rows = [
        header,
        ["Efficiency Factor (EF)", ef_val, "<1.8 slabo | 1.8-2.2 ok | >2.2 b.dobrze", ef_status],
        ["Pa:Hr Decoupling", pahr_val, "<5% stab. | 5-8% ostrz. | >8% ryzyko", pahr_status],
        ["SmO2 Drift", smo2_val, "<5% stabilny | >5% zmeczenie", smo2_status],
        ["VO2max", vo2max_val, f"Zrodlo: {vo2max_source}", vo2max_status],
    ]
    
    table = Table(rows, colWidths=[40 * mm, 28 * mm, 65 * mm, 32 * mm])
    
    # Dynamic styling based on status colors
    table_style = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), HexColor("#1a1a2e")),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # ALL CELLS must use DejaVuSans for Polish characters
        ('FONTNAME', (0, 1), (-1, -1), 'DejaVuSans'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#555555")),
        ('ROWHEIGHT', (0, 0), (-1, -1), 14 * mm),
        # Data row backgrounds - lighter for readability
        ('BACKGROUND', (0, 1), (2, 1), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 1), (2, 1), HexColor("#333333")),
        ('BACKGROUND', (0, 2), (2, 2), HexColor("#e8e8e8")),
        ('TEXTCOLOR', (0, 2), (2, 2), HexColor("#333333")),
        ('BACKGROUND', (0, 3), (2, 3), HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 3), (2, 3), HexColor("#333333")),
        ('BACKGROUND', (0, 4), (2, 4), HexColor("#e8e8e8")),
        ('TEXTCOLOR', (0, 4), (2, 4), HexColor("#333333")),
        # Status column colors per row - bright colors with white text
        ('BACKGROUND', (3, 1), (3, 1), HexColor(ef_color)),
        ('TEXTCOLOR', (3, 1), (3, 1), HexColor("#FFFFFF")),
        ('BACKGROUND', (3, 2), (3, 2), HexColor(pahr_color)),
        ('TEXTCOLOR', (3, 2), (3, 2), HexColor("#FFFFFF")),
        ('BACKGROUND', (3, 3), (3, 3), HexColor(smo2_color)),
        ('TEXTCOLOR', (3, 3), (3, 3), HexColor("#FFFFFF")),
        ('BACKGROUND', (3, 4), (3, 4), HexColor(vo2max_color)),
        ('TEXTCOLOR', (3, 4), (3, 4), HexColor("#FFFFFF")),
        ('FONTNAME', (3, 1), (3, -1), 'DejaVuSans-Bold'),
    ]
    
    table.setStyle(TableStyle(table_style))
    elements.append(table)
    elements.append(Spacer(1, 8 * mm))
    
    # === LEGEND ===
    legend_style = ParagraphStyle('legend', parent=styles["body"], fontSize=8, textColor=HexColor("#95A5A6"))
    elements.append(Paragraph(
        "<b>Legenda statusów:</b> "
        "<font color='#27AE60'>■ OK/STABILNY</font> | "
        "<font color='#F39C12'>■ OSTRZEŻENIE</font> | "
        "<font color='#E74C3C'>■ RYZYKO/SŁABO</font> | "
        "<font color='#808080'>■ BRAK DANYCH</font>",
        legend_style
    ))
    elements.append(Spacer(1, 6 * mm))
    
    # === INTERPRETIVE FOOTER ===
    footer_text = (
        "<b>Interpretacja:</b> KPI odzwierciedlają stabilność układu krążenia i koszt energetyczny "
        "utrzymania mocy. Efficiency Factor (EF) pokazuje ile watów generujesz na każde uderzenie "
        "serca - wyższy EF oznacza lepszą sprawność aerobową. Pa:Hr Decoupling >5% świadczy o "
        "niepełnej adaptacji termicznej lub chronicznym zmęczeniu. SmO2 Drift wskazuje na lokalne "
        "wyczerpanie mięśni niezależne od układu sercowo-naczyniowego."
    )
    elements.append(Paragraph(footer_text, styles["body"]))
    elements.append(Spacer(1, 10 * mm))
    
    # ==========================================================================
    # KPI – EXPECTED TREND (6–8 weeks)
    # ==========================================================================
    
    elements.append(Paragraph("<b>OCZEKIWANY TREND (6–8 tygodni)</b>", styles["subheading"]))
    elements.append(Spacer(1, 3 * mm))
    
    # Calculate target values heuristically
    def calc_target(current_str, improvement_pct, is_reduction=False):
        try:
            # Extract numeric value
            val = float(current_str.replace('%', '').replace(' ml/kg', '').replace('n/a', '0'))
            if val == 0:
                return "—"
            if is_reduction:
                target = val * (1 - improvement_pct / 100)
            else:
                target = val * (1 + improvement_pct / 100)
            return f"{target:.2f}" if target < 10 else f"{target:.1f}"
        except Exception:
            return "—"
    
    # Get current values (parsed earlier)
    ef_current = ef_val
    pahr_current = pahr_val
    smo2_current = smo2_val
    vo2_current = vo2max_val
    
    # Calculate targets
    ef_target = calc_target(ef_val, 6.5)  # +5-8% → 6.5% avg
    pahr_target = calc_target(pahr_val.replace('%', ''), 7.5, is_reduction=True)  # improve by 5-10 pp → 7.5% reduction
    smo2_target = calc_target(smo2_val.replace('%', ''), 35, is_reduction=True)  # reduce by 30-40% → 35%
    vo2_target = calc_target(vo2max_val.replace(' ml/kg', ''), 4)  # +3-5% → 4% avg
    
    # Build trend table
    trend_header = ["Metryka", "Obecny", "Cel (6–8 tyg.)", "Droga do celu"]
    trend_rows = [
        trend_header,
        ["Wsp. Efektywności (EF)", ef_current, ef_target, "+5–8% przez objętość Z2"],
        ["Pa:Hr (Rozjechanie)", pahr_current, f"{pahr_target}%", "Adaptacja cieplna + pacing"],
        ["% Dryf SmO2", smo2_current, f"{smo2_target}%", "−30–40% przez siłę + kadencję"],
        ["VO2max", vo2_current, f"{vo2_target} ml/kg", "+3–5% przez interwały VO2max"],
    ]
    
    trend_table = Table(trend_rows, colWidths=[45 * mm, 30 * mm, 40 * mm, 55 * mm])
    trend_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor("#2C3E50")),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ('FONTNAME', (0, 0), (-1, 0), FONT_FAMILY_BOLD),
        ('FONTNAME', (0, 1), (-1, -1), FONT_FAMILY),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#555555")),
        ('ROWHEIGHT', (0, 0), (-1, -1), 10 * mm),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor("#f8f9fa")),
        ('BACKGROUND', (2, 1), (2, -1), HexColor("#E8F6EF")),  # Target column highlight
    ]))
    elements.append(trend_table)
    elements.append(Spacer(1, 3 * mm))
    
    # Disclaimer
    disclaimer_style = ParagraphStyle('disclaimer', parent=styles["body"], fontSize=8, textColor=HexColor("#7F8C8D"), fontName=FONT_FAMILY_ITALIC)
    elements.append(Paragraph("Cele zakładają ustrukturyzowany trening i adaptację cieplną.", disclaimer_style))
    
    return elements


# Legacy compatibility wrapper
def build_page_drift_kpi(
    kpi: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict
) -> List:
    """Legacy wrapper - combines drift page content only, KPI is on separate page now."""
    return build_page_drift(kpi, figure_paths, styles)


# ============================================================================
# UPDATED PAGE 7: METABOLIC MODEL
# ============================================================================

def build_page_limiters(
    metadata: Dict[str, Any],
    cp_model: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict
) -> List:
    """Build Metabolic Profile page (Radar + VLaMax Balance)."""
    elements = []
    
    elements.append(Paragraph("Model Metaboliczny (INSCYD-style)", styles["title"]))
    elements.append(Spacer(1, 6 * mm))
    
    # 1. VLaMax Balance Schema
    if figure_paths and "vlamax_balance" in figure_paths:
        elements.extend(_build_chart(figure_paths["vlamax_balance"], "Balans VO2max vs VLaMax", styles))
        elements.append(Spacer(1, 4 * mm))
    else:
        elements.append(Paragraph("Brak danych do analizy VLaMax (wymagane min. 20 min MMP)", styles["small"]))

    # 2. Radar Chart
    if figure_paths and "limiters_radar" in figure_paths:
        elements.extend(_build_chart(figure_paths["limiters_radar"], "Radar Obciążenia (5 min Peak)", styles))
        elements.append(Spacer(1, 4 * mm))
        
    elements.append(Paragraph(
        "<b>Profil Zawodnika:</b> Twój profil wynika ze stosunku między zdolnością tlenową (VO₂max) "
        "a beztlenową (VLaMax). Wykryty limiter wskazuje, nad czym pracować w następnym bloku treningowym.",
        styles["body"]
    ))
    
    return elements


# ============================================================================
# PAGE 8: DODATKOWE ANALIZY
# ============================================================================

def build_page_extra(
    figure_paths: Dict[str, str],
    styles: Dict
) -> List:
    """Build Page 8: Extra Analytics (Ventilation & Drift)."""
    elements = []
    
    elements.append(Paragraph("Zaawansowana Analityka", styles["title"]))
    elements.append(Spacer(1, 6 * mm))
    
    # Vent Full
    if figure_paths and "vent_full" in figure_paths:
        elements.extend(_build_chart(figure_paths["vent_full"], "Dynamika Wentylacji (VE) vs Moc", styles))
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