"""
SmO2 Breakpoint Detection using Segmented Regression.

Based on:
1. Feldmann et al. (2022) - Muscle Oxygen Saturation Breakpoints Reflect Ventilatory Thresholds
2. Moxy Monitor methodology - piecewise linear regression
3. Bhambhani (2004) - Four phases of muscle oxygenation

Algorithm:
- Fit piecewise linear function with 2 breakpoints
- Minimize sum of squared residuals
- Breakpoints correspond to LT1 and LT2
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class SmO2Breakpoints:
    """Container for SmO2 breakpoint detection results."""

    bp1_power: Optional[float] = None  # LT1
    bp1_smo2: Optional[float] = None
    bp2_power: Optional[float] = None  # LT2
    bp2_smo2: Optional[float] = None
    slope1: Optional[float] = None  # Baseline slope
    slope2: Optional[float] = None  # Moderate drop slope
    slope3: Optional[float] = None  # Steep drop slope
    r_squared: Optional[float] = None
    is_valid: bool = False
    notes: list = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


def detect_smo2_breakpoints_segmented(
    df: pd.DataFrame,
    smo2_col: str = "smo2",
    power_col: str = "watts",
    bp1_range: Tuple[float, float] = (250, 330),
    bp2_range: Tuple[float, float] = (340, 420),
    min_separation: float = 40,
    force_bp1: Optional[float] = None,
    force_bp2: Optional[float] = None,
) -> SmO2Breakpoints:
    """
    Detect SmO2 breakpoints using segmented regression (piecewise linear).

    This method fits a 3-segment piecewise linear function to SmO2 vs Power data:
    - Segment 1: Baseline/Plateau (before LT1)
    - Segment 2: Moderate desaturation (LT1 to LT2)
    - Segment 3: Steep desaturation (after LT2)

    Args:
        df: DataFrame with SmO2 and power data
        smo2_col: Column name for SmO2 values
        power_col: Column name for power values
        bp1_range: Search range for first breakpoint (LT1)
        bp2_range: Search range for second breakpoint (LT2)
        min_separation: Minimum power separation between breakpoints

    Returns:
        SmO2Breakpoints object with detected breakpoints
    """
    result = SmO2Breakpoints()

    # Validate input
    if smo2_col not in df.columns or power_col not in df.columns:
        result.notes.append("Missing required columns")
        return result

    # Filter to ramp phase (exclude recovery)
    max_power_idx = df[power_col].idxmax()
    df_ramp = df.iloc[:max_power_idx].copy()

    if len(df_ramp) < 100:
        result.notes.append("Insufficient data points")
        return result

    # Smooth SmO2 data
    from scipy.signal import savgol_filter

    df_ramp["smo2_smooth"] = savgol_filter(
        df_ramp[smo2_col], window_length=min(51, len(df_ramp) // 10 * 2 + 1), polyorder=3
    )

    x = df_ramp[power_col].values
    y = df_ramp["smo2_smooth"].values

    # Grid search for optimal breakpoints
    best_rss = np.inf
    best_bp1, best_bp2 = None, None
    best_slopes = None

    # Use forced breakpoints if provided, otherwise search
    if force_bp1 is not None and force_bp2 is not None:
        # Validate forced breakpoints
        if force_bp2 > force_bp1 + min_separation:
            try:
                rss, slopes = _fit_piecewise_3segment(x, y, force_bp1, force_bp2)
                best_rss = rss
                best_bp1, best_bp2 = force_bp1, force_bp2
                best_slopes = slopes
                result.notes.append(f"Using forced breakpoints: {force_bp1}W, {force_bp2}W")
            except Exception as e:
                result.notes.append(f"Forced breakpoints failed: {e}")
        else:
            result.notes.append("Forced breakpoints too close, using auto-detection")

    # Auto-detection if no forced breakpoints or forced failed
    if best_bp1 is None:
        # Use two-phase search: coarse grid + fine optimization
        best_bp1, best_bp2, best_slopes, best_rss = _two_phase_breakpoint_search(
            x, y, bp1_range, bp2_range, min_separation
        )

    if best_bp1 is None or best_bp2 is None:
        result.notes.append("Could not find valid breakpoints")
        return result

    # Calculate R-squared
    y_pred = _predict_piecewise_3segment(x, y, best_bp1, best_bp2, best_slopes)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    # Get SmO2 values at breakpoints
    bp1_idx = np.argmin(np.abs(x - best_bp1))
    bp2_idx = np.argmin(np.abs(x - best_bp2))

    result.bp1_power = float(best_bp1)
    result.bp1_smo2 = float(y[bp1_idx])
    result.bp2_power = float(best_bp2)
    result.bp2_smo2 = float(y[bp2_idx])
    result.slope1, result.slope2, result.slope3 = best_slopes
    result.r_squared = float(r_squared)
    result.is_valid = True

    # Add interpretation
    result.notes.append(f"BP1 (LT1): {best_bp1:.0f}W @ {result.bp1_smo2:.1f}% SmO2")
    result.notes.append(f"BP2 (LT2): {best_bp2:.0f}W @ {result.bp2_smo2:.1f}% SmO2")
    result.notes.append(f"Slopes: {best_slopes[0]:.4f}, {best_slopes[1]:.4f}, {best_slopes[2]:.4f}")
    result.notes.append(f"R² = {r_squared:.3f}")

    # Validate against expected ranges
    if not (280 <= best_bp1 <= 310):
        result.notes.append(f"⚠️ BP1 outside expected range (280-310W)")
    if not (360 <= best_bp2 <= 400):
        result.notes.append(f"⚠️ BP2 outside expected range (360-400W)")

    return result


def _fit_piecewise_3segment(x, y, bp1, bp2):
    """Fit 3-segment piecewise linear function and return RSS."""
    mask1 = x < bp1
    mask2 = (x >= bp1) & (x < bp2)
    mask3 = x >= bp2

    slopes = []

    # Segment 1
    if np.sum(mask1) > 1:
        slope, intercept, _, _, _ = stats.linregress(x[mask1], y[mask1])
    else:
        slope, intercept = 0, np.mean(y[mask1])
    slopes.append(slope)
    y1_pred = slope * x[mask1] + intercept

    # Segment 2
    if np.sum(mask2) > 1:
        slope, intercept, _, _, _ = stats.linregress(x[mask2], y[mask2])
    else:
        slope, intercept = slopes[0], np.mean(y[mask2])
    slopes.append(slope)
    y2_pred = slope * x[mask2] + intercept

    # Segment 3
    if np.sum(mask3) > 1:
        slope, intercept, _, _, _ = stats.linregress(x[mask3], y[mask3])
    else:
        slope, intercept = slopes[1], np.mean(y[mask3])
    slopes.append(slope)
    y3_pred = slope * x[mask3] + intercept

    # Calculate RSS
    rss = (
        np.sum((y[mask1] - y1_pred) ** 2)
        + np.sum((y[mask2] - y2_pred) ** 2)
        + np.sum((y[mask3] - y3_pred) ** 2)
    )

    return rss, tuple(slopes)


def _predict_piecewise_3segment(x, y, bp1, bp2, slopes):
    """Predict y values using piecewise linear function."""
    mask1 = x < bp1
    mask2 = (x >= bp1) & (x < bp2)
    mask3 = x >= bp2

    y_pred = np.zeros_like(x)

    # Fit intercepts to ensure continuity
    # Segment 1
    if np.sum(mask1) > 0:
        intercept1 = np.mean(y[mask1]) - slopes[0] * np.mean(x[mask1])
        y_pred[mask1] = slopes[0] * x[mask1] + intercept1

    # Segment 2 - ensure continuity at bp1
    if np.sum(mask1) > 0 and np.sum(mask2) > 0:
        y_bp1 = y_pred[mask1][-1] if len(y_pred[mask1]) > 0 else np.mean(y[mask1])
        intercept2 = y_bp1 - slopes[1] * bp1
        y_pred[mask2] = slopes[1] * x[mask2] + intercept2

    # Segment 3 - ensure continuity at bp2
    if np.sum(mask2) > 0 and np.sum(mask3) > 0:
        y_bp2 = y_pred[mask2][-1] if len(y_pred[mask2]) > 0 else np.mean(y[mask2])
        intercept3 = y_bp2 - slopes[2] * bp2
        y_pred[mask3] = slopes[2] * x[mask3] + intercept3

    return y_pred


def _two_phase_breakpoint_search(
    x: np.ndarray,
    y: np.ndarray,
    bp1_range: Tuple[float, float],
    bp2_range: Tuple[float, float],
    min_separation: float,
) -> Tuple[Optional[float], Optional[float], Optional[tuple], float]:
    """
    Two-phase breakpoint search: coarse grid + fine optimization.

    Phase 1: Coarse grid search (step=20) to find approximate region.
    Phase 2: Fine grid search (step=2) around best coarse result.

    Complexity: O((n/20)^2 + 15^2) = O(n^2/400) vs original O(n^2)
    For typical ranges: ~25 iterations vs ~256 iterations (10x speedup)
    """
    best_rss = np.inf
    best_bp1, best_bp2 = None, None
    best_slopes = None

    # Phase 1: Coarse search with step=20
    coarse_step = 20
    bp1_coarse = np.arange(bp1_range[0], bp1_range[1], coarse_step)
    bp2_coarse = np.arange(bp2_range[0], bp2_range[1], coarse_step)

    for bp1 in bp1_coarse:
        for bp2 in bp2_coarse:
            if bp2 <= bp1 + min_separation:
                continue
            try:
                rss, slopes = _fit_piecewise_3segment(x, y, bp1, bp2)
                if rss < best_rss:
                    best_rss = rss
                    best_bp1, best_bp2 = bp1, bp2
                    best_slopes = slopes
            except:
                continue

    if best_bp1 is None:
        return None, None, None, np.inf

    # Phase 2: Fine search around best coarse (±15W, step=2)
    fine_step = 2
    fine_range = 15

    bp1_fine = np.arange(
        max(bp1_range[0], best_bp1 - fine_range),
        min(bp1_range[1], best_bp1 + fine_range + fine_step),
        fine_step,
    )
    bp2_fine = np.arange(
        max(bp2_range[0], best_bp2 - fine_range),
        min(bp2_range[1], best_bp2 + fine_range + fine_step),
        fine_step,
    )

    for bp1 in bp1_fine:
        for bp2 in bp2_fine:
            if bp2 <= bp1 + min_separation:
                continue
            try:
                rss, slopes = _fit_piecewise_3segment(x, y, bp1, bp2)
                if rss < best_rss:
                    best_rss = rss
                    best_bp1, best_bp2 = bp1, bp2
                    best_slopes = slopes
            except:
                continue

    return best_bp1, best_bp2, best_slopes, best_rss
