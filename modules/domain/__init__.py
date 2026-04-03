"""
Domain Module.

Contains domain-level concepts and value objects.
"""

from .session_type import (
    RAMP_CONFIDENCE_THRESHOLD,
    RampClassificationResult,
    SessionType,
    classify_ramp_test,
    classify_session_type,
)

__all__ = [
    "SessionType",
    "classify_session_type",
    "RampClassificationResult",
    "classify_ramp_test",
    "RAMP_CONFIDENCE_THRESHOLD",
]
