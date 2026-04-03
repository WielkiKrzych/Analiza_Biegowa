"""
Heart Rate Zones Module.

Implements three zone models for running:
1. %HRmax - Simple percentage of maximum heart rate
2. Karvonen (%HRR) - Heart Rate Reserve method
3. LTHR-based (Joe Friel) - Lactate Threshold Heart Rate zones

Each model has different use cases:
- %HRmax: Quick setup, less accurate
- Karvonen: Accounts for resting HR, more personalized
- LTHR: Most accurate for trained athletes (Joe Friel methodology)
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import pandas as pd

from .common import ensure_pandas


@dataclass
class HRZoneConfig:
    """Configuration for HR zone calculation."""
    max_hr: float
    resting_hr: float = 60.0
    lthr: Optional[float] = None  # Lactate Threshold HR (for Friel zones)


# Zone definitions for each model
ZONES_HRMAX = {
    "Z1 Recovery": (0.50, 0.60),
    "Z2 Aerobic": (0.60, 0.70),
    "Z3 Tempo": (0.70, 0.80),
    "Z4 Threshold": (0.80, 0.90),
    "Z5 VO2max": (0.90, 1.00),
    "Z6 Anaerobic": (1.00, 1.10),  # Allow slightly above max (measurement error)
}

ZONES_KARVONEN = {
    "Z1 Recovery": (0.00, 0.30),   # 0-30% of HRR
    "Z2 Aerobic": (0.30, 0.50),   # 30-50% of HRR
    "Z3 Tempo": (0.50, 0.70),     # 50-70% of HRR
    "Z4 Threshold": (0.70, 0.85), # 70-85% of HRR
    "Z5 VO2max": (0.85, 0.95),    # 85-95% of HRR
    "Z6 Anaerobic": (0.95, 1.10), # 95-100%+ of HRR
}

ZONES_LTHR = {
    # Joe Friel's LTHR-based zones (Cyclist's Training Bible, adapted for running)
    "Z1 Recovery": (0.00, 0.81),   # <81% LTHR
    "Z2 Aerobic": (0.81, 0.89),    # 81-89% LTHR
    "Z3 Tempo": (0.89, 0.94),      # 89-94% LTHR
    "Z4 Threshold": (0.94, 1.00),  # 94-100% LTHR
    "Z5 VO2max": (1.00, 1.05),     # 100-105% LTHR
    "Z6 Anaerobic": (1.05, 1.20),  # >105% LTHR
}


def calculate_hr_zones_hrmax(hr: float, max_hr: float) -> Dict[str, bool]:
    """Determine which zone a heart rate value falls into using %HRmax.
    
    Args:
        hr: Heart rate in bpm
        max_hr: Maximum heart rate in bpm
    
    Returns:
        Dict mapping zone names to boolean (True if HR in that zone)
    """
    if max_hr <= 0:
        return {}

    hr_pct = hr / max_hr
    zones = {}

    for zone_name, (low_pct, high_pct) in ZONES_HRMAX.items():
        zones[zone_name] = low_pct <= hr_pct < high_pct

    return zones


def calculate_hr_zones_karvonen(hr: float, max_hr: float, resting_hr: float) -> Dict[str, bool]:
    """Determine which zone a heart rate value falls into using Karvonen method.
    
    Karvonen formula: Target HR = Resting HR + (%HRR × (Max HR - Resting HR))
    
    Args:
        hr: Heart rate in bpm
        max_hr: Maximum heart rate in bpm
        resting_hr: Resting heart rate in bpm
    
    Returns:
        Dict mapping zone names to boolean (True if HR in that zone)
    """
    if max_hr <= 0 or resting_hr >= max_hr:
        return {}

    hrr = max_hr - resting_hr  # Heart Rate Reserve
    if hrr <= 0:
        return {}

    # Calculate % of HRR used
    hrr_used = hr - resting_hr
    hrr_pct = hrr_used / hrr if hrr > 0 else 0

    zones = {}
    for zone_name, (low_pct, high_pct) in ZONES_KARVONEN.items():
        zones[zone_name] = low_pct <= hrr_pct < high_pct

    return zones


def calculate_hr_zones_lthr(hr: float, lthr: float) -> Dict[str, bool]:
    """Determine which zone a heart rate value falls into using LTHR method.
    
    Joe Friel's zones based on Lactate Threshold Heart Rate.
    Most accurate for trained athletes.
    
    Args:
        hr: Heart rate in bpm
        lthr: Lactate Threshold Heart Rate in bpm
    
    Returns:
        Dict mapping zone names to boolean (True if HR in that zone)
    """
    if lthr <= 0:
        return {}

    lthr_pct = hr / lthr
    zones = {}

    for zone_name, (low_pct, high_pct) in ZONES_LTHR.items():
        zones[zone_name] = low_pct <= lthr_pct < high_pct

    return zones


def get_hr_zone(hr: float, config: HRZoneConfig, model: str = "auto") -> str:
    """Get the primary zone for a heart rate value.
    
    Args:
        hr: Heart rate in bpm
        config: HRZoneConfig with max_hr, resting_hr, lthr
        model: "hrmax", "karvonen", "lthr", or "auto" (uses LTHR if available, else Karvonen)
    
    Returns:
        Zone name string
    """
    if model == "auto":
        if config.lthr and config.lthr > 0:
            model = "lthr"
        elif config.resting_hr and config.resting_hr > 0:
            model = "karvonen"
        else:
            model = "hrmax"

    if model == "hrmax":
        zones = calculate_hr_zones_hrmax(hr, config.max_hr)
    elif model == "karvonen":
        zones = calculate_hr_zones_karvonen(hr, config.max_hr, config.resting_hr)
    elif model == "lthr":
        if not config.lthr or config.lthr <= 0:
            # Fallback to hrmax if LTHR not available
            zones = calculate_hr_zones_hrmax(hr, config.max_hr)
        else:
            zones = calculate_hr_zones_lthr(hr, config.lthr)
    else:
        zones = calculate_hr_zones_hrmax(hr, config.max_hr)

    # Return the zone that's True
    for zone_name, in_zone in zones.items():
        if in_zone:
            return zone_name

    return "Unknown"


def _resolve_model(config: HRZoneConfig, model: str) -> str:
    """Resolve 'auto' model to a concrete model name."""
    if model != "auto":
        return model
    if config.lthr and config.lthr > 0:
        return "lthr"
    elif config.resting_hr and config.resting_hr > 0:
        return "karvonen"
    else:
        return "hrmax"


def _get_zone_definitions(model: str) -> Dict[str, tuple]:
    """Get zone definitions for a given model."""
    if model == "lthr":
        return ZONES_LTHR
    elif model == "karvonen":
        return ZONES_KARVONEN
    else:
        return ZONES_HRMAX


def _get_absolute_boundaries(
    config: HRZoneConfig, model: str, zone_defs: Dict[str, tuple]
) -> Dict[str, tuple]:
    """Convert zone percentage boundaries to absolute HR bpm values."""
    boundaries = {}
    if model == "hrmax":
        for z, (lo, hi) in zone_defs.items():
            boundaries[z] = (config.max_hr * lo, config.max_hr * hi)
    elif model == "karvonen":
        hrr = max(0, config.max_hr - config.resting_hr)
        for z, (lo, hi) in zone_defs.items():
            boundaries[z] = (config.resting_hr + hrr * lo, config.resting_hr + hrr * hi)
    elif model == "lthr" and config.lthr:
        for z, (lo, hi) in zone_defs.items():
            boundaries[z] = (config.lthr * lo, config.lthr * hi)
    else:
        for z, (lo, hi) in zone_defs.items():
            boundaries[z] = (config.max_hr * lo, config.max_hr * hi)
    return boundaries


def calculate_time_in_hr_zones(
    df_pl: Union[pd.DataFrame, Any],
    config: HRZoneConfig,
    model: str = "auto",
    hr_col: str = "heartrate"
) -> Dict[str, int]:
    """Calculate time spent in each HR zone using vectorized pd.cut.

    Assumes 1Hz (1-second) sampled data — each row = 1 second.

    Args:
        df_pl: DataFrame with heart rate data
        config: HRZoneConfig with max_hr, resting_hr, lthr
        model: "hrmax", "karvonen", "lthr", or "auto"
        hr_col: Column name for heart rate

    Returns:
        Dict mapping zone names to seconds spent
    """
    df = ensure_pandas(df_pl)

    if hr_col not in df.columns:
        return {}

    hr = df[hr_col].dropna()
    if len(hr) == 0:
        return {}

    resolved_model = _resolve_model(config, model)
    zone_defs = _get_zone_definitions(resolved_model)
    boundaries = _get_absolute_boundaries(config, resolved_model, zone_defs)

    # Build bins for pd.cut (vectorized)
    zone_names = list(zone_defs.keys())
    bins = [boundaries[z][0] for z in zone_names] + [boundaries[zone_names[-1]][1]]

    zones = pd.cut(hr, bins=bins, labels=zone_names, right=False, ordered=False)
    counts = zones.value_counts()

    results = {z: int(counts.get(z, 0)) for z in zone_names}
    return results


def get_zone_boundaries(config: HRZoneConfig, model: str = "auto") -> Dict[str, tuple]:
    """Get HR boundaries for each zone in bpm.
    
    Useful for displaying zone ranges in UI.
    
    Args:
        config: HRZoneConfig with max_hr, resting_hr, lthr
        model: "hrmax", "karvonen", "lthr", or "auto"
    
    Returns:
        Dict mapping zone names to (low_bpm, high_bpm) tuples
    """
    if model == "auto":
        if config.lthr and config.lthr > 0:
            model = "lthr"
        elif config.resting_hr and config.resting_hr > 0:
            model = "karvonen"
        else:
            model = "hrmax"

    boundaries = {}
    hrr = config.max_hr - config.resting_hr

    if model == "hrmax":
        for zone_name, (low_pct, high_pct) in ZONES_HRMAX.items():
            boundaries[zone_name] = (
                int(config.max_hr * low_pct),
                int(config.max_hr * high_pct)
            )
    elif model == "karvonen":
        for zone_name, (low_pct, high_pct) in ZONES_KARVONEN.items():
            boundaries[zone_name] = (
                int(config.resting_hr + hrr * low_pct),
                int(config.resting_hr + hrr * high_pct)
            )
    elif model == "lthr" and config.lthr:
        for zone_name, (low_pct, high_pct) in ZONES_LTHR.items():
            boundaries[zone_name] = (
                int(config.lthr * low_pct),
                int(config.lthr * high_pct)
            )
    else:
        # Fallback to hrmax
        for zone_name, (low_pct, high_pct) in ZONES_HRMAX.items():
            boundaries[zone_name] = (
                int(config.max_hr * low_pct),
                int(config.max_hr * high_pct)
            )

    return boundaries


def estimate_lthr_from_threshold_pace(threshold_pace: float, max_hr: float) -> float:
    """Estimate LTHR from threshold pace using typical relationships.
    
    LTHR is typically 90-95% of max HR for trained runners.
    This is a rough estimate - actual LTHR should be determined by testing.
    
    Args:
        threshold_pace: Threshold pace in sec/km
        max_hr: Maximum heart rate in bpm
    
    Returns:
        Estimated LTHR in bpm
    """
    # LTHR is typically 90-95% of max HR for trained runners
    # Use 92% as default
    return max_hr * 0.92


__all__ = [
    "HRZoneConfig",
    "ZONES_HRMAX",
    "ZONES_KARVONEN",
    "ZONES_LTHR",
    "calculate_hr_zones_hrmax",
    "calculate_hr_zones_karvonen",
    "calculate_hr_zones_lthr",
    "get_hr_zone",
    "calculate_time_in_hr_zones",
    "get_zone_boundaries",
    "estimate_lthr_from_threshold_pace",
]
