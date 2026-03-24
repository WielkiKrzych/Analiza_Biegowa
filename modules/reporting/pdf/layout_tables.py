"""Table-of-contents and chapter table helpers extracted from layout.py."""
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
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


def build_table_of_contents(styles: Dict, section_titles: List[Dict[str, Any]]) -> List:
    """Build hierarchical Table of Contents page with clickable hyperlinks.
    
    Args:
        styles: PDF styles dictionary
        section_titles: List of dicts with 'title', 'page', 'level' keys
                        level=0 for main chapters, level=1 for subchapters
        
    Returns:
        List of reportlab flowables
    """
    
    elements = []
    
    # Header
    elements.append(Paragraph(
        "<font size='22'><b>SPIS TREŚCI</b></font>",
        styles["title"]
    ))
    elements.append(Spacer(1, 8 * mm))
    
    # Table of Contents entries with hierarchy and hyperlinks
    # We need to track row heights to add spacing before chapters
    toc_data = []
    row_heights = []  # Track heights for each row
    
    for i, section in enumerate(section_titles):
        title = section.get("title", "---")
        page = section.get("page", "---")
        level = section.get("level", 1)  # 0=chapter, 1=subchapter
        
        # Create anchor name from page number for internal linking
        # ReportLab uses <a href="#page_X"> format for internal links
        anchor_name = f"page_{page}"
        
        # Check if this is a chapter (level=0) and not the first entry
        # If so, check if the previous entry was a subchapter (level=1)
        is_chapter_after_subchapter = False
        if level == 0 and i > 0:
            prev_level = section_titles[i - 1].get("level", 1)
            if prev_level == 1:
                is_chapter_after_subchapter = True
        
        if level == 0:
            # Main chapter - bold, larger, dark blue background with hyperlink
            title_para = Paragraph(
                f"<a href='#{anchor_name}' color='#1A5276'><font size='11'><b>{title}</b></font></a>",
                styles["body"]
            )
            page_para = Paragraph(
                f"<a href='#{anchor_name}' color='#1A5276'><font size='11'><b>{page}</b></font></a>",
                styles["body"]
            )
        else:
            # Subchapter - indented with bullet and hyperlink
            title_para = Paragraph(
                f"<a href='#{anchor_name}' color='#555555'><font size='9'>    • {title}</font></a>",
                styles["body"]
            )
            page_para = Paragraph(
                f"<a href='#{anchor_name}' color='#7F8C8D'><font size='9'>{page}</font></a>",
                styles["body"]
            )
        
        toc_data.append([title_para, page_para])
        # Add extra height for chapters that follow subchapters (half-line, ~6mm extra)
        if is_chapter_after_subchapter:
            row_heights.append(14 * mm)  # Normal row ~8mm + extra 6mm
        else:
            row_heights.append(None)  # Auto height
    
    if toc_data:
        toc_table = Table(toc_data, colWidths=[150 * mm, 20 * mm], rowHeights=row_heights)
        toc_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(toc_table)
    else:
        elements.append(Paragraph(
            "<font color='#7F8C8D'>Brak sekcji do wyświetlenia</font>",
            styles["body"]
        ))
    
    return elements


def build_chapter_header(chapter_num: str, chapter_title: str, styles: Dict) -> List:
    """Build a prominent chapter header with Roman numeral.
    
    Args:
        chapter_num: Roman numeral (I, II, III, IV, V)
        chapter_title: Chapter title text
        styles: PDF styles dict
        
    Returns:
        List of flowables
    """
    elements = []
    
    # Chapter header with navy background
    header_content = [[Paragraph(
        f"<font color='white' size='16'><b>{chapter_num}. {chapter_title}</b></font>",
        styles["center"]
    )]]
    
    header_table = Table(header_content, colWidths=[170 * mm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PREMIUM_COLORS["navy"]),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6 * mm))
    
    return elements
