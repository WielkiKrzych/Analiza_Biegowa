"""Executive verdict page layout extracted from layout.py."""
from typing import Any, Dict, List
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

def build_page_executive_verdict(canonical_physio: Dict[str, Any], smo2_advanced: Dict[str, Any], biomech_occlusion: Dict[str, Any], thermo_analysis: Dict[str, Any], cardio_advanced: Dict[str, Any], metadata: Dict[str, Any], styles: Dict) -> List:
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
    elements = []
    summary = canonical_physio.get('summary', {})
    vo2max = summary.get('vo2max')
    vo2max_source = summary.get('vo2max_source', 'unknown')
    hr_coupling = smo2_advanced.get('hr_coupling_r', 0)
    halftime = smo2_advanced.get('halftime_reoxy_sec')
    smo2_slope = smo2_advanced.get('slope_per_100w', 0)
    limiter_type = smo2_advanced.get('limiter_type', 'unknown')
    smo2_drift = smo2_advanced.get('drift_pct', 0)
    biomech_metrics = biomech_occlusion.get('metrics', {})
    occlusion_index = biomech_metrics.get('occlusion_index', 0)
    torque_10 = biomech_metrics.get('torque_at_minus_10')
    torque_20 = biomech_metrics.get('torque_at_minus_20')
    occlusion_level = biomech_occlusion.get('classification', {}).get('level', 'unknown')
    thermo_metrics = thermo_analysis.get('metrics', {})
    max_core_temp = thermo_metrics.get('max_core_temp', 0)
    peak_hsi = thermo_metrics.get('peak_hsi', 0)
    cardiac_drift = thermo_analysis.get('cardiac_drift', {})
    ef_delta_pct = cardiac_drift.get('delta_pct', 0)
    drift_classification = cardiac_drift.get('classification', 'unknown')
    ef = cardio_advanced.get('efficiency_factor', 0)
    hr_drift_pct = cardio_advanced.get('hr_drift_pct', 0)
    test_date = metadata.get('test_date', '---')
    profile_parts = []
    if vo2max and vo2max > 50:
        profile_parts.append('STABILNY CENTRALNIE')
    elif vo2max:
        profile_parts.append('UMIARKOWANY CENTRALNIE')
    else:
        profile_parts.append('PROFIL NIEZNANY')
    limiters = []
    if occlusion_level in ['high', 'moderate']:
        limiters.append('OGRANICZANY MECHANICZNIE')
    if max_core_temp > 38.0 or peak_hsi > 6:
        limiters.append('OGRANICZANY TERMICZNIE')
    if abs(smo2_drift) > 8:
        limiters.append('DRYF OBWODOWY')
    if limiters:
        profile_parts.extend(limiters)
    profile_description = ', '.join(profile_parts)
    if limiter_type == 'central':
        main_interpretation = 'Wydajność VO₂max jest wysoka, układ krążenia dyktuje tempo. Priorytet: rozbudowa pojemności minutowej serca.'
    elif limiter_type == 'local':
        main_interpretation = 'Potencjał VO₂max jest wysoki, ale jego wykorzystanie ogranicza okluzja mięśniowa przy wysokim momencie obrotowym oraz narastający koszt termoregulacyjny.'
    else:
        main_interpretation = 'Profil mieszany: zarówno zdolność centralna jak i obwodowa wymagają równoczesnej pracy. Treningi zrównoważone dadzą najlepsze efekty.'
    confidence_score = smo2_advanced.get('limiter_confidence', 0.5)
    elements.append(Paragraph("<font size='14'>5.3 WERDYKT FIZJOLOGICZNY</font>", styles['center']))
    elements.append(Paragraph("<font size='10' color='#7F8C8D'>Decyzyjne podsumowanie całego raportu fizjologicznego</font>", styles['center']))
    elements.append(Spacer(1, 6 * mm))
    hero_content = [[Paragraph(f"<font size='12' color='#FFFFFF'><b>WERDYKT GŁÓWNY</b></font>", styles['center'])], [Paragraph(f"<font size='11' color='#F1C40F'><b>Profil wydolnościowy: {profile_description}</b></font>", styles['center'])], [Spacer(1, 2 * mm)], [Paragraph(f"<font size='10' color='#FFFFFF'>{main_interpretation}</font>", styles['center'])], [Spacer(1, 2 * mm)], [Paragraph(f"<font size='8' color='#BDC3C7'>Confidence score: {confidence_score:.2f} | Źródła: VO₂max ({vo2max_source}), SmO₂, HR coupling, Core Temp</font>", styles['center'])]]
    hero_table = Table(hero_content, colWidths=[170 * mm])
    hero_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor('#1a1a2e')), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10)]))
    elements.append(hero_table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph('<b>MATRYCA DECYZJI (DLACZEGO / CO / JAK)</b>', styles['subheading']))
    elements.append(Spacer(1, 2 * mm))
    bottleneck = 'MIESZANY'
    bottleneck_color = '#7F8C8D'
    if torque_20 and torque_20 < 65:
        bottleneck = 'MECHANICZNE (Okluzja)'
        bottleneck_color = '#E74C3C'
    elif hr_drift_pct > 15 and max_core_temp > 38.0:
        bottleneck = 'TERMICZNE (Obciążenie Cieplne)'
        bottleneck_color = '#F39C12'
    elif hr_coupling < -0.75:
        bottleneck = 'CENTRALNY (Pojemność Minutowa)'
        bottleneck_color = '#3498DB'
    elif limiter_type == 'central':
        bottleneck = 'CENTRALNY (Pojemność Minutowa)'
        bottleneck_color = '#3498DB'
    elif limiter_type == 'local':
        bottleneck = 'OBWODOWY (Ekstrakcja O₂)'
        bottleneck_color = '#9B59B6'
    why_text = ''
    what_text = ''
    how_text = ''
    if 'MECHANICAL' in bottleneck:
        why_text = f'Kompresja naczyniowa przy momencie >{torque_20 or 0:.0f} Nm ogranicza perfuzję mięśniową mimo dostępnego O₂ systemowego.'
        what_text = 'Szybszy spadek SmO₂, wcześniejsze zmęczenie nóg, utrata reaktywności na ataki.'
        how_text = 'Zwiększ kadencję do 95-105 rpm. Trenuj wysoko-kadencyjnie. Sprawdź ustawienie siodła.'
    elif 'THERMAL' in bottleneck:
        why_text = f'Core temp {max_core_temp:.1f}°C + drift {hr_drift_pct:.0f}% → redystrybucja krwi do skóry ogranicza dostawę do mięśni.'
        what_text = 'Postępujący spadek mocy po 45-60 min, wysokie HR przy niskiej mocy, ryzyko DNF.'
        how_text = 'Heat acclimation 10-14 dni. Pre-cooling przed startem. Nawodnienie 750ml/h + Na+.'
    elif 'CENTRAL' in bottleneck:
        why_text = f'Układ krążenia przy {vo2max or 0:.0f} ml/kg/min dyktuje limit – mięśnie mają rezerwę.'
        what_text = 'Limit tętna osiągany przed zmęczeniem mięśni. Płaski profil SmO₂ przy wysokim HR.'
        how_text = 'Interwały VO₂max (5×5 min @ 106-120% FTP). Z2 dla podniesienia SV. Hill repeats.'
    elif 'PERIPHERAL' in bottleneck:
        why_text = 'Ekstrakcja O₂ w mięśniu jest limitem – niska kapilaryzacja lub wysoka glikoliza.'
        what_text = 'SmO₂ spada szybko przy submaksymalnych wysiłkach. Szybka lokalna kwasica.'
        how_text = 'Sweet spot + threshold work. Siła na rowerze. Trening low-cadence.'
    else:
        why_text = 'Brak jednoznacznego limitera – wydolność zbalansowana między systemami.'
        what_text = 'Równomierne obciążenie wszystkich układów. Brak dominującego ograniczenia.'
        how_text = 'Kontynuuj polaryzowany trening. Monitoruj wszystkie KPI równolegle.'
    body_style = ParagraphStyle('matrix_body', parent=styles['body'], textColor=HexColor('#FFFFFF'), fontSize=8)
    matrix_rows = [[Paragraph('<b>GŁÓWNE OGRANICZENIE</b>', body_style), Paragraph(f'<b>{bottleneck}</b>', body_style)], [Paragraph('<b>DLACZEGO OGRANICZA WYDAJNOŚĆ</b>', body_style), Paragraph(why_text, body_style)], [Paragraph('<b>CO POWODUJE W WYŚCIGU</b>', body_style), Paragraph(what_text, body_style)], [Paragraph('<b>JAK TO NAPRAWIĆ</b>', body_style), Paragraph(how_text, body_style)]]
    matrix_table = Table(matrix_rows, colWidths=[45 * mm, 130 * mm])
    matrix_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, -1), HexColor('#2C3E50')), ('BACKGROUND', (1, 0), (1, 0), HexColor(bottleneck_color)), ('BACKGROUND', (1, 1), (1, -1), HexColor('#34495E')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#1a1a2e')), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6)]))
    elements.append(matrix_table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph('<b>CO JEST MOCNE</b>', styles['subheading']))
    elements.append(Spacer(1, 2 * mm))
    strengths = []
    if vo2max:
        vo2_interp = 'Wysoka wydolność aerobowa' if vo2max > 55 else 'Dobra wydolność' if vo2max > 45 else 'Do poprawy'
        strengths.append(f'• <b>VO₂max (canonical):</b> {vo2max:.1f} ml/kg/min → {vo2_interp}')
    if abs(hr_coupling) > 0.5:
        coup_interp = 'Silna korelacja HR-SmO₂ – układ spójny' if abs(hr_coupling) > 0.7 else 'Umiarkowana korelacja'
        strengths.append(f'• <b>HR–SmO₂ coupling (r):</b> {hr_coupling:.2f} → {coup_interp}')
    if halftime and halftime < 60:
        ht_interp = 'Szybka reoksygenacja – dobra kapilaryzacja' if halftime < 30 else 'Akceptowalna reoksygenacja'
        strengths.append(f'• <b>Reoxy half-time:</b> {halftime:.0f} s → {ht_interp}')
    if ef > 1.8:
        ef_interp = 'Wysoka efektywność sercowa'
        strengths.append(f'• <b>Efficiency Factor:</b> {ef:.2f} W/bpm → {ef_interp}')
    if not strengths:
        strengths.append('• Brak wyróżniających się mocnych stron w danych')
    strength_conclusion = 'Wniosek: układ krążenia jest gotowy na dalszą intensyfikację treningową.'
    strength_text = '<br/>'.join(strengths) + f'<br/><br/><i>{strength_conclusion}</i>'
    green_style = ParagraphStyle('green_box', parent=styles['body'], textColor=HexColor('#FFFFFF'), fontSize=9)
    green_box = Table([[Paragraph(strength_text, green_style)]], colWidths=[170 * mm])
    green_box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor('#27AE60')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    elements.append(green_box)
    elements.append(Spacer(1, 4 * mm))
    limiter_elements = []
    limiter_elements.append(Paragraph('<b>CO OGRANICZA WYNIK</b>', styles['subheading']))
    limiter_elements.append(Spacer(1, 2 * mm))
    occlusion_items = []
    occlusion_items.append('<b>1. OKLUZJA MECHANICZNA</b>')
    occlusion_items.append(f'• Moment przy −10% SmO₂: {torque_10:.0f} Nm' if torque_10 else '• Moment przy −10% SmO₂: ---')
    occlusion_items.append(f'• Moment przy −20% SmO₂: {torque_20:.0f} Nm' if torque_20 else '• Moment przy −20% SmO₂: ---')
    occlusion_items.append(f'• Occlusion Index: {occlusion_index:.3f}' if occlusion_index else '• Occlusion Index: ---')
    occlusion_items.append('<i>Moc dostępna centralnie, ale ograniczona przez kompresję naczyń w mięśniu.</i>')
    occlusion_color = '#E74C3C' if occlusion_level == 'high' else '#F39C12' if occlusion_level == 'moderate' else '#7F8C8D'
    red_style = ParagraphStyle('red_box', parent=styles['body'], textColor=HexColor('#FFFFFF'), fontSize=9)
    occlusion_box = Table([[Paragraph('<br/>'.join(occlusion_items), red_style)]], colWidths=[82 * mm])
    occlusion_box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor(occlusion_color)), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    thermo_items = []
    thermo_items.append('<b>2. TERMOREGULACJA</b>')
    thermo_items.append(f'• Max Core Temp: {max_core_temp:.1f} °C' if max_core_temp > 0 else '• Max Core Temp: ---')
    thermo_items.append(f'• Peak HSI: {peak_hsi:.1f}' if peak_hsi else '• Peak HSI: ---')
    thermo_items.append(f'• Cardiac Drift (ΔEF): {ef_delta_pct:+.1f}%' if ef_delta_pct else '• Cardiac Drift: ---')
    thermo_items.append('<i>Wzrost temperatury zwiększa koszt utrzymania mocy i przyspiesza dryf serca.</i>')
    thermo_color = '#E74C3C' if max_core_temp > 38.5 or peak_hsi > 8 else '#F39C12' if max_core_temp > 38.0 or peak_hsi > 6 else '#7F8C8D'
    thermo_box = Table([[Paragraph('<br/>'.join(thermo_items), red_style)]], colWidths=[82 * mm])
    thermo_box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor(thermo_color)), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    limiter_row = Table([[occlusion_box, thermo_box]], colWidths=[85 * mm, 85 * mm])
    limiter_row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    limiter_elements.append(limiter_row)
    elements.append(KeepTogether(limiter_elements))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph('<b>3 NAJWAŻNIEJSZE RYZYKA STARTOWE</b>', styles['subheading']))
    elements.append(Spacer(1, 2 * mm))
    risks = []
    if abs(ef_delta_pct) > 15 or max_core_temp > 38.0:
        risks.append('Ryzyko spadku mocy w drugiej połowie wysiłku z powodu narastającego kosztu termoregulacyjnego')
    else:
        risks.append('Umiarkowane ryzyko spadku mocy przy wydłużonych wysiłkach – monitoruj EF')
    if occlusion_level == 'high' or abs(smo2_slope) > 6:
        risks.append('Ryzyko załamania SmO₂ przy niskiej kadencji / wysokim momencie obrotowym')
    else:
        risks.append('Profil okluzyjny w normie – zachowaj ostrożność przy ekstremalnych momentach')
    if abs(hr_drift_pct) > 8:
        risks.append('Ryzyko nieproporcjonalnego wzrostu HR przy stałej mocy (cardiac drift >8%)')
    else:
        risks.append('Stabilność HR w zakresie normy – kontynuuj obecną strategię nawodnienia')
    risk_style = ParagraphStyle('risk_box', parent=styles['body'], textColor=HexColor('#FFFFFF'), fontSize=9)
    risk_text = '<br/>'.join([f'<b>{i + 1}.</b> {r}' for i, r in enumerate(risks)])
    risk_box = Table([[Paragraph(risk_text, risk_style)]], colWidths=[170 * mm])
    risk_box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor('#2C3E50')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    elements.append(risk_box)
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph('<b>3 PRIORYTETY TRENINGOWE</b>', styles['subheading']))
    elements.append(Spacer(1, 2 * mm))
    priorities = []
    if limiter_type == 'central':
        priorities.append({'name': 'VO₂max (centralnie)', 'example': '4–6 × 4 min @ 106–120% FTP, Cel: zwiększyć rzut serca bez wzrostu kosztu EF'})
    else:
        priorities.append({'name': 'Baza aerobowa (objętość)', 'example': '3–4h @ Z2 (60–75% FTP), Cel: rozbudowa kapilaryzacji i objętości wyrzutowej'})
    if occlusion_level in ['high', 'moderate']:
        priorities.append({'name': 'Redukcja okluzji (kadencja, SmO₂)', 'example': 'Treningi @ 95–105 rpm, unikaj momentów >50 Nm, monitoruj SmO₂ w czasie rzeczywistym'})
    else:
        priorities.append({'name': 'Siła wytrzymałościowa', 'example': '4×8 min @ 50–60 rpm pod LT1, Cel: poprawa rekrutacji włókien wolnokurczliwych'})
    if max_core_temp > 38.0 or peak_hsi > 6:
        priorities.append({'name': 'Adaptacja cieplna', 'example': '10–14 dni treningu w cieple (sauna post-workout), nawodnienie 500–750 ml/h + elektrolity'})
    else:
        priorities.append({'name': 'Strategia nawodnienia', 'example': '500 ml/h minimum, CHO 60–80g/h podczas wysiłków >90 min'})
    priority_style = ParagraphStyle('priority', parent=styles['body'], fontSize=9)
    for i, p in enumerate(priorities):
        prio_text = f"<b>PRIORYTET {i + 1} — {p['name']}</b><br/>• {p['example']}"
        prio_box = Table([[Paragraph(prio_text, priority_style)]], colWidths=[170 * mm])
        prio_box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor('#ECF0F1')), ('BOX', (0, 0), (-1, -1), 1, HexColor('#3498DB')), ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        elements.append(prio_box)
        elements.append(Spacer(1, 2 * mm))
    elements.append(Spacer(1, 2 * mm))
    tagline_style = ParagraphStyle('tagline', parent=styles['center'], fontSize=10, textColor=HexColor('#7F8C8D'))
    elements.append(Paragraph("<i>Ten raport pokazuje nie 'ile możesz', ale 'dlaczego tracisz' – i jak to naprawić.</i>", tagline_style))
    elements.append(Spacer(1, 4 * mm))
    footer_style = ParagraphStyle('footer', parent=styles['body'], fontSize=7, textColor=HexColor('#95A5A6'))
    footer_text = f'<b>Typ testu:</b> Ramp Test | <b>Metodologia:</b> Ventilatory & BreathRate + SmO₂ + Core Temp | <b>Źródło VO₂max:</b> {vo2max_source} | <b>System:</b> Tri Dashboard v2.0'
    elements.append(Paragraph(footer_text, footer_style))
    return elements
