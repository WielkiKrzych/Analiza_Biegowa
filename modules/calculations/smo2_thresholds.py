"""
SmO2 3-point threshold detection model for ramp test analysis.

Detects T1 (LT1 analog) and T2_onset (RCP analog) from SmO2 data
during incremental ramp tests using gradient, curvature, and trend analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _ThresholdDetection:
    """Intermediate result for a single threshold detection pass."""

    idx: Optional[int] = None
    is_systemic: bool = False
    confidence: int = 0
    notes: List[str] = field(default_factory=list)


def _normalize_columns(
    df: pd.DataFrame,
    smo2_col: str,
    power_col: str,
    hr_col: Optional[str],
    time_col: str,
) -> Tuple[pd.DataFrame, str, str, Optional[str], str]:
    """Lowercase & strip all DataFrame column names and references."""
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    return (
        df,
        smo2_col.lower(),
        power_col.lower(),
        hr_col.lower() if hr_col else None,
        time_col.lower(),
    )


def _validate_required_columns(
    df: pd.DataFrame,
    smo2_col: str,
    power_col: str,
) -> Optional[str]:
    """Return an error message if required columns are missing, else None."""
    if smo2_col not in df.columns:
        return "❌ Brak kolumny SmO2"
    if power_col not in df.columns:
        return "❌ Brak kolumny mocy"
    return None


def _preprocess_signal(
    df: pd.DataFrame,
    smo2_col: str,
    power_col: str,
    time_col: str,
    step_duration_sec: int,
    hr_col: Optional[str],
    hr_max: Optional[int],
) -> Tuple[pd.DataFrame, float, bool, Optional[int]]:
    """Apply median smoothing, assign step numbers, derive basic stats.

    Returns (df, max_power, has_hr, hr_max).
    """
    window = min(45, max(30, len(df) // 40))
    if window % 2 == 0:
        window += 1

    df["smo2_smooth"] = df[smo2_col].rolling(window=window, center=True, min_periods=1).median()

    if time_col in df.columns:
        df["step"] = (df[time_col] // step_duration_sec).astype(int)
    else:
        df["step"] = (df.index // step_duration_sec).astype(int)

    max_power = df[power_col].max()
    has_hr = hr_col is not None and hr_col in df.columns

    if hr_max is None and has_hr:
        hr_max = int(df[hr_col].max())

    return df, max_power, has_hr, hr_max


def _aggregate_single_step(
    step_df: pd.DataFrame,
    step_num: int,
    power_col: str,
    hr_col: Optional[str],
    time_col: str,
    has_hr: bool,
    is_last: bool,
) -> Dict:
    """Aggregate a single step into summary statistics."""
    last_90 = step_df.tail(90) if len(step_df) >= 90 else step_df
    last_60 = step_df.tail(60) if len(step_df) >= 60 else step_df

    avg_power = last_60[power_col].mean()
    avg_smo2 = last_60["smo2_smooth"].mean()
    avg_hr = last_60[hr_col].mean() if has_hr else None
    end_time = last_60[time_col].iloc[-1] if time_col in last_60.columns else None

    sd_smo2 = last_90["smo2_smooth"].std()
    cv_smo2 = (sd_smo2 / avg_smo2 * 100) if avg_smo2 > 0 else 0

    osc_amp = last_60["smo2_smooth"].max() - last_60["smo2_smooth"].min()

    trend = 0
    if len(last_90) >= 60 and time_col in last_90.columns:
        time_range = last_90[time_col].iloc[-1] - last_90[time_col].iloc[0]
        if time_range > 0:
            smo2_change = last_90["smo2_smooth"].iloc[-1] - last_90["smo2_smooth"].iloc[0]
            trend = smo2_change / (time_range / 60)

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
        "is_last_step": is_last,
    }


def _aggregate_steps(
    df: pd.DataFrame,
    power_col: str,
    hr_col: Optional[str],
    time_col: str,
    has_hr: bool,
    notes: List[str],
) -> Optional[pd.DataFrame]:
    """Aggregate data by step.  Returns *None* when data is insufficient."""
    all_steps = sorted(df["step"].unique())
    last_step = all_steps[-1] if len(all_steps) > 1 else None

    step_counts = df.groupby("step").size()
    valid_steps = step_counts[step_counts >= 30].index.tolist()

    if not valid_steps:
        notes.append("⚠️ Za mało danych w stopniach")
        return None

    step_data = [
        _aggregate_single_step(
            df[df["step"] == s],
            s,
            power_col,
            hr_col,
            time_col,
            has_hr,
            s == last_step,
        )
        for s in valid_steps
    ]

    if len(step_data) < 4:
        notes.append(f"⚠️ Za mało stopni ({len(step_data)})")
        return None

    return pd.DataFrame(step_data)


def _compute_derivatives(step_df: pd.DataFrame) -> None:
    """Add *gradient* and *curvature* columns to *step_df* in-place."""
    smo2_vals = step_df["smo2"].values
    power_vals = step_df["power"].values
    step_df["gradient"] = _fast_gradient(smo2_vals, power_vals)
    step_df["curvature"] = _fast_curvature(smo2_vals, power_vals)


# ---------------------------------------------------------------------------
# T1 detection helpers
# ---------------------------------------------------------------------------


def _is_t1_candidate(
    row: pd.Series,
    next_row: pd.Series,
    vt1_watts: Optional[int],
    power_min: float,
    power_max: float,
) -> bool:
    """Check whether a step meets T1 threshold criteria (assumes CV ≤ 6 %)."""
    if row["is_last_step"] or next_row["is_last_step"]:
        return False
    if vt1_watts and not (power_min <= row["power"] <= power_max):
        return False
    trend_ok = row["trend"] < -0.4 and next_row["trend"] < -0.4
    cv_ok = row["cv"] < 4.0
    hr_ok = row["hr_slope"] is None or row["hr_slope"] > 0
    return trend_ok and cv_ok and hr_ok


def _score_t1_match(
    row: pd.Series,
    vt1_watts: Optional[int],
) -> Tuple[bool, int, List[str]]:
    """Score a T1 match.  Returns *(is_systemic, confidence, notes)*."""
    is_systemic = False
    confidence = 0
    notes: List[str] = []

    if vt1_watts:
        pct_diff = abs(row["power"] - vt1_watts) / vt1_watts * 100
        if pct_diff <= 10:
            is_systemic = True
            confidence += 30
            notes.append(f"✓ T1 zgodny z VT1 ±{pct_diff:.0f}%")
        elif pct_diff <= 15:
            confidence += 15
            notes.append(f"⚠️ T1 w zakresie VT1 ±{pct_diff:.0f}%")
    else:
        confidence += 20

    if row["cv"] < 2.0:
        confidence += 10
    if abs(row["trend"]) > 0.6:
        confidence += 10

    return is_systemic, confidence, notes


def _detect_t1(
    step_df: pd.DataFrame,
    vt1_watts: Optional[int],
    max_power: float,
) -> _ThresholdDetection:
    """Detect SmO₂ T1 threshold (LT1 analog).

    Criteria: dSmO₂/dt < -0.4 %/min for ≥ 2 consecutive steps,
    CV < 4 %, VT1 ± 15 %.
    """
    det = _ThresholdDetection()

    power_min = vt1_watts * 0.85 if vt1_watts else 0
    power_max = vt1_watts * 1.15 if vt1_watts else max_power

    for i in range(1, len(step_df) - 1):
        row = step_df.iloc[i]
        next_row = step_df.iloc[i + 1]

        if row["cv"] > 6.0:
            det.notes.append(f"❌ Step {row['step']} rejected: CV={row['cv']:.1f}% > 6%")
            continue

        if not _is_t1_candidate(row, next_row, vt1_watts, power_min, power_max):
            continue

        det.idx = i
        det.is_systemic, inc_conf, t1_notes = _score_t1_match(row, vt1_watts)
        det.confidence += inc_conf
        det.notes.extend(t1_notes)
        break

    if det.idx is None:
        det.notes.append("⚠️ T1 nie wykryto")

    return det


def _apply_t1_to_result(
    result: SmO2ThresholdResult,
    step_df: pd.DataFrame,
    det: _ThresholdDetection,
) -> None:
    """Populate *result* fields from T1 detection."""
    if det.idx is None:
        return

    row = step_df.iloc[det.idx]
    result.t1_watts = int(row["power"])
    result.t1_smo2 = round(row["smo2"], 1)
    result.t1_hr = int(row["hr"]) if pd.notna(row["hr"]) else None
    result.t1_gradient = round(row["gradient"], 4)
    result.t1_trend = round(row["trend"], 2)
    result.t1_sd = round(row["sd"], 2)
    result.t1_step = int(row["step"])

    flag = "🟢 Systemic" if det.is_systemic else "🟡 Local"
    result.analysis_notes.append(
        f"SmO₂ T1: {result.t1_watts}W @ {result.t1_smo2}% "
        f"(slope={result.t1_trend}%/min, CV={row['cv']:.1f}%) [{flag}]"
    )


# ---------------------------------------------------------------------------
# T2 onset detection helpers
# ---------------------------------------------------------------------------


def _find_t2_candidates(
    step_df: pd.DataFrame,
    search_start: int,
    min_t2_power: float,
    rcp_onset_watts: Optional[int],
    t2_power_min: float,
    t2_power_max: float,
) -> Tuple[List[Dict], List[str]]:
    """Collect valid T2 candidate rows.  Returns *(candidates, rejection_notes)*."""
    candidates: List[Dict] = []
    notes: List[str] = []

    for i in range(search_start, len(step_df)):
        row = step_df.iloc[i]

        if row["is_last_step"]:
            continue
        if row["power"] < min_t2_power:
            continue
        if rcp_onset_watts and not (t2_power_min <= row["power"] <= t2_power_max):
            continue
        if row["cv"] > 6.0:
            notes.append(f"❌ Step {row['step']} rejected: CV={row['cv']:.1f}% > 6%")
            continue

        candidates.append({"idx": i, "row": row})

    return candidates, notes


def _score_t2_match(
    best_row: pd.Series,
    t1_osc: float,
    rcp_onset_watts: Optional[int],
) -> Tuple[bool, int, List[str]]:
    """Score a T2 onset match.  Returns *(is_systemic, confidence, notes)*."""
    is_systemic = False
    confidence = 0
    notes: List[str] = []

    trend_severe = best_row["trend"] < -1.5
    osc_increasing = best_row["osc_amp"] > t1_osc * 1.3

    if trend_severe:
        confidence += 20
    if osc_increasing:
        confidence += 15

    curv_abs = abs(best_row["curvature"])
    if curv_abs > 0.0005:
        confidence += 15
    elif curv_abs > 0.0003:
        confidence += 10

    if rcp_onset_watts:
        pct_diff = abs(best_row["power"] - rcp_onset_watts) / rcp_onset_watts * 100
        if pct_diff <= 10:
            is_systemic = True
            confidence += 30
            notes.append(f"✓ T2_onset zgodny z VT2/RCP ±{pct_diff:.0f}%")
        elif pct_diff <= 15:
            confidence += 15
            notes.append(f"⚠️ T2_onset w zakresie VT2/RCP ±{pct_diff:.0f}%")
        else:
            notes.append("❌ T2_onset poza VT2/RCP ±15%: Local Perfusion Limitation")
    else:
        confidence += 20

    return is_systemic, confidence, notes


def _detect_t2_onset(
    step_df: pd.DataFrame,
    t1_detection: _ThresholdDetection,
    vt1_watts: Optional[int],
    rcp_onset_watts: Optional[int],
    max_power: float,
) -> _ThresholdDetection:
    """Detect SmO₂ T2_onset threshold (RCP analog).

    Criteria: max global curvature, dSmO₂/dt < -1.5 %/min,
    osc ↑ 30 %, T1+20 %, VT2 ± 15 %.
    """
    det = _ThresholdDetection()

    t1_watts = step_df.iloc[t1_detection.idx]["power"] if t1_detection.idx is not None else None

    min_t2_power = (t1_watts * 1.20) if t1_watts else (vt1_watts * 1.20 if vt1_watts else 0)
    t2_power_min = rcp_onset_watts * 0.85 if rcp_onset_watts else min_t2_power
    t2_power_max = rcp_onset_watts * 1.15 if rcp_onset_watts else max_power

    search_start = t1_detection.idx + 1 if t1_detection.idx is not None else 2

    t1_osc = (
        step_df.iloc[t1_detection.idx]["osc_amp"]
        if t1_detection.idx is not None
        else step_df["osc_amp"].median()
    )

    candidates, rejection_notes = _find_t2_candidates(
        step_df,
        search_start,
        min_t2_power,
        rcp_onset_watts,
        t2_power_min,
        t2_power_max,
    )
    det.notes.extend(rejection_notes)

    if not candidates:
        return det

    max_curv_item = max(candidates, key=lambda x: abs(x["row"]["curvature"]))
    best_row = max_curv_item["row"]
    best_idx = max_curv_item["idx"]

    trend_severe = best_row["trend"] < -1.5
    if not (trend_severe or abs(best_row["curvature"]) > 0.0003):
        return det

    det.idx = best_idx
    det.is_systemic, det.confidence, t2_notes = _score_t2_match(
        best_row,
        t1_osc,
        rcp_onset_watts,
    )
    det.notes.extend(t2_notes)

    return det


def _apply_t2_onset_to_result(
    result: SmO2ThresholdResult,
    step_df: pd.DataFrame,
    det: _ThresholdDetection,
) -> None:
    """Populate *result* fields from T2_onset detection."""
    if det.idx is None:
        result.analysis_notes.append("⚠️ T2_onset nie wykryto")
        return

    row = step_df.iloc[det.idx]
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

    flag = "🟢 Systemic" if det.is_systemic else "🟡 Local"
    result.analysis_notes.append(
        f"SmO₂ T2_onset: {result.t2_onset_watts}W @ {result.t2_onset_smo2}% "
        f"(slope={row['trend']:.1f}%/min, curv={row['curvature']:.5f}) [{flag}]"
    )


# ---------------------------------------------------------------------------
# Validation & zones
# ---------------------------------------------------------------------------


def _validate_and_score(
    result: SmO2ThresholdResult,
    t1_det: _ThresholdDetection,
    t2_det: _ThresholdDetection,
    vt1_watts: Optional[int],
    rcp_onset_watts: Optional[int],
) -> int:
    """Validate hierarchy, compute confidence, and set agreement level.

    Returns the total confidence score (0-100).
    """
    # Hierarchy: T1 must be below T2_onset
    if result.t1_watts and result.t2_onset_watts:
        if result.t1_watts >= result.t2_onset_watts:
            result.analysis_notes.append("⚠️ Hierarchy violated: T1 >= T2_onset")
            result.t1_watts = None
            t1_det.confidence = 0

    # CPET correlations
    if vt1_watts and result.t1_watts:
        result.vt1_correlation_watts = abs(result.t1_watts - vt1_watts)

    if rcp_onset_watts and result.t2_onset_watts:
        result.rcp_onset_correlation_watts = abs(result.t2_onset_watts - rcp_onset_watts)

    # Overall confidence (0-100)
    total_confidence = t1_det.confidence + t2_det.confidence
    if result.t1_watts and result.t2_onset_watts:
        total_confidence += 20
    total_confidence = min(100, total_confidence)

    # Agreement level
    systemic_count = sum([t1_det.is_systemic, t2_det.is_systemic])

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

    return total_confidence


def _build_zones(result: SmO2ThresholdResult, max_power: float) -> None:
    """Build 4-domain training zones from detected thresholds."""
    max_power_int = int(max_power)
    zones: List[Dict] = []

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    df, smo2_col, power_col, hr_col, time_col = _normalize_columns(
        df,
        smo2_col,
        power_col,
        hr_col,
        time_col,
    )

    # Validate required columns
    error = _validate_required_columns(df, smo2_col, power_col)
    if error:
        result.analysis_notes.append(error)
        return result

    # Preprocess signal
    df, max_power, has_hr, hr_max = _preprocess_signal(
        df,
        smo2_col,
        power_col,
        time_col,
        step_duration_sec,
        hr_col,
        hr_max,
    )

    # Aggregate by step
    step_df = _aggregate_steps(
        df,
        power_col,
        hr_col,
        time_col,
        has_hr,
        result.analysis_notes,
    )
    if step_df is None:
        return result

    # Compute derivatives
    _compute_derivatives(step_df)

    # Detect T1
    t1_det = _detect_t1(step_df, vt1_watts, max_power)
    result.analysis_notes.extend(t1_det.notes)
    _apply_t1_to_result(result, step_df, t1_det)

    # Detect T2 onset
    t2_det = _detect_t2_onset(step_df, t1_det, vt1_watts, rcp_onset_watts, max_power)
    result.analysis_notes.extend(t2_det.notes)
    _apply_t2_onset_to_result(result, step_df, t2_det)

    # Ramp test note: no T2_steady
    result.analysis_notes.append(
        "ℹ️ T2_steady N/A w teście rampowym (brak plateau do detekcji MLSS_local)"
    )

    # Validate hierarchy and compute confidence
    total_confidence = _validate_and_score(
        result,
        t1_det,
        t2_det,
        vt1_watts,
        rcp_onset_watts,
    )

    # Build training zones
    _build_zones(result, max_power)
    result.step_data = step_df.to_dict("records")

    result.analysis_notes.append(
        f"Ramp Test Pipeline: T1+T2_onset only, no T2_steady. Confidence: {total_confidence}%."
    )

    return result


__all__ = [
    "SmO2ThresholdResult",
    "detect_smo2_thresholds_moxy",
]
