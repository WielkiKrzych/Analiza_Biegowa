"""
Signals Module - Signal Processing

This module contains signal processing and analysis functions.
NO STREAMLIT OR UI DEPENDENCIES ALLOWED.

Sub-modules:
- preprocessing: Smoothing, detrending, interpolation, quality
- validation: Input validation, artifact detection, warnings
- processing: Data normalization
- kinetics: O2/SmO2 kinetics analysis
"""

# Preprocessing module
from modules.calculations.data_processing import ensure_pandas, process_data

# Re-export from modules.calculations for now (gradual migration)
from modules.calculations.kinetics import (
                                           analyze_temporal_sequence,
                                           calculate_o2_deficit,
                                           calculate_resaturation_metrics,
                                           calculate_signal_lag,
                                           classify_smo2_context,
                                           detect_physiological_state,
                                           detect_smo2_breakpoints,
                                           detect_smo2_trend,
                                           fit_smo2_kinetics,
                                           generate_state_timeline,
                                           get_tau_interpretation,
                                           normalize_smo2_series,
)
from modules.calculations.quality import (
                                           check_data_suitability,
                                           check_signal_quality,
                                           check_step_test_protocol,
)

# Conflict detection module (new)
from signals.conflicts import (
                                           ConflictAnalysisResult,
                                           ConflictSeverity,
                                           ConflictType,
                                           SignalConflict,
                                           detect_cardiac_drift,
                                           detect_decoupling,
                                           detect_dfa_anomaly,
                                           detect_signal_conflicts,
                                           detect_smo2_power_conflict,
)
from signals.preprocessing import (
                                           SeriesResult,
                                           SignalQualityFlags,
                                           detrend_linear,
                                           detrend_polynomial,
                                           exponential_smooth,
                                           interpolate_gaps,
                                           preprocess_signal,
                                           rolling_smooth,
)

# Validation module (new)
from signals.validation import (
                                           Severity,
                                           ValidationResult,
                                           ValidationWarning,
                                           check_data_range,
                                           check_minimum_length,
                                           detect_artifacts,
                                           detect_missing_data,
                                           validate_signal,
)

__all__ = [
    # Preprocessing
    'SignalQualityFlags',
    'SeriesResult',
    'rolling_smooth',
    'exponential_smooth',
    'detrend_linear',
    'detrend_polynomial',
    'interpolate_gaps',
    'preprocess_signal',
    # Validation
    'Severity',
    'ValidationWarning',
    'ValidationResult',
    'detect_missing_data',
    'detect_artifacts',
    'check_minimum_length',
    'check_data_range',
    'validate_signal',
    # Conflict Detection
    'ConflictSeverity',
    'ConflictType',
    'SignalConflict',
    'ConflictAnalysisResult',
    'detect_cardiac_drift',
    'detect_smo2_power_conflict',
    'detect_dfa_anomaly',
    'detect_decoupling',
    'detect_signal_conflicts',
    # Kinetics
    'fit_smo2_kinetics',
    'get_tau_interpretation',
    'calculate_o2_deficit',
    'detect_smo2_breakpoints',
    'normalize_smo2_series',
    'detect_smo2_trend',
    'classify_smo2_context',
    'calculate_resaturation_metrics',
    'calculate_signal_lag',
    'analyze_temporal_sequence',
    'detect_physiological_state',
    'generate_state_timeline',
    # Processing
    'process_data',
    'ensure_pandas',
    # Quality
    'check_signal_quality',
    'check_step_test_protocol',
    'check_data_suitability',
]

