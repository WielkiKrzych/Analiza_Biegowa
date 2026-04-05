"""
Metabolic Threshold Detection (SmO2/LT).

IMPORTANT: SmO₂ is a LOCAL/REGIONAL signal - see limitations below.

Algorithm v2.0: Uses second derivative (curvature) to detect inflection points
instead of slope thresholds. This better identifies LT1/LT2 as points where
the rate of SmO2 desaturation changes, not just where it drops.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import signal

from .threshold_types import StepSmO2Result, StepTestRange, TransitionZone
from .ventilatory import calculate_slope

# Type alias for per-step summary dicts
StepSummary = Dict[str, Any]

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_CURVATURE_THRESHOLD_LT1 = -0.0005
_CURVATURE_THRESHOLD_LT2 = -0.001
_SLOPE_THRESHOLD_LT1 = -0.005
_SLOPE_THRESHOLD_LT2 = -0.01
_MIN_POWER_GAP_LT2 = 20.0


def _compute_step_analysis(
    df: pd.DataFrame,
    step_range: StepTestRange,
    smo2_column: str,
    power_column: str,
    hr_column: str,
    time_column: str,
) -> List[StepSummary]:
    """Build per-step summary dicts with avg power/HR/SmO2 and slope."""
    has_hr = hr_column in df.columns
    steps: List[StepSummary] = []
    for step in step_range.steps[1:]:
        mask = (df[time_column] >= step.start_time) & (df[time_column] < step.end_time)
        data = df[mask]
        if len(data) < 10:
            continue
        slope, _, _ = calculate_slope(data[time_column], data[smo2_column])
        steps.append(
            {
                "step_number": step.step_number,
                "start_time": data[time_column].min(),
                "end_time": data[time_column].max(),
                "avg_power": round(data[power_column].mean(), 0),
                "avg_hr": round(data[hr_column].mean(), 0) if has_hr else None,
                "avg_smo2": round(data[smo2_column].mean(), 1),
                "slope": round(slope, 5),
                "is_t1": False,
                "is_t2": False,
                "is_skipped": False,
            }
        )
    return steps


def _smooth_and_differentiate(
    smo2s: np.ndarray, powers: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Smooth SmO2 with Savitzky-Golay and return (d_smo2, dd_smo2)."""
    window_length = min(5, len(smo2s) if len(smo2s) % 2 == 1 else len(smo2s) - 1)
    smo2s_smooth = (
        signal.savgol_filter(smo2s, window_length=window_length, polyorder=2)
        if window_length >= 3
        else smo2s
    )
    d_smo2 = np.gradient(smo2s_smooth, powers)
    dd_smo2 = np.gradient(d_smo2, powers)
    return d_smo2, dd_smo2


def _find_inflection_candidates(
    dd_smo2: np.ndarray,
    d_smo2: np.ndarray,
    powers: np.ndarray,
    start_idx: int,
    end_idx: int,
    curvature_threshold: float,
    slope_threshold: float,
    min_power: Optional[float] = None,
) -> List[Tuple[int, float, float]]:
    """Find local curvature minima that indicate inflection points.

    Returns list of (index, dd_smo2_value, power) sorted by curvature strength.
    """
    candidates: List[Tuple[int, float, float]] = []
    for i in range(start_idx, end_idx):
        if dd_smo2[i] < dd_smo2[i - 1] and dd_smo2[i] < dd_smo2[i + 1]:
            if dd_smo2[i] < curvature_threshold and d_smo2[i] < slope_threshold:
                if min_power is not None and powers[i] <= min_power:
                    continue
                candidates.append((i, dd_smo2[i], powers[i]))
    candidates.sort(key=lambda x: x[1])
    return candidates


def _build_threshold_zone(
    all_steps: List[StepSummary],
    threshold_idx: int,
    dd_smo2: np.ndarray,
    d_smo2: np.ndarray,
    threshold_label: str,
) -> Tuple[TransitionZone, float, Optional[float], int, float, float]:
    """Build TransitionZone and derived metrics for LT1 or LT2.

    Returns:
        (zone, central_power, central_hr, step_number, slope, central_smo2)
    """
    lower_idx = max(0, threshold_idx - 1)
    lower_power = all_steps[lower_idx]["avg_power"]
    upper_power = all_steps[threshold_idx]["avg_power"]
    central_power = lower_power * 0.3 + upper_power * 0.7

    # Confidence
    curvature_strength = abs(dd_smo2[threshold_idx])
    slope_confidence = min(0.3, curvature_strength * 100)
    range_width = upper_power - lower_power
    stability_confidence = max(0.0, 0.2 - range_width / 100)
    total_confidence = min(0.6, 0.1 + slope_confidence + stability_confidence)

    # HR interpolation
    lower_hr = all_steps[lower_idx]["avg_hr"]
    upper_hr = all_steps[threshold_idx]["avg_hr"]
    central_hr = (lower_hr * 0.3 + upper_hr * 0.7) if lower_hr and upper_hr else upper_hr

    # SmO2 interpolation
    lower_smo2 = all_steps[lower_idx]["avg_smo2"]
    upper_smo2 = all_steps[threshold_idx]["avg_smo2"]
    central_smo2 = lower_smo2 * 0.3 + upper_smo2 * 0.7

    zone = TransitionZone(
        range_watts=(lower_power, upper_power),
        range_hr=(lower_hr, upper_hr) if lower_hr and upper_hr else None,
        confidence=total_confidence,
        stability_score=stability_confidence / 0.2 if stability_confidence > 0 else 0.5,
        method="smo2_curvature_v2",
        description=(
            f"SmO₂ {threshold_label} zone Steps "
            f"{all_steps[lower_idx]['step_number']}-{all_steps[threshold_idx]['step_number']} "
            f"(LOCAL, curvature-based)"
        ),
        detection_sources=["SmO2"],
        variability_watts=range_width,
    )

    return (
        zone,
        central_power,
        central_hr,
        all_steps[threshold_idx]["step_number"],
        d_smo2[threshold_idx],
        central_smo2,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_smo2_from_steps(
    df: pd.DataFrame,
    step_range: StepTestRange,
    smo2_column: str = "smo2",
    power_column: str = "watts",
    hr_column: str = "hr",
    time_column: str = "time",
    smo2_t1_slope_threshold: float = -0.01,
    smo2_t2_slope_threshold: float = -0.02,
) -> StepSmO2Result:
    """Detect SmO2 thresholds from step data.

    ⚠️ CRITICAL LIMITATIONS - SmO₂ is a LOCAL signal:

    1. SmO₂ reflects oxygen saturation in ONE muscle group only.
       Example: Vastus lateralis SmO₂ ≠ whole-body VO₂.

    2. This function detects POTENTIAL thresholds that should:
       - SUPPORT ventilatory thresholds (VT1, VT2)
       - NOT be used as standalone decision points
       - Be interpreted WITH VE/HR data, not instead of it

    3. Sensor placement, subcutaneous fat, and movement artifacts
       significantly affect readings.

    4. Results are returned with is_supporting_only=True to indicate
       these should influence interpretation of VT, not replace it.

    Args:
        df: DataFrame with SmO2 data
        step_range: Detected step test range
        smo2_column: Column name for SmO2 (default: 'smo2')
        power_column: Column name for power (default: 'watts')
        hr_column: Column name for HR (default: 'hr')
        time_column: Column name for time (default: 'time')
        smo2_t1_slope_threshold: Slope threshold for LT1 detection
        smo2_t2_slope_threshold: Slope threshold for LT2 detection

    Returns:
        StepSmO2Result with is_supporting_only=True (local signal)
    """
    result = StepSmO2Result()
    result.notes.append("⚠️ SmO₂ = sygnał LOKALNY - potwierdzaj z VT z wentylacji")

    # Guard: valid step range
    if not step_range or not step_range.is_valid or len(step_range.steps) < 3:
        result.notes.append("Insufficient steps for SmO2 detection (need > 2)")
        return result

    # Guard: required column
    if smo2_column not in df.columns:
        result.notes.append(f"Missing SmO2 column: {smo2_column}")
        return result

    # --- Step analysis ---
    all_steps = _compute_step_analysis(
        df, step_range, smo2_column, power_column, hr_column, time_column
    )

    if len(all_steps) < 5:
        result.notes.append("Too few steps for curvature-based detection (need >= 5)")
        result.step_analysis = all_steps
        return result

    # --- Curvature analysis ---
    powers = np.array([s["avg_power"] for s in all_steps])
    smo2s = np.array([s["avg_smo2"] for s in all_steps])
    d_smo2, dd_smo2 = _smooth_and_differentiate(smo2s, powers)

    # --- LT1 detection ---
    candidates_lt1 = _find_inflection_candidates(
        dd_smo2,
        d_smo2,
        powers,
        start_idx=2,
        end_idx=len(all_steps) - 2,
        curvature_threshold=_CURVATURE_THRESHOLD_LT1,
        slope_threshold=_SLOPE_THRESHOLD_LT1,
    )

    lt1_idx = -1
    if candidates_lt1:
        lt1_idx = candidates_lt1[0][0]
        all_steps[lt1_idx]["is_t1"] = True

        zone, central_p, central_hr, step_num, slope, central_smo2 = _build_threshold_zone(
            all_steps, lt1_idx, dd_smo2, d_smo2, "LT1"
        )
        lower_p = all_steps[max(0, lt1_idx - 1)]["avg_power"]
        upper_p = all_steps[lt1_idx]["avg_power"]

        result.smo2_1_zone = zone
        result.smo2_1_watts = round(central_p, 0)
        result.smo2_1_hr = round(central_hr, 0) if central_hr else None
        result.smo2_1_step_number = step_num
        result.smo2_1_slope = slope
        result.smo2_1_value = round(central_smo2, 1)
        result.notes.append(
            f"LT1 (SmO2) zone: {lower_p:.0f}–{upper_p:.0f} W "
            f"(central: {central_p:.0f} W, curvature: {dd_smo2[lt1_idx]:.6f}, "
            f"confidence: {zone.confidence:.2f})"
        )

    # --- LT2 detection ---
    if lt1_idx != -1:
        candidates_lt2 = _find_inflection_candidates(
            dd_smo2,
            d_smo2,
            powers,
            start_idx=lt1_idx + 2,
            end_idx=len(all_steps) - 2,
            curvature_threshold=_CURVATURE_THRESHOLD_LT2,
            slope_threshold=_SLOPE_THRESHOLD_LT2,
            min_power=powers[lt1_idx] + _MIN_POWER_GAP_LT2,
        )

        if candidates_lt2:
            lt2_idx = candidates_lt2[0][0]
            all_steps[lt2_idx]["is_t2"] = True

            zone, central_p, central_hr, step_num, slope, central_smo2 = _build_threshold_zone(
                all_steps, lt2_idx, dd_smo2, d_smo2, "LT2"
            )
            lower_p = all_steps[max(0, lt2_idx - 1)]["avg_power"]
            upper_p = all_steps[lt2_idx]["avg_power"]

            result.smo2_2_zone = zone
            result.smo2_2_watts = round(central_p, 0)
            result.smo2_2_hr = round(central_hr, 0) if central_hr else None
            result.smo2_2_step_number = step_num
            result.smo2_2_slope = slope
            result.smo2_2_value = round(central_smo2, 1)
            result.notes.append(
                f"LT2 (SmO2) zone: {lower_p:.0f}–{upper_p:.0f} W "
                f"(central: {central_p:.0f} W, curvature: {dd_smo2[lt2_idx]:.6f}, "
                f"confidence: {zone.confidence:.2f})"
            )

    result.step_analysis = all_steps
    return result


# NOTE: _detect_smo2_thresholds_legacy was removed (2026-01-02)
# REASON: Function was never called - detect_smo2_from_steps is the active implementation
