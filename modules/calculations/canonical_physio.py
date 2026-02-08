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

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import logging

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
            source_key = "acsm_5min"
        elif source == "cp_watts":
            # CP is ~90-95% of 5-min power, so use CP * 1.05 as estimate
            est_5min = value * 1.05
            vo2 = calculate_vo2max_acsm(est_5min, weight_kg)
            alternatives["acsm_cp"] = vo2
            source_key = "acsm_cp"
        else:
            # Direct VO2max value
            alternatives[source] = value
            source_key = source

    if not alternatives:
        return metric

    # Select best candidate based on priority
    best_source = None
    best_priority = -1

    for source, value in alternatives.items():
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

    # === WEIGHT ===
    weight = data.get("metadata", {}).get("athlete_weight_kg", 0)
    if not weight:
        weight = data.get("athlete", {}).get("weight_kg", 75)
    physio.weight_kg = CanonicalMetric(
        value=weight or 75,
        source="metadata" if weight else "default",
        confidence=0.95 if weight else 0.3,
    )
    weight_kg = physio.weight_kg.value

    # === CP / FTP ===
    cp = data.get("cp_model", {}).get("cp_watts", 0)
    if cp:
        physio.cp_watts = CanonicalMetric(value=cp, source="cp_model", confidence=0.85)

    ftp = data.get("thresholds", {}).get("ftp_watts", 0)
    if ftp:
        physio.ftp_watts = CanonicalMetric(value=ftp, source="thresholds", confidence=0.80)
    elif cp:
        physio.ftp_watts = CanonicalMetric(value=cp, source="derived_from_cp", confidence=0.70)

    # === W' ===
    w_prime_j = data.get("cp_model", {}).get("w_prime_joules", 0)
    if w_prime_j:
        physio.w_prime_kj = CanonicalMetric(
            value=w_prime_j / 1000, source="cp_model", confidence=0.80
        )

    # === Pmax ===
    pmax = data.get("metadata", {}).get("pmax_watts", 0)
    if not pmax and time_series:
        power_data = time_series.get("power_watts", [])
        if power_data:
            pmax = max(power_data)
    if pmax:
        physio.pmax_watts = CanonicalMetric(value=pmax, source="peak_power", confidence=0.90)

    # === VO2max (CANONICAL SELECTION) ===
    vo2max_candidates = {}

    # Source 1: Direct VO2max from metrics (calculated with pandas rolling - SAME AS UI)
    # This is the CANONICAL source that matches UI KPI display
    direct_vo2 = data.get("metrics", {}).get("vo2max", 0)
    if direct_vo2 and direct_vo2 > 0:
        vo2max_candidates["acsm_5min"] = direct_vo2  # Use acsm_5min key for proper priority

    # Source 2: From external API (Intervals.icu etc.)
    api_vo2 = data.get("athlete", {}).get("vo2max", 0)
    if api_vo2 and api_vo2 > 0:
        vo2max_candidates["intervals_api"] = api_vo2

    # Source 3: User input
    user_vo2 = data.get("user_input", {}).get("vo2max", 0)
    if user_vo2 and user_vo2 > 0:
        vo2max_candidates["user_input"] = user_vo2

    # Source 4: Calculate from 5-min MMP (ONLY if metrics.vo2max is not available)
    # Note: metrics.vo2max is calculated using pandas rolling (same as UI) so it's preferred
    if "acsm_5min" not in vo2max_candidates and time_series and weight_kg > 0:
        power_data = time_series.get("power_watts", [])
        if len(power_data) >= 300:
            # Find 5-min MMP using rolling window
            window = 300
            mmp_5m = 0
            for i in range(len(power_data) - window + 1):
                avg = sum(power_data[i : i + window]) / window
                if avg > mmp_5m:
                    mmp_5m = avg
            if mmp_5m > 0:
                vo2max_candidates["mmp_5min"] = mmp_5m  # Will be converted

    # Source 5: Estimate from CP (lowest priority)
    if cp and cp > 0:
        vo2max_candidates["cp_watts"] = cp  # Will be converted

    # Select canonical VO2max
    physio.vo2max = select_canonical_vo2max(vo2max_candidates, weight_kg)

    # =========================================================================
    # CONSISTENCY ASSERTION (light - logs divergence, doesn't block)
    # =========================================================================
    if physio.vo2max.is_valid() and time_series and weight_kg > 0:
        # Calculate time_series estimate for comparison
        power_data = time_series.get("power_watts", [])
        if len(power_data) >= 300:
            window = 300
            ts_mmp5 = 0
            for i in range(len(power_data) - window + 1):
                avg = sum(power_data[i : i + window]) / window
                if avg > ts_mmp5:
                    ts_mmp5 = avg
            if ts_mmp5 > 0:
                ts_vo2max = calculate_vo2max_acsm(ts_mmp5, weight_kg)
                divergence = abs(physio.vo2max.value - ts_vo2max)

                # Log if divergence > 5 ml/kg/min (significant)
                if divergence > 5:
                    logger.warning(
                        f"VO2max divergence detected: metrics={physio.vo2max.value:.1f} vs "
                        f"time_series={ts_vo2max:.1f} (Δ={divergence:.1f} ml/kg/min). "
                        f"Using metrics (pandas rolling) as canonical."
                    )
                    # Store divergence for debugging
                    physio.vo2max.alternatives["time_series_estimate"] = round(ts_vo2max, 2)

    # === VLaMax (always estimated) ===
    if cp > 0 and pmax > 0:
        anaerobic_reserve = pmax - cp
        w_prime_kj = physio.w_prime_kj.value or 15
        w_prime_factor = w_prime_kj / 20
        vlamax = 0.3 + (anaerobic_reserve / pmax) * 0.5 + (w_prime_factor - 1) * 0.1
        vlamax = max(0.2, min(1.0, vlamax))
        physio.vlamax = CanonicalMetric(
            value=vlamax, source="estimated_from_power", confidence=0.50
        )

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
