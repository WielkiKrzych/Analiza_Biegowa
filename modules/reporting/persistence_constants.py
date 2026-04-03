"""
Persistence constants for Ramp Test Report.

Canonical versioning, index structure, and shared configuration.
"""

import logging

from modules.calculations.version import RAMP_METHOD_VERSION

logger = logging.getLogger(__name__)

# canonical version of the JSON structure
CANONICAL_SCHEMA = "ramp_test_result_v1.json"
CANONICAL_VERSION = "1.0.0"
METHOD_VERSION = RAMP_METHOD_VERSION  # Pipeline version

# Index structure
INDEX_COLUMNS = [
    "session_id",
    "test_date",
    "athlete_id",
    "method_version",
    "json_path",
    "pdf_path",
    "source_file",
]
