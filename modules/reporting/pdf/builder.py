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

import logging
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, SimpleDocTemplate

from ...calculations.executive_summary import generate_executive_summary
from .layout import (
    build_page_cardiovascular,
    build_page_cover,
    build_page_interpretation,
    build_page_limitations,
    build_page_limiter_radar,
    build_page_metabolic_engine,
    build_page_pdc,
    build_page_smo2,
    build_page_test_profile,
    build_page_theory,
    build_page_thermal,
    build_page_thresholds,
    build_page_ventilation,
)
from .layout_executive_summary import build_page_executive_summary
from .layout_executive_verdict import build_page_executive_verdict
from .layout_tables import build_table_of_contents
from .layout_title import build_contact_footer, build_title_page
from .styles import COLORS, FONT_FAMILY, PAGE_SIZE, PDFConfig, create_styles

# Setup logger
logger = logging.getLogger("Tri_Dashboard.PDFBuilder")


def _deep_get_num(
    report_json: Dict[str, Any],
    section: str,
    key: str,
    path: List[str],
    fallback: str = "brak danych",
) -> str:
    """Deep-get a numeric field from report_json with formatting and logging."""
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


def _extract_metadata(
    report_json: Dict[str, Any],
    manual_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract and override metadata section for PDF."""
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

    mapped: Dict[str, Any] = {
        "test_date": meta.get("test_date", "brak danych"),
        "session_id": meta.get("session_id", "nieznany"),
        "method_version": meta.get("method_version", "1.0.0"),
        "protocol": meta.get("protocol", "Ramp Test"),
        "notes": meta.get("notes", "-"),
        "pmax_watts": pmax_val,
        "athlete_weight_kg": meta.get("athlete_weight_kg", meta.get("rider_weight", 0)),
        "subject_name": "",
        "subject_anthropometry": "",
        "test_start_power": "---",
        "test_end_power": pmax_val,
        "test_duration": "---",
    }

    # === METADATA OVERRIDES from Ramp Archive editor ===
    if manual_overrides.get("test_date_override"):
        mapped["test_date"] = manual_overrides["test_date_override"]
        logger.info(f"PDF: test_date overridden to {mapped['test_date']} (manual)")

    if manual_overrides.get("subject_name"):
        mapped["subject_name"] = manual_overrides["subject_name"]
        logger.info(f"PDF: subject_name set to '{mapped['subject_name']}' (manual)")

    if manual_overrides.get("subject_anthropometry"):
        mapped["subject_anthropometry"] = manual_overrides["subject_anthropometry"]
        logger.info(
            f"PDF: subject_anthropometry set to '{mapped['subject_anthropometry']}' (manual)"
        )

    # === TEST PROTOCOL OVERRIDES from Vent - Progi Manuals ===
    if (
        manual_overrides.get("test_start_power") is not None
        and manual_overrides["test_start_power"] > 0
    ):
        mapped["test_start_power"] = str(manual_overrides["test_start_power"])
        logger.info(f"PDF: test_start_power set to {mapped['test_start_power']}W (manual)")

    if (
        manual_overrides.get("test_end_power") is not None
        and manual_overrides["test_end_power"] > 0
    ):
        mapped["test_end_power"] = str(manual_overrides["test_end_power"])
        logger.info(f"PDF: test_end_power set to {mapped['test_end_power']}W (manual)")

    if manual_overrides.get("test_duration") and manual_overrides["test_duration"] != "45:00":
        mapped["test_duration"] = manual_overrides["test_duration"]
        logger.info(f"PDF: test_duration set to {mapped['test_duration']} (manual)")

    return mapped


def _apply_vt_override(
    mapped: Dict[str, Any],
    overrides: Dict[str, Any],
    prefix: str,
    raw_midpoint_key: str,
    watts_key: str,
) -> None:
    """Apply manual overrides for a single VT (VT1 or VT2). Mutates *mapped* in place."""
    watts_override = overrides.get(f"manual_{prefix}_watts")
    if watts_override and watts_override > 0:
        mapped[watts_key] = str(int(watts_override))
        mapped[raw_midpoint_key] = float(watts_override)
        logger.info(f"PDF: {prefix.upper()} power overridden to {mapped[watts_key]} W (manual)")

    hr = overrides.get(f"{prefix}_hr")
    if hr and hr > 0:
        mapped[f"{prefix}_hr"] = str(int(hr))

    ve = overrides.get(f"{prefix}_ve")
    if ve and ve > 0:
        mapped[f"{prefix}_ve"] = f"{ve:.1f}"

    br = overrides.get(f"{prefix}_br")
    if br and br > 0:
        mapped[f"{prefix}_br"] = str(int(br))

    # Range recalculation: ±5% around manual midpoint
    if watts_override and watts_override > 0:
        mid = float(watts_override)
        mapped[f"{prefix}_range_watts"] = f"{int(mid * 0.95)}–{int(mid * 1.05)}"
        logger.info(
            f"PDF: {prefix.upper()} range recalculated to {mapped[f'{prefix}_range_watts']} (based on manual midpoint)"
        )


def _extract_thresholds(
    report_json: Dict[str, Any],
    manual_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract thresholds section and apply manual overrides."""
    mapped: Dict[str, Any] = {
        "vt1_watts": _deep_get_num(report_json, "thresholds", "vt1", ["vt1", "midpoint_watts"]),
        "vt1_hr": _deep_get_num(report_json, "thresholds", "vt1", ["vt1", "midpoint_hr"]),
        "vt1_ve": _deep_get_num(report_json, "thresholds", "vt1", ["vt1", "midpoint_ve"]),
        "vt1_range_watts": _deep_get_num(report_json, "thresholds", "vt1", ["vt1", "range_watts"]),
        "vt2_watts": _deep_get_num(report_json, "thresholds", "vt2", ["vt2", "midpoint_watts"]),
        "vt2_hr": _deep_get_num(report_json, "thresholds", "vt2", ["vt2", "midpoint_hr"]),
        "vt2_ve": _deep_get_num(report_json, "thresholds", "vt2", ["vt2", "midpoint_ve"]),
        "vt2_range_watts": _deep_get_num(report_json, "thresholds", "vt2", ["vt2", "range_watts"]),
        "vt1_raw_midpoint": report_json.get("thresholds", {}).get("vt1", {}).get("midpoint_watts"),
        "vt2_raw_midpoint": report_json.get("thresholds", {}).get("vt2", {}).get("midpoint_watts"),
    }

    _apply_vt_override(mapped, manual_overrides, "vt1", "vt1_raw_midpoint", "vt1_watts")
    _apply_vt_override(mapped, manual_overrides, "vt2", "vt2_raw_midpoint", "vt2_watts")

    return mapped


def _extract_smo2_context(report_json: Dict[str, Any]) -> Dict[str, Any]:
    """Extract SmO2 context section."""
    smo2 = report_json.get("smo2_context", {})
    mapped: Dict[str, Any] = {
        "drop_point_watts": "brak danych",
        "interpretation": smo2.get("interpretation", "nie przeanalizowano"),
        "advanced_metrics": report_json.get("smo2_advanced", {}),
    }
    if smo2 and "drop_point" in smo2 and smo2["drop_point"]:
        mapped["drop_point_watts"] = _deep_get_num(
            report_json, "smo2_context", "drop_point", ["drop_point", "midpoint_watts"]
        )
    return mapped


def _extract_cp_model(
    report_json: Dict[str, Any],
    manual_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract CP model section and apply sidebar override."""
    cp = report_json.get("cp_model", {})
    mapped: Dict[str, Any] = {
        "cp_watts": _deep_get_num(report_json, "cp_model", "cp_watts", ["cp_watts"]),
        "w_prime_kj": "brak danych",
    }
    w_prime = cp.get("w_prime_joules")
    if w_prime is not None and isinstance(w_prime, (int, float)):
        mapped["w_prime_kj"] = f"{w_prime / 1000:.0f}"

    if manual_overrides.get("cp_input") and manual_overrides["cp_input"] > 0:
        mapped["cp_watts"] = str(int(manual_overrides["cp_input"]))
        logger.info(f"PDF: CP overridden to {mapped['cp_watts']} W (sidebar)")

    return mapped


def _extract_confidence(report_json: Dict[str, Any]) -> Dict[str, Any]:
    """Extract interpretation and confidence section."""
    interp = report_json.get("interpretation", {})
    return {
        "overall_confidence": interp.get("overall_confidence", 0.0),
        "confidence_level": interp.get("confidence_level", "low"),
        "warnings": interp.get("warnings", []),
        "notes": interp.get("notes", []),
    }


def _extract_smo2_manual(
    report_json: Dict[str, Any],
    manual_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract SmO2 manual thresholds and apply overrides."""
    mapped: Dict[str, Any] = {
        "lt1_watts": _deep_get_num(report_json, "smo2_manual", "lt1_watts", ["lt1_watts"]),
        "lt2_watts": _deep_get_num(report_json, "smo2_manual", "lt2_watts", ["lt2_watts"]),
        "lt1_hr": _deep_get_num(report_json, "smo2_manual", "lt1_hr", ["lt1_hr"]),
        "lt2_hr": _deep_get_num(report_json, "smo2_manual", "lt2_hr", ["lt2_hr"]),
    }

    smo2_lt1 = manual_overrides.get("smo2_lt1_m")
    if smo2_lt1 and smo2_lt1 > 0:
        mapped["lt1_watts"] = str(int(smo2_lt1))
        logger.info(f"PDF: SmO2 LT1 overridden to {mapped['lt1_watts']} W (manual)")

    smo2_lt2 = manual_overrides.get("smo2_lt2_m")
    if smo2_lt2 and smo2_lt2 > 0:
        mapped["lt2_watts"] = str(int(smo2_lt2))
        logger.info(f"PDF: SmO2 LT2 overridden to {mapped['lt2_watts']} W (manual)")

    return mapped


def _extract_kpi(report_json: Dict[str, Any]) -> Tuple[Dict[str, Any], Any, str]:
    """Extract KPI section.

    Returns:
        (mapped_kpi, vo2max_canonical, vo2max_source) tuple.
    """
    m_data = report_json.get("metrics", {})
    cardio_adv = report_json.get("cardio_advanced", {})
    smo2_adv = report_json.get("smo2_advanced", {})

    # Get canonical VO2max (Single Source of Truth)
    canonical = report_json.get("canonical_physiology", {}).get("summary", {})
    vo2max_canonical = canonical.get("vo2max")
    vo2max_source = canonical.get("vo2max_source", "unknown")

    if not vo2max_canonical:
        vo2max_canonical = m_data.get("vo2max", m_data.get("estimated_vo2max"))
        vo2max_source = "metrics_fallback"

    ef_value = cardio_adv.get("efficiency_factor") or m_data.get(
        "ef", m_data.get("efficiency_factor")
    )
    pa_hr_value = cardio_adv.get("hr_drift_pct") or m_data.get(
        "pa_hr", m_data.get("decoupling_pct")
    )
    smo2_drift_value = smo2_adv.get("drift_pct") or m_data.get("smo2_drift")

    mapped_kpi: Dict[str, Any] = {
        "ef": ef_value if ef_value else "brak danych",
        "pa_hr": pa_hr_value if pa_hr_value else "brak danych",
        "smo2_drift": smo2_drift_value if smo2_drift_value else "brak danych",
        "vo2max_est": vo2max_canonical if vo2max_canonical else "brak danych",
        "vo2max_source": vo2max_source,
    }

    return mapped_kpi, vo2max_canonical, vo2max_source


def _enforce_canonical_vo2max(
    report_json: Dict[str, Any],
    vo2max_canonical: Any,
    vo2max_source: str,
) -> Dict[str, Any]:
    """Enforce canonical VO2max in metabolic_strategy profile."""
    metabolic_strategy: Dict[str, Any] = report_json.get("metabolic_strategy", {})

    if not metabolic_strategy or not vo2max_canonical:
        return metabolic_strategy

    profile = metabolic_strategy.get("profile")
    if not profile:
        return metabolic_strategy

    profile["vo2max"] = vo2max_canonical
    profile["vo2max_source"] = vo2max_source

    vlamax = profile.get("vlamax", 0)
    profile["vo2max_vlamax_ratio"] = (
        round(vo2max_canonical / vlamax, 1) if vlamax and vlamax > 0 else None
    )

    return metabolic_strategy


def _apply_advanced_overrides(
    report_json: Dict[str, Any],
    manual_overrides: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Apply manual overrides to cardio_advanced, vent_advanced, smo2_advanced.

    Returns:
        (cardio_advanced_data, vent_advanced_data, smo2_advanced_data) tuple.
    """
    # CCI Breakpoint override
    cardio_advanced_data: Dict[str, Any] = report_json.get("cardio_advanced", {}).copy()
    cci_bp = manual_overrides.get("cci_breakpoint_manual")
    if cci_bp and cci_bp > 0:
        manual_cci_bp = float(cci_bp)
        cardio_advanced_data["cci_breakpoint_watts"] = manual_cci_bp
        logger.info(f"PDF: CCI breakpoint overridden to {manual_cci_bp} W (manual)")

        interp = cardio_advanced_data.get("interpretation", "")
        if interp and "przy" in interp.lower():
            interp = re.sub(r"CCI przy \d+W", f"CCI przy {int(manual_cci_bp)}W", interp)
            interp = re.sub(r"CCI przy \d+ W", f"CCI przy {int(manual_cci_bp)} W", interp)
            cardio_advanced_data["interpretation"] = interp
            logger.info(
                f"PDF: CCI interpretation updated to use manual breakpoint {manual_cci_bp}W"
            )

    # VE Breakpoint override
    vent_advanced_data: Dict[str, Any] = report_json.get("vent_advanced", {}).copy()
    ve_bp = manual_overrides.get("ve_breakpoint_manual")
    if ve_bp and ve_bp > 0:
        vent_advanced_data["ve_breakpoint_watts"] = float(ve_bp)
        logger.info(f"PDF: VE breakpoint overridden to {float(ve_bp)} W (manual)")

    # SmO2 Reoxy half-time override
    smo2_advanced_data: Dict[str, Any] = report_json.get("smo2_advanced", {}).copy()
    reoxy_ht = manual_overrides.get("reoxy_halftime_manual")
    if reoxy_ht and reoxy_ht > 0:
        smo2_advanced_data["halftime_reoxy_sec"] = float(reoxy_ht)
        logger.info(f"PDF: Reoxy half-time overridden to {float(reoxy_ht)} s (manual)")

    return cardio_advanced_data, vent_advanced_data, smo2_advanced_data


def _extract_cpet_overrides(
    report_json: Dict[str, Any],
    manual_overrides: Dict[str, Any],
) -> Tuple[Any, Any]:
    """Extract CPET 4-point analysis data with manual overrides.

    Returns:
        (vt1_onset_watts, rcp_onset_watts) tuple.
    """
    cpet = report_json.get("cpet_analysis", {})
    vt1_onset = manual_overrides.get("vt1_onset_watts") or cpet.get("vt1_onset_watts")
    rcp_onset = manual_overrides.get("rcp_onset_watts") or cpet.get("rcp_onset_watts")
    return vt1_onset, rcp_onset


def map_ramp_json_to_pdf_data(
    report_json: Dict[str, Any], manual_overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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

    mapped_meta = _extract_metadata(report_json, manual_overrides)
    mapped_thresholds = _extract_thresholds(report_json, manual_overrides)
    mapped_smo2 = _extract_smo2_context(report_json)
    mapped_cp = _extract_cp_model(report_json, manual_overrides)
    mapped_confidence = _extract_confidence(report_json)
    mapped_smo2_manual = _extract_smo2_manual(report_json, manual_overrides)
    mapped_kpi, vo2max_canonical, vo2max_source = _extract_kpi(report_json)
    metabolic_strategy = _enforce_canonical_vo2max(report_json, vo2max_canonical, vo2max_source)
    cardio_advanced_data, vent_advanced_data, smo2_advanced_data = _apply_advanced_overrides(
        report_json, manual_overrides
    )

    # Update mapped_smo2 with overridden advanced_metrics
    mapped_smo2["advanced_metrics"] = smo2_advanced_data

    # CPET 4-point analysis data
    vt1_onset_watts, rcp_onset_watts = _extract_cpet_overrides(report_json, manual_overrides)

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
        "vt1_onset_watts": vt1_onset_watts,
        "rcp_onset_watts": rcp_onset_watts,
        "executive_summary": generate_executive_summary(
            thresholds=mapped_thresholds,
            smo2_manual=mapped_smo2_manual,
            cp_model=mapped_cp,
            kpi=mapped_kpi,
            confidence=mapped_confidence,
            smo2_advanced=smo2_advanced_data,
            cardio_advanced=cardio_advanced_data,
            canonical_physiology=report_json.get("canonical_physiology", {}),
            biomech_occlusion=report_json.get("biomech_occlusion", {}),
        ),
    }


def _add_page_footer(canvas: Any, doc: Any) -> None:
    """Add footer, watermark, and page bookmark to each page."""
    import os

    canvas.saveState()

    page_num = doc.page
    canvas.bookmarkPage(f"page_{page_num}")

    watermark_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "assets", "watermark.jpg"
    )
    if os.path.exists(watermark_path):
        try:
            canvas.saveState()
            canvas.setFillAlpha(0.12)

            page_width, page_height = PAGE_SIZE
            wm_width = 60 * mm
            wm_height = 60 * mm
            x = (page_width - wm_width) / 2
            y = (page_height - wm_height) / 2

            canvas.drawImage(
                watermark_path,
                x,
                y,
                width=wm_width,
                height=wm_height,
                mask="auto",
                preserveAspectRatio=True,
            )
            canvas.restoreState()
        except (OSError, IOError):
            pass

    datetime.now().strftime("%Y-%m-%d %H:%M")
    footer_text = f"Strona {page_num}"

    canvas.setFont(FONT_FAMILY, 8)
    canvas.setFillColor(COLORS["text_light"])
    canvas.drawCentredString(PAGE_SIZE[0] / 2, 10 * mm, footer_text)

    canvas.restoreState()


def _build_pdf_story(
    pdf_data: Dict[str, Any],
    figure_paths: Dict[str, str],
    styles: Dict,
    config: PDFConfig,
    compact_mode: bool,
) -> List:
    """Build the ordered list of flowables for the complete PDF report."""
    from .layout import build_page_biomech, build_page_drift_kpi, build_page_kpi_dashboard

    metadata = pdf_data["metadata"]
    thresholds = pdf_data["thresholds"]
    cp_model = pdf_data["cp_model"]
    confidence = pdf_data["confidence"]

    story: List = []

    # STRONA TYTUŁOWA
    story.extend(build_title_page(metadata=metadata, styles=styles))
    story.append(PageBreak())

    # SPIS TREŚCI
    section_titles = [
        {"title": "1. PODSUMOWANIE WYKONAWCZE", "page": "3", "level": 0},
        {"title": "1.1 Raport potestowy", "page": "3", "level": 1},
        {"title": "1.2 Przebieg testu", "page": "4", "level": 1},
        {"title": "2. PROGI METABOLICZNE", "page": "5", "level": 0},
        {"title": "2.1 Szczegóły VT1/VT2", "page": "5", "level": 1},
        {"title": "2.2 Co oznaczają wyniki?", "page": "6", "level": 1},
        {"title": "2.3 Model metaboliczny", "page": "7", "level": 1},
        {"title": "2.4 Silnik metaboliczny", "page": "8", "level": 1},
        {"title": "2.5 Krzywa mocy (PDC)", "page": "10", "level": 1},
        {"title": "3. DIAGNOSTYKA UKŁADÓW", "page": "12", "level": 0},
        {"title": "3.1 Kontrola oddychania", "page": "12", "level": 1},
        {"title": "3.2 Układ sercowo-naczyniowy", "page": "13", "level": 1},
        {"title": "3.3 Oksygenacja mięśniowa (SmO₂)", "page": "14", "level": 1},
        {"title": "3.4 Biomechanika", "page": "16", "level": 1},
        {"title": "4. LIMITERY I OBCIĄŻENIE CIEPLNE", "page": "17", "level": 0},
        {"title": "4.1 Radar obciążenia systemów", "page": "17", "level": 1},
        {"title": "4.2 Dryf fizjologiczny", "page": "18", "level": 1},
        {"title": "4.3 Termoregulacja", "page": "19", "level": 1},
        {"title": "5. PODSUMOWANIE", "page": "21", "level": 0},
        {"title": "5.1 Wskaźniki KPI", "page": "21", "level": 1},
        {"title": "5.2 Podsumowanie fizjologiczne", "page": "22", "level": 1},
        {"title": "5.3 Werdykt fizjologiczny", "page": "23", "level": 1},
        {"title": "5.4 Protokół testu", "page": "24", "level": 1},
        {"title": "5.5 Ograniczenia interpretacji", "page": "25", "level": 1},
    ]

    story.extend(build_table_of_contents(styles=styles, section_titles=section_titles))
    story.append(PageBreak())

    # ROZDZIAŁ 1: PODSUMOWANIE WYKONAWCZE
    story.extend(
        build_page_cover(
            metadata=metadata,
            thresholds=thresholds,
            cp_model=cp_model,
            confidence=confidence,
            figure_paths=figure_paths,
            styles=styles,
            is_conditional=config.is_conditional,
            vt1_onset_watts=pdf_data.get("vt1_onset_watts"),
            rcp_onset_watts=pdf_data.get("rcp_onset_watts"),
        )
    )
    story.append(PageBreak())

    story.extend(
        build_page_test_profile(metadata=metadata, figure_paths=figure_paths, styles=styles)
    )
    story.append(PageBreak())

    # ROZDZIAŁ 2: PROGI METABOLICZNE
    story.extend(
        build_page_thresholds(
            thresholds=thresholds, smo2=pdf_data["smo2"], figure_paths=figure_paths, styles=styles
        )
    )
    story.append(PageBreak())

    story.extend(build_page_interpretation(thresholds=thresholds, cp_model=cp_model, styles=styles))
    story.append(PageBreak())

    if not compact_mode:
        story.extend(build_page_theory(styles=styles))
        story.append(PageBreak())

    metabolic_data = pdf_data.get("metabolic_strategy", {})
    if metabolic_data:
        story.extend(build_page_metabolic_engine(metabolic_data=metabolic_data, styles=styles))
        story.append(PageBreak())

    story.extend(
        build_page_pdc(
            cp_model=cp_model, metadata=metadata, figure_paths=figure_paths, styles=styles
        )
    )
    story.append(PageBreak())

    # ROZDZIAŁ 3: DIAGNOSTYKA UKŁADÓW
    vent_data = pdf_data.get("vent_advanced", {})
    if vent_data:
        story.extend(build_page_ventilation(vent_data=vent_data, styles=styles))
        story.append(PageBreak())

    cardio_data = pdf_data.get("cardio_advanced", {})
    if cardio_data:
        story.extend(build_page_cardiovascular(cardio_data=cardio_data, styles=styles))
        story.append(PageBreak())

    story.extend(
        build_page_smo2(
            smo2_data=pdf_data["smo2"],
            smo2_manual=pdf_data["smo2_manual"],
            figure_paths=figure_paths,
            styles=styles,
        )
    )
    story.append(PageBreak())

    biomech_data = pdf_data.get("biomech_occlusion", {})
    if any(k in figure_paths for k in ["biomech_summary", "biomech_torque_smo2"]) or biomech_data:
        story.extend(
            build_page_biomech(figure_paths=figure_paths, styles=styles, biomech_data=biomech_data)
        )
        story.append(PageBreak())

    # ROZDZIAŁ 4: LIMITERY I OBCIĄŻENIE CIEPLNE
    limiter_data = pdf_data.get("limiter_analysis", {})
    if limiter_data:
        story.extend(
            build_page_limiter_radar(
                limiter_data=limiter_data, figure_paths=figure_paths, styles=styles
            )
        )
        story.append(PageBreak())

    if any(k in figure_paths for k in ["drift_heatmap_hr", "drift_heatmap_smo2"]):
        story.extend(
            build_page_drift_kpi(kpi=pdf_data["kpi"], figure_paths=figure_paths, styles=styles)
        )
        story.append(PageBreak())

    story.extend(
        build_page_thermal(
            thermo_data=pdf_data.get("thermo_analysis", {}),
            figure_paths=figure_paths,
            styles=styles,
        )
    )
    story.append(PageBreak())

    # ROZDZIAŁ 5: PODSUMOWANIE
    story.extend(build_page_kpi_dashboard(kpi=pdf_data["kpi"], styles=styles))
    story.append(PageBreak())

    story.extend(
        build_page_executive_summary(
            executive_data=pdf_data.get("executive_summary", {}), metadata=metadata, styles=styles
        )
    )
    story.append(PageBreak())

    story.extend(
        build_page_executive_verdict(
            canonical_physio=pdf_data.get("canonical_physiology", {}),
            smo2_advanced=pdf_data.get(
                "smo2_advanced", pdf_data.get("smo2", {}).get("advanced_metrics", {})
            ),
            biomech_occlusion=pdf_data.get("biomech_occlusion", {}),
            thermo_analysis=pdf_data.get("thermo_analysis", {}),
            cardio_advanced=pdf_data.get("cardio_advanced", {}),
            metadata=metadata,
            styles=styles,
        )
    )
    story.append(PageBreak())

    if not compact_mode:
        from .layout import build_page_protocol

        story.extend(build_page_protocol(styles=styles))
        story.append(PageBreak())

    story.extend(build_page_limitations(styles=styles, is_conditional=config.is_conditional))
    story.extend(build_contact_footer(styles=styles))

    return story


def build_ramp_pdf(
    report_data: Dict[str, Any],
    figure_paths: Optional[Dict[str, str]] = None,
    output_path: Optional[str] = None,
    config: Optional[PDFConfig] = None,
    manual_overrides: Optional[Dict[str, Any]] = None,
    compact_mode: bool = False,
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

    buffer = BytesIO()
    pdf_data = map_ramp_json_to_pdf_data(report_data, manual_overrides=manual_overrides)
    styles = create_styles()

    story = _build_pdf_story(pdf_data, figure_paths, styles, config, compact_mode)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=config.page_size,
        leftMargin=config.margin,
        rightMargin=config.margin,
        topMargin=config.margin,
        bottomMargin=20 * mm,
    )
    doc.build(story, onFirstPage=_add_page_footer, onLaterPages=_add_page_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"PDF saved to: {output_path}")

    return pdf_bytes


# Alias for backward compatibility
generate_ramp_pdf = build_ramp_pdf
