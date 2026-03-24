"""Formatting helpers extracted from layout.py."""
from typing import Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

# Premium color constants
PREMIUM_COLORS = {
    "navy": HexColor("#1A5276"),      # Recommendations/training
    "dark_glass": HexColor("#17252A"), # Title page background
    "red": HexColor("#C0392B"),        # Warnings/limitations
    "green": HexColor("#27AE60"),      # Positives/strengths
    "white": HexColor("#FFFFFF"),
    "light_gray": HexColor("#BDC3C7"),
}


def build_colored_box(text: str, styles: Dict, bg_color: str = "navy") -> List:
    """Create a colored box with text for recommendations/warnings/positives.
    
    Args:
        text: Text content
        styles: PDF styles dict
        bg_color: "navy", "red", or "green"
        
    Returns:
        List of flowables
    """
    color_map = {
        "navy": PREMIUM_COLORS["navy"],
        "red": PREMIUM_COLORS["red"],
        "green": PREMIUM_COLORS["green"],
    }
    bg = color_map.get(bg_color, PREMIUM_COLORS["navy"])
    
    table_data = [[Paragraph(
        f"<font color='white'><b>{text}</b></font>",
        styles["center"]
    )]]
    
    box_table = Table(table_data, colWidths=[170 * mm])
    box_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
    ]))
    
    return [box_table, Spacer(1, 4 * mm)]


def build_section_description(text: str, styles: Dict) -> List:
    """Add 10pt italic description under section header.
    
    Args:
        text: Description text (1-2 sentences)
        styles: PDF styles dict
        
    Returns:
        List of flowables
    """
    desc_style = ParagraphStyle(
        "SectionDescription",
        fontName="DejaVuSans-Oblique" if "DejaVuSans" in str(styles.get("body", {})) else "Helvetica-Oblique",
        fontSize=10,
        textColor=HexColor("#7F8C8D"),
        leading=12,
        spaceAfter=4 * mm,
    )
    return [Paragraph(text, desc_style)]
