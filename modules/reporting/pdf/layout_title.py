"""Title page and contact/footer layout extracted from layout.py."""
import logging
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

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


def build_title_page(metadata: Dict[str, Any], styles: Dict) -> List:
    """Build premium title page with background image.
    
    Layout similar to KNF CSIRT document:
    - Background image banner with title overlay
    - Document metadata at bottom
    
    Args:
        metadata: Report metadata (test_date, session_id, etc.)
        styles: PDF styles dict
        
    Returns:
        List of flowables for title page
    """
    import os
    from datetime import datetime

    elements = []

    # Get path to background image
    # Try multiple locations for the background image
    bg_paths = [
        "assets/title_background.jpg",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "title_background.jpg"),
    ]

    bg_image_path = None
    for path in bg_paths:
        if os.path.exists(path):
            bg_image_path = path
            break

    # Title banner with background image
    if bg_image_path and os.path.exists(bg_image_path):
        # Use image as banner
        try:
            from reportlab.platypus import Image as RLImage

            # Add banner image (full width)
            banner = RLImage(bg_image_path, width=180 * mm, height=100 * mm)
            elements.append(banner)

            # Overlay title - use negative spacer to position on image
            elements.append(Spacer(1, -70 * mm))  # Move up into image area

            # Title with proper spacing between lines
            title_content = [
                [Paragraph(
                    "<font color='white' size='28'><b>BADANIA WYDOLNOŚCIOWE</b></font>",
                    styles["center"]
                )],
                [Spacer(1, 8 * mm)],  # Space between title and subtitle
                [Paragraph(
                    "<font color='#E0E0E0' size='12'>w oparciu o Wentylację Minutową (VE)</font>",
                    styles["center"]
                )],
                [Paragraph(
                    "<font color='#E0E0E0' size='12'>i Natlenienie Mięśniowe (SmO₂)</font>",
                    styles["center"]
                )],
            ]

            title_table = Table(title_content, colWidths=[170 * mm])
            title_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(title_table)

            elements.append(Spacer(1, 50 * mm))  # Move back down

        except Exception as e:
            logger.warning(f"Could not load background image: {e}")
            # Fallback to solid color
            elements.append(Spacer(1, 30 * mm))
            _add_fallback_title(elements, styles)
    else:
        # Fallback: solid color background
        elements.append(Spacer(1, 30 * mm))
        _add_fallback_title(elements, styles)

    # Spacer before metadata (balanced to show watermark and fit on one page)
    elements.append(Spacer(1, 15 * mm))

    # === METRYKA DOKUMENTU (CENTERED) ===
    elements.append(Paragraph(
        "<font size='14'><b>Metryka dokumentu:</b></font>",
        styles["center"]
    ))
    elements.append(Spacer(1, 6 * mm))

    # Test info
    test_date = metadata.get('test_date', '---')
    session_id = metadata.get('session_id', '')[:8] if metadata.get('session_id') else ''
    method_version = metadata.get('method_version', '1.0.0')
    gen_date = datetime.now().strftime("%d.%m.%Y, %H:%M")
    subject_name = metadata.get('subject_name', '')
    subject_anthropometry = metadata.get('subject_anthropometry', '')

    meta_data = [
        [Paragraph("<b>Data testu:</b>", styles["center"]),
         Paragraph(str(test_date), styles["center"])],
        [Paragraph("<b>ID sesji:</b>", styles["center"]),
         Paragraph(session_id, styles["center"])],
        [Paragraph("<b>Wersja metody:</b>", styles["center"]),
         Paragraph(method_version, styles["center"])],
        [Paragraph("<b>Data generowania:</b>", styles["center"]),
         Paragraph(gen_date, styles["center"])],
    ]

    # Add subject name row if provided
    if subject_name:
        meta_data.append([
            Paragraph("<b>Osoba badana:</b>", styles["center"]),
            Paragraph(subject_name, styles["center"])
        ])

    # Add anthropometry row if provided
    if subject_anthropometry:
        meta_data.append([
            Paragraph("<b>Wiek / Wzrost / Waga:</b>", styles["center"]),
            Paragraph(subject_anthropometry, styles["center"])
        ])

    meta_table = Table(meta_data, colWidths=[60 * mm, 80 * mm])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)

    # Spacer before author section (reduced to fit on one page)
    elements.append(Spacer(1, 20 * mm))

    # === OPRACOWANIE SECTION WITH BACKGROUND IMAGE (like title banner) ===
    # Use the same background image for premium styling
    if bg_image_path and os.path.exists(bg_image_path):
        try:
            from reportlab.platypus import Image as RLImage

            # Add smaller banner for author section (compact to fit on one page)
            author_banner = RLImage(bg_image_path, width=180 * mm, height=25 * mm)
            elements.append(author_banner)

            # Overlay author text - use negative spacer to position on image
            elements.append(Spacer(1, -18 * mm))  # Move up into image area

            author_content = [[Paragraph(
                "<font color='white' size='20'><b>Opracowanie: Krzysztof Kubicz</b></font>",
                styles["center"]
            )]]

            author_table = Table(author_content, colWidths=[170 * mm])
            author_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(author_table)
            elements.append(Spacer(1, 5 * mm))  # Move back down

        except Exception as e:
            logger.warning(f"Could not create author banner: {e}")
            # Fallback to simple larger bold text
            elements.append(Paragraph(
                "<font size='20'><b>Opracowanie: Krzysztof Kubicz</b></font>",
                styles["center"]
            ))
    else:
        # Fallback: larger bold text with solid background
        author_content = [[Paragraph(
            "<font color='white' size='20'><b>Opracowanie: Krzysztof Kubicz</b></font>",
            styles["center"]
        )]]
        author_table = Table(author_content, colWidths=[170 * mm])
        author_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), PREMIUM_COLORS["navy"]),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(author_table)

    return elements


def _add_fallback_title(elements: List, styles: Dict):
    """Add title block with solid color background (fallback when no image)."""
    title_content = [
        [Paragraph(
            "<font color='white' size='24'><b>BADANIA WYDOLNOŚCIOWE</b></font>",
            styles["center"]
        )],
        [Paragraph(
            "<font color='#BDC3C7' size='14'>w oparciu o Wentylację Minutową (VE)</font>",
            styles["center"]
        )],
        [Paragraph(
            "<font color='#BDC3C7' size='14'>i Natlenienie Mięśniowe (SmO₂)</font>",
            styles["center"]
        )],
    ]

    title_table = Table(title_content, colWidths=[170 * mm])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PREMIUM_COLORS["dark_glass"]),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (0, 0), 25),
        ('BOTTOMPADDING', (-1, -1), (-1, -1), 25),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -2), 5),
    ]))
    elements.append(title_table)


def build_contact_footer(styles: Dict) -> List:
    """Build contact info footer for last page.
    
    Args:
        styles: PDF styles dict
        
    Returns:
        List of flowables
    """
    elements = []

    # Separator
    elements.append(Spacer(1, 10 * mm))
    sep_table = Table([[""]], colWidths=[170 * mm])
    sep_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 1, HexColor("#DEE2E6")),
    ]))
    elements.append(sep_table)
    elements.append(Spacer(1, 5 * mm))

    # Contact info
    elements.append(Paragraph(
        "<font size='12'><b>Krzysztof Kubicz</b></font>",
        styles["center"]
    ))
    elements.append(Paragraph(
        "<font size='11' color='#1A5276'>kubiczk@icloud.com</font>",
        styles["center"]
    ))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        "<font size='9' color='#7F8C8D'>Kontakt, pytania, konsultacje oraz umówienie się na ponowne badanie - "
        "wiadomość mailowa lub tekstowa na nr tel.: 453 330 419</font>",
        styles["center"]
    ))

    return elements
