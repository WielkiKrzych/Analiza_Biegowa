"""
PDF Builder Module.

Orchestrates the construction of complete Ramp Test PDF reports.
Assembles all 6 pages as per methodology/ramp_test/10_pdf_layout.md.

Pages:
1. Okładka / Podsumowanie
2. Szczegóły Progów VT1/VT2
3. Power-Duration Curve / CP
4. Interpretacja Wyników
5. Strefy Treningowe
6. Ograniczenia Interpretacji

No physiological calculations - only document assembly.
"""
from io import BytesIO
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Any, Optional, List

from reportlab.platypus import SimpleDocTemplate, PageBreak
from reportlab.lib.units import mm

from .styles import PDFConfig, create_styles, PAGE_SIZE, COLORS, FONT_FAMILY
from .layout import (
    build_page_cover,
    build_page_thresholds,
    build_page_pdc,
    build_page_interpretation,
    build_page_zones,
    build_page_limitations,
    build_page_smo2,
    build_page_theory,
    build_page_thermal,
    build_page_executive_summary,
    build_page_executive_verdict,
    build_page_cardiovascular,
    build_page_ventilation,
    build_page_metabolic_engine,
    build_page_limiter_radar,
    build_table_of_contents,
    build_title_page,
    build_contact_footer,
    build_page_test_profile,
)
from ...calculations.executive_summary import generate_executive_summary


# Setup logger
logger = logging.getLogger("Tri_Dashboard.PDFBuilder")


def map_ramp_json_to_pdf_data(report_json: Dict[str, Any], manual_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Map canonical JSON report to internal PDF data structure.
    
    This is the ONLY function that reads the raw JSON structure.
    Ensures all required fields for layouts are present with safe fallbacks.
    
    MANUAL OVERRIDE PRIORITY:
    Manual values from session_state ALWAYS take priority over auto-detected values.
    Keys checked in manual_overrides (from st.session_state):
    - manual_vt1_watts, manual_vt2_watts (VT power)
    - vt1_hr, vt2_hr, vt1_ve, vt2_ve, vt1_br, vt2_br (VT parameters)
    - smo2_lt1_m, smo2_lt2_m (SmO2 thresholds)
    - cp_input (CP from Sidebar)
    
    Args:
        report_json: Raw canonical JSON report
        manual_overrides: Dict of manual values from st.session_state (optional)
        
    Returns:
        Dict mapped for PDF generation
    """
    if manual_overrides is None:
        manual_overrides = {}
    def get_num(section: str, key: str, path: List[str], fallback: str = "brak danych"):
        """Deep get with formatting and logging."""
        curr = report_json.get(section, {})
        for p in path[:-1]:
            curr = curr.get(p, {})
        
        val = curr.get(path[-1]) if curr else None
        
        if val is None or val == "" or val == "-":
            logger.warning(f"PDF Mapping: Missing expected field {section}.{'.'.join(path)}")
            return fallback
            
        if isinstance(val, (int, float)):
            if val == int(val):
                return str(int(val))
            return f"{val:.0f}"
        
        # Handle lists (ranges)
        if isinstance(val, list) and len(val) == 2:
            try:
                return f"{float(val[0]):.0f}–{float(val[1]):.0f}"
            except (ValueError, TypeError):
                pass
                
        return str(val)

    # 1. Metadata extraction
    meta = report_json.get("metadata", {})
    
    # Try to get pmax from various places
    validity = report_json.get("test_validity", {})
    metrics = validity.get("metrics", {})
    pmax_list = metrics.get("power_range_watts")
    pmax_val = "brak danych"
    if isinstance(pmax_list, list) and len(pmax_list) == 2:
        pmax_val = f"{pmax_list[1]:.0f}"
    elif "pmax_watts" in meta:
        pmax_val = str(round(meta["pmax_watts"]))
    
    if pmax_val == "brak danych":
         # logger.warning("PDF Mapping: Pmax not found in metadata or test_validity")
         pass

    mapped_meta = {
        "test_date": meta.get("test_date", "brak danych"),
        "session_id": meta.get("session_id", "nieznany"),
        "method_version": meta.get("method_version", "1.0.0"),
        "protocol": meta.get("protocol", "Ramp Test"),
        "notes": meta.get("notes", "-"),
        "pmax_watts": pmax_val,
        "athlete_weight_kg": meta.get("athlete_weight_kg", meta.get("rider_weight", 0)),
        # NEW: Metryka Dokumentu fields (default empty)
        "subject_name": "",
        "subject_anthropometry": "",
        # NEW: Test Protocol fields for section 1.2
        "test_start_power": "---",
        "test_end_power": pmax_val,  # default to pmax
        "test_duration": "---",
    }
    
    # === METADATA OVERRIDES from Ramp Archive editor ===
    if manual_overrides.get("test_date_override"):
        mapped_meta["test_date"] = manual_overrides["test_date_override"]
        logger.info(f"PDF: test_date overridden to {mapped_meta['test_date']} (manual)")
    
    if manual_overrides.get("subject_name"):
        mapped_meta["subject_name"] = manual_overrides["subject_name"]
        logger.info(f"PDF: subject_name set to '{mapped_meta['subject_name']}' (manual)")
        
    if manual_overrides.get("subject_anthropometry"):
        mapped_meta["subject_anthropometry"] = manual_overrides["subject_anthropometry"]
        logger.info(f"PDF: subject_anthropometry set to '{mapped_meta['subject_anthropometry']}' (manual)")
    
    # === TEST PROTOCOL OVERRIDES from Vent - Progi Manuals ===
    if manual_overrides.get("test_start_power") is not None and manual_overrides["test_start_power"] > 0:
        mapped_meta["test_start_power"] = str(manual_overrides["test_start_power"])
        logger.info(f"PDF: test_start_power set to {mapped_meta['test_start_power']}W (manual)")
    
    if manual_overrides.get("test_end_power") is not None and manual_overrides["test_end_power"] > 0:
        mapped_meta["test_end_power"] = str(manual_overrides["test_end_power"])
        logger.info(f"PDF: test_end_power set to {mapped_meta['test_end_power']}W (manual)")
        
    if manual_overrides.get("test_duration") and manual_overrides["test_duration"] != "45:00":  # Check not default
        mapped_meta["test_duration"] = manual_overrides["test_duration"]
        logger.info(f"PDF: test_duration set to {mapped_meta['test_duration']} (manual)")

    # 2. Thresholds (midpoints and ranges)
    thresholds = report_json.get("thresholds", {})
    
    # Debug helper for VE
    vt1_data = thresholds.get("vt1", {})
    vt2_data = thresholds.get("vt2", {})
    
    mapped_thresholds = {
        "vt1_watts": get_num("thresholds", "vt1", ["vt1", "midpoint_watts"]),
        "vt1_hr": get_num("thresholds", "vt1", ["vt1", "midpoint_hr"]),
        "vt1_ve": get_num("thresholds", "vt1", ["vt1", "midpoint_ve"]),
        "vt1_range_watts": get_num("thresholds", "vt1", ["vt1", "range_watts"]),
        
        "vt2_watts": get_num("thresholds", "vt2", ["vt2", "midpoint_watts"]),
        "vt2_hr": get_num("thresholds", "vt2", ["vt2", "midpoint_hr"]),
        "vt2_ve": get_num("thresholds", "vt2", ["vt2", "midpoint_ve"]),
        "vt2_range_watts": get_num("thresholds", "vt2", ["vt2", "range_watts"]),
        
        "vt1_raw_midpoint": report_json.get("thresholds", {}).get("vt1", {}).get("midpoint_watts"), # for calcs
        "vt2_raw_midpoint": report_json.get("thresholds", {}).get("vt2", {}).get("midpoint_watts"),
    }
    
    # =========================================================================
    # MANUAL OVERRIDE APPLICATION (from session_state)
    # Manual values ALWAYS take priority over auto-detected
    # =========================================================================
    
    # VT1 overrides
    if manual_overrides.get("manual_vt1_watts") and manual_overrides["manual_vt1_watts"] > 0:
        mapped_thresholds["vt1_watts"] = str(int(manual_overrides["manual_vt1_watts"]))
        mapped_thresholds["vt1_raw_midpoint"] = float(manual_overrides["manual_vt1_watts"])
        logger.info(f"PDF: VT1 power overridden to {mapped_thresholds['vt1_watts']} W (manual)")
    
    if manual_overrides.get("vt1_hr") and manual_overrides["vt1_hr"] > 0:
        mapped_thresholds["vt1_hr"] = str(int(manual_overrides["vt1_hr"]))
        
    if manual_overrides.get("vt1_ve") and manual_overrides["vt1_ve"] > 0:
        mapped_thresholds["vt1_ve"] = f"{manual_overrides['vt1_ve']:.1f}"
        
    if manual_overrides.get("vt1_br") and manual_overrides["vt1_br"] > 0:
        mapped_thresholds["vt1_br"] = str(int(manual_overrides["vt1_br"]))
    
    # VT2 overrides
    if manual_overrides.get("manual_vt2_watts") and manual_overrides["manual_vt2_watts"] > 0:
        mapped_thresholds["vt2_watts"] = str(int(manual_overrides["manual_vt2_watts"]))
        mapped_thresholds["vt2_raw_midpoint"] = float(manual_overrides["manual_vt2_watts"])
        logger.info(f"PDF: VT2 power overridden to {mapped_thresholds['vt2_watts']} W (manual)")
        
    if manual_overrides.get("vt2_hr") and manual_overrides["vt2_hr"] > 0:
        mapped_thresholds["vt2_hr"] = str(int(manual_overrides["vt2_hr"]))
        
    if manual_overrides.get("vt2_ve") and manual_overrides["vt2_ve"] > 0:
        mapped_thresholds["vt2_ve"] = f"{manual_overrides['vt2_ve']:.1f}"
        
    if manual_overrides.get("vt2_br") and manual_overrides["vt2_br"] > 0:
        mapped_thresholds["vt2_br"] = str(int(manual_overrides["vt2_br"]))
    
    # RANGE RECALCULATION: When manual midpoint is set, recalculate range as ±5%
    # This fixes the issue where table shows old auto-detected range with new manual midpoint
    if manual_overrides.get("manual_vt1_watts") and manual_overrides["manual_vt1_watts"] > 0:
        vt1_mid = float(manual_overrides["manual_vt1_watts"])
        vt1_low = int(vt1_mid * 0.95)
        vt1_high = int(vt1_mid * 1.05)
        mapped_thresholds["vt1_range_watts"] = f"{vt1_low}–{vt1_high}"
        logger.info(f"PDF: VT1 range recalculated to {mapped_thresholds['vt1_range_watts']} (based on manual midpoint)")
    
    if manual_overrides.get("manual_vt2_watts") and manual_overrides["manual_vt2_watts"] > 0:
        vt2_mid = float(manual_overrides["manual_vt2_watts"])
        vt2_low = int(vt2_mid * 0.95)
        vt2_high = int(vt2_mid * 1.05)
        mapped_thresholds["vt2_range_watts"] = f"{vt2_low}–{vt2_high}"
        logger.info(f"PDF: VT2 range recalculated to {mapped_thresholds['vt2_range_watts']} (based on manual midpoint)")

    # 3. SmO2 Context
    smo2 = report_json.get("smo2_context", {})
    mapped_smo2 = {
        "drop_point_watts": "brak danych",
        "interpretation": smo2.get("interpretation", "nie przeanalizowano"),
        "advanced_metrics": report_json.get("smo2_advanced", {})  # Advanced SmO2 metrics
    }
    if smo2 and "drop_point" in smo2 and smo2["drop_point"]:
        mapped_smo2["drop_point_watts"] = get_num("smo2_context", "drop_point", ["drop_point", "midpoint_watts"])

    # 4. CP Model mapping (if available)
    cp = report_json.get("cp_model", {})
    mapped_cp = {
        "cp_watts": get_num("cp_model", "cp_watts", ["cp_watts"]),
        "w_prime_kj": "brak danych"
    }
    w_prime = cp.get("w_prime_joules")
    if w_prime is not None and isinstance(w_prime, (int, float)):
        mapped_cp["w_prime_kj"] = f"{w_prime / 1000:.0f}"
    
    # CP override from sidebar
    if manual_overrides.get("cp_input") and manual_overrides["cp_input"] > 0:
        mapped_cp["cp_watts"] = str(int(manual_overrides["cp_input"]))
        logger.info(f"PDF: CP overridden to {mapped_cp['cp_watts']} W (sidebar)")

    # 5. Interpretation & Confidence
    interp = report_json.get("interpretation", {})
    mapped_confidence = {
        "overall_confidence": interp.get("overall_confidence", 0.0),
        "confidence_level": interp.get("confidence_level", "low"),
        "warnings": interp.get("warnings", []),
        "notes": interp.get("notes", [])
    }

    # 6. SmO2 Manual
    smo2_manual = report_json.get("smo2_manual", {})
    mapped_smo2_manual = {
        "lt1_watts": get_num("smo2_manual", "lt1_watts", ["lt1_watts"]),
        "lt2_watts": get_num("smo2_manual", "lt2_watts", ["lt2_watts"]),
        "lt1_hr": get_num("smo2_manual", "lt1_hr", ["lt1_hr"]),
        "lt2_hr": get_num("smo2_manual", "lt2_hr", ["lt2_hr"])
    }
    
    # SmO2 LT1/LT2 override from session_state
    if manual_overrides.get("smo2_lt1_m") and manual_overrides["smo2_lt1_m"] > 0:
        mapped_smo2_manual["lt1_watts"] = str(int(manual_overrides["smo2_lt1_m"]))
        logger.info(f"PDF: SmO2 LT1 overridden to {mapped_smo2_manual['lt1_watts']} W (manual)")
        
    if manual_overrides.get("smo2_lt2_m") and manual_overrides["smo2_lt2_m"] > 0:
        mapped_smo2_manual["lt2_watts"] = str(int(manual_overrides["smo2_lt2_m"]))
        logger.info(f"PDF: SmO2 LT2 overridden to {mapped_smo2_manual['lt2_watts']} W (manual)")

    # 7. KPI mapping - use CANONICAL VO2max and cardio_advanced for EF/Pa:Hr
    m_data = report_json.get("metrics", {})
    cardio_adv = report_json.get("cardio_advanced", {})
    smo2_adv = report_json.get("smo2_advanced", {})
    
    # Get canonical VO2max (Single Source of Truth)
    canonical = report_json.get("canonical_physiology", {}).get("summary", {})
    vo2max_canonical = canonical.get("vo2max")
    vo2max_source = canonical.get("vo2max_source", "unknown")
    
    # Fallback to metrics if canonical not available
    if not vo2max_canonical:
        vo2max_canonical = m_data.get("vo2max", m_data.get("estimated_vo2max"))
        vo2max_source = "metrics_fallback"
    
    # Extract EF from cardio_advanced (primary source)
    ef_value = cardio_adv.get("efficiency_factor")
    if not ef_value:
        ef_value = m_data.get("ef", m_data.get("efficiency_factor"))
    
    # Extract Pa:Hr (HR drift) from cardio_advanced
    pa_hr_value = cardio_adv.get("hr_drift_pct")
    if not pa_hr_value:
        pa_hr_value = m_data.get("pa_hr", m_data.get("decoupling_pct"))
    
    # Extract SmO2 drift from smo2_advanced
    smo2_drift_value = smo2_adv.get("drift_pct")
    if not smo2_drift_value:
        smo2_drift_value = m_data.get("smo2_drift")
    
    mapped_kpi = {
        "ef": ef_value if ef_value else "brak danych",
        "pa_hr": pa_hr_value if pa_hr_value else "brak danych",
        "smo2_drift": smo2_drift_value if smo2_drift_value else "brak danych",
        "vo2max_est": vo2max_canonical if vo2max_canonical else "brak danych",
        "vo2max_source": vo2max_source
    }

    # =========================================================================
    # CRITICAL: Enforce CANONICAL VO2max in metabolic_strategy
    # metabolic_strategy MUST NOT override canonical VO2max
    # =========================================================================
    metabolic_strategy = report_json.get("metabolic_strategy", {})
    
    if metabolic_strategy and vo2max_canonical:
        # Force canonical VO2max into metabolic profile
        if "profile" in metabolic_strategy:
            metabolic_strategy["profile"]["vo2max"] = vo2max_canonical
            metabolic_strategy["profile"]["vo2max_source"] = vo2max_source
            
            # Recalculate ratio with canonical VO2max
            vlamax = metabolic_strategy["profile"].get("vlamax", 0)
            if vlamax and vlamax > 0:
                metabolic_strategy["profile"]["vo2max_vlamax_ratio"] = round(vo2max_canonical / vlamax, 1)
            else:
                metabolic_strategy["profile"]["vo2max_vlamax_ratio"] = None

    # === MANUAL OVERRIDE: CCI Breakpoint ===
    cardio_advanced_data = report_json.get("cardio_advanced", {}).copy()
    if manual_overrides.get("cci_breakpoint_manual") and manual_overrides["cci_breakpoint_manual"] > 0:
        manual_cci_bp = float(manual_overrides["cci_breakpoint_manual"])
        cardio_advanced_data["cci_breakpoint_watts"] = manual_cci_bp
        logger.info(f"PDF: CCI breakpoint overridden to {cardio_advanced_data['cci_breakpoint_watts']} W (manual)")
        
        # Also fix interpretation text to use the manual breakpoint value
        interp = cardio_advanced_data.get("interpretation", "")
        if interp and "przy" in interp.lower():
            import re
            # Replace "CCI przy XXW" or "CCI przy XX W" with the manual value
            interp = re.sub(r'CCI przy \d+W', f'CCI przy {int(manual_cci_bp)}W', interp)
            interp = re.sub(r'CCI przy \d+ W', f'CCI przy {int(manual_cci_bp)} W', interp)
            cardio_advanced_data["interpretation"] = interp
            logger.info(f"PDF: CCI interpretation updated to use manual breakpoint {manual_cci_bp}W")
    
    # === MANUAL OVERRIDE: VE Breakpoint ===
    vent_advanced_data = report_json.get("vent_advanced", {}).copy()
    if manual_overrides.get("ve_breakpoint_manual") and manual_overrides["ve_breakpoint_manual"] > 0:
        vent_advanced_data["ve_breakpoint_watts"] = float(manual_overrides["ve_breakpoint_manual"])
        logger.info(f"PDF: VE breakpoint overridden to {vent_advanced_data['ve_breakpoint_watts']} W (manual)")
    
    # === MANUAL OVERRIDE: SmO2 Reoxy half-time ===
    smo2_advanced_data = report_json.get("smo2_advanced", {}).copy()
    if manual_overrides.get("reoxy_halftime_manual") and manual_overrides["reoxy_halftime_manual"] > 0:
        smo2_advanced_data["halftime_reoxy_sec"] = float(manual_overrides["reoxy_halftime_manual"])
        logger.info(f"PDF: Reoxy half-time overridden to {smo2_advanced_data['halftime_reoxy_sec']} s (manual)")
    
    # Update mapped_smo2 with overridden advanced_metrics
    mapped_smo2["advanced_metrics"] = smo2_advanced_data

    # === CPET 4-point analysis data (VT1_onset, RCP_onset for Upper Aerobic range) ===
    cpet = report_json.get("cpet_analysis", {})
    vt1_onset_watts = cpet.get("vt1_onset_watts")
    rcp_onset_watts = cpet.get("rcp_onset_watts")
    
    # Manual override for Upper Aerobic range
    if manual_overrides.get("vt1_onset_watts"):
        vt1_onset_watts = manual_overrides["vt1_onset_watts"]
    if manual_overrides.get("rcp_onset_watts"):
        rcp_onset_watts = manual_overrides["rcp_onset_watts"]
    
    return {
        "metadata": mapped_meta,
        "thresholds": mapped_thresholds,
        "smo2": mapped_smo2,
        "cp_model": mapped_cp,
        "smo2_manual": mapped_smo2_manual,
        "confidence": mapped_confidence,
        "kpi": mapped_kpi,
        "cardio_advanced": cardio_advanced_data,
        "vent_advanced": vent_advanced_data,
        "smo2_advanced": smo2_advanced_data,
        "metabolic_strategy": metabolic_strategy,
        "canonical_physiology": report_json.get("canonical_physiology", {}),
        "biomech_occlusion": report_json.get("biomech_occlusion", {}),
        "thermo_analysis": report_json.get("thermo_analysis", {}),
        "limiter_analysis": report_json.get("limiter_analysis", {}),
        # CPET 4-point data for Upper Aerobic range
        "vt1_onset_watts": vt1_onset_watts,
        "rcp_onset_watts": rcp_onset_watts,
        "executive_summary": generate_executive_summary(
            thresholds=mapped_thresholds,
            smo2_manual=mapped_smo2_manual,
            cp_model=mapped_cp,
            kpi=mapped_kpi,
            confidence=mapped_confidence,
            # Pass advanced data for consistent limiter detection (aligns Summary with Verdict)
            smo2_advanced=smo2_advanced_data,
            cardio_advanced=cardio_advanced_data,
            canonical_physiology=report_json.get("canonical_physiology", {}),
            # Pass biomech_occlusion for cadence constraints in training cards
            biomech_occlusion=report_json.get("biomech_occlusion", {})
        )
    }


def build_ramp_pdf(
    report_data: Dict[str, Any],
    figure_paths: Optional[Dict[str, str]] = None,
    output_path: Optional[str] = None,
    config: Optional[PDFConfig] = None,
    manual_overrides: Optional[Dict[str, Any]] = None,
    compact_mode: bool = False
) -> bytes:
    """Build complete Ramp Test PDF report (6 pages).
    
    Assembles all sections into a multi-page PDF document
    following the specification in 10_pdf_layout.md.
    
    Args:
        report_data: Canonical JSON report dictionary
        figure_paths: Dict mapping figure name to file path
        output_path: Optional file path to save PDF
        config: PDF configuration
        manual_overrides: Dict of manual threshold values from session_state
            (VT1/VT2, SmO2 LT1/LT2, CP from sidebar) - these override auto-detected
        compact_mode: If True, skips educational/theory pages for pro users
        
    Returns:
        PDF bytes
    """
    config = config or PDFConfig()
    figure_paths = figure_paths or {}
    
    # Setup document with custom page callback for footer
    buffer = BytesIO()
    
    # Map data with robust fallbacks and apply manual overrides
    pdf_data = map_ramp_json_to_pdf_data(report_data, manual_overrides=manual_overrides)
    
    metadata = pdf_data["metadata"]
    thresholds = pdf_data["thresholds"]
    cp_model = pdf_data["cp_model"]
    confidence = pdf_data["confidence"]
    
    # Store metadata for footer
    session_id = metadata.get("session_id", "")[:8]
    method_version = metadata.get("method_version", "1.0.0")
    
    def add_page_footer(canvas, doc):
        """Add footer, watermark, and page bookmark to each page."""
        import os
        canvas.saveState()
        
        # === PAGE BOOKMARK for TOC navigation ===
        page_num = doc.page
        canvas.bookmarkPage(f"page_{page_num}")
        
        # === WATERMARK (subtle, centered) ===
        watermark_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "watermark.jpg")
        if os.path.exists(watermark_path):
            try:
                # Draw watermark as semi-transparent image in center
                canvas.saveState()
                canvas.setFillAlpha(0.12)  # Semi-transparent watermark
                
                # Center of page
                page_width, page_height = PAGE_SIZE
                wm_width = 60 * mm
                wm_height = 60 * mm
                x = (page_width - wm_width) / 2
                y = (page_height - wm_height) / 2
                
                canvas.drawImage(watermark_path, x, y, width=wm_width, height=wm_height, 
                                mask='auto', preserveAspectRatio=True)
                canvas.restoreState()
            except Exception:
                pass  # Silently skip if watermark fails
        
        # === FOOTER TEXT ===
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        footer_text = f"Strona {page_num}"
        
        canvas.setFont(FONT_FAMILY, 8)
        canvas.setFillColor(COLORS["text_light"])
        canvas.drawCentredString(PAGE_SIZE[0] / 2, 10 * mm, footer_text)
        
        canvas.restoreState()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=config.page_size,
        leftMargin=config.margin,
        rightMargin=config.margin,
        topMargin=config.margin,
        bottomMargin=20 * mm  # Extra space for footer
    )
    
    # Create styles
    styles = create_styles()
    
    # Build story (list of flowables)
    story = []
    
    # ===========================================================================
    # STRONA TYTUŁOWA (TITLE PAGE) - DarkGlass Premium
    # ===========================================================================
    story.extend(build_title_page(metadata=metadata, styles=styles))
    story.append(PageBreak())
    
    # ===========================================================================
    # SPIS TREŚCI (TABLE OF CONTENTS)
    # ===========================================================================
    
    section_titles = [
        # === ROZDZIAŁ 1: PODSUMOWANIE WYKONAWCZE ===
        {"title": "1. PODSUMOWANIE WYKONAWCZE", "page": "3", "level": 0},
        {"title": "1.1 Raport potestowy", "page": "3", "level": 1},
        {"title": "1.2 Przebieg testu", "page": "4", "level": 1},
        
        # === ROZDZIAŁ 2: PROGI METABOLICZNE ===
        {"title": "2. PROGI METABOLICZNE", "page": "5", "level": 0},
        {"title": "2.1 Szczegóły VT1/VT2", "page": "5", "level": 1},
        {"title": "2.2 Co oznaczają wyniki?", "page": "6", "level": 1},
        {"title": "2.3 Model metaboliczny", "page": "7", "level": 1},
        {"title": "2.4 Silnik metaboliczny", "page": "8", "level": 1},
        {"title": "2.5 Krzywa mocy (PDC)", "page": "10", "level": 1},
        
        # === ROZDZIAŁ 3: DIAGNOSTYKA UKŁADÓW ===
        {"title": "3. DIAGNOSTYKA UKŁADÓW", "page": "12", "level": 0},
        {"title": "3.1 Kontrola oddychania", "page": "12", "level": 1},
        {"title": "3.2 Układ sercowo-naczyniowy", "page": "13", "level": 1},
        {"title": "3.3 Oksygenacja mięśniowa (SmO₂)", "page": "14", "level": 1},
        {"title": "3.4 Biomechanika", "page": "16", "level": 1},
        
        # === ROZDZIAŁ 4: LIMITERY I OBCIĄŻENIE CIEPLNE ===
        {"title": "4. LIMITERY I OBCIĄŻENIE CIEPLNE", "page": "17", "level": 0},
        {"title": "4.1 Radar obciążenia systemów", "page": "17", "level": 1},
        {"title": "4.2 Dryf fizjologiczny", "page": "18", "level": 1},
        {"title": "4.3 Termoregulacja", "page": "19", "level": 1},
        
        # === ROZDZIAŁ 5: PODSUMOWANIE ===
        {"title": "5. PODSUMOWANIE", "page": "21", "level": 0},
        {"title": "5.1 Wskaźniki KPI", "page": "21", "level": 1},
        {"title": "5.2 Podsumowanie fizjologiczne", "page": "22", "level": 1},
        {"title": "5.3 Werdykt fizjologiczny", "page": "23", "level": 1},
        {"title": "5.4 Protokół testu", "page": "24", "level": 1},
        {"title": "5.5 Ograniczenia interpretacji", "page": "25", "level": 1},
    ]
    
    story.extend(build_table_of_contents(styles=styles, section_titles=section_titles))
    story.append(PageBreak())
    
    # ===========================================================================
    # NOWA KOLEJNOŚĆ STRON PDF (wg specyfikacji użytkownika)
    # ===========================================================================
    
    # ===========================================================================
    # ROZDZIAŁ 1: PODSUMOWANIE WYKONAWCZE
    # ===========================================================================
    
    # === 1.1 RAPORT POTESTOWY ===
    story.extend(build_page_cover(
        metadata=metadata,
        thresholds=thresholds,
        cp_model=cp_model,
        confidence=confidence,
        figure_paths=figure_paths,
        styles=styles,
        is_conditional=config.is_conditional,
        vt1_onset_watts=pdf_data.get("vt1_onset_watts"),
        rcp_onset_watts=pdf_data.get("rcp_onset_watts")
    ))
    story.append(PageBreak())
    
    # === 1.2 PRZEBIEG TESTU ===
    story.extend(build_page_test_profile(
        metadata=metadata,
        figure_paths=figure_paths,
        styles=styles
    ))
    story.append(PageBreak())
    
    # ===========================================================================
    # ROZDZIAŁ 2: PROGI METABOLICZNE
    # ===========================================================================
    
    # === 2.1 SZCZEGÓŁY VT1/VT2 ===
    story.extend(build_page_thresholds(
        thresholds=thresholds,
        smo2=pdf_data["smo2"],
        figure_paths=figure_paths,
        styles=styles
    ))
    story.append(PageBreak())
    
    # === 2.2 CO OZNACZAJĄ TE WYNIKI? ===
    story.extend(build_page_interpretation(
        thresholds=thresholds,
        cp_model=cp_model,
        styles=styles
    ))
    story.append(PageBreak())
    
    # === 2.3 MODEL METABOLICZNY (teoria) ===
    if not compact_mode:
        story.extend(build_page_theory(styles=styles))
        story.append(PageBreak())
    
    # === 2.4 SILNIK METABOLICZNY ===
    metabolic_data = pdf_data.get("metabolic_strategy", {})
    if metabolic_data:
        story.extend(build_page_metabolic_engine(
            metabolic_data=metabolic_data,
            styles=styles
        ))
        story.append(PageBreak())
    
    # === 2.5 KRZYWA MOCY (PDC) ===
    story.extend(build_page_pdc(
        cp_model=cp_model,
        metadata=metadata,
        figure_paths=figure_paths,
        styles=styles
    ))
    story.append(PageBreak())
    
    # ===========================================================================
    # ROZDZIAŁ 3: DIAGNOSTYKA UKŁADÓW
    # ===========================================================================
    
    # === 3.1 KONTROLA ODDYCHANIA ===
    vent_data = pdf_data.get("vent_advanced", {})
    if vent_data:
        story.extend(build_page_ventilation(
            vent_data=vent_data,
            styles=styles
        ))
        story.append(PageBreak())
    
    # === 3.2 UKŁAD SERCOWO-NACZYNIOWY ===
    cardio_data = pdf_data.get("cardio_advanced", {})
    if cardio_data:
        story.extend(build_page_cardiovascular(
            cardio_data=cardio_data,
            styles=styles
        ))
        story.append(PageBreak())
    
    # === 3.3 OKSYGENACJA MIĘŚNIOWA (SmO2) ===
    story.extend(build_page_smo2(
        smo2_data=pdf_data["smo2"],
        smo2_manual=pdf_data["smo2_manual"],
        figure_paths=figure_paths,
        styles=styles
    ))
    story.append(PageBreak())
    
    # === 3.4 BIOMECHANIKA ===
    from .layout import build_page_biomech, build_page_drift_kpi
    biomech_data = pdf_data.get("biomech_occlusion", {})
    if any(k in figure_paths for k in ["biomech_summary", "biomech_torque_smo2"]) or biomech_data:
        story.extend(build_page_biomech(
            figure_paths=figure_paths,
            styles=styles,
            biomech_data=biomech_data
        ))
        story.append(PageBreak())
    
    # ===========================================================================
    # ROZDZIAŁ 4: LIMITERY I OBCIĄŻENIE CIEPLNE
    # ===========================================================================
    
    # === 4.1 RADAR OBCIĄŻENIA SYSTEMÓW ===
    limiter_data = pdf_data.get("limiter_analysis", {})
    if limiter_data:
        story.extend(build_page_limiter_radar(
            limiter_data=limiter_data,
            figure_paths=figure_paths,
            styles=styles
        ))
        story.append(PageBreak())
    
    # === 4.2 DRYF FIZJOLOGICZNY ===
    if any(k in figure_paths for k in ["drift_heatmap_hr", "drift_heatmap_smo2"]):
        story.extend(build_page_drift_kpi(
            kpi=pdf_data["kpi"],
            figure_paths=figure_paths,
            styles=styles
        ))
        story.append(PageBreak())
    
    # === 4.3 TERMOREGULACJA ===
    story.extend(build_page_thermal(
        thermo_data=pdf_data.get("thermo_analysis", {}),
        figure_paths=figure_paths,
        styles=styles
    ))
    story.append(PageBreak())
    
    # ===========================================================================
    # ROZDZIAŁ 5: PODSUMOWANIE
    # ===========================================================================
    
    # === 5.1 WSKAŹNIKI KPI ===
    from .layout import build_page_kpi_dashboard
    story.extend(build_page_kpi_dashboard(
        kpi=pdf_data["kpi"],
        styles=styles
    ))
    story.append(PageBreak())
    
    # === 5.2 PODSUMOWANIE FIZJOLOGICZNE ===
    story.extend(build_page_executive_summary(
        executive_data=pdf_data.get("executive_summary", {}),
        metadata=metadata,
        styles=styles
    ))
    story.append(PageBreak())
    
    # === 5.3 WERDYKT FIZJOLOGICZNY ===
    story.extend(build_page_executive_verdict(
        canonical_physio=pdf_data.get("canonical_physiology", {}),
        smo2_advanced=pdf_data.get("smo2_advanced", pdf_data.get("smo2", {}).get("advanced_metrics", {})),
        biomech_occlusion=pdf_data.get("biomech_occlusion", {}),
        thermo_analysis=pdf_data.get("thermo_analysis", {}),
        cardio_advanced=pdf_data.get("cardio_advanced", {}),
        metadata=metadata,
        styles=styles
    ))
    story.append(PageBreak())
    
    # === 5.4 PROTOKÓŁ TESTU ===
    if not compact_mode:
        from .layout import build_page_protocol
        story.extend(build_page_protocol(styles=styles))
        story.append(PageBreak())
    
    # === 5.5 OGRANICZENIA INTERPRETACJI ===
    story.extend(build_page_limitations(
        styles=styles,
        is_conditional=config.is_conditional
    ))
    
    # === DANE KONTAKTOWE NA KOŃCU ===
    story.extend(build_contact_footer(styles=styles))
    
    # Build PDF with footer on each page
    doc.build(story, onFirstPage=add_page_footer, onLaterPages=add_page_footer)
    
    # Get bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    # Save to file if path provided
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)
        print(f"PDF saved to: {output_path}")
    
    return pdf_bytes


# Alias for backward compatibility
generate_ramp_pdf = build_ramp_pdf
