"""
Ventilatory Threshold Detection (VT1/VT2).

This module re-exports all functions from the split submodules for backward compatibility.
"""

from .ventilatory_cpet import (
    _aggregate_steps,
    _calculate_segment_slope,
    _detect_vt1_cpet,
    _detect_vt2_cpet,
    _find_breakpoint_segmented,
    _preprocess_ventilation_data,
    _run_ve_only_mode,
    detect_vt_cpet,
    detect_vt_vslope_savgol,
)
from .ventilatory_step import (
    calculate_slope,
    detect_vt1_peaks_heuristic,
    detect_vt_from_steps,
    detect_vt_transition_zone,
    run_sensitivity_analysis,
)

__all__ = [
    "calculate_slope",
    "detect_vt1_peaks_heuristic",
    "detect_vt_from_steps",
    "detect_vt_transition_zone",
    "run_sensitivity_analysis",
    "detect_vt_vslope_savgol",
    "_preprocess_ventilation_data",
    "_detect_vt1_cpet",
    "_detect_vt2_cpet",
    "_run_ve_only_mode",
    "_aggregate_steps",
    "detect_vt_cpet",
    "_find_breakpoint_segmented",
    "_calculate_segment_slope",
]
