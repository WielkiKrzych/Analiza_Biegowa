"""
Power Calculations Module.

Functions for power-based metrics:
- Normalized Power (NP)
- Pulse Power statistics
- Power Duration Curve (PDC)
- Fatigue Resistance Index (FRI)
- Match burns (above-CP efforts)
- Power zone time distribution
- Time to Exhaustion (TTE) estimation
- Athlete phenotype classification
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple, Union

from .common import DEFAULT_PDC_DURATIONS

logger = logging.getLogger(__name__)


# ── Normalized Power ──────────────────────────────────────────

def calculate_normalized_power(
    df: pd.DataFrame, window: int = 30
) -> float:
    """
    Calculate Normalized Power (NP) using Coggan's algorithm.

    NP = 4th root of the mean of rolling 30s power raised to 4th power.

    Args:
        df: DataFrame with 'watts' column (1-second data)
        window: Rolling window in seconds (default 30)

    Returns:
        Normalized Power in watts
    """
    if "watts" not in df.columns or len(df) < window:
        return 0.0

    rolling = df["watts"].rolling(window=window, min_periods=1).mean()
    np_val = np.power(np.nanmean(np.power(rolling, 4)), 0.25)

    return float(np_val) if not np.isnan(np_val) else 0.0


# ── Pulse Power ───────────────────────────────────────────────

def calculate_pulse_power_stats(
    df: pd.DataFrame,
    min_watts: int = 50,
    min_hr: int = 90,
) -> Dict[str, float]:
    """
    Calculate pulse-power statistics (efficiency metrics).

    Pulse Power = watts / heartrate  (for active samples).

    Args:
        df: DataFrame with 'watts' and 'heartrate' columns
        min_watts: Minimum watts to consider active
        min_hr: Minimum HR to consider active

    Returns:
        Dict with avg_pp, max_pp, std_pp
    """
    result = {"avg_pp": 0.0, "max_pp": 0.0, "std_pp": 0.0}

    if "watts" not in df.columns or "heartrate" not in df.columns:
        return result

    mask = (df["watts"] > min_watts) & (df["heartrate"] > min_hr)
    if mask.sum() == 0:
        return result

    pp = df.loc[mask, "watts"] / df.loc[mask, "heartrate"]
    pp = pp.replace([np.inf, -np.inf], np.nan).dropna()

    if len(pp) == 0:
        return result

    result["avg_pp"] = float(pp.mean())
    result["max_pp"] = float(pp.max())
    result["std_pp"] = float(pp.std())
    return result


# ── Power Duration Curve ──────────────────────────────────────

def calculate_power_duration_curve(
    df: pd.DataFrame,
    durations: Optional[List[int]] = None,
) -> Dict[int, float]:
    """
    Calculate the Power Duration Curve (best average power for each duration).

    Args:
        df: DataFrame with 'watts' column (1-second data)
        durations: List of durations in seconds (default: DEFAULT_PDC_DURATIONS)

    Returns:
        Dict mapping duration (seconds) -> best average power (watts)
    """
    if "watts" not in df.columns or len(df) < 1:
        return {}

    if durations is None:
        durations = DEFAULT_PDC_DURATIONS

    watts = df["watts"].values
    pdc: Dict[int, float] = {}

    for dur in durations:
        if dur > len(watts):
            continue
        if dur == 1:
            pdc[dur] = float(np.max(watts))
        else:
            rolling = pd.Series(watts).rolling(window=dur, min_periods=dur).mean()
            best = rolling.max()
            if not np.isnan(best):
                pdc[dur] = float(best)

    return pdc


# ── Fatigue Resistance Index ──────────────────────────────────

def calculate_fatigue_resistance_index(
    pdc: Dict[int, float],
    short_dur: int = 60,
    long_dur: int = 1200,
) -> float:
    """
    Calculate Fatigue Resistance Index (FRI).

    FRI = long_power / short_power × 100
    Higher FRI = better endurance relative to short efforts.

    Args:
        pdc: Power Duration Curve dict
        short_dur: Short-duration key (seconds)
        long_dur: Long-duration key (seconds)

    Returns:
        FRI percentage (0-100+)
    """
    short_power = pdc.get(short_dur, 0)
    long_power = pdc.get(long_dur, 0)

    if short_power <= 0:
        return 0.0

    return round((long_power / short_power) * 100, 1)


def get_fri_interpretation(fri: float) -> str:
    """
    Interpret the Fatigue Resistance Index.

    Args:
        fri: FRI percentage

    Returns:
        Interpretation string
    """
    if fri >= 80:
        return "🟢 Exceptional endurance – diesel engine profile"
    elif fri >= 70:
        return "🟢 Very good fatigue resistance"
    elif fri >= 60:
        return "🟡 Good – solid endurance base"
    elif fri >= 50:
        return "🟡 Average – room for endurance improvement"
    elif fri >= 40:
        return "🟠 Below average – focus on aerobic base"
    else:
        return "🔴 Low fatigue resistance – sprinter profile"


# ── Match Burns ───────────────────────────────────────────────

def count_match_burns(
    df: pd.DataFrame,
    cp: float,
    min_duration: int = 10,
) -> int:
    """
    Count 'match burns' — sustained efforts above CP.

    A match burn is a continuous period above CP lasting at least min_duration seconds.

    Args:
        df: DataFrame with 'watts' column
        cp: Critical Power in watts
        min_duration: Minimum duration in seconds to count as a match

    Returns:
        Number of match burns
    """
    if "watts" not in df.columns or cp <= 0:
        return 0

    above_cp = (df["watts"] > cp).astype(int)
    # Detect contiguous blocks
    blocks = above_cp.diff().fillna(above_cp.iloc[0] if len(above_cp) > 0 else 0)
    starts = blocks[blocks == 1].index.tolist()

    count = 0
    for start_idx in starts:
        # Find end of this block
        remaining = above_cp.loc[start_idx:]
        end_mask = remaining == 0
        if end_mask.any():
            end_idx = end_mask.idxmax()
            duration = end_idx - start_idx
        else:
            duration = len(remaining)

        if duration >= min_duration:
            count += 1

    return count


# ── Power Zones ───────────────────────────────────────────────

def calculate_power_zones_time(
    df: pd.DataFrame,
    cp: float,
    zones: Optional[List[Tuple[float, float]]] = None,
) -> Dict[str, int]:
    """
    Calculate time spent in each power zone.

    Default zones (as fraction of CP):
        Z1: 0-55%, Z2: 55-75%, Z3: 75-90%, Z4: 90-105%,
        Z5: 105-120%, Z6: 120-150%, Z7: 150%+

    Args:
        df: DataFrame with 'watts' column
        cp: Critical Power in watts
        zones: Optional custom zones as list of (lower, upper) fractions of CP

    Returns:
        Dict mapping zone name -> seconds in zone
    """
    if "watts" not in df.columns or cp <= 0:
        return {}

    if zones is None:
        zones = [
            (0.0, 0.55),
            (0.55, 0.75),
            (0.75, 0.90),
            (0.90, 1.05),
            (1.05, 1.20),
            (1.20, 1.50),
            (1.50, float("inf")),
        ]

    result: Dict[str, int] = {}
    watts = df["watts"]

    for i, (lo, hi) in enumerate(zones, 1):
        lo_w = lo * cp
        hi_w = hi * cp
        count = int(((watts >= lo_w) & (watts < hi_w)).sum())
        result[f"Z{i}"] = count

    return result


# ── Time to Exhaustion ────────────────────────────────────────

def estimate_tte(
    target_power: float,
    cp: float,
    w_prime: float,
) -> float:
    """
    Estimate Time to Exhaustion (TTE) at a given power above CP.

    Based on the 2-parameter CP model: TTE = W' / (P - CP)

    Args:
        target_power: Target power in watts
        cp: Critical Power in watts
        w_prime: W' in Joules

    Returns:
        Estimated TTE in seconds (inf if target <= CP)
    """
    if target_power <= cp:
        return float("inf")
    if w_prime <= 0 or cp <= 0:
        return 0.0

    return w_prime / (target_power - cp)


def estimate_tte_range(
    cp: float,
    w_prime: float,
    power_range: Optional[List[float]] = None,
) -> Dict[float, float]:
    """
    Estimate TTE for a range of power outputs.

    Args:
        cp: Critical Power in watts
        w_prime: W' in Joules
        power_range: List of power values (default: CP+10% to CP+100%)

    Returns:
        Dict mapping power -> TTE in seconds
    """
    if power_range is None:
        power_range = [
            cp * frac
            for frac in [1.05, 1.10, 1.20, 1.30, 1.50, 1.75, 2.00]
            if cp * frac > cp
        ]

    return {p: estimate_tte(p, cp, w_prime) for p in power_range}


# ── Phenotype (power-based, re-exported for convenience) ──────

def classify_phenotype(
    vo2max: float,
    vlamax: float,
    anaerobic_reserve_pct: float,
) -> str:
    """
    Classify athlete phenotype based on physiological markers.

    Args:
        vo2max: VO2max in ml/min/kg
        vlamax: VLamax in mmol/L/s
        anaerobic_reserve_pct: Anaerobic reserve as fraction (0-1)

    Returns:
        Phenotype string: 'diesel', 'allrounder', 'sprinter', 'puncher', 'unknown'
    """
    if vo2max <= 0:
        return "unknown"

    if vo2max >= 65 and vlamax < 0.4:
        return "diesel"
    elif vo2max >= 60 and 0.4 <= vlamax < 0.6:
        return "allrounder"
    elif anaerobic_reserve_pct > 0.5 and vlamax >= 0.6:
        return "sprinter"
    elif 50 <= vo2max < 65 and vlamax >= 0.5:
        return "puncher"
    else:
        return "allrounder"


def get_phenotype_description(phenotype: str) -> Tuple[str, str, str]:
    """
    Get emoji, name and description for a phenotype.

    Args:
        phenotype: Phenotype string

    Returns:
        Tuple of (emoji, display_name, description)
    """
    phenotypes = {
        "diesel": (
            "🚂",
            "Diesel Engine",
            "High aerobic capacity with low glycolytic power. "
            "Excels in long, steady efforts.",
        ),
        "allrounder": (
            "⚖️",
            "All-Rounder",
            "Balanced aerobic and anaerobic capacity. "
            "Versatile across different effort types.",
        ),
        "sprinter": (
            "⚡",
            "Sprinter",
            "High anaerobic power with strong glycolytic capacity. "
            "Excels in short, explosive efforts.",
        ),
        "puncher": (
            "🥊",
            "Puncher",
            "Good anaerobic power relative to moderate aerobic base. "
            "Strong in repeated hard efforts.",
        ),
        "marathoner": (
            "🏃",
            "Marathoner",
            "Exceptional endurance with high efficiency. "
            "Built for sustained long-duration efforts.",
        ),
        "unknown": (
            "❓",
            "Unknown",
            "Insufficient data to classify phenotype.",
        ),
    }

    return phenotypes.get(
        phenotype, ("❓", "Unknown", "Phenotype not recognized.")
    )
