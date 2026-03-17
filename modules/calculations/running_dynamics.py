"""
Running Dynamics Analysis Module.

Analyzes biomechanical metrics from Garmin/Stryd:
- Cadence (SPM - steps per minute)
- Ground Contact Time (GCT)
- Vertical Oscillation
- Stride Length
- Running Effectiveness
"""

from typing import Dict, Optional, Union, Any
import numpy as np
import pandas as pd
from .pace_utils import pace_to_speed, pace_array_to_speed_array


def calculate_cadence_stats(cadence_spm: np.ndarray) -> Dict:
    """Calculate cadence statistics."""
    # Running cadence filter: 120-300 SPM (running minimum ~120 vs cycling ~50)
    valid_cadence = cadence_spm[(cadence_spm > 120) & (cadence_spm < 300)]

    if len(valid_cadence) == 0:
        return {"mean_spm": 0.0, "std_spm": 0.0, "zone": "unknown"}

    mean_spm = float(np.mean(valid_cadence))
    std_spm = float(np.std(valid_cadence))

    if mean_spm < 160:
        zone = "low"
    elif mean_spm < 170:
        zone = "low-moderate"
    elif mean_spm < 180:
        zone = "optimal"
    elif mean_spm < 190:
        zone = "high"
    else:
        zone = "very-high"

    return {
        "mean_spm": round(mean_spm, 1),
        "std_spm": round(std_spm, 1),
        "min_spm": int(np.min(valid_cadence)),
        "max_spm": int(np.max(valid_cadence)),
        "zone": zone,
        "cv_pct": round(std_spm / mean_spm * 100, 1) if mean_spm > 0 else 0
    }


def classify_gct(gct_ms: float, pace_sec_per_km: float) -> str:
    """Classify GCT normalized for pace.

    GCT naturally increases at slower paces.  Reference values are for
    ~4:30/km.  We normalize by scaling thresholds linearly with pace ratio.

    Args:
        gct_ms: Ground contact time in milliseconds.
        pace_sec_per_km: Current pace in sec/km.

    Returns:
        Classification string.
    """
    reference_pace = 270.0  # 4:30/km in seconds
    if pace_sec_per_km <= 0:
        pace_sec_per_km = reference_pace

    pace_ratio = pace_sec_per_km / reference_pace

    # Scale thresholds by pace ratio (slower pace -> higher acceptable GCT)
    if gct_ms < 200 * pace_ratio:
        return "excellent"
    elif gct_ms < 220 * pace_ratio:
        return "good"
    elif gct_ms < 240 * pace_ratio:
        return "average"
    else:
        return "needs-improvement"


def calculate_gct_stats(gct_ms: np.ndarray, pace_sec_per_km: Optional[np.ndarray] = None) -> Dict:
    """Calculate Ground Contact Time statistics with optional pace normalization.

    Args:
        gct_ms: GCT values in milliseconds.
        pace_sec_per_km: Optional matching pace array for pace-normalized classification.
    """
    valid_gct = gct_ms[(gct_ms > 100) & (gct_ms < 400)]

    if len(valid_gct) == 0:
        return {"mean_ms": 0.0, "classification": "unknown"}

    mean_ms = float(np.mean(valid_gct))

    # Use pace-normalized classification if pace is available
    if pace_sec_per_km is not None:
        valid_pace = pace_sec_per_km[(gct_ms > 100) & (gct_ms < 400)]
        if len(valid_pace) > 0:
            mean_pace = float(np.mean(valid_pace[(valid_pace > 0) & (~np.isnan(valid_pace))]))
        else:
            mean_pace = 0.0
        classification = classify_gct(mean_ms, mean_pace) if mean_pace > 0 else classify_gct(mean_ms, 270.0)
    else:
        classification = classify_gct(mean_ms, 270.0)

    return {
        "mean_ms": round(mean_ms, 1),
        "std_ms": round(float(np.std(valid_gct)), 1),
        "min_ms": int(np.min(valid_gct)),
        "max_ms": int(np.max(valid_gct)),
        "classification": classification
    }


def calculate_stride_metrics(df_pl: Union[pd.DataFrame, Any], runner_height: float) -> Dict:
    """Calculate step length and related metrics.

    Garmin reports cadence as steps per minute (SPM) where each foot strike
    is one step.  One stride = two steps (left + right).

    step_length = speed / (cadence_spm / 60)
    stride_length = 2 * step_length = speed / (cadence_spm / 60 / 2)

    If FIT data contains a real ``step_length`` column from the running
    dynamics pod, that value is preferred over derived calculation.
    """
    df = df_pl if isinstance(df_pl, pd.DataFrame) else df_pl.to_pandas()

    if "cadence" not in df.columns or "pace" not in df.columns:
        return {}

    valid = df[(df["cadence"] > 120) & (df["cadence"] < 300) & (df["pace"] > 0)]

    if len(valid) == 0:
        return {}

    # Prefer FIT-native step_length if available
    if "step_length" in valid.columns:
        raw_step = valid["step_length"].dropna()
        # Garmin step_length is in meters (typically 0.6-1.6m)
        raw_step = raw_step[(raw_step > 0.3) & (raw_step < 2.5)]
        if len(raw_step) > 0:
            mean_step = float(np.mean(raw_step))
            mean_stride = mean_step * 2.0  # stride = 2 steps
            height_m = runner_height / 100
            return {
                "step_length_m": round(mean_step, 3),
                "stride_length_m": round(mean_stride, 3),
                "stride_length_std_m": round(float(np.std(raw_step)) * 2, 3),
                "height_ratio": round(mean_stride / height_m, 2) if height_m > 0 else 0,
                "samples": len(raw_step),
                "source": "FIT"
            }

    speed_m_s = pace_array_to_speed_array(valid["pace"].values)
    cadence_spm = valid["cadence"].values

    # step_length = speed / steps_per_second
    # Garmin SPM = total steps/min (each foot contact = 1 step)
    step_length_m = speed_m_s / (cadence_spm / 60.0)
    stride_length_m = step_length_m * 2.0  # stride = left + right

    mean_step = float(np.mean(step_length_m))
    mean_stride = float(np.mean(stride_length_m))
    height_m = runner_height / 100

    return {
        "step_length_m": round(mean_step, 3),
        "stride_length_m": round(mean_stride, 3),
        "stride_length_std_m": round(float(np.std(stride_length_m)), 3),
        "height_ratio": round(mean_stride / height_m, 2) if height_m > 0 else 0,
        "samples": len(valid),
        "source": "derived"
    }


def analyze_cadence_drift(cadence_spm: np.ndarray, min_samples: int = 100) -> Dict:
    """Analyze cadence drift over workout."""
    # Running cadence filter: 120-300 SPM
    valid = cadence_spm[(cadence_spm > 120) & (cadence_spm < 300)]

    if len(valid) < min_samples:
        return {"drift_spm": 0.0, "classification": "insufficient-data"}

    mid = len(valid) // 2
    mean_first = float(np.mean(valid[:mid]))
    mean_second = float(np.mean(valid[mid:]))

    drift_spm = mean_second - mean_first
    drift_pct = (drift_spm / mean_first) * 100 if mean_first > 0 else 0

    if drift_pct < -5:
        classification = "significant-drop"
    elif drift_pct < -2:
        classification = "moderate-drop"
    elif drift_pct < 2:
        classification = "stable"
    else:
        classification = "increased"

    return {
        "drift_spm": round(drift_spm, 1),
        "drift_pct": round(drift_pct, 1),
        "classification": classification
    }


def calculate_running_effectiveness(pace_sec_per_km: float, running_power: float, weight_kg: float) -> float:
    """Calculate Running Effectiveness (RE). RE = Speed (m/s) / Power (W/kg)."""
    if pace_sec_per_km <= 0 or running_power <= 0 or weight_kg <= 0:
        return 0.0

    speed = pace_to_speed(pace_sec_per_km)
    power_per_kg = running_power / weight_kg

    return speed / power_per_kg


def calculate_vo_stats(vo_cm: np.ndarray) -> Dict:
    """Calculate Vertical Oscillation statistics.

    Args:
        vo_cm: Vertical oscillation in centimeters

    Returns:
        Dict with VO statistics
    """
    # Filter physiologically valid VO range: 2-20 cm
    valid_vo = vo_cm[(~np.isnan(vo_cm)) & (vo_cm >= 2.0) & (vo_cm <= 20.0)]
    if len(valid_vo) == 0:
        return {}

    mean_vo = float(np.mean(valid_vo))

    return {
        "mean_vo": round(mean_vo, 1),
        "min_vo": round(float(np.min(valid_vo)), 1),
        "max_vo": round(float(np.max(valid_vo)), 1),
        "std_vo": round(float(np.std(valid_vo)), 1),
        "cv_vo": round(float(np.std(valid_vo)) / mean_vo * 100, 1) if mean_vo > 0 else 0,
    }


def analyze_vo_efficiency(vo_cm: np.ndarray, cadence_spm: np.ndarray) -> Dict:
    """
    Analyze running efficiency based on VO and cadence.

    Lower VO at same cadence = better efficiency (less bouncing).
    """
    # Filter valid data (including VO range 2-20 cm)
    mask = (~np.isnan(vo_cm)) & (~np.isnan(cadence_spm)) & (cadence_spm > 0) & (vo_cm >= 2.0) & (vo_cm <= 20.0)
    if mask.sum() < 10:
        return {}

    vo_valid = vo_cm[mask]
    cad_valid = cadence_spm[mask]

    # Calculate VO per cadence bin
    cad_bins = np.arange(140, 200, 10)  # 140-200 SPM
    vo_by_cadence = {}

    for i, cad_start in enumerate(cad_bins[:-1]):
        cad_end = cad_bins[i+1]
        mask_bin = (cad_valid >= cad_start) & (cad_valid < cad_end)
        if mask_bin.sum() > 5:
            vo_by_cadence[f"{cad_start}-{cad_end}"] = round(float(np.mean(vo_valid[mask_bin])), 1)

    return {
        "vo_by_cadence": vo_by_cadence,
        "optimal_cadence": _find_optimal_cadence(vo_by_cadence),
    }


def _find_optimal_cadence(vo_by_cadence: Dict) -> Optional[str]:
    """Find cadence range with lowest VO."""
    if not vo_by_cadence:
        return None
    return min(vo_by_cadence.items(), key=lambda x: x[1])[0]


def calculate_running_effectiveness_from_vo(
    pace_sec_per_km: float,
    vo_cm: float,
    runner_height_cm: float
) -> Dict:
    """
    Calculate running effectiveness using Vertical Oscillation.

    Lower VO relative to height = better efficiency.
    """
    if pace_sec_per_km <= 0 or vo_cm <= 0 or runner_height_cm <= 0:
        return {}

    # VO as percentage of height
    vo_percent_height = (vo_cm / runner_height_cm) * 100

    # Calculate effectiveness score (0-100)
    if vo_percent_height < 5:
        score = 100
    elif vo_percent_height < 10:
        score = 100 - (vo_percent_height - 5) * 10
    else:
        score = max(0, 50 - (vo_percent_height - 10) * 5)

    return {
        "vo_percent_height": round(vo_percent_height, 2),
        "effectiveness_score": round(score, 1),
        "classification": _classify_vo_efficiency(vo_percent_height),
    }


def _classify_vo_efficiency(vo_percent_height: float) -> str:
    """Classify VO efficiency."""
    if vo_percent_height < 5:
        return "elite"
    elif vo_percent_height < 6.5:
        return "very-good"
    elif vo_percent_height < 8:
        return "good"
    elif vo_percent_height < 10:
        return "average"
    else:
        return "needs-improvement"
