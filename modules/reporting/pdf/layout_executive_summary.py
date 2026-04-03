"""Executive summary page layout extracted from layout.py."""
from typing import Any, Dict, List

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from .styles import COLORS


def build_page_executive_summary(
    executive_data: Dict[str, Any],
    metadata: Dict[str, Any],
    styles: Dict
) -> List:
    """Build Page 0: PREMIUM Executive Physio Summary.
    
    Commercial-grade layout with:
    - Hero Header with status badge
    - Physiological Verdict Card
    - Signal Agreement Matrix
    - Test Confidence Panel
    - Training Decision Cards
    """
    from reportlab.lib.colors import HexColor

    elements = []

    limiter = executive_data.get("limiter", {})
    signal_matrix = executive_data.get("signal_matrix", {})
    confidence_panel = executive_data.get("confidence_panel", {})
    training_cards = executive_data.get("training_cards", [])

    test_date = metadata.get("test_date", "---")

    # ==========================================================================
    # 1. HERO HEADER
    # ==========================================================================

    limiter_color = HexColor(limiter.get("color", "#7F8C8D"))
    limiter_icon = limiter.get("icon", "⚖️")
    limiter_name = limiter.get("name", "NIEZNANY")

    # Title row
    elements.append(Paragraph(
        "<font size='14'>5.2 PODSUMOWANIE FIZJOLOGICZNE</font>",
        styles["center"]
    ))

    # Status badge + date row
    status_text = f"{limiter_icon} {limiter_name}"
    header_table = Table([
        [
            Paragraph("", styles["body"]),  # Removed duplicate CENTRALNY header
            Paragraph("", styles["body"])  # Removed Data testu line
        ]
    ], colWidths=[100 * mm, 70 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 2. PHYSIOLOGICAL VERDICT CARD
    # ==========================================================================

    verdict = limiter.get("verdict", "Brak diagnozy")
    interpretation = limiter.get("interpretation", [])
    subtitle = limiter.get("subtitle", "")

    # Card content
    verdict_content = [
        Paragraph(f"<font size='14'><b>{limiter_icon} DOMINUJĄCY LIMITER: {limiter_name}</b></font>", styles["heading"]),
        Paragraph(f"<font size='10' color='#7F8C8D'>{subtitle}</font>", styles["body"]),
        Spacer(1, 2 * mm),
        Paragraph(f"<b>{verdict}</b>", styles["body"]),
        Spacer(1, 2 * mm),
    ]

    for line in interpretation[:3]:
        verdict_content.append(Paragraph(f"• {line}", styles["body"]))

    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F8F9FA")),
        ('BOX', (0, 0), (-1, -1), 2, limiter_color),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 3. SIGNAL AGREEMENT MATRIX
    # ==========================================================================

    elements.append(Paragraph("<b>MACIERZ SYGNAŁÓW</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    signals = signal_matrix.get("signals", [])
    agreement_idx = signal_matrix.get("agreement_index", 1.0)
    agreement_label = signal_matrix.get("agreement_label", "Wysoka")

    # Signal tiles
    signal_cells = []
    for sig in signals:
        status = sig.get("status", "ok")
        icon = sig.get("icon", "❓")
        name = sig.get("name", "?")
        note = sig.get("note", "")

        if status == "ok":
            bg_color = HexColor("#D5F5E3")
            status_label = "✓ OK"
        elif status == "warning":
            bg_color = HexColor("#FCF3CF")
            status_label = "⚠ WARNING"
        else:
            bg_color = HexColor("#FADBD8")
            status_label = "✗ CONFLICT"

        # Use simple pictogram symbols for PDF compatibility
        icon_map = {
            "🫁": "~",      # VE - wave for ventilation
            "🩸": "O₂",     # O2 - oxygen symbol
            "♥": "♥",       # HR - heart (standard character)
            "💪": "O₂",     # SmO2 - oxygen symbol
            "❓": "?"
        }
        display_icon = icon_map.get(icon, "•")

        tile_content = [
            Paragraph(f"<font size='14'>{display_icon}</font>", styles["center"]),
            Paragraph(f"<b>{name}</b>", styles["center"]),
            Paragraph(f"<font size='8'>{status_label}</font>", styles["center"]),
        ]

        tile_table = Table([[tile_content]], colWidths=[52 * mm])
        tile_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ]))
        signal_cells.append(tile_table)

    # Add conflict index tile
    idx_color = HexColor("#D5F5E3") if agreement_idx >= 0.8 else (HexColor("#FCF3CF") if agreement_idx >= 0.5 else HexColor("#FADBD8"))
    idx_content = [
        Paragraph(f"<font size='14'><b>{agreement_idx:.2f}</b></font>", styles["center"]),
        Paragraph("<font size='8'>Indeks zgodności</font>", styles["center"]),
        Paragraph(f"<font size='9'>{agreement_label}</font>", styles["center"]),
    ]
    idx_table = Table([[idx_content]], colWidths=[52 * mm])
    idx_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), idx_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.5, COLORS["border"]),
    ]))
    signal_cells.append(idx_table)

    # Horizontal layout for signal tiles
    if signal_cells:
        row_table = Table([signal_cells], colWidths=[55 * mm] * len(signal_cells))
        row_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(row_table)

    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 4. TEST CONFIDENCE PANEL
    # ==========================================================================

    elements.append(Paragraph("<b>PEWNOŚĆ TESTU</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    overall_score = confidence_panel.get("overall_score", 0)
    breakdown = confidence_panel.get("breakdown", {})
    limiting_factor = confidence_panel.get("limiting_factor", "---")
    score_color = confidence_panel.get("color", "#7F8C8D")
    score_label = confidence_panel.get("label", "---")

    # Score display + breakdown
    score_para = Paragraph(
        f"<font size='28' color='{score_color}'><b>{overall_score}%</b></font> "
        f"<font size='12'>({score_label})</font>",
        styles["body"]
    )

    # Breakdown bars
    breakdown_rows = []
    for key, label in [("ve_stability", "VE Stability"), ("hr_lag", "HR Response"), ("smo2_noise", "SmO₂ Quality"), ("protocol_quality", "Protocol")]:
        val = breakdown.get(key, 50)
        bar_color = "#2ECC71" if val >= 70 else ("#F39C12" if val >= 50 else "#E74C3C")
        breakdown_rows.append([
            Paragraph(f"<font size='8'>{label}</font>", styles["body"]),
            Paragraph(f"<font size='9' color='{bar_color}'><b>{val}%</b></font>", styles["body"])
        ])

    breakdown_table = Table(breakdown_rows, colWidths=[35 * mm, 20 * mm])
    breakdown_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    confidence_row = Table([[score_para, breakdown_table]], colWidths=[60 * mm, 110 * mm])
    confidence_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(confidence_row)
    elements.append(Paragraph(f"<font size='9' color='#7F8C8D'>Ogranicza: <b>{limiting_factor}</b></font>", styles["body"]))
    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 5. TRAINING DECISION CARDS - na osobnej stronie dla spójności
    # ==========================================================================

    # PageBreak przed sekcją DECYZJE TRENINGOWE aby karty były na tej samej stronie co nagłówek
    elements.append(PageBreak())

    elements.append(Paragraph("<b>DECYZJE TRENINGOWE</b>", styles["subheading"]))
    elements.append(Spacer(1, 3 * mm))

    for i, card in enumerate(training_cards[:3], 1):
        strategy = card.get("strategy_name", "---")
        power = card.get("power_range", "---")
        volume = card.get("volume", "---")
        goal = card.get("adaptation_goal", "---")
        response = card.get("expected_response", "---")
        risk = card.get("risk_level", "low")
        constraint = card.get("constraint", "")  # OCCLUSION CONSTRAINT

        risk_color = "#2ECC71" if risk == "low" else ("#F39C12" if risk == "medium" else "#E74C3C")
        risk_label = "NISKIE" if risk == "low" else ("ŚREDNIE" if risk == "medium" else "WYSOKIE")

        card_content = [
            Paragraph(f"<font size='11'><b>{i}. {strategy}</b></font>", styles["heading"]),
            Paragraph(f"<b>Moc:</b> {power} | <b>Objętość:</b> {volume}", styles["body"]),
            Paragraph(f"<b>Cel:</b> {goal}", styles["body"]),
            Paragraph(f"<font size='9' color='#7F8C8D'>Spodziewany efekt: {response}</font>", styles["body"]),
            Paragraph(f"<font size='8' color='{risk_color}'>Ryzyko: {risk_label}</font>", styles["body"]),
        ]

        # Add occlusion constraint if present (CRITICAL for athlete safety)
        if constraint:
            card_content.append(Paragraph(
                f"<font size='8' color='#E67E22'><b>{constraint}</b></font>",
                styles["body"]
            ))

        card_table = Table([[card_content]], colWidths=[170 * mm])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLORS["background"]),
            ('BOX', (0, 0), (-1, -1), 0.5, COLORS["border"]),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(card_table)
        elements.append(Spacer(1, 2 * mm))

    return elements
