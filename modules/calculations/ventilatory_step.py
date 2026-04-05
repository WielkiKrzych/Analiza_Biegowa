"""
Step-test based Ventilatory Threshold Detection (VT1/VT2).

Functions for detecting ventilatory thresholds from incremental step tests,
including recursive window scan, heuristic peak detection, sliding window
transition zones, and sensitivity analysis.
"""

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import signal, stats

from .common import (
    BASE_CONFIDENCE,
    LOWER_STEP_WEIGHT,
    MAX_CONFIDENCE,
    SLOPE_CONFIDENCE_MAX,
    STABILITY_CONFIDENCE_MAX,
    UPPER_STEP_WEIGHT,
    VT1_SLOPE_SPIKE_SKIP,
    VT1_SLOPE_THRESHOLD,
)
from .threshold_types import SensitivityResult, StepTestRange, StepVTResult, TransitionZone


def calculate_slope(time_series: pd.Series, value_series: pd.Series) -> Tuple[float, float, float]:
    """Calculate linear regression slope and standard error."""
    if len(time_series) < 2:
        return 0.0, 0.0, 0.0

    mask = ~(time_series.isna() | value_series.isna())
    if mask.sum() < 2:
        return 0.0, 0.0, 0.0

    slope, intercept, _, _, std_err = stats.linregress(time_series[mask], value_series[mask])
    return slope, intercept, std_err


def detect_vt1_peaks_heuristic(
    df: pd.DataFrame, time_column: str, ve_column: str
) -> Tuple[Optional[dict], List[str]]:
    """Heuristic VT1 Detection based on peaks."""
    if len(df) < 120:
        return None, ["Data too short for peak analysis"]

    ve_smooth = df[ve_column].rolling(window=20, center=True).mean().fillna(df[ve_column])
    peaks, _ = signal.find_peaks(ve_smooth, distance=60, prominence=1.5)

    if len(peaks) < 2:
        return None, [f"Found only {len(peaks)} peaks (need 2+)"]

    p1_idx = peaks[0]
    p2_idx = peaks[1]
    p1_time = df.iloc[p1_idx][time_column]
    p2_time = df.iloc[p2_idx][time_column]

    mask = (df[time_column] >= p1_time) & (df[time_column] <= p2_time)
    segment = df[mask]

    if len(segment) < 10:
        return None, ["Segment between peaks too short"]

    slope, _, _ = calculate_slope(segment[time_column], segment[ve_column])

    if slope > 0.05:
        return {
            "slope": slope,
            "start_time": p1_time,
            "end_time": p2_time,
            "avg_power": segment["watts"].mean() if "watts" in segment else 0,
            "avg_hr": segment["hr"].mean() if "hr" in segment else 0,
            "avg_ve": segment[ve_column].mean(),
            "idx_end": p2_idx,
        }, [f"Peak-to-Peak: Found Slope {slope:.4f} between {p1_time:.0f}s and {p2_time:.0f}s"]
    else:
        return None, [f"Peak-to-Peak: Slope {slope:.4f} too low (<= 0.05) between peaks"]


def _build_step_stages(
    df: pd.DataFrame,
    step_range: StepTestRange,
    ve_column: str,
    power_column: str,
    hr_column: str,
    time_column: str,
) -> List[dict]:
    """Build per-step stage dicts with averages and VE slope."""
    has_hr = hr_column in df.columns
    br_column = next(
        (c for c in ["tymebreathrate", "br", "rr", "breath_rate"] if c in df.columns), None
    )

    stages: List[dict] = []
    for step in step_range.steps[1:]:
        step_mask = (df[time_column] >= step.start_time) & (df[time_column] < step.end_time)
        full_step_data = df[step_mask]

        if len(full_step_data) < 10:
            continue

        slope, _, _ = calculate_slope(full_step_data[time_column], full_step_data[ve_column])

        stages.append(
            {
                "data": full_step_data,
                "avg_power": full_step_data[power_column].mean(),
                "avg_hr": full_step_data[hr_column].mean() if has_hr else None,
                "avg_ve": full_step_data[ve_column].mean(),
                "avg_br": full_step_data[br_column].mean() if br_column else None,
                "step_number": step.step_number,
                "start_time": full_step_data[time_column].min(),
                "end_time": full_step_data[time_column].max(),
                "ve_slope": slope,
            }
        )
    return stages


def _apply_vt1_result(
    result: StepVTResult,
    stages: List[dict],
    v1_idx: int,
    v1_slope: float,
    v1_stage: dict,
    v1_start_idx: int,
) -> None:
    """Apply VT1 detection results: zone, confidence, and legacy point values."""
    lower_step_idx = max(0, v1_start_idx - 1)
    lower_power = (
        stages[lower_step_idx]["avg_power"]
        if lower_step_idx < len(stages)
        else v1_stage["avg_power"]
    )
    upper_power = v1_stage["avg_power"]
    central_power = lower_power * LOWER_STEP_WEIGHT + upper_power * UPPER_STEP_WEIGHT

    slope_confidence = min(SLOPE_CONFIDENCE_MAX, v1_slope * 4)
    range_width = upper_power - lower_power
    stability_confidence = max(0.0, STABILITY_CONFIDENCE_MAX - range_width / 100)

    step_ve_values = [s["avg_ve"] for s in stages[v1_start_idx:v1_idx]]
    variance_penalty = min(0.5, np.var(step_ve_values) / 20) if len(step_ve_values) > 1 else 0.0

    total_confidence = min(
        MAX_CONFIDENCE,
        BASE_CONFIDENCE + slope_confidence + stability_confidence - variance_penalty,
    )

    lower_hr = stages[lower_step_idx]["avg_hr"] if stages[lower_step_idx]["avg_hr"] else None
    upper_hr = v1_stage["avg_hr"]
    central_hr = (lower_hr * 0.3 + upper_hr * 0.7) if lower_hr and upper_hr else upper_hr

    lower_ve = stages[lower_step_idx]["avg_ve"]
    upper_ve = v1_stage["avg_ve"]
    central_ve = lower_ve * 0.3 + upper_ve * 0.7

    result.vt1_zone = TransitionZone(
        range_watts=(lower_power, upper_power),
        range_hr=(lower_hr, upper_hr) if lower_hr and upper_hr else None,
        midpoint_ve=central_ve,
        range_ve=[lower_ve, upper_ve],
        confidence=total_confidence,
        stability_score=stability_confidence / 0.4 if stability_confidence > 0 else 0.5,
        method="step_ve_slope_range",
        description=f"VT1 zone spanning Steps {stages[lower_step_idx]['step_number']}-{v1_stage['step_number']}",
        detection_sources=["VE"],
        variability_watts=range_width,
    )

    result.vt1_watts = round(central_power, 0)
    result.vt1_hr = round(central_hr, 0) if central_hr else None
    result.vt1_ve = round(v1_stage["avg_ve"], 1)
    result.vt1_br = round(v1_stage["avg_br"], 0) if v1_stage["avg_br"] else None
    result.vt1_ve_slope = round(v1_slope, 4)
    result.vt1_step_number = v1_stage["step_number"]

    result.notes.append(
        f"VT1 zone: {lower_power:.0f}\u2013{upper_power:.0f} W "
        f"(central: {central_power:.0f} W, confidence: {total_confidence:.2f})"
    )


def _apply_vt2_result(
    result: StepVTResult,
    stages: List[dict],
    v2_slope: float,
    v2_stage: dict,
    v2_start_idx: int,
) -> None:
    """Apply VT2 detection results: zone, confidence, and legacy point values."""
    lower_step_idx = max(0, v2_start_idx - 1)
    lower_power = (
        stages[lower_step_idx]["avg_power"]
        if lower_step_idx < len(stages)
        else v2_stage["avg_power"]
    )
    upper_power = v2_stage["avg_power"]
    central_power = lower_power * 0.3 + upper_power * 0.7

    slope_confidence = min(0.4, v2_slope * 4)
    range_width = upper_power - lower_power
    stability_confidence = max(0.0, 0.4 - range_width / 100)
    base_confidence = 0.2
    total_confidence = min(0.95, base_confidence + slope_confidence + stability_confidence)

    lower_hr = stages[lower_step_idx]["avg_hr"] if stages[lower_step_idx]["avg_hr"] else None
    upper_hr = v2_stage["avg_hr"]
    central_hr = (lower_hr * 0.3 + upper_hr * 0.7) if lower_hr and upper_hr else upper_hr

    lower_ve = stages[lower_step_idx]["avg_ve"]
    upper_ve = v2_stage["avg_ve"]
    central_ve = lower_ve * 0.3 + upper_ve * 0.7

    result.vt2_zone = TransitionZone(
        range_watts=(lower_power, upper_power),
        range_hr=(lower_hr, upper_hr) if lower_hr and upper_hr else None,
        midpoint_ve=central_ve,
        range_ve=[lower_ve, upper_ve],
        confidence=total_confidence,
        stability_score=stability_confidence / 0.4 if stability_confidence > 0 else 0.5,
        method="step_ve_slope_range",
        description=f"VT2 zone spanning Steps {stages[lower_step_idx]['step_number']}-{v2_stage['step_number']}",
        detection_sources=["VE"],
        variability_watts=range_width,
    )

    result.vt2_watts = round(central_power, 0)
    result.vt2_hr = round(central_hr, 0) if central_hr else None
    result.vt2_ve = round(v2_stage["avg_ve"], 1)
    result.vt2_br = round(v2_stage["avg_br"], 0) if v2_stage["avg_br"] else None
    result.vt2_ve_slope = round(v2_slope, 4)
    result.vt2_step_number = v2_stage["step_number"]

    result.notes.append(
        f"VT2 zone: {lower_power:.0f}\u2013{upper_power:.0f} W "
        f"(central: {central_power:.0f} W, confidence: {total_confidence:.2f})"
    )


def _search_slope_threshold(
    stages: List[dict],
    time_column: str,
    ve_column: str,
    start_idx: int,
    threshold: float,
) -> Tuple:
    """Search stages for a window where VE slope exceeds threshold."""
    n = len(stages)
    for i in range(start_idx, n):
        max_w = min(6, n - i)
        for w in range(1, max_w + 1):
            combined = pd.concat([s["data"] for s in stages[i : i + w]])
            if len(combined) < 5:
                continue
            slope, _, _ = calculate_slope(combined[time_column], combined[ve_column])
            if slope > threshold:
                return i + w, slope, stages[i + w - 1], i
    return None, None, None, None


def _build_step_analysis_records(
    stages: List[dict],
    s_stage: Optional[dict],
    v1_stage: Optional[dict],
    vt1_step_number: Optional[int],
    v2_stage: Optional[dict],
    vt2_step_number: Optional[int],
) -> List[dict]:
    """Build per-step analysis records with VT markers."""
    return [
        {
            "step_number": s["step_number"],
            "avg_power": s["avg_power"],
            "avg_hr": s["avg_hr"],
            "avg_ve": s["avg_ve"],
            "avg_br": s["avg_br"],
            "ve_slope": s["ve_slope"],
            "start_time": s["start_time"],
            "end_time": s["end_time"],
            "is_skipped": s_stage is not None and s["step_number"] == s_stage["step_number"],
            "is_vt1": v1_stage is not None and s["step_number"] == vt1_step_number,
            "is_vt2": v2_stage is not None and s["step_number"] == vt2_step_number,
        }
        for s in stages
    ]


def detect_vt_from_steps(
    df: pd.DataFrame,
    step_range: StepTestRange,
    ve_column: str = "tymeventilation",
    power_column: str = "watts",
    hr_column: str = "hr",
    time_column: str = "time",
    vt1_slope_threshold: float = 0.05,
    vt2_slope_threshold: float = 0.05,
) -> StepVTResult:
    """Detect VT1 and VT2 using recursive window scan."""
    result = StepVTResult()

    if not step_range or not step_range.is_valid or len(step_range.steps) < 2:
        result.notes.append("Insufficient steps for VT detection")
        return result

    if ve_column not in df.columns:
        result.notes.append(f"Missing VE column: {ve_column}")
        return result

    stages = _build_step_stages(df, step_range, ve_column, power_column, hr_column, time_column)

    if not stages:
        result.notes.append("No valid stages generated for analysis")
        return result

    s_idx, s_slope, s_stage, _ = _search_slope_threshold(
        stages, time_column, ve_column, 0, VT1_SLOPE_SPIKE_SKIP
    )
    vt1_start = s_idx if s_stage else 0
    if s_stage:
        result.notes.append(
            f"Skipped spike > {VT1_SLOPE_SPIKE_SKIP} at Step {s_stage['step_number']} (Slope: {s_slope:.4f})"
        )

    v1_idx, v1_slope, v1_stage, v1_start_idx = _search_slope_threshold(
        stages, time_column, ve_column, vt1_start, VT1_SLOPE_THRESHOLD
    )
    if v1_stage and v1_start_idx is not None:
        _apply_vt1_result(result, stages, v1_idx, v1_slope, v1_stage, v1_start_idx)

    v2_start = v1_idx if v1_stage else vt1_start
    v2_idx, v2_slope, v2_stage, v2_start_idx = _search_slope_threshold(
        stages, time_column, ve_column, v2_start, vt2_slope_threshold
    )
    if v2_stage and v2_start_idx is not None:
        if not v1_stage or (v2_stage["avg_power"] > result.vt1_watts):
            _apply_vt2_result(result, stages, v2_slope, v2_stage, v2_start_idx)

    result.step_analysis = _build_step_analysis_records(
        stages, s_stage, v1_stage, result.vt1_step_number, v2_stage, result.vt2_step_number
    )
    return result


def detect_vt_transition_zone(
    df: pd.DataFrame,
    window_duration: int = 60,
    step_size: int = 10,
    ve_column: str = "tymeventilation",
    power_column: str = "watts",
    hr_column: str = "hr",
    time_column: str = "time",
) -> Tuple[Optional[TransitionZone], Optional[TransitionZone]]:
    """Detect VT transition zones using sliding window."""
    if len(df) < window_duration:
        return None, None
    min_time, max_time = df[time_column].min(), df[time_column].max()
    vt1_c, vt2_c = [], []
    Z = 1.96

    for t in range(int(min_time), int(max_time) - window_duration, step_size):
        mask = (df[time_column] >= t) & (df[time_column] < t + window_duration)
        w = df[mask]
        if len(w) < 10:
            continue
        slope, _, err = calculate_slope(w[time_column], w[ve_column])
        l, u = slope - Z * err, slope + Z * err
        if l <= 0.05 <= u and 0.02 <= slope <= 0.08:
            vt1_c.append(
                {
                    "avg_watts": w[power_column].mean(),
                    "avg_hr": w[hr_column].mean() if hr_column in w else None,
                    "std_err": err,
                }
            )
        if l <= 0.15 <= u and 0.10 <= slope <= 0.20:
            vt2_c.append(
                {
                    "avg_watts": w[power_column].mean(),
                    "avg_hr": w[hr_column].mean() if hr_column in w else None,
                    "std_err": err,
                }
            )

    def process_c(c, threshold, err_scale):
        if not c:
            return None
        df_c = pd.DataFrame(c)
        avg_err = df_c["std_err"].mean()
        return TransitionZone(
            range_watts=(df_c["avg_watts"].min(), df_c["avg_watts"].max()),
            range_hr=(df_c["avg_hr"].min(), df_c["avg_hr"].max())
            if "avg_hr" in df_c and df_c["avg_hr"].min()
            else None,
            confidence=max(0.1, min(1.0, 1.0 - (avg_err * err_scale))),
            method=f"Sliding Window (threshold {threshold})",
            description=f"Region where slope CI overlaps {threshold}.",
        )

    return process_c(vt1_c, 0.05, 100), process_c(vt2_c, 0.15, 50)


def run_sensitivity_analysis(
    df: pd.DataFrame, ve_column: str, power_column: str, hr_column: str, time_column: str
) -> SensitivityResult:
    """Check stability by varying window size."""
    wins = [30, 45, 60, 90]
    r1, r2 = [], []
    for w in wins:
        v1, v2 = detect_vt_transition_zone(
            df, w, 5, ve_column, power_column, hr_column, time_column
        )
        if v1:
            r1.append(sum(v1.range_watts) / 2)
        if v2:
            r2.append(sum(v2.range_watts) / 2)

    res = SensitivityResult()

    # Calculate noise level from raw VE data
    ve_noise = 0.0
    if ve_column in df.columns:
        ve_data = df[ve_column].dropna()
        if len(ve_data) > 10:
            # Use rolling std to estimate noise
            rolling_std = ve_data.rolling(window=30, min_periods=5).std().mean()
            ve_noise = rolling_std if not pd.isna(rolling_std) else 0.0

    def analyze(r, name):
        if len(r) >= 2:
            std = np.std(r)
            base_score = max(0.0, min(1.0, 1.0 - (std / 50.0)))
            # Apply noise penalty (only for significant noise > 1.0)
            noise_penalty = min(
                0.3, max(0.0, (ve_noise - 1.0) / 10)
            )  # Max 0.3 penalty, threshold at 1.0
            score = max(0.0, base_score - noise_penalty)
            res.details.append(f"{name} variability: {std:.1f}W")
            return std, score, std > 30.0
        res.details.append(f"{name} not enough data points.")
        return 0.0, 0.5, False

    res.vt1_variability_watts, res.vt1_stability_score, res.is_vt1_unreliable = analyze(r1, "VT1")
    res.vt2_variability_watts, res.vt2_stability_score, res.is_vt2_unreliable = analyze(r2, "VT2")
    return res
