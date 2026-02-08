"""
PDF Styles Module.

Defines typography, colors, and reusable styles for PDF generation.
Uses ReportLab library. No physiological logic.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from dataclasses import dataclass
from typing import Dict


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

PAGE_SIZE = A4
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
MARGIN = 15 * mm


# ============================================================================
# COLOR PALETTE
# ============================================================================

COLORS = {
    "primary": HexColor("#1F77B4"),
    "secondary": HexColor("#7F8C8D"),
    "success": HexColor("#2ECC71"),
    "warning": HexColor("#F1C40F"),
    "danger": HexColor("#E74C3C"),
    "vt1": HexColor("#FFA15A"),
    "vt2": HexColor("#EF553B"),
    "text": HexColor("#2C3E50"),
    "text_light": HexColor("#7F8C8D"),
    "background": HexColor("#F8F9FA"),
    "border": HexColor("#DEE2E6"),
    "grey": HexColor("#95A5A6"),
    "light_grey": HexColor("#ECF0F1"),
    "white": white,
    "black": black,
}


# ============================================================================
# TYPOGRAPHY (Polish Characters & UTF-8 Support)
# ============================================================================

# NOTE: Standard PDF fonts like "Helvetica" do NOT support Polish characters 
# in ReportLab. Using DejaVuSans TrueType font for full UTF-8 support.

def register_fonts():
    """Register TrueType fonts for PDF generation."""
    try:
        # Try to find DejaVuSans font from matplotlib (usually bundled)
        import matplotlib
        font_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        
        pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(font_dir, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", os.path.join(font_dir, "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Italic", os.path.join(font_dir, "DejaVuSans-Oblique.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVuSans-BoldItalic", os.path.join(font_dir, "DejaVuSans-BoldOblique.ttf")))
        
        return "DejaVuSans", "DejaVuSans-Bold", "DejaVuSans-Italic", "DejaVuSans-BoldItalic"
    except Exception:
        # Fallback to standard fonts if registration fails
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"

FONT_FAMILY, FONT_FAMILY_BOLD, FONT_FAMILY_ITALIC, FONT_FAMILY_BOLD_ITALIC = register_fonts()

FONT_SIZE_BODY = 10
FONT_SIZE_SMALL = 8
FONT_SIZE_HEADING = 14
FONT_SIZE_TITLE = 18


@dataclass
class PDFConfig:
    """Configuration for PDF generation."""
    page_size: tuple = A4
    margin: float = MARGIN
    title: str = "Raport z testu Ramp"
    author: str = "Tri_Dashboard"
    include_charts: bool = True
    is_conditional: bool = False  # True if RAMP_TEST_CONDITIONAL


def create_styles() -> Dict[str, ParagraphStyle]:
    """Create and return all paragraph styles for PDF.
    
    Returns:
        Dictionary mapping style names to ParagraphStyle objects.
    """
    base_styles = getSampleStyleSheet()
    
    styles = {}
    
    # Title style (main report title)
    styles["title"] = ParagraphStyle(
        "Title",
        parent=base_styles["Heading1"],
        fontName=FONT_FAMILY_BOLD,
        fontSize=FONT_SIZE_TITLE,
        textColor=COLORS["text"],
        spaceAfter=8 * mm,
        alignment=TA_CENTER,
    )
    
    # Heading style (section headers)
    styles["heading"] = ParagraphStyle(
        "Heading",
        parent=base_styles["Heading2"],
        fontName=FONT_FAMILY_BOLD,
        fontSize=FONT_SIZE_HEADING,
        textColor=COLORS["primary"],
        spaceBefore=6 * mm,
        spaceAfter=4 * mm,
        alignment=TA_LEFT,
    )
    
    # Subheading style (made bolder and more prominent)
    styles["subheading"] = ParagraphStyle(
        "Subheading",
        parent=base_styles["Heading3"],
        fontName=FONT_FAMILY_BOLD,
        fontSize=13,
        textColor=COLORS["text"],
        spaceBefore=5 * mm,
        spaceAfter=3 * mm,
        alignment=TA_LEFT,
    )
    
    # Body text style
    styles["body"] = ParagraphStyle(
        "Body",
        parent=base_styles["Normal"],
        fontName=FONT_FAMILY,
        fontSize=FONT_SIZE_BODY,
        textColor=COLORS["text"],
        leading=14,
        spaceAfter=3 * mm,
        alignment=TA_LEFT,
    )
    
    # Body Italic style
    styles["body_italic"] = ParagraphStyle(
        "BodyItalic",
        parent=styles["body"],
        fontName=FONT_FAMILY_ITALIC,
    )
    
    # Small text style (captions, footnotes)
    styles["small"] = ParagraphStyle(
        "Small",
        parent=base_styles["Normal"],
        fontName=FONT_FAMILY,
        fontSize=FONT_SIZE_SMALL,
        textColor=COLORS["text_light"],
        leading=10,
        alignment=TA_LEFT,
    )
    
    # Footer style
    styles["footer"] = ParagraphStyle(
        "Footer",
        parent=base_styles["Normal"],
        fontName=FONT_FAMILY,
        fontSize=FONT_SIZE_SMALL,
        textColor=COLORS["text_light"],
        alignment=TA_CENTER,
    )
    
    # Centered text
    styles["center"] = ParagraphStyle(
        "Center",
        parent=styles["body"],
        alignment=TA_CENTER,
    )
    
    # Warning text (for conditional tests)
    styles["warning"] = ParagraphStyle(
        "Warning",
        parent=base_styles["Normal"],
        fontName=FONT_FAMILY_BOLD,
        fontSize=FONT_SIZE_BODY,
        textColor=HexColor("#856404"),
        backColor=HexColor("#FFF3CD"),
        leading=14,
        spaceBefore=2 * mm,
        spaceAfter=2 * mm,
        alignment=TA_LEFT,
    )
    
    return styles


def get_table_style():
    """Get standard table style for data tables.
    
    Returns:
        List of table style commands.
    """
    from reportlab.platypus import TableStyle
    
    return TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), COLORS["primary"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLORS["white"]),
        ("FONTNAME", (0, 0), (-1, 0), FONT_FAMILY_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_BODY),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), FONT_FAMILY),
        ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_BODY),
        ("ALIGN", (0, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        
        # Alternating row colors
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLORS["white"], COLORS["background"]]),
        
        # Borders
        ("GRID", (0, 0), (-1, -1), 0.5, COLORS["border"]),
        ("BOX", (0, 0), (-1, -1), 1, COLORS["border"]),
        
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ])


def get_card_style():
    """Get style for card-like containers.
    
    Returns:
        List of table style commands for cards.
    """
    from reportlab.platypus import TableStyle
    
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 1, COLORS["border"]),
    ])
