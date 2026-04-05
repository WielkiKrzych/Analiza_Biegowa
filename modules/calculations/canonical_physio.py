"""
Canonical Physiological Parameters Module.

Single Source of Truth for all physiological metrics across the system.
All UI components, PDF reports, and analysis modules must use this.

This module provides:
- VO2max (canonical value with source tracking)
- VLaMax (estimated)
- CP / FTP
- Weight
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Tri_Dashboard.CanonicalPhysio")


@dataclass
class CanonicalMetric:
    """A metric with source tracking and confidence."""

    value: float = 0.0
    source: str = "none"  # Where the value came from
    confidence: float = 0.0  # 0-1, how reliable this value is
    alternatives: Dict[str, float] = field(default_factory=dict)  # Other estimates

    def is_valid(self) -> bool:
        return self.value > 0 and self.source != "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": round(self.value, 2),
            "source": self.source,
            "confidence": round(self.confidence, 2),
            "alternatives": {k: round(v, 2) for k, v in self.alternatives.items()},
        }


@dataclass
class CanonicalPhysiology:
    """Single Source of Truth for physiological parameters."""

    vo2max: CanonicalMetric = field(default_factory=CanonicalMetric)
    vlamax: CanonicalMetric = field(default_factory=CanonicalMetric)
    cp_watts: CanonicalMetric = field(default_factory=CanonicalMetric)
    ftp_watts: CanonicalMetric = field(default_factory=CanonicalMetric)
    weight_kg: CanonicalMetric = field(default_factory=CanonicalMetric)
    pmax_watts: CanonicalMetric = field(default_factory=CanonicalMetric)
    w_prime_kj: CanonicalMetric = field(default_factory=CanonicalMetric)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vo2max": self.vo2max.to_dict(),
            "vlamax": self.vlamax.to_dict(),
            "cp_watts": self.cp_watts.to_dict(),
            "ftp_watts": self.ftp_watts.to_dict(),
            "weight_kg": self.weight_kg.to_dict(),
            "pmax_watts": self.pmax_watts.to_dict(),
            "w_prime_kj": self.w_prime_kj.to_dict(),
        }


# =============================================================================
# VO2max SELECTION POLICY
# =============================================================================

# Priority order for VO2max sources (higher = preferred)
VO2MAX_SOURCE_PRIORITY = {
    "lab_measured": 1.0,  # Laboratory gas exchange (gold standard)
    "field_cpet": 0.95,  # Field CPET test
    "ramp_test_peak": 0.85,  # Peak from ramp test with VO2 sensor
    "intervals_api": 0.80,  # From Intervals.icu or similar
    "acsm_5min": 0.70,  # ACSM formula from 5-min power
    "acsm_cp": 0.50,  # ACSM formula from CP estimate
    "user_input": 0.60,  # User-provided value
    "estimated": 0.40,  # Generic estimate
    "none": 0.0,
}


def calculate_vo2max_acsm(power_watts: float, weight_kg: float) -> float:
    """
    Calculate VO2max using Sitko et al. 2021 formula.

    VO2max = 16.61 + 8.87 × 5' max power (W/kg)

    This is the CANONICAL formula used throughout the system.
    """
    if power_watts <= 0 or weight_kg <= 0:
        return 0.0
    power_per_kg = power_watts / weight_kg
    return 16.61 + 8.87 * power_per_kg


def select_canonical_vo2max(
    candidates: Dict[str, float], weight_kg: float = 75.0
) -> CanonicalMetric:
    """
    Select canonical VO2max from multiple candidates based on priority.

    Args:
        candidates: Dict of {source: value} pairs
            - "lab_measured": Direct lab measurement
            - "ramp_test_peak": Peak VO2 from ramp test
            - "intervals_api": From external API
            - "mmp_5min": 5-minute max power (will be converted)
            - "cp_watts": Critical Power (will be converted)
            - "user_input": User-provided value

    Returns:
        CanonicalMetric with selected value and alternatives
    """
    metric = CanonicalMetric()
    alternatives = {}

    # Process candidates
    for source, value in candidates.items():
        if value is None or value <= 0:
            continue

        # Convert power-based inputs to VO2max
        if source == "mmp_5min":
            vo2 = calculate_vo2max_acsm(value, weight_kg)
            alternatives["acsm_5min"] = vo2
        elif source == "cp_watts":
            # CP is ~90-95% of 5-min power, so use CP * 1.05 as estimate
            est_5min = value * 1.05
            vo2 = calculate_vo2max_acsm(est_5min, weight_kg)
            alternatives["acsm_cp"] = vo2
        else:
            # Direct VO2max value
            alternatives[source] = value

    if not alternatives:
        return metric

    # Select best candidate based on priority
    best_source = None
    best_priority = -1

    for source, _value in alternatives.items():
        priority = VO2MAX_SOURCE_PRIORITY.get(source, 0.3)
        if priority > best_priority:
            best_priority = priority
            best_source = source

    if best_source:
        metric.value = alternatives[best_source]
        metric.source = best_source
        metric.confidence = best_priority
        # Store all alternatives except the selected one
        metric.alternatives = {k: v for k, v in alternatives.items() if k != best_source}

    return metric


# =============================================================================
# PRIVATE HELPERS — extracted from build_canonical_physiology
# =============================================================================


def _extract_weight(data: Dict[str, Any]) -> Tuple[CanonicalMetric, float]:
    """Extract athlete weight from report data, returning the metric and raw value."""
    weight = data.get("metadata", {}).get("athlete_weight_kg", 0)
    if not weight:
        weight = data.get("athlete", {}).get("weight_kg", 75)
    weight_kg = weight or 75
    metric = CanonicalMetric(
        value=weight_kg,
        source="metadata" if weight else "default",
        confidence=0.95 if weight else 0.3,
    )
    return metric, weight_kg


def _extract_cp_ftp(data: Dict[str, Any]) -> Tuple[float, CanonicalMetric, CanonicalMetric]:
    """Extract CP and FTP from report data.

    Returns (raw_cp, cp_metric, ftp_metric).
    FTP falls back to CP-derived estimate when not directly available.
    """
    cp = data.get("cp_model", {}).get("cp_watts", 0)
    cp_metric = (
        CanonicalMetric(value=cp, source="cp_model", confidence=0.85) if cp else CanonicalMetric()
    )

    ftp = data.get("thresholds", {}).get("ftp_watts", 0)
    if ftp:
        ftp_metric = CanonicalMetric(value=ftp, source="thresholds", confidence=0.80)
    elif cp:
        ftp_metric = CanonicalMetric(value=cp, source="derived_from_cp", confidence=0.70)
    else:
        ftp_metric = CanonicalMetric()

    return cp, cp_metric, ftp_metric


def _extract_w_prime(data: Dict[str, Any]) -> CanonicalMetric:
    """Extract W' (anaerobic work capacity) from CP model data."""
    w_prime_j = data.get("cp_model", {}).get("w_prime_joules", 0)
    if w_prime_j:
        return CanonicalMetric(value=w_prime_j / 1000, source="cp_model", confidence=0.80)
    return CanonicalMetric()


def _extract_pmax(data: Dict[str, Any], time_series: Optional[Dict[str, List]]) -> CanonicalMetric:
    """Extract peak maximal power from metadata or time series."""
    pmax: float = data.get("metadata", {}).get("pmax_watts", 0)
    if not pmax and time_series:
        power_data = time_series.get("power_watts", [])
        if power_data:
            pmax = max(power_data)
    if pmax:
        return CanonicalMetric(value=pmax, source="peak_power", confidence=0.90)
    return CanonicalMetric()


def _compute_mmp_5min(power_data: List[float]) -> float:
    """Compute 5-minute mean maximal power using a rolling window."""
    if len(power_data) < 300:
        return 0.0
    window = 300
    mmp = 0.0
    for i in range(len(power_data) - window + 1):
        avg = sum(power_data[i : i + window]) / window
        if avg > mmp:
            mmp = avg
    return mmp


def _collect_vo2max_candidates(
    data: Dict[str, Any],
    time_series: Optional[Dict[str, List]],
    weight_kg: float,
    cp: float,
) -> Dict[str, float]:
    """Collect VO2max estimates from all available data sources."""
    candidates: Dict[str, float] = {}

    # Source 1: Direct VO2max from metrics (calculated with pandas rolling - SAME AS UI)
    direct_vo2 = data.get("metrics", {}).get("vo2max", 0)
    if direct_vo2 and direct_vo2 > 0:
        candidates["acsm_5min"] = direct_vo2

    # Source 2: From external API (Intervals.icu etc.)
    api_vo2 = data.get("athlete", {}).get("vo2max", 0)
    if api_vo2 and api_vo2 > 0:
        candidates["intervals_api"] = api_vo2

    # Source 3: User input
    user_vo2 = data.get("user_input", {}).get("vo2max", 0)
    if user_vo2 and user_vo2 > 0:
        candidates["user_input"] = user_vo2

    # Source 4: Calculate from 5-min MMP (only if metrics.vo2max is not available)
    if "acsm_5min" not in candidates and time_series and weight_kg > 0:
        power_data = time_series.get("power_watts", [])
        mmp_5m = _compute_mmp_5min(power_data)
        if mmp_5m > 0:
            candidates["mmp_5min"] = mmp_5m

    # Source 5: Estimate from CP (lowest priority)
    if cp > 0:
        candidates["cp_watts"] = cp

    return candidates


def _check_vo2max_divergence(
    vo2max_metric: CanonicalMetric,
    time_series: Optional[Dict[str, List]],
    weight_kg: float,
) -> None:
    """Log a warning when VO2max diverges significantly from time-series estimate."""
    if not vo2max_metric.is_valid() or not time_series or weight_kg <= 0:
        return

    power_data = time_series.get("power_watts", [])
    mmp5 = _compute_mmp_5min(power_data)
    if mmp5 <= 0:
        return

    ts_vo2max = calculate_vo2max_acsm(mmp5, weight_kg)
    divergence = abs(vo2max_metric.value - ts_vo2max)

    if divergence > 5:
        logger.warning(
            f"VO2max divergence detected: metrics={vo2max_metric.value:.1f} vs "
            f"time_series={ts_vo2max:.1f} (Δ={divergence:.1f} ml/kg/min). "
            f"Using metrics (pandas rolling) as canonical."
        )
        vo2max_metric.alternatives["time_series_estimate"] = round(ts_vo2max, 2)


def _estimate_vlamax(cp: float, pmax: float, w_prime_kj: float) -> CanonicalMetric:
    """Estimate VLaMax from power-based anaerobic reserve."""
    if cp <= 0 or pmax <= 0:
        return CanonicalMetric()

    anaerobic_reserve = pmax - cp
    w_prime_kj = w_prime_kj or 15
    w_prime_factor = w_prime_kj / 20
    vlamax = 0.3 + (anaerobic_reserve / pmax) * 0.5 + (w_prime_factor - 1) * 0.1
    vlamax = max(0.2, min(1.0, vlamax))
    return CanonicalMetric(value=vlamax, source="estimated_from_power", confidence=0.50)


# =============================================================================
# PUBLIC API
# =============================================================================


def build_canonical_physiology(
    data: Dict[str, Any], time_series: Optional[Dict[str, List]] = None
) -> CanonicalPhysiology:
    """
    Build canonical physiology from report data.

    This is the SINGLE ENTRY POINT for physiological parameters.
    All modules (UI, PDF, Metabolic Engine) must use this.

    Args:
        data: Report data dictionary (from result.to_dict() or JSON)
        time_series: Optional time series data for power-based calculations

    Returns:
        CanonicalPhysiology with all parameters set
    """
    physio = CanonicalPhysiology()

    physio.weight_kg, weight_kg = _extract_weight(data)
    cp, physio.cp_watts, physio.ftp_watts = _extract_cp_ftp(data)
    physio.w_prime_kj = _extract_w_prime(data)
    physio.pmax_watts = _extract_pmax(data, time_series)

    vo2max_candidates = _collect_vo2max_candidates(data, time_series, weight_kg, cp)
    physio.vo2max = select_canonical_vo2max(vo2max_candidates, weight_kg)
    _check_vo2max_divergence(physio.vo2max, time_series, weight_kg)

    physio.vlamax = _estimate_vlamax(cp, physio.pmax_watts.value, physio.w_prime_kj.value)

    return physio


def format_canonical_for_report(physio: CanonicalPhysiology) -> Dict[str, Any]:
    """Format canonical physiology for JSON storage."""
    return {
        "canonical_physiology": physio.to_dict(),
        "summary": {
            "vo2max": physio.vo2max.value if physio.vo2max.is_valid() else None,
            "vo2max_source": physio.vo2max.source,
            "vlamax": physio.vlamax.value if physio.vlamax.is_valid() else None,
            "cp_watts": physio.cp_watts.value if physio.cp_watts.is_valid() else None,
            "weight_kg": physio.weight_kg.value,
        },
    }


__all__ = [
    "CanonicalMetric",
    "CanonicalPhysiology",
    "calculate_vo2max_acsm",
    "select_canonical_vo2max",
    "build_canonical_physiology",
    "format_canonical_for_report",
    "VO2MAX_SOURCE_PRIORITY",
]
