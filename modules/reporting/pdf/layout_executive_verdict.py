"""Executive verdict page layout extracted from layout.py."""

from typing import Any, Dict, List, Tuple

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle


def _extract_metrics(
    canonical_physio: Dict[str, Any],
    smo2_advanced: Dict[str, Any],
    biomech_occlusion: Dict[str, Any],
    thermo_analysis: Dict[str, Any],
    cardio_advanced: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract and flatten all metrics from input dicts into a single dict."""
    summary = canonical_physio.get("summary", {})
    biomech_metrics = biomech_occlusion.get("metrics", {})
    cardiac_drift = thermo_analysis.get("cardiac_drift", {})
    thermo_metrics = thermo_analysis.get("metrics", {})
    return {
        "vo2max": summary.get("vo2max"),
        "vo2max_source": summary.get("vo2max_source", "unknown"),
        "hr_coupling": smo2_advanced.get("hr_coupling_r", 0),
        "halftime": smo2_advanced.get("halftime_reoxy_sec"),
        "smo2_slope": smo2_advanced.get("slope_per_100w", 0),
        "limiter_type": smo2_advanced.get("limiter_type", "unknown"),
        "smo2_drift": smo2_advanced.get("drift_pct", 0),
        "confidence_score": smo2_advanced.get("limiter_confidence", 0.5),
        "occlusion_index": biomech_metrics.get("occlusion_index", 0),
        "torque_10": biomech_metrics.get("torque_at_minus_10"),
        "torque_20": biomech_metrics.get("torque_at_minus_20"),
        "occlusion_level": biomech_occlusion.get("classification", {}).get("level", "unknown"),
        "max_core_temp": thermo_metrics.get("max_core_temp", 0),
        "peak_hsi": thermo_metrics.get("peak_hsi", 0),
        "ef_delta_pct": cardiac_drift.get("delta_pct", 0),
        "ef": cardio_advanced.get("efficiency_factor", 0),
        "hr_drift_pct": cardio_advanced.get("hr_drift_pct", 0),
    }


def _build_profile_description(metrics: Dict[str, Any]) -> str:
    """Build the athlete profile description string."""
    vo2max = metrics["vo2max"]
    parts: List[str] = []

    if vo2max and vo2max > 50:
        parts.append("STABILNY CENTRALNIE")
    elif vo2max:
        parts.append("UMIARKOWANY CENTRALNIE")
    else:
        parts.append("PROFIL NIEZNANY")

    limiters: List[str] = []
    if metrics["occlusion_level"] in ["high", "moderate"]:
        limiters.append("OGRANICZANY MECHANICZNIE")
    if metrics["max_core_temp"] > 38.0 or metrics["peak_hsi"] > 6:
        limiters.append("OGRANICZANY TERMICZNIE")
    if abs(metrics["smo2_drift"]) > 8:
        limiters.append("DRYF OBWODOWY")
    parts.extend(limiters)

    return ", ".join(parts)


def _build_main_interpretation(limiter_type: str) -> str:
    """Return the main interpretation text based on limiter type."""
    interpretations = {
        "central": (
            "Wydajność VO₂max jest wysoka, układ krążenia dyktuje tempo. "
            "Priorytet: rozbudowa pojemności minutowej serca."
        ),
        "local": (
            "Potencjał VO₂max jest wysoki, ale jego wykorzystanie ogranicza okluzja mięśniowa "
            "przy wysokim momencie obrotowym oraz narastający koszt termoregulacyjny."
        ),
    }
    return interpretations.get(
        limiter_type,
        "Profil mieszany: zarówno zdolność centralna jak i obwodowa wymagają "
        "równoczesnej pracy. Treningi zrównoważone dadzą najlepsze efekty.",
    )


def _build_hero_table(
    profile_description: str,
    main_interpretation: str,
    confidence_score: float,
    vo2max_source: str,
    styles: Dict,
) -> Table:
    """Build the hero verdict table."""
    from reportlab.lib.colors import HexColor

    hero_content = [
        [
            Paragraph(
                "<font size='12' color='#FFFFFF'><b>WERDYKT GŁÓWNY</b></font>", styles["center"]
            )
        ],
        [
            Paragraph(
                f"<font size='11' color='#F1C40F'><b>Profil wydolnościowy: {profile_description}</b></font>",
                styles["center"],
            )
        ],
        [Spacer(1, 2 * mm)],
        [
            Paragraph(
                f"<font size='10' color='#FFFFFF'>{main_interpretation}</font>", styles["center"]
            )
        ],
        [Spacer(1, 2 * mm)],
        [
            Paragraph(
                f"<font size='8' color='#BDC3C7'>Confidence score: {confidence_score:.2f} | "
                f"Źródła: VO₂max ({vo2max_source}), SmO₂, HR coupling, Core Temp</font>",
                styles["center"],
            )
        ],
    ]
    hero_table = Table(hero_content, colWidths=[170 * mm])
    hero_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#1a1a2e")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return hero_table


def _resolve_bottleneck(metrics: Dict[str, Any]) -> Tuple[str, str]:
    """Determine bottleneck type and its display color."""
    if metrics["torque_20"] and metrics["torque_20"] < 65:
        return "MECHANICZNE (Okluzja)", "#E74C3C"
    if metrics["hr_drift_pct"] > 15 and metrics["max_core_temp"] > 38.0:
        return "TERMICZNE (Obciążenie Cieplne)", "#F39C12"
    if metrics["hr_coupling"] < -0.75 or metrics["limiter_type"] == "central":
        return "CENTRALNY (Pojemność Minutowa)", "#3498DB"
    if metrics["limiter_type"] == "local":
        return "OBWODOWY (Ekstrakcja O₂)", "#9B59B6"
    return "MIESZANY", "#7F8C8D"


def _build_matrix_texts(bottleneck: str, metrics: Dict[str, Any]) -> Tuple[str, str, str]:
    """Build the WHY / WHAT / HOW texts for the decision matrix."""
    if "MECHANICAL" in bottleneck:
        return (
            f"Kompresja naczyniowa przy momencie >{metrics['torque_20'] or 0:.0f} Nm "
            "ogranicza perfuzję mięśniową mimo dostępnego O₂ systemowego.",
            "Szybszy spadek SmO₂, wcześniejsze zmęczenie nóg, utrata reaktywności na ataki.",
            "Zwiększ kadencję do 95-105 rpm. Trenuj wysoko-kadencyjnie. Sprawdź ustawienie siodła.",
        )
    if "THERMAL" in bottleneck:
        return (
            f"Core temp {metrics['max_core_temp']:.1f}°C + drift {metrics['hr_drift_pct']:.0f}% "
            "→ redystrybucja krwi do skóry ogranicza dostawę do mięśni.",
            "Postępujący spadek mocy po 45-60 min, wysokie HR przy niskiej mocy, ryzyko DNF.",
            "Heat acclimation 10-14 dni. Pre-cooling przed startem. Nawodnienie 750ml/h + Na+.",
        )
    if "CENTRAL" in bottleneck:
        return (
            f"Układ krążenia przy {metrics['vo2max'] or 0:.0f} ml/kg/min dyktuje limit – mięśnie mają rezerwę.",
            "Limit tętna osiągany przed zmęczeniem mięśni. Płaski profil SmO₂ przy wysokim HR.",
            "Interwały VO₂max (5×5 min @ 106-120% FTP). Z2 dla podniesienia SV. Hill repeats.",
        )
    if "PERIPHERAL" in bottleneck:
        return (
            "Ekstrakcja O₂ w mięśniu jest limitem – niska kapilaryzacja lub wysoka glikoliza.",
            "SmO₂ spada szybko przy submaksymalnych wysiłkach. Szybka lokalna kwasica.",
            "Sweet spot + threshold work. Siła na rowerze. Trening low-cadence.",
        )
    return (
        "Brak jednoznacznego limitera – wydolność zbalansowana między systemami.",
        "Równomierne obciążenie wszystkich układów. Brak dominującego ograniczenia.",
        "Kontynuuj polaryzowany trening. Monitoruj wszystkie KPI równolegle.",
    )


def _build_decision_matrix(
    bottleneck: str,
    bottleneck_color: str,
    why_text: str,
    what_text: str,
    how_text: str,
    styles: Dict,
) -> Table:
    """Build the decision matrix table (WHY/WHAT/HOW)."""
    from reportlab.lib.colors import HexColor

    body_style = ParagraphStyle(
        "matrix_body", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=8
    )
    matrix_rows = [
        [
            Paragraph("<b>GŁÓWNE OGRANICZENIE</b>", body_style),
            Paragraph(f"<b>{bottleneck}</b>", body_style),
        ],
        [
            Paragraph("<b>DLACZEGO OGRANICZA WYDAJNOŚĆ</b>", body_style),
            Paragraph(why_text, body_style),
        ],
        [Paragraph("<b>CO POWODUJE W WYŚCIGU</b>", body_style), Paragraph(what_text, body_style)],
        [Paragraph("<b>JAK TO NAPRAWIĆ</b>", body_style), Paragraph(how_text, body_style)],
    ]
    matrix_table = Table(matrix_rows, colWidths=[45 * mm, 130 * mm])
    matrix_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), HexColor("#2C3E50")),
                ("BACKGROUND", (1, 0), (1, 0), HexColor(bottleneck_color)),
                ("BACKGROUND", (1, 1), (1, -1), HexColor("#34495E")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#1a1a2e")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return matrix_table


def _build_strengths_box(metrics: Dict[str, Any], styles: Dict) -> Table:
    """Build the green strengths box."""
    from reportlab.lib.colors import HexColor

    strengths: List[str] = []
    vo2max = metrics["vo2max"]
    if vo2max:
        vo2_interp = (
            "Wysoka wydolność aerobowa"
            if vo2max > 55
            else "Dobra wydolność"
            if vo2max > 45
            else "Do poprawy"
        )
        strengths.append(f"• <b>VO₂max (canonical):</b> {vo2max:.1f} ml/kg/min → {vo2_interp}")
    if abs(metrics["hr_coupling"]) > 0.5:
        coup_interp = (
            "Silna korelacja HR-SmO₂ – układ spójny"
            if abs(metrics["hr_coupling"]) > 0.7
            else "Umiarkowana korelacja"
        )
        strengths.append(
            f"• <b>HR–SmO₂ coupling (r):</b> {metrics['hr_coupling']:.2f} → {coup_interp}"
        )
    if metrics["halftime"] and metrics["halftime"] < 60:
        ht_interp = (
            "Szybka reoksygenacja – dobra kapilaryzacja"
            if metrics["halftime"] < 30
            else "Akceptowalna reoksygenacja"
        )
        strengths.append(f"• <b>Reoxy half-time:</b> {metrics['halftime']:.0f} s → {ht_interp}")
    if metrics["ef"] > 1.8:
        strengths.append(
            f"• <b>Efficiency Factor:</b> {metrics['ef']:.2f} W/bpm → Wysoka efektywność sercowa"
        )
    if not strengths:
        strengths.append("• Brak wyróżniających się mocnych stron w danych")

    strength_conclusion = "Wniosek: układ krążenia jest gotowy na dalszą intensyfikację treningową."
    strength_text = "<br/>".join(strengths) + f"<br/><br/><i>{strength_conclusion}</i>"

    green_style = ParagraphStyle(
        "green_box", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9
    )
    green_box = Table([[Paragraph(strength_text, green_style)]], colWidths=[170 * mm])
    green_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#27AE60")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return green_box


def _build_limiters_section(metrics: Dict[str, Any], styles: Dict) -> List:
    """Build the occlusion + thermo limiter section as a KeepTogether block."""
    from reportlab.lib.colors import HexColor

    limiter_elements: List = []
    limiter_elements.append(Paragraph("<b>CO OGRANICZA WYNIK</b>", styles["subheading"]))
    limiter_elements.append(Spacer(1, 2 * mm))

    torque_10 = metrics["torque_10"]
    torque_20 = metrics["torque_20"]
    occlusion_items = [
        "<b>1. OKLUZJA MECHANICZNA</b>",
        f"• Moment przy −10% SmO₂: {torque_10:.0f} Nm"
        if torque_10
        else "• Moment przy −10% SmO₂: ---",
        f"• Moment przy −20% SmO₂: {torque_20:.0f} Nm"
        if torque_20
        else "• Moment przy −20% SmO₂: ---",
        f"• Occlusion Index: {metrics['occlusion_index']:.3f}"
        if metrics["occlusion_index"]
        else "• Occlusion Index: ---",
        "<i>Moc dostępna centralnie, ale ograniczona przez kompresję naczyń w mięśniu.</i>",
    ]
    occlusion_color = (
        "#E74C3C"
        if metrics["occlusion_level"] == "high"
        else "#F39C12"
        if metrics["occlusion_level"] == "moderate"
        else "#7F8C8D"
    )

    red_style = ParagraphStyle(
        "red_box", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9
    )

    occlusion_box = Table(
        [[Paragraph("<br/>".join(occlusion_items), red_style)]], colWidths=[82 * mm]
    )
    occlusion_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(occlusion_color)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    thermo_items = [
        "<b>2. TERMOREGULACJA</b>",
        f"• Max Core Temp: {metrics['max_core_temp']:.1f} °C"
        if metrics["max_core_temp"] > 0
        else "• Max Core Temp: ---",
        f"• Peak HSI: {metrics['peak_hsi']:.1f}" if metrics["peak_hsi"] else "• Peak HSI: ---",
        f"• Cardiac Drift (ΔEF): {metrics['ef_delta_pct']:+.1f}%"
        if metrics["ef_delta_pct"]
        else "• Cardiac Drift: ---",
        "<i>Wzrost temperatury zwiększa koszt utrzymania mocy i przyspiesza dryf serca.</i>",
    ]
    thermo_color = (
        "#E74C3C"
        if metrics["max_core_temp"] > 38.5 or metrics["peak_hsi"] > 8
        else "#F39C12"
        if metrics["max_core_temp"] > 38.0 or metrics["peak_hsi"] > 6
        else "#7F8C8D"
    )

    thermo_box = Table([[Paragraph("<br/>".join(thermo_items), red_style)]], colWidths=[82 * mm])
    thermo_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(thermo_color)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    limiter_row = Table([[occlusion_box, thermo_box]], colWidths=[85 * mm, 85 * mm])
    limiter_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    limiter_elements.append(limiter_row)
    return [KeepTogether(limiter_elements)]


def _build_risks_box(metrics: Dict[str, Any], styles: Dict) -> Table:
    """Build the 3 startup risks box."""
    from reportlab.lib.colors import HexColor

    risks: List[str] = []
    if abs(metrics["ef_delta_pct"]) > 15 or metrics["max_core_temp"] > 38.0:
        risks.append(
            "Ryzyko spadku mocy w drugiej połowie wysiłku z powodu narastającego kosztu termoregulacyjnego"
        )
    else:
        risks.append("Umiarkowane ryzyko spadku mocy przy wydłużonych wysiłkach – monitoruj EF")
    if metrics["occlusion_level"] == "high" or abs(metrics["smo2_slope"]) > 6:
        risks.append("Ryzyko załamania SmO₂ przy niskiej kadencji / wysokim momencie obrotowym")
    else:
        risks.append("Profil okluzyjny w normie – zachowaj ostrożność przy ekstremalnych momentach")
    if abs(metrics["hr_drift_pct"]) > 8:
        risks.append("Ryzyko nieproporcjonalnego wzrostu HR przy stałej mocy (cardiac drift >8%)")
    else:
        risks.append("Stabilność HR w zakresie normy – kontynuuj obecną strategię nawodnienia")

    risk_style = ParagraphStyle(
        "risk_box", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9
    )
    risk_text = "<br/>".join([f"<b>{i + 1}.</b> {r}" for i, r in enumerate(risks)])
    risk_box = Table([[Paragraph(risk_text, risk_style)]], colWidths=[170 * mm])
    risk_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#2C3E50")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return risk_box


def _build_priorities(metrics: Dict[str, Any], styles: Dict) -> List:
    """Build the 3 training priority boxes."""
    from reportlab.lib.colors import HexColor

    priorities: List[Dict[str, str]] = []

    if metrics["limiter_type"] == "central":
        priorities.append(
            {
                "name": "VO₂max (centralnie)",
                "example": "4–6 × 4 min @ 106–120% FTP, Cel: zwiększyć rzut serca bez wzrostu kosztu EF",
            }
        )
    else:
        priorities.append(
            {
                "name": "Baza aerobowa (objętość)",
                "example": "3–4h @ Z2 (60–75% FTP), Cel: rozbudowa kapilaryzacji i objętości wyrzutowej",
            }
        )

    if metrics["occlusion_level"] in ["high", "moderate"]:
        priorities.append(
            {
                "name": "Redukcja okluzji (kadencja, SmO₂)",
                "example": "Treningi @ 95–105 rpm, unikaj momentów >50 Nm, monitoruj SmO₂ w czasie rzeczywistym",
            }
        )
    else:
        priorities.append(
            {
                "name": "Siła wytrzymałościowa",
                "example": "4×8 min @ 50–60 rpm pod LT1, Cel: poprawa rekrutacji włókien wolnokurczliwych",
            }
        )

    if metrics["max_core_temp"] > 38.0 or metrics["peak_hsi"] > 6:
        priorities.append(
            {
                "name": "Adaptacja cieplna",
                "example": "10–14 dni treningu w cieple (sauna post-workout), nawodnienie 500–750 ml/h + elektrolity",
            }
        )
    else:
        priorities.append(
            {
                "name": "Strategia nawodnienia",
                "example": "500 ml/h minimum, CHO 60–80g/h podczas wysiłków >90 min",
            }
        )

    priority_style = ParagraphStyle("priority", parent=styles["body"], fontSize=9)
    elements: List = []
    for i, p in enumerate(priorities):
        prio_text = f"<b>PRIORYTET {i + 1} — {p['name']}</b><br/>• {p['example']}"
        prio_box = Table([[Paragraph(prio_text, priority_style)]], colWidths=[170 * mm])
        prio_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#ECF0F1")),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor("#3498DB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(prio_box)
        elements.append(Spacer(1, 2 * mm))
    return elements


def build_page_executive_verdict(
    canonical_physio: Dict[str, Any],
    smo2_advanced: Dict[str, Any],
    biomech_occlusion: Dict[str, Any],
    thermo_analysis: Dict[str, Any],
    cardio_advanced: Dict[str, Any],
    metadata: Dict[str, Any],
    styles: Dict,
) -> List:
    """Build Page 2: EXECUTIVE VERDICT - 1-page decision summary.

    Contains ONLY decision boxes, numbers and conclusions. NO CHARTS.

    Sections:
    A. HERO BOX - Main verdict with profile
    B. GREEN BOX - Strengths (VO2max, coupling, reoxy)
    C. RED/AMBER BOX - Limiters (occlusion, thermoregulation)
    D. 3 STARTUP RISKS
    E. 3 TRAINING PRIORITIES
    F. TAGLINE
    G. TECHNICAL FOOTER
    """
    from reportlab.lib.colors import HexColor

    metrics = _extract_metrics(
        canonical_physio, smo2_advanced, biomech_occlusion, thermo_analysis, cardio_advanced
    )

    profile_description = _build_profile_description(metrics)
    main_interpretation = _build_main_interpretation(metrics["limiter_type"])

    elements: List = []

    elements.append(Paragraph("<font size='14'>5.3 WERDYKT FIZJOLOGICZNY</font>", styles["center"]))
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Decyzyjne podsumowanie całego raportu fizjologicznego</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    elements.append(
        _build_hero_table(
            profile_description,
            main_interpretation,
            metrics["confidence_score"],
            metrics["vo2max_source"],
            styles,
        )
    )
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("<b>MATRYCA DECYZJI (DLACZEGO / CO / JAK)</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    bottleneck, bottleneck_color = _resolve_bottleneck(metrics)
    why_text, what_text, how_text = _build_matrix_texts(bottleneck, metrics)
    elements.append(
        _build_decision_matrix(bottleneck, bottleneck_color, why_text, what_text, how_text, styles)
    )
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("<b>CO JEST MOCNE</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    elements.append(_build_strengths_box(metrics, styles))
    elements.append(Spacer(1, 4 * mm))

    elements.extend(_build_limiters_section(metrics, styles))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph("<b>3 NAJWAŻNIEJSZE RYZYKA STARTOWE</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    elements.append(_build_risks_box(metrics, styles))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph("<b>3 PRIORYTETY TRENINGOWE</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))
    elements.extend(_build_priorities(metrics, styles))
    elements.append(Spacer(1, 2 * mm))

    tagline_style = ParagraphStyle(
        "tagline", parent=styles["center"], fontSize=10, textColor=HexColor("#7F8C8D")
    )
    elements.append(
        Paragraph(
            "<i>Ten raport pokazuje nie 'ile możesz', ale 'dlaczego tracisz' – i jak to naprawić.</i>",
            tagline_style,
        )
    )
    elements.append(Spacer(1, 4 * mm))

    footer_style = ParagraphStyle(
        "footer", parent=styles["body"], fontSize=7, textColor=HexColor("#95A5A6")
    )
    footer_text = (
        f"<b>Typ testu:</b> Ramp Test | <b>Metodologia:</b> Ventilatory & BreathRate + SmO₂ + Core Temp "
        f"| <b>Źródło VO₂max:</b> {metrics['vo2max_source']} | <b>System:</b> Tri Dashboard v2.0"
    )
    elements.append(Paragraph(footer_text, footer_style))

    return elements
