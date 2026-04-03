"""
Reporting Module.

Contains report generation utilities for Ramp Test and other analyses.
"""
from .figures import (
                      generate_all_ramp_figures,
                      generate_pdc_chart,
                      generate_ramp_profile_chart,
                      generate_smo2_power_chart,
)
from .pdf import PDFConfig, generate_ramp_pdf
from .persistence import (
                      check_git_tracking,
                      generate_and_save_pdf,
                      load_ramp_test_report,
                      save_ramp_test_report,
                      update_index_pdf_path,
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
