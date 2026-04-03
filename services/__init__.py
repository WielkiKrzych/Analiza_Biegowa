"""
Services Package - Business Logic Layer

This package separates business logic and data analysis from the application entrypoint.
All session analysis, validation, and orchestration logic resides here.

Modules:
- session_analysis: Metrics calculations (NP, IF, TSS, extended metrics)
- data_validation: DataFrame structure validation
- session_orchestrator: High-level session processing pipeline
"""

from .data_validation import validate_dataframe
from .session_analysis import (
                               MIN_HR_ACTIVE,
                               MIN_RECORDS_FOR_ROLLING,
                               MIN_WATTS_ACTIVE,
                               RESAMPLE_STEP,
                               RESAMPLE_THRESHOLD,
                               ROLLING_WINDOW_5MIN,
                               ROLLING_WINDOW_30S,
                               ROLLING_WINDOW_60S,
                               apply_smo2_smoothing,
                               calculate_extended_metrics,
                               calculate_header_metrics,
                               resample_dataframe,
)
from .session_orchestrator import (
                               prepare_session_record,
                               prepare_sticky_header_data,
                               process_uploaded_session,
)

__all__ = [
    # Session Analysis
    'calculate_header_metrics',
    'calculate_extended_metrics',
    'apply_smo2_smoothing',
    'resample_dataframe',
    # Constants
    'ROLLING_WINDOW_5MIN',
    'ROLLING_WINDOW_30S',
    'ROLLING_WINDOW_60S',
    'MIN_WATTS_ACTIVE',
    'MIN_HR_ACTIVE',
    'MIN_RECORDS_FOR_ROLLING',
    'RESAMPLE_THRESHOLD',
    'RESAMPLE_STEP',
    # Validation
    'validate_dataframe',
    # Orchestration
    'process_uploaded_session',
    'prepare_session_record',
    'prepare_sticky_header_data',
]
