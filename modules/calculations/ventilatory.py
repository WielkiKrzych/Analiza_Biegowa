"""
Ventilatory Threshold Detection (VT1/VT2).
"""

import numpy as np
import pandas as pd
from scipy import stats, signal
from typing import Optional, List, Tuple, Any

from .threshold_types import TransitionZone, SensitivityResult, StepVTResult, StepTestRange
from .common import (
    VT1_SLOPE_THRESHOLD,
    VT2_SLOPE_THRESHOLD,
    VT1_SLOPE_SPIKE_SKIP,
    SLOPE_CONFIDENCE_MAX,
    STABILITY_CONFIDENCE_MAX,
    BASE_CONFIDENCE,
    MAX_CONFIDENCE,
    LOWER_STEP_WEIGHT,
    UPPER_STEP_WEIGHT,
)


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

    has_hr = hr_column in df.columns
    br_column = next(
        (c for c in ["tymebreathrate", "br", "rr", "breath_rate"] if c in df.columns), None
    )

    stages = []
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

    if not stages:
        result.notes.append("No valid stages generated for analysis")
        return result

    def search(start_idx, threshold):
        n = len(stages)
        for i in range(start_idx, n):
            max_w = min(6, n - i)
            for w in range(1, max_w + 1):
                combined = pd.concat([s["data"] for s in stages[i : i + w]])
                if len(combined) < 5:
                    continue
                slope, _, _ = calculate_slope(combined[time_column], combined[ve_column])
                if slope > threshold:
                    return i + w, slope, stages[i + w - 1], i  # Return start index too
        return None, None, None, None

    s_idx, s_slope, s_stage, _ = search(0, VT1_SLOPE_SPIKE_SKIP)
    vt1_start = s_idx if s_stage else 0
    if s_stage:
        result.notes.append(
            f"Skipped spike > {VT1_SLOPE_SPIKE_SKIP} at Step {s_stage['step_number']} (Slope: {s_slope:.4f})"
        )

    # VT1 Detection with RANGE logic
    v1_idx, v1_slope, v1_stage, v1_start_idx = search(vt1_start, VT1_SLOPE_THRESHOLD)
    if v1_stage and v1_start_idx is not None:
        # Calculate RANGE from adjacent steps (not a single point)
        # Lower bound: step before detection, Upper bound: detection step
        lower_step_idx = max(0, v1_start_idx - 1)
        lower_power = (
            stages[lower_step_idx]["avg_power"]
            if lower_step_idx < len(stages)
            else v1_stage["avg_power"]
        )
        upper_power = v1_stage["avg_power"]

        # Central tendency: weighted average (upper gets more weight due to detection there)
        central_power = lower_power * LOWER_STEP_WEIGHT + upper_power * UPPER_STEP_WEIGHT

        # CONFIDENCE based on:
        # 1. Slope sharpness (higher = more confident)
        # 2. Stability (narrow range = more confident)
        # 3. Number of confirming steps
        # 4. Variance penalty (high variance = less confident)
        slope_confidence = min(SLOPE_CONFIDENCE_MAX, v1_slope * 4)
        range_width = upper_power - lower_power
        stability_confidence = max(0.0, STABILITY_CONFIDENCE_MAX - range_width / 100)

        # Calculate variance penalty from step data
        step_ve_values = [s["avg_ve"] for s in stages[v1_start_idx:v1_idx]]
        if len(step_ve_values) > 1:
            ve_variance = np.var(step_ve_values)
            variance_penalty = min(0.5, ve_variance / 20)  # Max 0.5 penalty, stronger effect
        else:
            variance_penalty = 0.0

        total_confidence = min(
            MAX_CONFIDENCE,
            BASE_CONFIDENCE + slope_confidence + stability_confidence - variance_penalty,
        )

        # HR range calculation
        lower_hr = stages[lower_step_idx]["avg_hr"] if stages[lower_step_idx]["avg_hr"] else None
        upper_hr = v1_stage["avg_hr"]
        central_hr = (lower_hr * 0.3 + upper_hr * 0.7) if lower_hr and upper_hr else upper_hr

        # VE range calculation
        lower_ve = stages[lower_step_idx]["avg_ve"]
        upper_ve = v1_stage["avg_ve"]
        central_ve = lower_ve * 0.3 + upper_ve * 0.7

        # Create TransitionZone (PRIMARY OUTPUT)
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

        # Legacy point values (DERIVED from zone, for backward compatibility only)
        result.vt1_watts = round(central_power, 0)
        result.vt1_hr = round(central_hr, 0) if central_hr else None
        result.vt1_ve = round(v1_stage["avg_ve"], 1)
        result.vt1_br = round(v1_stage["avg_br"], 0) if v1_stage["avg_br"] else None
        result.vt1_ve_slope = round(v1_slope, 4)
        result.vt1_step_number = v1_stage["step_number"]

        result.notes.append(
            f"VT1 zone: {lower_power:.0f}–{upper_power:.0f} W "
            f"(central: {central_power:.0f} W, confidence: {total_confidence:.2f})"
        )

    # VT2 Detection with RANGE logic
    v2_start = v1_idx if v1_stage else vt1_start
    v2_idx, v2_slope, v2_stage, v2_start_idx = search(v2_start, vt2_slope_threshold)
    if v2_stage and v2_start_idx is not None:
        if not v1_stage or (v2_stage["avg_power"] > result.vt1_watts):
            # Calculate VT2 RANGE
            lower_step_idx = max(0, v2_start_idx - 1)
            lower_power = (
                stages[lower_step_idx]["avg_power"]
                if lower_step_idx < len(stages)
                else v2_stage["avg_power"]
            )
            upper_power = v2_stage["avg_power"]
            central_power = lower_power * 0.3 + upper_power * 0.7

            # Confidence calculation for VT2
            slope_confidence = min(0.4, v2_slope * 4)
            range_width = upper_power - lower_power
            stability_confidence = max(0.0, 0.4 - range_width / 100)
            base_confidence = 0.2
            total_confidence = min(0.95, base_confidence + slope_confidence + stability_confidence)

            # HR
            lower_hr = (
                stages[lower_step_idx]["avg_hr"] if stages[lower_step_idx]["avg_hr"] else None
            )
            upper_hr = v2_stage["avg_hr"]
            central_hr = (lower_hr * 0.3 + upper_hr * 0.7) if lower_hr and upper_hr else upper_hr

            # VE
            lower_ve = stages[lower_step_idx]["avg_ve"]
            upper_ve = v2_stage["avg_ve"]
            central_ve = lower_ve * 0.3 + upper_ve * 0.7

            # Create TransitionZone (PRIMARY OUTPUT)
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

            # Legacy point values (DERIVED)
            result.vt2_watts = round(central_power, 0)
            result.vt2_hr = round(central_hr, 0) if central_hr else None
            result.vt2_ve = round(v2_stage["avg_ve"], 1)
            result.vt2_br = round(v2_stage["avg_br"], 0) if v2_stage["avg_br"] else None
            result.vt2_ve_slope = round(v2_slope, 4)
            result.vt2_step_number = v2_stage["step_number"]

            result.notes.append(
                f"VT2 zone: {lower_power:.0f}–{upper_power:.0f} W "
                f"(central: {central_power:.0f} W, confidence: {total_confidence:.2f})"
            )

    result.step_analysis = [
        {
            "step_number": s["step_number"],
            "avg_power": s["avg_power"],
            "avg_hr": s["avg_hr"],
            "avg_ve": s["avg_ve"],
            "avg_br": s["avg_br"],
            "ve_slope": s["ve_slope"],
            "start_time": s["start_time"],
            "end_time": s["end_time"],
            "is_skipped": s_stage and s["step_number"] == s_stage["step_number"],
            "is_vt1": v1_stage and s["step_number"] == result.vt1_step_number,
            "is_vt2": v2_stage and s["step_number"] == result.vt2_step_number,
        }
        for s in stages
    ]
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


# =============================================================================
# V-SLOPE METHOD WITH SAVITZKY-GOLAY SMOOTHING
# =============================================================================


def detect_vt_vslope_savgol(
    df: pd.DataFrame,
    step_range: Optional[Any] = None,
    power_column: str = "watts",
    ve_column: str = "tymeventilation",
    time_column: str = "time",
    min_power_watts: Optional[int] = None,
) -> dict:
    """
    DEPRECATED: Use detect_vt_cpet() for CPET-grade detection.
    This wrapper calls the new function for backward compatibility.
    """
    return detect_vt_cpet(
        df, step_range, power_column, ve_column, time_column, min_power_watts=min_power_watts
    )


# =============================================================================
# CPET-GRADE VT DETECTION (V2.0 - Laboratory Standard)
# =============================================================================


def detect_vt_cpet(
    df: pd.DataFrame,
    step_range: Optional[Any] = None,
    power_column: str = "watts",
    ve_column: str = "tymeventilation",
    time_column: str = "time",
    vo2_column: str = "tymevo2",
    vco2_column: str = "tymevco2",
    hr_column: str = "hr",
    step_duration_sec: int = 180,
    smoothing_window_sec: int = 25,
    min_power_watts: Optional[int] = None,
) -> dict:
    """
    CPET-Grade VT1/VT2 Detection using Ventilatory Equivalents.

    Algorithm:
    1. Preprocessing: Smooth signals with rolling window, remove artifacts
    2. Calculate VE/VO2, VE/VCO2, RER for each step (steady-state)
    3. VT1: Segmented regression on VE/VO2 - find first breakpoint
       - VE/VO2 slope increases while VE/VCO2 remains flat
    4. VT2: Segmented regression on VE/VCO2 - find breakpoint
       - VE/VCO2 transitions from flat to rising, RER ≈ 1.0
    5. Physiological validation: VT1 < VT2 < max power

    Args:
        df: DataFrame with test data (1Hz or breath-by-breath)
        step_range: Optional detected step ranges
        power_column: Power column name [W]
        ve_column: Ventilation column name [L/min or L/s]
        time_column: Time column name [s]
        vo2_column: VO2 column name [L/min or ml/min]
        vco2_column: VCO2 column name [L/min or ml/min]
        hr_column: Heart rate column name [bpm]
        step_duration_sec: Expected step duration (default 180s = 3min)
        smoothing_window_sec: Smoothing window size (default 25s)
        min_power_watts: Manual override - minimum power to start VT search (skip warmup)

    Returns:
        dict with vt1_watts, vt2_watts, charts data, analysis notes
    """
    from scipy.signal import savgol_filter
    from scipy.optimize import minimize

    # Initialize result
    result = {
        "vt1_watts": None,
        "vt2_watts": None,
        "vt1_hr": None,
        "vt2_hr": None,
        "vt1_ve": None,
        "vt2_ve": None,
        "vt1_br": None,
        "vt2_br": None,  # Breathing rate
        "vt1_vo2": None,
        "vt2_vo2": None,
        "vt1_step": None,
        "vt2_step": None,
        "vt1_pct_vo2max": None,
        "vt2_pct_vo2max": None,
        "df_steps": None,
        "method": "cpet_segmented_regression",
        "has_gas_exchange": False,
        "analysis_notes": [],
        "validation": {"vt1_lt_vt2": False, "ve_vo2_rises_first": False},
        "ramp_start_step": None,  # First actual ramp step (after warmup)
    }

    # =========================================================================
    # 1. DATA PREPARATION
    # =========================================================================
    data = df.copy()
    data.columns = data.columns.str.lower().str.strip()

    # Normalize column names
    cols = {
        "power": power_column.lower(),
        "ve": ve_column.lower(),
        "time": time_column.lower(),
        "vo2": vo2_column.lower(),
        "vco2": vco2_column.lower(),
        "hr": hr_column.lower(),
    }

    # Check required columns
    if cols["power"] not in data.columns:
        result["error"] = f"Missing {power_column}"
        return result
    if cols["ve"] not in data.columns:
        result["error"] = f"Missing {ve_column}"
        return result

    # Check for gas exchange data
    has_vo2 = cols["vo2"] in data.columns and data[cols["vo2"]].notna().sum() > 10
    has_vco2 = cols["vco2"] in data.columns and data[cols["vco2"]].notna().sum() > 10
    has_hr = cols["hr"] in data.columns and data[cols["hr"]].notna().sum() > 10
    result["has_gas_exchange"] = has_vo2 and has_vco2

    # =========================================================================
    # 2. UNIT NORMALIZATION
    # =========================================================================
    # VE: L/s → L/min
    if data[cols["ve"]].mean() < 10:
        data["ve_lmin"] = data[cols["ve"]] * 60
    else:
        data["ve_lmin"] = data[cols["ve"]]

    # VO2/VCO2: ml/min → L/min (if > 100, assume ml/min)
    if has_vo2:
        if data[cols["vo2"]].mean() > 100:
            data["vo2_lmin"] = data[cols["vo2"]] / 1000
        else:
            data["vo2_lmin"] = data[cols["vo2"]]

    if has_vco2:
        if data[cols["vco2"]].mean() > 100:
            data["vco2_lmin"] = data[cols["vco2"]] / 1000
        else:
            data["vco2_lmin"] = data[cols["vco2"]]

    # =========================================================================
    # 3. SMOOTHING (Artifact Removal)
    # =========================================================================
    window = min(smoothing_window_sec, len(data) // 4)
    if window < 3:
        window = 3

    data["ve_smooth"] = data["ve_lmin"].rolling(window, center=True, min_periods=1).mean()

    if has_vo2:
        data["vo2_smooth"] = data["vo2_lmin"].rolling(window, center=True, min_periods=1).mean()
    if has_vco2:
        data["vco2_smooth"] = data["vco2_lmin"].rolling(window, center=True, min_periods=1).mean()

    # Artifact detection: Remove spikes in VE without matching VO2/VCO2 change
    if has_vo2 and has_vco2:
        ve_diff = data["ve_smooth"].diff().abs()
        vo2_diff = data["vo2_smooth"].diff().abs()
        vco2_diff = data["vco2_smooth"].diff().abs()

        # Spike = VE changes > 3σ but VO2/VCO2 change < 1σ
        ve_threshold = ve_diff.std() * 3
        gas_threshold = max(vo2_diff.std(), vco2_diff.std())

        artifact_mask = (ve_diff > ve_threshold) & (
            (vo2_diff < gas_threshold) & (vco2_diff < gas_threshold)
        )
        artifact_count = artifact_mask.sum()
        if artifact_count > 0:
            result["analysis_notes"].append(f"Removed {artifact_count} respiratory artifacts")
            data.loc[artifact_mask, "ve_smooth"] = np.nan
            data["ve_smooth"] = data["ve_smooth"].interpolate(method="linear")

    # =========================================================================
    # 4. STEP AGGREGATION (Steady-State from last 60-90s)
    # =========================================================================
    step_data = []

    # Check if we have breathing rate column
    br_col = None
    for col in ["tymebreathrate", "br", "resprate", "breathing_rate", "rf", "rr"]:
        if col in data.columns:
            br_col = col
            break
    has_br = br_col is not None

    if step_range and hasattr(step_range, "steps") and step_range.steps:
        # Use detected steps
        for i, step in enumerate(step_range.steps):
            mask = (data[cols["time"]] >= step.start_time) & (data[cols["time"]] <= step.end_time)
            step_df = data[mask]

            if len(step_df) < 30:  # Need at least 30 samples
                continue

            # Steady-state: last 60-90s or last 50% of step
            step_duration = step.end_time - step.start_time
            ss_start_ratio = max(0.5, 1 - (90 / step_duration)) if step_duration > 90 else 0.5
            cutoff = int(len(step_df) * ss_start_ratio)
            ss_df = step_df.iloc[cutoff:]

            row = {
                "step": i + 1,
                "power": step.avg_power,
                "ve": ss_df["ve_smooth"].mean(),
                "time": step.start_time,
                "duration": step_duration,
            }

            if has_vo2:
                row["vo2"] = ss_df["vo2_smooth"].mean()
            if has_vco2:
                row["vco2"] = ss_df["vco2_smooth"].mean()
            if has_hr and cols["hr"] in ss_df.columns:
                row["hr"] = ss_df[cols["hr"]].mean()
            if br_col and br_col in ss_df.columns:
                row["br"] = ss_df[br_col].mean()

            step_data.append(row)
    else:
        # Auto-detect steps by power grouping with 20W bins (better for 20-30W protocol)
        data["power_bin"] = (data[cols["power"]] // 20) * 20  # 20W bins for 20-30W increments

        raw_steps = []
        for power_bin, group in data.groupby("power_bin"):
            if len(group) < 30:  # Skip very short segments
                continue

            # Calculate duration in seconds
            if cols["time"] in group.columns:
                duration = group[cols["time"]].max() - group[cols["time"]].min()
            else:
                duration = len(group)  # Assume 1Hz data

            # Steady-state averaging:
            # 1. Skip first 30s (kinetics phase - VO2 slow component settling)
            # 2. Use EXACTLY last 60s for steady-state analysis
            if cols["time"] in group.columns:
                step_start_time = group[cols["time"]].min()
                step_end_time = group[cols["time"]].max()

                # Skip first 30s kinetics
                kinetics_cutoff = step_start_time + 30
                steady_group = group[group[cols["time"]] >= kinetics_cutoff]

                # Use last 60s of remaining data
                if len(steady_group) > 0:
                    ss_start_time = step_end_time - 60
                    ss_df = steady_group[steady_group[cols["time"]] >= ss_start_time]
                else:
                    ss_df = group.iloc[-60:]  # Fallback
            else:
                # Fallback for data without time: skip first 30 samples, use last 60
                if len(group) > 90:
                    ss_df = group.iloc[-60:]
                else:
                    ss_df = group.iloc[30:] if len(group) > 30 else group

            row = {
                "power": power_bin,
                "ve": ss_df["ve_smooth"].mean(),
                "time": group[cols["time"]].iloc[0] if cols["time"] in group.columns else 0,
                "duration": duration,
            }

            if has_vo2:
                row["vo2"] = ss_df["vo2_smooth"].mean()
            if has_vco2:
                row["vco2"] = ss_df["vco2_smooth"].mean()
            if has_hr and cols["hr"] in ss_df.columns:
                row["hr"] = ss_df[cols["hr"]].mean()
            if br_col and br_col in ss_df.columns:
                row["br"] = ss_df[br_col].mean()

            raw_steps.append(row)

        # Sort by power
        raw_steps = sorted(raw_steps, key=lambda x: x["power"])

        # =====================================================================
        # RAMP TEST DETECTION: Find where actual protocol begins
        # Priority: 1) Manual min_power_watts, 2) Auto-detect consecutive steps
        # =====================================================================
        ramp_start_idx = 0

        # Option 1: Manual override - filter by minimum power
        if min_power_watts is not None and min_power_watts > 0:
            for i, step in enumerate(raw_steps):
                if step["power"] >= min_power_watts:
                    ramp_start_idx = i
                    result["ramp_start_step"] = i + 1
                    result["analysis_notes"].append(
                        f"Manual override: Starting analysis from {int(min_power_watts)}W (step {i + 1})"
                    )
                    break
        else:
            # Option 2: Auto-detect - look for consecutive 3-min steps with +20-30W increments
            min_step_duration = 120  # At least 2 minutes
            power_increment_range = (15, 40)  # Accept 15-40W increments

            for i in range(len(raw_steps) - 2):
                step1 = raw_steps[i]
                step2 = raw_steps[i + 1]
                step3 = raw_steps[i + 2]

                # Check if all 3 steps are at least ~3 minutes
                dur_ok = all(s["duration"] >= min_step_duration for s in [step1, step2, step3])

                # Check power increments are in expected range
                inc1 = step2["power"] - step1["power"]
                inc2 = step3["power"] - step2["power"]
                inc_ok = (
                    power_increment_range[0] <= inc1 <= power_increment_range[1]
                    and power_increment_range[0] <= inc2 <= power_increment_range[1]
                )

                if dur_ok and inc_ok:
                    ramp_start_idx = i
                    result["ramp_start_step"] = i + 1
                    result["analysis_notes"].append(
                        f"Ramp test detected starting at step {i + 1} ({int(step1['power'])}W)"
                    )
                    break

        # Use only steps from ramp start onwards
        if ramp_start_idx > 0:
            result["analysis_notes"].append(f"Skipping first {ramp_start_idx} warmup steps")

        # Filter to ramp test steps only and renumber
        for i, step in enumerate(raw_steps[ramp_start_idx:]):
            step["step"] = i + 1
            step_data.append(step)

    if len(step_data) < 5:
        result["error"] = f"Insufficient steps ({len(step_data)}). Need at least 5."
        result["analysis_notes"].append("Not enough steps for reliable analysis")
        return result

    df_steps = pd.DataFrame(step_data).sort_values("power").reset_index(drop=True)
    result["df_steps"] = df_steps

    # =========================================================================
    # 5. CALCULATE VENTILATORY EQUIVALENTS
    # =========================================================================
    if has_vo2 and has_vco2:
        # CPET Mode: Full analysis with VE/VO2 and VE/VCO2
        df_steps["ve_vo2"] = df_steps["ve"] / df_steps["vo2"].replace(0, np.nan)
        df_steps["ve_vco2"] = df_steps["ve"] / df_steps["vco2"].replace(0, np.nan)
        df_steps["rer"] = df_steps["vco2"] / df_steps["vo2"].replace(0, np.nan)

        result["analysis_notes"].append("Using CPET mode: VE/VO2 and VE/VCO2 analysis")

        # Calculate VO2max for %VO2max
        vo2max = df_steps["vo2"].max()

        # -----------------------------------------------------------------
        # VT1 DETECTION: Segmented regression on VE/VO2
        # -----------------------------------------------------------------
        vt1_idx = _find_breakpoint_segmented(
            df_steps["power"].values, df_steps["ve_vo2"].values, min_segment_size=3
        )

        if vt1_idx is not None and 1 < vt1_idx < len(df_steps) - 1:
            # Validate: VE/VCO2 should be relatively flat at VT1
            vco2_slope_before = _calculate_segment_slope(
                df_steps["power"].values[:vt1_idx], df_steps["ve_vco2"].values[:vt1_idx]
            )
            vco2_slope_at = _calculate_segment_slope(
                df_steps["power"].values[max(0, vt1_idx - 2) : vt1_idx + 2],
                df_steps["ve_vco2"].values[max(0, vt1_idx - 2) : vt1_idx + 2],
            )

            # VE/VCO2 should not be rising significantly at VT1
            if abs(vco2_slope_at) < 0.1 or vco2_slope_at < vco2_slope_before * 1.5:
                result["vt1_watts"] = int(df_steps.loc[vt1_idx, "power"])
                result["vt1_ve"] = round(df_steps.loc[vt1_idx, "ve"], 1)
                result["vt1_vo2"] = round(df_steps.loc[vt1_idx, "vo2"], 2)
                result["vt1_step"] = int(df_steps.loc[vt1_idx, "step"])
                result["vt1_pct_vo2max"] = (
                    round(df_steps.loc[vt1_idx, "vo2"] / vo2max * 100, 1) if vo2max > 0 else None
                )
                if "hr" in df_steps.columns and pd.notna(df_steps.loc[vt1_idx, "hr"]):
                    result["vt1_hr"] = int(df_steps.loc[vt1_idx, "hr"])
                if "br" in df_steps.columns and pd.notna(df_steps.loc[vt1_idx, "br"]):
                    result["vt1_br"] = int(df_steps.loc[vt1_idx, "br"])
                result["analysis_notes"].append(
                    f"VT1 detected at step {result['vt1_step']} via VE/VO2 breakpoint"
                )
            else:
                result["analysis_notes"].append("VT1 candidate rejected: VE/VCO2 already rising")

        # -----------------------------------------------------------------
        # VT2 DETECTION: Segmented regression on VE/VCO2 + RER validation
        # -----------------------------------------------------------------
        search_start = vt1_idx + 1 if vt1_idx else 3

        # Guard: ensure search_start is within bounds
        if search_start >= len(df_steps) - 4:
            search_start = max(3, len(df_steps) // 2)

        # Only search if we have enough data points remaining
        remaining_points = len(df_steps) - search_start
        if remaining_points >= 4:
            vt2_idx = _find_breakpoint_segmented(
                df_steps["power"].values[search_start:],
                df_steps["ve_vco2"].values[search_start:],
                min_segment_size=2,
            )

            if vt2_idx is not None:
                vt2_idx += search_start  # Adjust for subset

                if vt2_idx < len(df_steps):
                    # Validate: RER should be near 1.0
                    rer_at_vt2 = df_steps.loc[vt2_idx, "rer"]

                    if pd.notna(rer_at_vt2) and 0.95 <= rer_at_vt2 <= 1.15:
                        result["vt2_watts"] = int(df_steps.loc[vt2_idx, "power"])
                        result["vt2_ve"] = round(df_steps.loc[vt2_idx, "ve"], 1)
                        result["vt2_vo2"] = (
                            round(df_steps.loc[vt2_idx, "vo2"], 2)
                            if "vo2" in df_steps.columns
                            else None
                        )
                        result["vt2_step"] = int(df_steps.loc[vt2_idx, "step"])
                        result["vt2_pct_vo2max"] = (
                            round(df_steps.loc[vt2_idx, "vo2"] / vo2max * 100, 1)
                            if vo2max > 0 and "vo2" in df_steps.columns
                            else None
                        )
                        if "hr" in df_steps.columns and pd.notna(df_steps.loc[vt2_idx, "hr"]):
                            result["vt2_hr"] = int(df_steps.loc[vt2_idx, "hr"])
                        if "br" in df_steps.columns and pd.notna(df_steps.loc[vt2_idx, "br"]):
                            result["vt2_br"] = int(df_steps.loc[vt2_idx, "br"])
                        result["analysis_notes"].append(
                            f"VT2 detected at step {result['vt2_step']} (RER={rer_at_vt2:.2f})"
                        )
                    else:
                        # Accept but note RER discrepancy
                        result["vt2_watts"] = int(df_steps.loc[vt2_idx, "power"])
                        result["vt2_ve"] = round(df_steps.loc[vt2_idx, "ve"], 1)
                        result["vt2_step"] = int(df_steps.loc[vt2_idx, "step"])
                        if "hr" in df_steps.columns and pd.notna(df_steps.loc[vt2_idx, "hr"]):
                            result["vt2_hr"] = int(df_steps.loc[vt2_idx, "hr"])
                        if "br" in df_steps.columns and pd.notna(df_steps.loc[vt2_idx, "br"]):
                            result["vt2_br"] = int(df_steps.loc[vt2_idx, "br"])
                        rer_str = f"{rer_at_vt2:.2f}" if pd.notna(rer_at_vt2) else "N/A"
                        result["analysis_notes"].append(
                            f"VT2 detected but RER={rer_str} (expected ~1.0)"
                        )

    else:
        # =========================================================================
        # VE-ONLY MODE: 4-POINT CPET DETECTION
        # =========================================================================
        # Clinical CPET algorithm for TymeWear data (VE, BR, VT, Power, HR)
        # Detects: VT1_onset, VT1_steady, RCP_onset, RCP_steady
        # Builds: 4 metabolic domains (Pure Aerobic, Upper Aerobic, Heavy, Severe)

        result["analysis_notes"].append("VE-only mode: 4-point CPET detection")
        result["method"] = "ve_only_4point_cpet"

        # =====================================================================
        # 1. PREPROCESSING
        # =====================================================================

        # Savitzky-Golay smoothing for VE
        try:
            window = min(5, len(df_steps) if len(df_steps) % 2 == 1 else len(df_steps) - 1)
            if window < 3:
                window = 3
            df_steps["ve_smooth"] = savgol_filter(
                df_steps["ve"].values, window_length=window, polyorder=2
            )
        except:
            df_steps["ve_smooth"] = df_steps["ve"].rolling(3, center=True, min_periods=1).mean()

        # Check data availability
        has_hr = "hr" in df_steps.columns and df_steps["hr"].notna().sum() > 3
        has_br = "br" in df_steps.columns and df_steps["br"].notna().sum() > 3

        # Smooth BR if available
        if has_br:
            df_steps["br_smooth"] = df_steps["br"].rolling(3, center=True, min_periods=1).mean()
            # Tidal Volume = VE / BR
            df_steps["vt_calc"] = df_steps["ve_smooth"] / df_steps["br_smooth"].replace(0, np.nan)
            df_steps["vt_smooth"] = (
                df_steps["vt_calc"].rolling(3, center=True, min_periods=1).mean()
            )

        # =====================================================================
        # 2. CALCULATE DERIVATIVES
        # =====================================================================

        # VE derivatives
        ve_slope = np.gradient(df_steps["ve_smooth"].values, df_steps["power"].values)
        df_steps["ve_slope"] = ve_slope

        ve_accel = np.gradient(ve_slope, df_steps["power"].values)
        df_steps["ve_accel"] = ve_accel
        df_steps["ve_accel_smooth"] = (
            df_steps["ve_accel"].rolling(3, center=True, min_periods=1).mean()
        )

        # BR derivatives (if available)
        if has_br:
            br_slope = np.gradient(df_steps["br_smooth"].values, df_steps["power"].values)
            df_steps["br_slope"] = br_slope
            df_steps["br_slope_smooth"] = (
                df_steps["br_slope"].rolling(3, center=True, min_periods=1).mean()
            )

            # VT (tidal volume) derivatives
            vt_slope = np.gradient(
                df_steps["vt_smooth"].fillna(method="ffill").values, df_steps["power"].values
            )
            df_steps["vt_slope"] = vt_slope
            df_steps["vt_slope_smooth"] = (
                df_steps["vt_slope"].rolling(3, center=True, min_periods=1).mean()
            )

        # HR derivatives (if available)
        if has_hr:
            hr_slope = np.gradient(df_steps["hr"].values, df_steps["power"].values)
            df_steps["hr_slope"] = hr_slope
            baseline_hr_slope = np.mean(hr_slope[: min(4, len(hr_slope))])
            if baseline_hr_slope > 0:
                df_steps["hr_drift"] = hr_slope / baseline_hr_slope
            else:
                df_steps["hr_drift"] = np.ones(len(hr_slope))

        # =====================================================================
        # 3. DETECT 4 PHYSIOLOGICAL POINTS
        # =====================================================================

        baseline_ve_slope = np.mean(df_steps["ve_slope"].iloc[: min(4, len(df_steps))])
        baseline_ve_accel = np.mean(df_steps["ve_accel_smooth"].iloc[: min(4, len(df_steps))])
        baseline_br_slope = 0
        if has_br:
            baseline_br_slope = np.mean(df_steps["br_slope_smooth"].iloc[: min(4, len(df_steps))])

        vt1_onset_idx = None
        vt1_steady_idx = None
        rcp_onset_idx = None
        rcp_steady_idx = None

        # ---------------------------------------------------------------------
        # A. VT1_ONSET (GET / LT1 Onset)
        # First point where:
        # - d²VE/dP² changes sign (start of nonlinearity)
        # - VE gradient starts rising persistently
        # - BR not accelerating sharply yet
        # ---------------------------------------------------------------------

        for i in range(3, len(df_steps) - 4):
            # Check d²VE/dP² sign change (goes positive)
            accel_prev = df_steps["ve_accel_smooth"].iloc[i - 1]
            accel_curr = df_steps["ve_accel_smooth"].iloc[i]
            sign_change = (accel_prev <= 0 and accel_curr > 0) or (
                accel_curr > baseline_ve_accel * 2
            )

            # VE slope increasing persistently (2 steps)
            slope_rising = (
                df_steps["ve_slope"].iloc[i] > baseline_ve_slope * 1.15
                and df_steps["ve_slope"].iloc[i + 1] > baseline_ve_slope * 1.10
            )

            # BR not spiking yet (if available)
            br_not_spiking = True
            if has_br and baseline_br_slope > 0:
                br_not_spiking = df_steps["br_slope_smooth"].iloc[i] < baseline_br_slope * 2.0

            if (sign_change or slope_rising) and br_not_spiking:
                # Verify persistence (2 more steps)
                if df_steps["ve_slope"].iloc[i + 2] > baseline_ve_slope * 1.05:
                    vt1_onset_idx = i
                    break

        # ---------------------------------------------------------------------
        # B. VT1_STEADY (LT1 Steady / Upper Aerobic Ceiling)
        # STRICT PLATEAU CONDITIONS - only detect if physiologically present
        #
        # Conditions for REAL VT1_steady:
        # 1. After VT1_onset, at least 2 consecutive steps where:
        #    - dVE/dP is significantly higher than pre-VT1_onset baseline
        #    - dVE/dP is STABLE (|Δgradient| < 10-15%)
        #    - No sharp BR increase (no respiratory compensation signs)
        #    - No exponential VE acceleration
        #
        # If conditions NOT met → VT1_steady_virtual (interpolated)
        # ---------------------------------------------------------------------

        vt1_steady_is_real = False  # Flag to track if plateau exists

        if vt1_onset_idx is not None:
            # Get VE slope at VT1_onset as reference
            vt1_onset_slope = df_steps["ve_slope"].iloc[vt1_onset_idx]

            # Search for plateau starting at least 2 steps after onset
            for i in range(vt1_onset_idx + 2, len(df_steps) - 3):
                curr_slope = df_steps["ve_slope"].iloc[i]
                next_slope = df_steps["ve_slope"].iloc[i + 1]
                next2_slope = df_steps["ve_slope"].iloc[i + 2]

                # Condition 1: Slope significantly higher than baseline
                elevated = curr_slope > baseline_ve_slope * 1.15

                # Condition 2: Slope is STABLE across 2+ steps (within 10-15%)
                delta_1 = abs(next_slope - curr_slope) / max(abs(curr_slope), 0.01)
                delta_2 = abs(next2_slope - curr_slope) / max(abs(curr_slope), 0.01)
                slope_stable = delta_1 < 0.12 and delta_2 < 0.15

                # Condition 3: No sharp BR acceleration (no RC signs)
                br_ok = True
                if has_br and baseline_br_slope > 0:
                    br_at_i = df_steps["br_slope_smooth"].iloc[i]
                    br_ok = br_at_i < baseline_br_slope * 1.5  # Stricter than before

                # Condition 4: No exponential VE acceleration
                ve_accel_at_i = df_steps["ve_accel_smooth"].iloc[i]
                no_exponential = ve_accel_at_i < baseline_ve_accel * 2.5

                # All conditions must be met
                if elevated and slope_stable and br_ok and no_exponential:
                    vt1_steady_idx = i
                    vt1_steady_is_real = True
                    break

        result["vt1_steady_is_real"] = vt1_steady_is_real

        # ---------------------------------------------------------------------
        # C. RCP_ONSET (VT2 / LT2 Onset - Respiratory Compensation Point)
        # Point where simultaneously:
        # - d²VE/dP² reaches local maximum
        # - BR slope spikes sharply
        # - VT (tidal volume) slope starts flattening (plateau)
        # ---------------------------------------------------------------------

        search_start = (
            vt1_steady_idx if vt1_steady_idx else (vt1_onset_idx + 2 if vt1_onset_idx else 4)
        )

        if search_start and search_start < len(df_steps) - 3:
            search_df = df_steps.iloc[search_start:]

            if len(search_df) >= 3:
                # Find max VE acceleration
                max_accel_idx = search_df["ve_accel_smooth"].idxmax()
                max_accel_val = df_steps.loc[max_accel_idx, "ve_accel_smooth"]

                # Check BR spike and VT plateau
                rcp_candidates = []

                for idx in search_df.index:
                    ve_accel_high = df_steps.loc[idx, "ve_accel_smooth"] > max_accel_val * 0.6

                    br_spike = True
                    vt_plateau = True

                    if has_br:
                        br_slope_val = df_steps.loc[idx, "br_slope_smooth"]
                        br_spike = (
                            br_slope_val > baseline_br_slope * 2.0
                            if baseline_br_slope > 0
                            else br_slope_val > 0.1
                        )

                        # VT flattening
                        vt_slope_val = abs(df_steps.loc[idx, "vt_slope_smooth"])
                        baseline_vt_slope = abs(
                            np.mean(df_steps["vt_slope_smooth"].iloc[: min(4, len(df_steps))])
                        )
                        vt_plateau = (
                            vt_slope_val < baseline_vt_slope * 0.7
                            if baseline_vt_slope > 0
                            else True
                        )

                    if ve_accel_high and br_spike and vt_plateau:
                        rcp_candidates.append((idx, df_steps.loc[idx, "ve_accel_smooth"]))

                if rcp_candidates:
                    # Take the one with highest acceleration
                    rcp_onset_idx = max(rcp_candidates, key=lambda x: x[1])[0]
                else:
                    # Fallback: just use max acceleration
                    rcp_onset_idx = max_accel_idx

        # ---------------------------------------------------------------------
        # D. RCP_STEADY (Full RCP / Severe Domain Entry)
        # Point where:
        # - VE grows exponentially (acceleration stays high)
        # - BR dominates over VT as main VE driver
        # - HR shows strong drift
        # ---------------------------------------------------------------------

        if rcp_onset_idx is not None:
            rcp_onset_loc = df_steps.index.get_loc(rcp_onset_idx)

            for i in range(rcp_onset_loc + 1, len(df_steps) - 1):
                idx = df_steps.index[i]

                # VE still accelerating (exponential growth)
                ve_accel_high = df_steps.loc[idx, "ve_accel_smooth"] > baseline_ve_accel * 3

                # BR dominates VT
                br_dominates = True
                if has_br:
                    br_slope_val = df_steps.loc[idx, "br_slope_smooth"]
                    vt_slope_val = df_steps.loc[idx, "vt_slope_smooth"]
                    # BR/VT ratio: BR contribution > VT contribution
                    br_dominates = (
                        abs(br_slope_val) > abs(vt_slope_val) * 1.5 if vt_slope_val != 0 else True
                    )

                # HR strong drift
                hr_drift_strong = True
                if has_hr:
                    hr_drift_strong = df_steps.loc[idx, "hr_drift"] > 1.5

                if ve_accel_high and br_dominates and hr_drift_strong:
                    rcp_steady_idx = idx
                    break

            # Fallback: if not found, estimate 10-15W above RCP_onset
            if rcp_steady_idx is None and rcp_onset_loc + 1 < len(df_steps):
                rcp_steady_idx = df_steps.index[min(rcp_onset_loc + 1, len(df_steps) - 1)]

        # =====================================================================
        # 4. STORE RESULTS
        # =====================================================================

        def get_point_data(idx, point_name):
            """Extract all metrics for a detection point."""
            if idx is None:
                return None
            row = (
                df_steps.loc[idx]
                if isinstance(idx, (int, np.integer)) and idx in df_steps.index
                else df_steps.iloc[idx]
            )
            data = {
                "watts": int(row["power"]),
                "ve": round(row["ve"], 1),
                "step": int(row["step"]),
                "time": row.get("time", 0),
            }
            if "hr" in row and pd.notna(row["hr"]):
                data["hr"] = int(row["hr"])
            if "br" in row and pd.notna(row["br"]):
                data["br"] = int(row["br"])
            if "vt_smooth" in row and pd.notna(row["vt_smooth"]):
                data["vt"] = round(row["vt_smooth"], 2)
            return data

        # VT1 Onset
        if vt1_onset_idx is not None:
            pt = get_point_data(vt1_onset_idx, "vt1_onset")
            result["vt1_onset_watts"] = pt["watts"]
            result["vt1_watts"] = pt["watts"]  # Legacy compatibility
            result["vt1_ve"] = pt["ve"]
            result["vt1_step"] = pt["step"]
            result["vt1_hr"] = pt.get("hr")
            result["vt1_br"] = pt.get("br")
            result["vt1_vt"] = pt.get("vt")
            result["vt1_onset_time"] = pt.get("time")
            result["analysis_notes"].append(
                f"VT1_onset (GET/LT1): {pt['watts']}W @ step {pt['step']}"
            )

        # VT1 Steady (or Virtual if no plateau)
        if vt1_steady_idx is not None and result.get("vt1_steady_is_real", False):
            # REAL VT1_steady detected
            pt = get_point_data(vt1_steady_idx, "vt1_steady")
            result["vt1_steady_watts"] = pt["watts"]
            result["vt1_steady_ve"] = pt["ve"]
            result["vt1_steady_hr"] = pt.get("hr")
            result["vt1_steady_br"] = pt.get("br")
            result["vt1_steady_vt"] = pt.get("vt")
            result["vt1_steady_time"] = pt.get("time")
            result["vt1_steady_is_interpolated"] = False
            result["analysis_notes"].append(
                f"VT1_steady (LT1 steady): {pt['watts']}W @ step {pt['step']} ✓plateau"
            )
        elif result.get("vt1_onset_watts") and result.get("rcp_onset_watts"):
            # NO REAL PLATEAU - create VIRTUAL interpolated point
            vt1_onset_w = result["vt1_onset_watts"]
            rcp_onset_w = result["rcp_onset_watts"]

            # Interpolate: midpoint between VT1_onset and RCP_onset
            vt1_steady_virtual_w = int((vt1_onset_w + rcp_onset_w) / 2)

            # Get metrics at this power level
            virtual_mask = (df_steps["power"] >= vt1_steady_virtual_w - 15) & (
                df_steps["power"] <= vt1_steady_virtual_w + 15
            )
            if virtual_mask.any():
                closest_idx = (
                    df_steps.loc[virtual_mask, "power"].sub(vt1_steady_virtual_w).abs().idxmin()
                )
                pt = get_point_data(closest_idx, "vt1_steady_virtual")
                result["vt1_steady_watts"] = pt["watts"]
                result["vt1_steady_ve"] = pt["ve"]
                result["vt1_steady_hr"] = pt.get("hr")
                result["vt1_steady_br"] = pt.get("br")
                result["vt1_steady_time"] = pt.get("time")
            else:
                result["vt1_steady_watts"] = vt1_steady_virtual_w

            result["vt1_steady_is_interpolated"] = True
            result["analysis_notes"].append(
                f"VT1_steady (interpolated): {result['vt1_steady_watts']}W - no physiological plateau detected"
            )

            # Add physiological interpretation
            result["no_steady_state_interpretation"] = (
                "Pomiędzy VT1_onset a RCP_onset nie występuje stabilny stan ustalony wentylacji. "
                "Krzywa VE wykazuje ciągłe przyspieszanie, co wskazuje na: "
                "wąską strefę przejściową, szybkie narastanie buforowania H⁺, "
                "wczesne wejście w domenę heavy. "
                "Profil typowy dla sportowca o wysokiej pojemności tlenowej i stromym przejściu do kompensacji oddechowej."
            )

        # RCP Onset (VT2)
        if rcp_onset_idx is not None:
            pt = get_point_data(rcp_onset_idx, "rcp_onset")
            result["rcp_onset_watts"] = pt["watts"]
            result["vt2_watts"] = pt["watts"]  # Legacy compatibility
            result["vt2_ve"] = pt["ve"]
            result["vt2_step"] = pt["step"]
            result["vt2_hr"] = pt.get("hr")
            result["vt2_br"] = pt.get("br")
            result["rcp_onset_vt"] = pt.get("vt")
            result["rcp_onset_time"] = pt.get("time")
            result["analysis_notes"].append(
                f"RCP_onset (VT2/LT2): {pt['watts']}W @ step {pt['step']}"
            )

        # RCP Steady
        if rcp_steady_idx is not None:
            pt = get_point_data(rcp_steady_idx, "rcp_steady")
            result["rcp_steady_watts"] = pt["watts"]
            result["rcp_steady_ve"] = pt["ve"]
            result["rcp_steady_hr"] = pt.get("hr")
            result["rcp_steady_br"] = pt.get("br")
            result["rcp_steady_vt"] = pt.get("vt")
            result["rcp_steady_time"] = pt.get("time")
            result["analysis_notes"].append(f"RCP_steady (Full RCP): {pt['watts']}W")

        # =====================================================================
        # 5. BUILD METABOLIC ZONES
        # =====================================================================

        max_power = int(df_steps["power"].max())

        # =====================================================================
        # 5. BUILD METABOLIC ZONES (ALWAYS 4 ZONES)
        # =====================================================================

        # Get boundary values (use virtual if real not available)
        vt1_onset_w = result.get("vt1_onset_watts")
        vt1_steady_w = result.get("vt1_steady_watts")
        rcp_onset_w = result.get("rcp_onset_watts") or result.get("vt2_watts")
        rcp_steady_w = result.get("rcp_steady_watts")
        is_vt1_steady_interpolated = result.get("vt1_steady_is_interpolated", False)

        # Fallback: if VT1_onset missing, use 60th percentile
        if vt1_onset_w is None:
            vt1_onset_w = int(np.percentile(df_steps["power"].values, 60))
            result["vt1_onset_watts"] = vt1_onset_w
            result["vt1_watts"] = vt1_onset_w
            result["analysis_notes"].append(
                f"⚠️ VT1_onset nie wykryty - szacunek 60 percentyl ({vt1_onset_w}W)"
            )

        # Fallback: if RCP_onset missing, use 80th percentile
        if rcp_onset_w is None:
            rcp_onset_w = int(np.percentile(df_steps["power"].values, 80))
            result["rcp_onset_watts"] = rcp_onset_w
            result["vt2_watts"] = rcp_onset_w
            result["analysis_notes"].append(
                f"⚠️ RCP_onset nie wykryty - szacunek 80 percentyl ({rcp_onset_w}W)"
            )

        # CRITICAL: If VT1_steady still None, create virtual interpolation
        if vt1_steady_w is None:
            vt1_steady_w = int((vt1_onset_w + rcp_onset_w) / 2)
            result["vt1_steady_watts"] = vt1_steady_w
            result["vt1_steady_is_interpolated"] = True
            is_vt1_steady_interpolated = True
            result["analysis_notes"].append(
                f"⚠️ VT1_steady interpolowany: {vt1_steady_w}W = (VT1_onset + RCP_onset) / 2"
            )
            # Add diagnostic interpretation
            result["no_steady_state_interpretation"] = (
                "Nie wykryto stabilnego LT1 steady-state pomiędzy VT1_onset a RCP_onset. "
                "Wentylacja wykazuje ciągłe przyspieszanie, co wskazuje na wąską strefę przejściową "
                "i szybkie wejście w domenę heavy. "
                "Zastosowano interpolowany VT1_steady jako punkt referencyjny dla stref treningowych."
            )

        # RCP_steady fallback
        if rcp_steady_w is None:
            rcp_steady_w = int(rcp_onset_w + (max_power - rcp_onset_w) * 0.4)
            result["rcp_steady_watts"] = rcp_steady_w

        # =====================================================================
        # VALIDATE MONOTONIC BOUNDARIES
        # =====================================================================
        boundaries_valid = vt1_onset_w < vt1_steady_w < rcp_onset_w < rcp_steady_w <= max_power

        if not boundaries_valid:
            # Fix non-monotonic boundaries
            result["analysis_notes"].append("⚠️ Korekta granic: wymuszenie monotoniczności")

            # Ensure VT1_steady > VT1_onset
            if vt1_steady_w <= vt1_onset_w:
                vt1_steady_w = vt1_onset_w + int((rcp_onset_w - vt1_onset_w) * 0.4)
                result["vt1_steady_watts"] = vt1_steady_w

            # Ensure RCP_onset > VT1_steady
            if rcp_onset_w <= vt1_steady_w:
                rcp_onset_w = vt1_steady_w + int((max_power - vt1_steady_w) * 0.5)
                result["rcp_onset_watts"] = rcp_onset_w
                result["vt2_watts"] = rcp_onset_w

            # Ensure RCP_steady > RCP_onset
            if rcp_steady_w <= rcp_onset_w:
                rcp_steady_w = rcp_onset_w + 15
                result["rcp_steady_watts"] = rcp_steady_w

        result["boundaries_valid"] = vt1_onset_w < vt1_steady_w < rcp_onset_w < rcp_steady_w

        # =====================================================================
        # PERCENTILE VALIDATION: Check if detected values are in expected range
        # Use raw data percentiles for more accurate threshold estimation
        # =====================================================================
        # Get raw power data (not aggregated steps) for percentile calculation
        raw_power = data[data[cols["power"]] >= 100][cols["power"]].values
        power_60th_raw = int(np.percentile(raw_power, 60))
        power_80th_raw = int(np.percentile(raw_power, 80))

        # Check if detected VT1 is too low (below 60th percentile of raw data)
        if vt1_onset_w < power_60th_raw:
            result["analysis_notes"].append(
                f"⚠️ VT1_onset ({vt1_onset_w}W) poniżej 60 percentyla ({power_60th_raw}W) - korekta"
            )
            vt1_onset_w = power_60th_raw
            result["vt1_onset_watts"] = vt1_onset_w
            result["vt1_watts"] = vt1_onset_w

        # Check if detected VT2 is too low (below 80th percentile of raw data)
        if rcp_onset_w < power_80th_raw:
            result["analysis_notes"].append(
                f"⚠️ RCP_onset ({rcp_onset_w}W) poniżej 80 percentyla ({power_80th_raw}W) - korekta"
            )
            rcp_onset_w = power_80th_raw
            result["rcp_onset_watts"] = rcp_onset_w
            result["vt2_watts"] = rcp_onset_w

        # Re-validate boundaries after potential corrections
        if vt1_steady_w <= vt1_onset_w:
            vt1_steady_w = int((vt1_onset_w + rcp_onset_w) / 2)
            result["vt1_steady_watts"] = vt1_steady_w
            result["vt1_steady_is_interpolated"] = True

        # =====================================================================
        # BUILD 4 ZONES (MANDATORY)
        # =====================================================================
        zones = []

        # Zone 1: Pure Aerobic (< VT1_onset)
        zones.append(
            {
                "zone": 1,
                "name": "Pure Aerobic",
                "power_min": 0,
                "power_max": vt1_onset_w,
                "hr_min": None,
                "hr_max": result.get("vt1_hr"),
                "description": "Full homeostasis, linear VE, no H⁺ buffering",
                "training": "Recovery / Endurance Base",
                "domain": "Moderate",
            }
        )

        # Zone 2: Upper Aerobic (VT1_onset → VT1_steady)
        zone2_name = "Upper Aerobic (Unstable)" if is_vt1_steady_interpolated else "Upper Aerobic"
        zone2_desc = (
            "Strefa niestabilna - brak plateau VE, ciągłe przyspieszanie"
            if is_vt1_steady_interpolated
            else "Buffering onset, rising VE, stable metabolism"
        )
        zones.append(
            {
                "zone": 2,
                "name": zone2_name,
                "power_min": vt1_onset_w,
                "power_max": vt1_steady_w,
                "hr_min": result.get("vt1_hr"),
                "hr_max": result.get("vt1_steady_hr"),
                "description": zone2_desc,
                "training": "Tempo / Sweet Spot",
                "domain": "Moderate-Heavy Transition",
                "is_interpolated": is_vt1_steady_interpolated,
            }
        )

        # Zone 3: Heavy Domain (VT1_steady → RCP_onset)
        zones.append(
            {
                "zone": 3,
                "name": "Heavy Domain",
                "power_min": vt1_steady_w,
                "power_max": rcp_onset_w,
                "hr_min": result.get("vt1_steady_hr"),
                "hr_max": result.get("vt2_hr"),
                "description": "Building acidosis, VE > VO₂, pre-compensation",
                "training": "Threshold / FTP Work",
                "domain": "Heavy",
            }
        )

        # Zone 4: Severe Domain (≥ RCP_onset) with subzones 4a/4b
        zones.append(
            {
                "zone": 4,
                "name": "Severe Domain",
                "power_min": rcp_onset_w,
                "power_max": max_power,
                "hr_min": result.get("vt2_hr"),
                "hr_max": None,
                "description": "Compensatory hyperventilation, no steady-state possible",
                "training": "VO₂max / Anaerobic",
                "domain": "Severe",
                "subzones": [
                    {
                        "name": "4a - Severe Onset",
                        "power_min": rcp_onset_w,
                        "power_max": rcp_steady_w,
                        "description": "RCP onset → full RCP transition",
                    },
                    {
                        "name": "4b - Full Severe",
                        "power_min": rcp_steady_w,
                        "power_max": max_power,
                        "description": "Full respiratory compensation, exhaustion imminent",
                    },
                ],
            }
        )

        # Validate: must have exactly 4 zones
        if len(zones) != 4:
            result["analysis_notes"].append(f"❌ BŁĄD: Wygenerowano {len(zones)} stref zamiast 4!")
        else:
            result["analysis_notes"].append(f"✓ 4 strefy wygenerowane poprawnie")

        result["metabolic_zones"] = zones

    # =========================================================================
    # 6. FALLBACK DEFAULTS
    # =========================================================================
    max_power = df_steps["power"].max()

    if result["vt1_watts"] is None:
        # Use percentile-based estimation for better accuracy
        vt1_power = int(np.percentile(df_steps["power"].values, 60))
        result["vt1_watts"] = vt1_power
        result["analysis_notes"].append(f"VT1 not detected - using 60th percentile ({vt1_power}W)")

    if result["vt2_watts"] is None:
        # Use percentile-based estimation for better accuracy
        vt2_power = int(np.percentile(df_steps["power"].values, 80))
        result["vt2_watts"] = vt2_power
        result["analysis_notes"].append(f"VT2 not detected - using 80th percentile ({vt2_power}W)")

    # =========================================================================
    # 7. PHYSIOLOGICAL VALIDATION
    # =========================================================================
    # VT1 < VT2
    if result["vt1_watts"] >= result["vt2_watts"]:
        # Swap or adjust
        result["analysis_notes"].append("⚠️ VT1 >= VT2 - adjusted VT2 to VT1 + 15%")
        result["vt2_watts"] = int(result["vt1_watts"] * 1.15)
    result["validation"]["vt1_lt_vt2"] = result["vt1_watts"] < result["vt2_watts"]

    # VE/VO2 rises before VE/VCO2 (only check if both thresholds detected via CPET)
    if result["vt1_step"] and result["vt2_step"]:
        result["validation"]["ve_vo2_rises_first"] = result["vt1_step"] < result["vt2_step"]

    return result


def _find_breakpoint_segmented(
    x: np.ndarray, y: np.ndarray, min_segment_size: int = 3
) -> Optional[int]:
    """
    Find optimal breakpoint using piecewise linear regression.

    Tests each potential breakpoint and returns the one minimizing total SSE.

    Args:
        x: Independent variable (power)
        y: Dependent variable (VE/VO2 or VE/VCO2)
        min_segment_size: Minimum points in each segment

    Returns:
        Index of optimal breakpoint, or None if not found
    """
    if len(x) < 2 * min_segment_size:
        return None

    # Remove NaN values
    mask = ~(np.isnan(x) | np.isnan(y))
    x = x[mask]
    y = y[mask]

    if len(x) < 2 * min_segment_size:
        return None

    best_idx = None
    best_sse = np.inf
    best_slope_ratio = 0

    for i in range(min_segment_size, len(x) - min_segment_size):
        # Fit two segments
        x1, y1 = x[:i], y[:i]
        x2, y2 = x[i:], y[i:]

        try:
            # Segment 1
            slope1, intercept1, _, _, _ = stats.linregress(x1, y1)
            pred1 = slope1 * x1 + intercept1
            sse1 = np.sum((y1 - pred1) ** 2)

            # Segment 2
            slope2, intercept2, _, _, _ = stats.linregress(x2, y2)
            pred2 = slope2 * x2 + intercept2
            sse2 = np.sum((y2 - pred2) ** 2)

            total_sse = sse1 + sse2

            # We want slope2 > slope1 (increasing trend after breakpoint)
            slope_ratio = slope2 / slope1 if slope1 != 0 else slope2

            if total_sse < best_sse and slope_ratio > 1.1:
                best_sse = total_sse
                best_idx = i
                best_slope_ratio = slope_ratio

        except Exception:
            continue

    return best_idx


def _calculate_segment_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Calculate slope of a segment using linear regression."""
    if len(x) < 2:
        return 0.0

    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 2:
        return 0.0

    try:
        slope, _, _, _, _ = stats.linregress(x[mask], y[mask])
        return slope
    except:
        return 0.0
