"""
Ramp Test Report Persistence.

Handles saving of analysis results to filesystem in canonical JSON format.
Per methodology/ramp_test/10_canonical_json_spec.md.

This module is a backward-compatible re-export wrapper.
"""

from .persistence_constants import (
    CANONICAL_SCHEMA,
    CANONICAL_VERSION,
    INDEX_COLUMNS,
    METHOD_VERSION,
)
from .persistence_helpers import NumpyEncoder
from .persistence_load import check_git_tracking, load_ramp_test_report
from .persistence_pdf import (
    generate_and_save_pdf,
    generate_ramp_test_pdf,
    update_index_pdf_path,
)
from .persistence_save import save_ramp_test_report

__all__ = [
    "CANONICAL_SCHEMA",
    "CANONICAL_VERSION",
    "INDEX_COLUMNS",
    "METHOD_VERSION",
    "NumpyEncoder",
    "check_git_tracking",
    "generate_and_save_pdf",
    "generate_ramp_test_pdf",
    "load_ramp_test_report",
    "save_ramp_test_report",
    "update_index_pdf_path",
]
