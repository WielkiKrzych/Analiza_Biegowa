"""
SmO2 Four-Phase Temporal Model.

Based on Contreras-Briceno et al. (2023, PMC10232742) and Bhambhani (2004):
Phase 1: Initial increase (vasodilation > extraction)
Phase 2: Linear/exponential decrease (extraction > delivery)
Phase 3: Plateau at minimal SmO2 (maximal extraction)
Phase 4: Recovery overshoot (post-exercise hyperemia)

Also implements SmO2 slope classification for sustainable vs unsustainable
intensity detection (Rodriguez et al. 2023, PMC10108753).
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class SmO2PhaseResult:
    """Results from 4-phase SmO2 temporal analysis."""
    phases: List[Dict] = field(default_factory=list)
    phase_boundaries: List[int] = field(default_factory=list)
    min_smo2: float = 0.0
    max_smo2: float = 0.0
    desaturation_magnitude: float = 0.0
    recovery_rate_pct_per_min: float = 0.0
    is_valid: bool = False
    notes: List[str] = field(default_factory=list)


def detect_smo2_phases(
    smo2_series: pd.Series,
    time_series: Optional[pd.Series] = None,
    min_phase_duration_sec: int = 30,
) -> SmO2PhaseResult:
    """Detect the four physiological phases in SmO2 temporal response.

    Args:
        smo2_series: SmO2 values (%) at 1Hz
        time_series: Time in seconds (optional, defaults to 0..N)
        min_phase_duration_sec: Minimum samples per phase

    Returns:
        SmO2PhaseResult with detected phases and boundaries
    """
    result = SmO2PhaseResult()

    smo2 = smo2_series.dropna().values.astype(float)
    if len(smo2) < min_phase_duration_sec * 4:
        result.notes.append("Insufficient data for phase detection")
        return result

    time = time_series.values[:len(smo2)] if time_series is not None else np.arange(len(smo2))

    # Smooth for phase detection (60s rolling median — robust to spikes)
    window = min(61, len(smo2) // 4)
    if window % 2 == 0:
        window += 1
    smo2_smooth = pd.Series(smo2).rolling(window, center=True, min_periods=1).median().values

    # Compute rate of change (first derivative, smoothed)
    dsmo2 = np.gradient(smo2_smooth)
    dsmo2_smooth = pd.Series(dsmo2).rolling(31, center=True, min_periods=1).mean().values

    result.min_smo2 = float(np.nanmin(smo2))
    result.max_smo2 = float(np.nanmax(smo2))
    result.desaturation_magnitude = float(result.max_smo2 - result.min_smo2)

    # Phase detection using sign changes in derivative
    # Phase 1: dsmo2 > 0 (initial rise or stable)
    # Phase 2: dsmo2 < 0 (desaturation)
    # Phase 3: dsmo2 ≈ 0 at low SmO2 (plateau)
    # Phase 4: dsmo2 > 0 after minimum (recovery)

    n = len(smo2_smooth)
    min_idx = int(np.argmin(smo2_smooth[n // 4:]) + n // 4)  # skip first quarter for min search

    # Find Phase 1→2 boundary: first sustained negative slope after start
    phase1_end = min_phase_duration_sec
    for i in range(min_phase_duration_sec, min(min_idx, n)):
        segment = dsmo2_smooth[i:i + min_phase_duration_sec]
        if len(segment) >= min_phase_duration_sec and np.mean(segment) < -0.01:
            phase1_end = i
            break

    # Find Phase 2→3 boundary: where slope flattens near minimum
    threshold_flat = 0.005  # near-zero derivative
    phase2_end = min_idx
    for i in range(max(phase1_end + min_phase_duration_sec, min_idx - 300), min_idx + 1):
        segment = dsmo2_smooth[i:i + min_phase_duration_sec]
        if len(segment) >= min_phase_duration_sec and abs(np.mean(segment)) < threshold_flat:
            phase2_end = i
            break

    # Find Phase 3→4 boundary: sustained positive slope after minimum
    phase3_end = min(min_idx + min_phase_duration_sec, n - 1)
    for i in range(min_idx, n - min_phase_duration_sec):
        segment = dsmo2_smooth[i:i + min_phase_duration_sec]
        if len(segment) >= min_phase_duration_sec and np.mean(segment) > 0.02:
            phase3_end = i
            break

    boundaries = sorted(set([0, phase1_end, phase2_end, phase3_end, n - 1]))
    result.phase_boundaries = boundaries

    phase_names = ["Phase 1: Rise", "Phase 2: Desaturation", "Phase 3: Plateau", "Phase 4: Recovery"]
    for idx in range(min(len(boundaries) - 1, 4)):
        start, end = boundaries[idx], boundaries[idx + 1]
        if end <= start:
            continue
        seg = smo2_smooth[start:end]
        slope, _, r, _, _ = stats.linregress(np.arange(len(seg)), seg) if len(seg) > 2 else (0, 0, 0, 0, 0)
        result.phases.append({
            "name": phase_names[idx] if idx < len(phase_names) else f"Phase {idx + 1}",
            "start_sec": int(time[start]) if start < len(time) else start,
            "end_sec": int(time[min(end, len(time) - 1)]),
            "duration_sec": int(time[min(end, len(time) - 1)] - time[start]) if start < len(time) else end - start,
            "mean_smo2": float(np.mean(seg)),
            "slope_pct_per_sec": float(slope),
            "r_squared": float(r ** 2),
        })

    # Recovery rate: SmO2 rise in Phase 4
    if len(result.phases) >= 4:
        p4 = result.phases[3]
        if p4["duration_sec"] > 0:
            result.recovery_rate_pct_per_min = p4["slope_pct_per_sec"] * 60.0

    result.is_valid = len(result.phases) >= 3
    return result


def classify_smo2_slope(
    smo2_series: pd.Series,
    window_sec: int = 120,
) -> pd.Series:
    """Classify SmO2 slope as sustainable or unsustainable intensity.

    Positive slope → delivery > extraction → sustainable (below CS/CP)
    Negative slope → extraction > delivery → unsustainable (above CS/CP)
    Near-zero → at threshold

    Args:
        smo2_series: SmO2 values at 1Hz
        window_sec: Rolling window for slope calculation

    Returns:
        Series of classifications: "sustainable", "threshold", "unsustainable"
    """
    smo2 = smo2_series.astype(float)
    n = len(smo2)
    classifications = pd.Series(["unknown"] * n, index=smo2_series.index)

    if n < window_sec:
        return classifications

    # Rolling linear regression slope
    slopes = np.full(n, np.nan)
    half_w = window_sec // 2
    x = np.arange(window_sec, dtype=float)

    for i in range(half_w, n - half_w):
        y = smo2.iloc[i - half_w:i + half_w].values
        valid = ~np.isnan(y)
        if valid.sum() > window_sec // 2:
            s, _, _, _, _ = stats.linregress(x[:valid.sum()], y[valid])
            slopes[i] = s

    slopes_series = pd.Series(slopes, index=smo2_series.index)

    # Classification thresholds (% per second)
    classifications[slopes_series > 0.005] = "sustainable"
    classifications[(slopes_series >= -0.005) & (slopes_series <= 0.005)] = "threshold"
    classifications[slopes_series < -0.005] = "unsustainable"

    return classifications


def calculate_smo2_recovery_halftime(
    smo2_series: pd.Series,
    exercise_end_idx: Optional[int] = None,
) -> Dict:
    """Calculate half-time of SmO2 reoxygenation after exercise.

    Faster reoxygenation indicates better aerobic fitness and
    capillary density. Reference: Contreras-Briceno et al. 2023.

    Args:
        smo2_series: SmO2 values at 1Hz
        exercise_end_idx: Index where exercise ends (auto-detected if None)

    Returns:
        dict with halftime_sec, baseline, nadir, recovery_magnitude
    """
    smo2 = smo2_series.dropna().values.astype(float)
    if len(smo2) < 60:
        return {"halftime_sec": None, "is_valid": False}

    # Auto-detect exercise end: find the global minimum in last third
    if exercise_end_idx is None:
        search_start = len(smo2) * 2 // 3
        exercise_end_idx = search_start + int(np.argmin(smo2[search_start:]))

    nadir = float(smo2[exercise_end_idx])
    recovery = smo2[exercise_end_idx:]

    if len(recovery) < 30:
        return {"halftime_sec": None, "is_valid": False}

    # Baseline: mean of last 30s of recovery (or available data)
    baseline = float(np.mean(recovery[-min(30, len(recovery)):]))
    target = nadir + (baseline - nadir) * 0.5

    # Find halftime: first index where SmO2 >= target
    halftime_sec = None
    for i, val in enumerate(recovery):
        if val >= target:
            halftime_sec = i
            break

    return {
        "halftime_sec": halftime_sec,
        "nadir_pct": nadir,
        "baseline_pct": baseline,
        "recovery_magnitude_pct": baseline - nadir,
        "is_valid": halftime_sec is not None,
        "classification": (
            "excellent" if halftime_sec is not None and halftime_sec < 30
            else "good" if halftime_sec is not None and halftime_sec < 60
            else "average" if halftime_sec is not None and halftime_sec < 120
            else "slow"
        ),
    }
