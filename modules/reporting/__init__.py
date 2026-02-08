"""
Reporting Module.

Contains report generation utilities for Ramp Test and other analyses.
"""
from .persistence import (
    save_ramp_test_report,
    load_ramp_test_report,
    check_git_tracking,
    generate_and_save_pdf,
    update_index_pdf_path,
)
from .pdf import generate_ramp_pdf, PDFConfig
from .figures import (
    generate_ramp_profile_chart,
    generate_smo2_power_chart,
    generate_pdc_chart,
    generate_all_ramp_figures,
)

__all__ = [
    # Persistence
    "save_ramp_test_report",
    "load_ramp_test_report",
    "check_git_tracking",
    "generate_and_save_pdf",
    "update_index_pdf_path",
    # PDF
    "generate_ramp_pdf",
    "PDFConfig",
    # Figures
    "generate_ramp_profile_chart",
    "generate_smo2_power_chart",
    "generate_pdc_chart",
    "generate_all_ramp_figures",
]
