"""
Metabolic Threshold Detection (SmO2/LT).

IMPORTANT: SmO₂ is a LOCAL/REGIONAL signal - see limitations below.

Algorithm v2.0: Uses second derivative (curvature) to detect inflection points
instead of slope thresholds. This better identifies LT1/LT2 as points where
the rate of SmO2 desaturation changes, not just where it drops.
"""

import pandas as pd
import numpy as np
from scipy import signal
from .threshold_types import StepSmO2Result, StepTestRange, TransitionZone
from .ventilatory import calculate_slope


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

    # Add interpretation note to results
    result.notes.append("⚠️ SmO₂ = sygnał LOKALNY - potwierdzaj z VT z wentylacji")

    if not step_range or not step_range.is_valid or len(step_range.steps) < 3:
        result.notes.append("Insufficient steps for SmO2 detection (need > 2)")
        return result

    if smo2_column not in df.columns:
        result.notes.append(f"Missing SmO2 column: {smo2_column}")
        return result

    has_hr = hr_column in df.columns
    all_steps = []
    for step in step_range.steps[1:]:
        mask = (df[time_column] >= step.start_time) & (df[time_column] < step.end_time)
        data = df[mask]
        if len(data) < 10:
            continue
        slope, _, _ = calculate_slope(data[time_column], data[smo2_column])
        all_steps.append(
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

    # NEW ALGORITHM v2.0: Use second derivative (curvature) to detect inflection points
    # This identifies LT1/LT2 as points where the RATE of SmO2 desaturation changes
    # rather than just where it drops below a threshold

    if len(all_steps) < 5:
        result.notes.append("Too few steps for curvature-based detection (need >= 5)")
        result.step_analysis = all_steps
        return result

    # Extract power and smo2 arrays
    powers = np.array([s["avg_power"] for s in all_steps])
    smo2s = np.array([s["avg_smo2"] for s in all_steps])
    hrs = np.array([s["avg_hr"] if s["avg_hr"] else np.nan for s in all_steps])

    # Smooth SmO2 data with Savitzky-Golay filter to reduce noise
    window_length = min(5, len(smo2s) if len(smo2s) % 2 == 1 else len(smo2s) - 1)
    if window_length >= 3:
        smo2s_smooth = signal.savgol_filter(smo2s, window_length=window_length, polyorder=2)
    else:
        smo2s_smooth = smo2s

    # Calculate first derivative (slope) and second derivative (curvature)
    d_smo2 = np.gradient(smo2s_smooth, powers)
    dd_smo2 = np.gradient(d_smo2, powers)

    # Find inflection points: local maxima in second derivative (most negative curvature)
    # These indicate where the desaturation accelerates (LT1, LT2)

    # LT1: First significant inflection point where SmO2 starts dropping faster
    # Look for points where second derivative is negative (accelerating drop)
    # and first derivative is negative (dropping)

    lt1_idx = -1
    lt2_idx = -1

    # Find candidate inflection points (negative curvature)
    curvature_threshold_lt1 = -0.0005  # Tune based on data
    curvature_threshold_lt2 = -0.001  # Stronger curvature for LT2

    candidates_lt1 = []
    candidates_lt2 = []

    for i in range(2, len(all_steps) - 2):  # Skip edges
        # Check if this is a local minimum in curvature (most negative)
        if dd_smo2[i] < dd_smo2[i - 1] and dd_smo2[i] < dd_smo2[i + 1]:
            if dd_smo2[i] < curvature_threshold_lt1 and d_smo2[i] < -0.005:
                # This is an inflection point where SmO2 is dropping and accelerating
                candidates_lt1.append((i, dd_smo2[i], powers[i]))

    # Sort by curvature strength (most negative first)
    candidates_lt1.sort(key=lambda x: x[1])

    if len(candidates_lt1) >= 1:
        lt1_idx = candidates_lt1[0][0]
        all_steps[lt1_idx]["is_t1"] = True

        # Calculate LT1 range
        lower_step_idx = max(0, lt1_idx - 1)
        lower_power = all_steps[lower_step_idx]["avg_power"]
        upper_power = all_steps[lt1_idx]["avg_power"]
        central_power = lower_power * 0.3 + upper_power * 0.7

        # Confidence based on curvature strength
        curvature_strength = abs(dd_smo2[lt1_idx])
        slope_confidence = min(0.3, curvature_strength * 100)
        range_width = upper_power - lower_power
        stability_confidence = max(0.0, 0.2 - range_width / 100)
        base_confidence = 0.1
        total_confidence = min(0.6, base_confidence + slope_confidence + stability_confidence)

        lower_hr = all_steps[lower_step_idx]["avg_hr"]
        upper_hr = all_steps[lt1_idx]["avg_hr"]
        central_hr = (lower_hr * 0.3 + upper_hr * 0.7) if lower_hr and upper_hr else upper_hr

        lower_smo2 = all_steps[lower_step_idx]["avg_smo2"]
        upper_smo2 = all_steps[lt1_idx]["avg_smo2"]
        central_smo2 = lower_smo2 * 0.3 + upper_smo2 * 0.7

        result.smo2_1_zone = TransitionZone(
            range_watts=(lower_power, upper_power),
            range_hr=(lower_hr, upper_hr) if lower_hr and upper_hr else None,
            confidence=total_confidence,
            stability_score=stability_confidence / 0.2 if stability_confidence > 0 else 0.5,
            method="smo2_curvature_v2",
            description=f"SmO₂ LT1 zone Steps {all_steps[lower_step_idx]['step_number']}-{all_steps[lt1_idx]['step_number']} (LOCAL, curvature-based)",
            detection_sources=["SmO2"],
            variability_watts=range_width,
        )

        result.smo2_1_watts = round(central_power, 0)
        result.smo2_1_hr = round(central_hr, 0) if central_hr else None
        result.smo2_1_step_number = all_steps[lt1_idx]["step_number"]
        result.smo2_1_slope = d_smo2[lt1_idx]
        result.smo2_1_value = round(central_smo2, 1)

        result.notes.append(
            f"LT1 (SmO2) zone: {lower_power:.0f}–{upper_power:.0f} W "
            f"(central: {central_power:.0f} W, curvature: {dd_smo2[lt1_idx]:.6f}, confidence: {total_confidence:.2f})"
        )

    # LT2: Second inflection point (stronger curvature, higher power)
    if lt1_idx != -1:
        for i in range(lt1_idx + 2, len(all_steps) - 2):
            if dd_smo2[i] < dd_smo2[i - 1] and dd_smo2[i] < dd_smo2[i + 1]:
                if dd_smo2[i] < curvature_threshold_lt2 and d_smo2[i] < -0.01:
                    # Must be significantly higher power than LT1 (min 20W difference)
                    if powers[i] > powers[lt1_idx] + 20:
                        candidates_lt2.append((i, dd_smo2[i], powers[i]))

        candidates_lt2.sort(key=lambda x: x[1])

        if len(candidates_lt2) >= 1:
            lt2_idx = candidates_lt2[0][0]
            all_steps[lt2_idx]["is_t2"] = True

            lower_step_idx = max(0, lt2_idx - 1)
            lower_power = all_steps[lower_step_idx]["avg_power"]
            upper_power = all_steps[lt2_idx]["avg_power"]
            central_power = lower_power * 0.3 + upper_power * 0.7

            curvature_strength = abs(dd_smo2[lt2_idx])
            slope_confidence = min(0.3, curvature_strength * 100)
            range_width = upper_power - lower_power
            stability_confidence = max(0.0, 0.2 - range_width / 100)
            total_confidence = min(0.6, 0.1 + slope_confidence + stability_confidence)

            lower_hr = all_steps[lower_step_idx]["avg_hr"]
            upper_hr = all_steps[lt2_idx]["avg_hr"]
            central_hr = (lower_hr * 0.3 + upper_hr * 0.7) if lower_hr and upper_hr else upper_hr

            lower_smo2 = all_steps[lower_step_idx]["avg_smo2"]
            upper_smo2 = all_steps[lt2_idx]["avg_smo2"]
            central_smo2 = lower_smo2 * 0.3 + upper_smo2 * 0.7

            result.smo2_2_zone = TransitionZone(
                range_watts=(lower_power, upper_power),
                range_hr=(lower_hr, upper_hr) if lower_hr and upper_hr else None,
                confidence=total_confidence,
                stability_score=stability_confidence / 0.2 if stability_confidence > 0 else 0.5,
                method="smo2_curvature_v2",
                description=f"SmO₂ LT2 zone Steps {all_steps[lower_step_idx]['step_number']}-{all_steps[lt2_idx]['step_number']} (LOCAL, curvature-based)",
                detection_sources=["SmO2"],
                variability_watts=range_width,
            )

            result.smo2_2_watts = round(central_power, 0)
            result.smo2_2_hr = round(central_hr, 0) if central_hr else None
            result.smo2_2_step_number = all_steps[lt2_idx]["step_number"]
            result.smo2_2_slope = d_smo2[lt2_idx]
            result.smo2_2_value = round(central_smo2, 1)

            result.notes.append(
                f"LT2 (SmO2) zone: {lower_power:.0f}–{upper_power:.0f} W "
                f"(central: {central_power:.0f} W, curvature: {dd_smo2[lt2_idx]:.6f}, confidence: {total_confidence:.2f})"
            )
    result.step_analysis = all_steps
    return result


# NOTE: _detect_smo2_thresholds_legacy was removed (2026-01-02)
# REASON: Function was never called - detect_smo2_from_steps is the active implementation
