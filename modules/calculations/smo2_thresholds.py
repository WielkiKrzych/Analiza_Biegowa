"""
SmO2 3-point threshold detection model for ramp test analysis.

Detects T1 (LT1 analog) and T2_onset (RCP analog) from SmO2 data
during incremental ramp tests using gradient, curvature, and trend analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ._smo2_utils import _fast_curvature, _fast_gradient


@dataclass
class SmO2ThresholdResult:
    """Result of 3-point SmO2 threshold detection (T1, T2_onset, T2_steady)."""

    # T1 (LT1 analog - onset of desaturation)
    t1_watts: Optional[int] = None
    t1_hr: Optional[int] = None
    t1_smo2: Optional[float] = None
    t1_gradient: Optional[float] = None  # dSmO2/dP
    t1_trend: Optional[float] = None  # dSmO2/dt (%/min)
    t1_sd: Optional[float] = None  # Variability
    t1_step: Optional[int] = None

    # T2_onset (Heavy→Severe transition)
    t2_onset_watts: Optional[int] = None
    t2_onset_hr: Optional[int] = None
    t2_onset_smo2: Optional[float] = None
    t2_onset_gradient: Optional[float] = None
    t2_onset_curvature: Optional[float] = None
    t2_onset_sd: Optional[float] = None
    t2_onset_step: Optional[int] = None

    # T2_steady (MLSS_local / RCP_steady analog)
    t2_steady_watts: Optional[int] = None
    t2_steady_hr: Optional[int] = None
    t2_steady_smo2: Optional[float] = None
    t2_steady_gradient: Optional[float] = None
    t2_steady_trend: Optional[float] = None  # dSmO2/dt (%/min)
    t2_steady_sd: Optional[float] = None
    t2_steady_step: Optional[int] = None

    # Legacy compatibility (map to primary thresholds)
    t2_watts: Optional[int] = None  # Maps to t2_onset_watts
    t2_hr: Optional[int] = None
    t2_smo2: Optional[float] = None
    t2_gradient: Optional[float] = None
    t2_step: Optional[int] = None

    # Zones
    zones: List[Dict] = field(default_factory=list)

    # Validation
    vt1_correlation_watts: Optional[int] = None
    rcp_onset_correlation_watts: Optional[int] = None
    rcp_steady_correlation_watts: Optional[int] = None
    physiological_agreement: str = "not_checked"

    # Analysis info
    analysis_notes: List[str] = field(default_factory=list)
    method: str = "moxy_3point"
    step_data: List[Dict] = field(default_factory=list)


def detect_smo2_thresholds_moxy(
    df: pd.DataFrame,
    step_duration_sec: int = 180,
    smo2_col: str = "smo2",
    power_col: str = "watts",
    hr_col: str = "hr",
    time_col: str = "time",
    cp_watts: Optional[int] = None,
    hr_max: Optional[int] = None,
    vt1_watts: Optional[int] = None,
    rcp_onset_watts: Optional[int] = None,
    rcp_steady_watts: Optional[int] = None,
) -> SmO2ThresholdResult:
    """
    RAMP TEST SmO₂ THRESHOLD DETECTION (Senior Physiologist + Signal Processing):

    CRITICAL: Only 2 breakpoints valid in ramp test:
    - SmO2_T1 (LT1 analog)
    - SmO2_T2_onset (RCP / Heavy→Severe)

    T2_steady (MLSS_local) MUST NOT be detected in ramp tests.

    Pipeline:
    1. Median smoothing 30-45s
    2. Remove last 1 step (ischemic crash)
    3. Reject CV > 6% (motion artefact)
    4. T1: dSmO2/dt < -0.4%/min ≥2 consecutive steps, CV < 4%, VT1±15%
    5. T2_onset: max global curvature, dSmO2/dt < -1.5%/min, osc ↑30%, T1+20%, VT2±15%
    6. 4-domain zones
    7. Confidence score
    """

    result = SmO2ThresholdResult()

    # Normalize columns
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    smo2_col = smo2_col.lower()
    power_col = power_col.lower()
    hr_col = hr_col.lower() if hr_col else None
    time_col = time_col.lower()

    if smo2_col not in df.columns:
        result.analysis_notes.append("❌ Brak kolumny SmO2")
        return result

    if power_col not in df.columns:
        result.analysis_notes.append("❌ Brak kolumny mocy")
        return result

    # =========================================================================
    # 1. PREPROCESSING: MEDIAN SMOOTHING (30-45s)
    # =========================================================================

    window = min(45, max(30, len(df) // 40))
    if window % 2 == 0:
        window += 1

    df["smo2_smooth"] = df[smo2_col].rolling(window=window, center=True, min_periods=1).median()

    if time_col in df.columns:
        df["step"] = (df[time_col] // step_duration_sec).astype(int)
    else:
        df["step"] = (df.index // step_duration_sec).astype(int)

    max_power = df[power_col].max()
    has_hr = hr_col and hr_col in df.columns

    if hr_max is None and has_hr:
        hr_max = int(df[hr_col].max())

    # =========================================================================
    # 2. AGGREGATE BY STEP
    # =========================================================================

    # OPTIMIZED: Vectorized step aggregation using groupby
    all_steps = sorted(df["step"].unique())

    # REMOVE LAST 1 STEP (ischemic crash zone)
    if len(all_steps) > 1:
        last_step = all_steps[-1]
    else:
        last_step = None

    # Filter steps with at least 30 samples
    step_counts = df.groupby("step").size()
    valid_steps = step_counts[step_counts >= 30].index.tolist()

    if not valid_steps:
        result.analysis_notes.append("⚠️ Za mało danych w stopniach")
        return result

    # Vectorized aggregation per step
    def aggregate_step(step_num):
        step_df = df[df["step"] == step_num]
        last_90 = step_df.tail(90) if len(step_df) >= 90 else step_df
        last_60 = step_df.tail(60) if len(step_df) >= 60 else step_df

        avg_power = last_60[power_col].mean()
        avg_smo2 = last_60["smo2_smooth"].mean()
        avg_hr = last_60[hr_col].mean() if has_hr else None
        end_time = last_60[time_col].iloc[-1] if time_col in last_60.columns else None

        # CV in 90s window
        sd_smo2 = last_90["smo2_smooth"].std()
        cv_smo2 = (sd_smo2 / avg_smo2 * 100) if avg_smo2 > 0 else 0

        # Oscillation amplitude (peak-to-peak)
        osc_amp = last_60["smo2_smooth"].max() - last_60["smo2_smooth"].min()

        # Trend (dSmO2/dt in %/min)
        trend = 0
        if len(last_90) >= 60 and time_col in last_90.columns:
            time_range = last_90[time_col].iloc[-1] - last_90[time_col].iloc[0]
            if time_range > 0:
                smo2_change = last_90["smo2_smooth"].iloc[-1] - last_90["smo2_smooth"].iloc[0]
                trend = smo2_change / (time_range / 60)

        # HR slope (linear check)
        hr_slope = None
        if has_hr and len(last_90) >= 30:
            hr_vals = last_90[hr_col].values
            time_vals = np.arange(len(hr_vals))
            if len(hr_vals) > 2:
                hr_slope = np.polyfit(time_vals, hr_vals, 1)[0]

        return {
            "step": step_num,
            "power": avg_power,
            "smo2": avg_smo2,
            "hr": avg_hr,
            "end_time": end_time,
            "sd": sd_smo2,
            "cv": cv_smo2,
            "osc_amp": osc_amp,
            "trend": trend,
            "hr_slope": hr_slope,
            "is_last_step": step_num == last_step,
        }

    # Use list comprehension for better performance
    step_data = [aggregate_step(step) for step in valid_steps]

    if len(step_data) < 4:
        result.analysis_notes.append(f"⚠️ Za mało stopni ({len(step_data)})")
        return result

    step_df = pd.DataFrame(step_data)

    # =========================================================================
    # 3. CALCULATE DERIVATIVES
    # =========================================================================

    # Use Numba-optimized functions if available
    smo2_vals = step_df["smo2"].values
    power_vals = step_df["power"].values
    step_df["gradient"] = _fast_gradient(smo2_vals, power_vals)
    step_df["curvature"] = _fast_curvature(smo2_vals, power_vals)

    # =========================================================================
    # 4. SmO₂_T1 DETECTION (LT1 analog)
    # =========================================================================
    # Criteria: dSmO2/dt < -0.4%/min for ≥2 consecutive steps, CV < 4%, VT1±15%

    t1_idx = None
    t1_is_systemic = False
    t1_confidence = 0

    # Power window for T1: VT1 ± 15%
    t1_power_min = vt1_watts * 0.85 if vt1_watts else 0
    t1_power_max = vt1_watts * 1.15 if vt1_watts else max_power

    for i in range(1, len(step_df) - 1):
        row = step_df.iloc[i]
        next_row = step_df.iloc[i + 1]

        # Skip last step (ischemic)
        if row["is_last_step"] or next_row["is_last_step"]:
            continue

        # ARTEFACT REJECTION: CV > 6%
        if row["cv"] > 6.0:
            result.analysis_notes.append(
                f"❌ Step {row['step']} rejected: CV={row['cv']:.1f}% > 6%"
            )
            continue

        # Power window check
        if vt1_watts:
            if not (t1_power_min <= row["power"] <= t1_power_max):
                continue

        # T1 CRITERIA:
        # dSmO2/dt < -0.4%/min for ≥2 consecutive steps
        trend_ok = row["trend"] < -0.4 and next_row["trend"] < -0.4

        # CV < 4%
        cv_ok = row["cv"] < 4.0

        # HR slope remains linear (not accelerating excessively)
        hr_linear = True
        if row["hr_slope"] is not None:
            hr_linear = row["hr_slope"] > 0  # HR should be increasing

        if trend_ok and cv_ok and hr_linear:
            t1_idx = i

            # Check VT1 validation
            if vt1_watts:
                pct_diff = abs(row["power"] - vt1_watts) / vt1_watts * 100
                if pct_diff <= 10:
                    t1_is_systemic = True
                    t1_confidence += 30
                    result.analysis_notes.append(f"✓ T1 zgodny z VT1 ±{pct_diff:.0f}%")
                elif pct_diff <= 15:
                    t1_confidence += 15
                    result.analysis_notes.append(f"⚠️ T1 w zakresie VT1 ±{pct_diff:.0f}%")
            else:
                t1_confidence += 20

            # Additional confidence from signal quality
            if row["cv"] < 2.0:
                t1_confidence += 10
            if abs(row["trend"]) > 0.6:
                t1_confidence += 10

            break

    if t1_idx is None:
        result.analysis_notes.append("⚠️ T1 nie wykryto")
    else:
        row = step_df.iloc[t1_idx]
        result.t1_watts = int(row["power"])
        result.t1_smo2 = round(row["smo2"], 1)
        result.t1_hr = int(row["hr"]) if pd.notna(row["hr"]) else None
        result.t1_gradient = round(row["gradient"], 4)
        result.t1_trend = round(row["trend"], 2)
        result.t1_sd = round(row["sd"], 2)
        result.t1_step = int(row["step"])
        flag = "🟢 Systemic" if t1_is_systemic else "🟡 Local"
        result.analysis_notes.append(
            f"SmO₂ T1: {result.t1_watts}W @ {result.t1_smo2}% "
            f"(slope={result.t1_trend}%/min, CV={row['cv']:.1f}%) [{flag}]"
        )

    # =========================================================================
    # 5. SmO₂_T2_onset DETECTION (RCP analog)
    # =========================================================================
    # Criteria: max global curvature, dSmO2/dt < -1.5%/min, osc ↑30%, T1+20%, VT2±15%

    t2_onset_idx = None
    t2_onset_is_systemic = False
    t2_confidence = 0

    # Power constraints
    min_t2_power = (
        (result.t1_watts * 1.20) if result.t1_watts else (vt1_watts * 1.20 if vt1_watts else 0)
    )
    t2_power_min = rcp_onset_watts * 0.85 if rcp_onset_watts else min_t2_power
    t2_power_max = rcp_onset_watts * 1.15 if rcp_onset_watts else max_power

    search_start = t1_idx + 1 if t1_idx is not None else 2

    # Get baseline oscillation amplitude
    t1_osc = step_df.iloc[t1_idx]["osc_amp"] if t1_idx else step_df["osc_amp"].median()

    # Find max global curvature in valid range
    valid_rows = []
    for i in range(search_start, len(step_df)):
        row = step_df.iloc[i]

        # Skip last step (ischemic)
        if row["is_last_step"]:
            continue

        # Power constraints
        if row["power"] < min_t2_power:
            continue
        if rcp_onset_watts:
            if not (t2_power_min <= row["power"] <= t2_power_max):
                continue

        # ARTEFACT REJECTION: CV > 6%
        if row["cv"] > 6.0:
            result.analysis_notes.append(
                f"❌ Step {row['step']} rejected: CV={row['cv']:.1f}% > 6%"
            )
            continue

        valid_rows.append({"idx": i, "row": row})

    if valid_rows:
        # Find max curvature (global peak)
        max_curv_item = max(valid_rows, key=lambda x: abs(x["row"]["curvature"]))
        best_row = max_curv_item["row"]
        best_idx = max_curv_item["idx"]

        # Check T2_onset criteria
        trend_severe = best_row["trend"] < -1.5
        osc_increasing = best_row["osc_amp"] > t1_osc * 1.3  # ≥30% increase

        if trend_severe or abs(best_row["curvature"]) > 0.0003:
            t2_onset_idx = best_idx

            # Confidence from trend
            if trend_severe:
                t2_confidence += 20

            # Confidence from oscillation
            if osc_increasing:
                t2_confidence += 15

            # Confidence from curvature magnitude
            if abs(best_row["curvature"]) > 0.0005:
                t2_confidence += 15
            elif abs(best_row["curvature"]) > 0.0003:
                t2_confidence += 10

            # Check VT2/RCP validation
            if rcp_onset_watts:
                pct_diff = abs(best_row["power"] - rcp_onset_watts) / rcp_onset_watts * 100
                if pct_diff <= 10:
                    t2_onset_is_systemic = True
                    t2_confidence += 30
                    result.analysis_notes.append(f"✓ T2_onset zgodny z VT2/RCP ±{pct_diff:.0f}%")
                elif pct_diff <= 15:
                    t2_confidence += 15
                    result.analysis_notes.append(f"⚠️ T2_onset w zakresie VT2/RCP ±{pct_diff:.0f}%")
                else:
                    result.analysis_notes.append(
                        "❌ T2_onset poza VT2/RCP ±15%: Local Perfusion Limitation"
                    )
            else:
                t2_confidence += 20

    if t2_onset_idx is None:
        result.analysis_notes.append("⚠️ T2_onset nie wykryto")
    else:
        row = step_df.iloc[t2_onset_idx]
        result.t2_onset_watts = int(row["power"])
        result.t2_onset_smo2 = round(row["smo2"], 1)
        result.t2_onset_hr = int(row["hr"]) if pd.notna(row["hr"]) else None
        result.t2_onset_gradient = round(row["gradient"], 4)
        result.t2_onset_curvature = round(row["curvature"], 5)
        result.t2_onset_sd = round(row["sd"], 2)
        result.t2_onset_step = int(row["step"])

        result.t2_watts = result.t2_onset_watts
        result.t2_hr = result.t2_onset_hr
        result.t2_smo2 = result.t2_onset_smo2
        result.t2_gradient = result.t2_onset_gradient
        result.t2_step = result.t2_onset_step

        flag = "🟢 Systemic" if t2_onset_is_systemic else "🟡 Local"
        result.analysis_notes.append(
            f"SmO₂ T2_onset: {result.t2_onset_watts}W @ {result.t2_onset_smo2}% "
            f"(slope={row['trend']:.1f}%/min, curv={row['curvature']:.5f}) [{flag}]"
        )

    # =========================================================================
    # 6. NO T2_STEADY FOR RAMP TESTS
    # =========================================================================
    # CRITICAL: T2_steady (MLSS_local) MUST NOT be detected in ramp tests

    result.analysis_notes.append(
        "ℹ️ T2_steady N/A w teście rampowym (brak plateau do detekcji MLSS_local)"
    )

    # =========================================================================
    # 7. HIERARCHICAL VALIDATION + CONFIDENCE SCORE
    # =========================================================================

    # Check T1 < T2_onset
    if result.t1_watts and result.t2_onset_watts:
        if result.t1_watts >= result.t2_onset_watts:
            result.analysis_notes.append("⚠️ Hierarchy violated: T1 >= T2_onset")
            result.t1_watts = None
            t1_confidence = 0

    # Correlation with CPET
    if vt1_watts and result.t1_watts:
        result.vt1_correlation_watts = abs(result.t1_watts - vt1_watts)

    if rcp_onset_watts and result.t2_onset_watts:
        result.rcp_onset_correlation_watts = abs(result.t2_onset_watts - rcp_onset_watts)

    # Overall confidence score (0-100)
    total_confidence = t1_confidence + t2_confidence
    if result.t1_watts and result.t2_onset_watts:
        total_confidence += 20  # Both thresholds detected

    # Cap at 100
    total_confidence = min(100, total_confidence)

    # Determine agreement level
    systemic_count = sum([t1_is_systemic, t2_onset_is_systemic])

    if systemic_count >= 2:
        result.physiological_agreement = "high"
        result.analysis_notes.append(
            f"🟢 High systemic agreement (confidence: {total_confidence}%)"
        )
    elif systemic_count == 1:
        result.physiological_agreement = "moderate"
        result.analysis_notes.append(f"🟡 Moderate agreement (confidence: {total_confidence}%)")
    else:
        result.physiological_agreement = "low"
        result.analysis_notes.append(
            f"🔴 Low agreement - Local Perfusion Limitation (confidence: {total_confidence}%)"
        )

    # =========================================================================
    # 8. BUILD 4-DOMAIN ZONES
    # =========================================================================

    max_power_int = int(max_power)
    zones = []

    # Zone 1: Stable aerobic extraction (< T1)
    if result.t1_watts:
        zones.append(
            {
                "zone": 1,
                "name": "Stable Aerobic",
                "power_min": 0,
                "power_max": result.t1_watts,
                "description": "<T1 - stable O₂ extraction",
                "training": "Endurance / Recovery",
            }
        )

    # Zone 2: Heavy domain, progressive extraction (T1 → T2)
    t2_w = result.t2_onset_watts
    if result.t1_watts and t2_w:
        zones.append(
            {
                "zone": 2,
                "name": "Progressive Extraction",
                "power_min": result.t1_watts,
                "power_max": t2_w,
                "description": "T1→T2 - progressive O₂ extraction",
                "training": "Tempo / Threshold",
            }
        )

    # Zone 3: Severe domain, non-steady ischemic (T2 → end)
    if t2_w:
        zones.append(
            {
                "zone": 3,
                "name": "Non-Steady Severe",
                "power_min": t2_w,
                "power_max": max_power_int,
                "description": "T2→end - compensatory desaturation",
                "training": "VO₂max intervals",
            }
        )

    # Zone 4: Post-failure ischemic collapse (artefact, not training zone)
    zones.append(
        {
            "zone": 4,
            "name": "Ischemic Collapse",
            "power_min": max_power_int,
            "power_max": max_power_int,
            "description": "Post-failure artefact",
            "training": "N/A",
        }
    )

    result.zones = zones
    result.step_data = step_df.to_dict("records")

    result.analysis_notes.append(
        f"Ramp Test Pipeline: T1+T2_onset only, no T2_steady. Confidence: {total_confidence}%."
    )

    return result


__all__ = [
    "SmO2ThresholdResult",
    "detect_smo2_thresholds_moxy",
]
