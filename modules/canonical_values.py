"""
Canonical Values Module - GLOBAL PRIORITY POLICY.

This module provides the SINGLE DECISION POINT for resolving all metric values.
ALL METRICS (VT1/2, SmO2, VO2max, CP, FTP, EF, etc.) MUST pass through this mechanism.

RULE: MANUAL > AUTO > MISSING
- Manual values have confidence 1.0
- Auto values have confidence 0.6 (algorithm-derived)
- Missing values have confidence 0.0
"""

from dataclasses import dataclass
from typing import Optional, Any, Dict, List
from enum import Enum


class MetricSource(Enum):
    """Source of a metric value."""
    MANUAL = "manual"      # User-entered value (priority 1.0)
    AUTO = "auto"          # Algorithm-detected value (priority 0.6)
    MISSING = "missing"    # No value available (priority 0.0)


@dataclass
class ResolvedMetric:
    """
    Result of resolving a metric through the priority policy.
    
    Attributes:
        value: The resolved value (manual or auto, or None if missing)
        source: Where the value came from
        confidence: How confident we are in this value
        name: Name of the metric (for debugging/logging)
    """
    value: Optional[Any]
    source: MetricSource
    confidence: float
    name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "value": self.value,
            "source": self.source.value,
            "confidence": self.confidence
        }
    
    def is_valid(self) -> bool:
        """Check if this metric has a valid value."""
        return self.value is not None and self.confidence > 0


def resolve_metric(
    name: str,
    manual: Optional[Any],
    auto: Optional[Any],
    manual_confidence: float = 1.0,
    auto_confidence: float = 0.6
) -> ResolvedMetric:
    """
    GLOBAL PRIORITY POLICY - Single decision point for all metrics.
    
    RULE (NON-NEGOTIABLE):
    1. If manual is not None and not 0 → return manual (confidence 1.0)
    2. Else if auto is not None and not 0 → return auto (confidence 0.6)
    3. Else → return None (confidence 0.0)
    
    Args:
        name: Name of the metric (for logging/debugging)
        manual: User-entered manual value (PRIORITY)
        auto: Algorithm-detected automatic value (FALLBACK)
        manual_confidence: Confidence for manual values (default 1.0)
        auto_confidence: Confidence for auto values (default 0.6)
        
    Returns:
        ResolvedMetric with value, source, and confidence
    """
    # MANUAL HAS ABSOLUTE PRIORITY
    if manual is not None and manual != 0:
        return ResolvedMetric(
            value=manual,
            source=MetricSource.MANUAL,
            confidence=manual_confidence,
            name=name
        )
    
    # AUTO is fallback
    if auto is not None and auto != 0:
        return ResolvedMetric(
            value=auto,
            source=MetricSource.AUTO,
            confidence=auto_confidence,
            name=name
        )
    
    # MISSING - no valid value
    return ResolvedMetric(
        value=None,
        source=MetricSource.MISSING,
        confidence=0.0,
        name=name
    )


def resolve_all_thresholds(
    manual_overrides: Dict[str, Any],
    auto_values: Dict[str, Any]
) -> Dict[str, ResolvedMetric]:
    """
    Resolve all threshold metrics at once.
    
    Args:
        manual_overrides: Dict of manual values from session_state
        auto_values: Dict of auto-detected values from algorithms
        
    Returns:
        Dict mapping metric names to ResolvedMetric objects
    """
    # Define all metrics to resolve
    metrics = [
        "vt1", "vt2",
        "smo2_lt1", "smo2_lt2",
        "vo2max", "cp", "ftp",
        "vlamax", 
        "vt1_hr", "vt2_hr",
        "vt1_ve", "vt2_ve",
        "vt1_br", "vt2_br",
        "reoxy_halftime", "cci_breakpoint", "ve_breakpoint"
    ]
    
    # Map for manual key aliases
    manual_key_map = {
        "vt1": ["manual_vt1_watts", "vt1_watts", "vt1"],
        "vt2": ["manual_vt2_watts", "vt2_watts", "vt2"],
        "smo2_lt1": ["smo2_lt1_m", "smo2_lt1"],
        "smo2_lt2": ["smo2_lt2_m", "smo2_lt2"],
        "cp": ["cp_input", "cp"],
        "ftp": ["ftp_input", "ftp"],
        "reoxy_halftime": ["reoxy_halftime_manual", "reoxy_halftime"],
        "cci_breakpoint": ["cci_breakpoint_manual", "cci_breakpoint"],
        "ve_breakpoint": ["ve_breakpoint_manual", "ve_breakpoint"],
    }
    
    results = {}
    
    for metric in metrics:
        # Get manual value (try aliases)
        manual_val = None
        for key in manual_key_map.get(metric, [metric]):
            if key in manual_overrides and manual_overrides[key]:
                manual_val = manual_overrides[key]
                break
        
        # Get auto value
        auto_val = auto_values.get(metric)
        
        # Resolve
        results[metric] = resolve_metric(metric, manual_val, auto_val)
    
    return results


def log_resolution(resolved: Dict[str, ResolvedMetric]) -> List[str]:
    """
    Generate log lines for resolved metrics (debugging).
    
    Returns:
        List of formatted log strings
    """
    lines = []
    for name, metric in resolved.items():
        if metric.is_valid():
            source_icon = "✋" if metric.source == MetricSource.MANUAL else "🤖"
            lines.append(
                f"{source_icon} {name}: {metric.value} "
                f"(source={metric.source.value}, confidence={metric.confidence:.1f})"
            )
    return lines


def build_data_policy(resolved: Dict[str, ResolvedMetric]) -> Dict[str, Any]:
    """
    Build data_policy section for JSON report.
    
    This shows which values are manual vs auto, building user trust.
    
    Args:
        resolved: Dict of resolved metrics
        
    Returns:
        data_policy dict for JSON inclusion
    """
    manual_fields = []
    auto_fields = []
    missing_fields = []
    
    for name, metric in resolved.items():
        if metric.source == MetricSource.MANUAL:
            manual_fields.append(name)
        elif metric.source == MetricSource.AUTO:
            auto_fields.append(name)
        else:
            missing_fields.append(name)
    
    return {
        "mode": "manual_preferred",
        "manual_fields_used": sorted(manual_fields),
        "auto_fields_used": sorted(auto_fields),
        "missing_fields": sorted(missing_fields),
        "manual_count": len(manual_fields),
        "auto_count": len(auto_fields),
        "total_resolved": len(manual_fields) + len(auto_fields)
    }


def format_with_source(value: Any, source: MetricSource, unit: str = "") -> str:
    """
    Format a value with source indicator for PDF/DOCX display.
    
    MANUAL values get ✍️ icon to show user they were manually entered.
    
    Args:
        value: The metric value
        source: MetricSource (MANUAL, AUTO, MISSING)
        unit: Optional unit suffix (e.g., "W", "bpm")
        
    Returns:
        Formatted string like "300 W ✍️" or "280 W"
    """
    if value is None:
        return "–"
    
    # Format value
    if isinstance(value, float):
        if value == int(value):
            formatted = f"{int(value)}"
        else:
            formatted = f"{value:.1f}"
    else:
        formatted = str(value)
    
    # Add unit
    if unit:
        formatted = f"{formatted} {unit}"
    
    # Add source indicator
    if source == MetricSource.MANUAL:
        formatted = f"{formatted} ✍️"
    
    return formatted


def get_source_tooltip(source: MetricSource) -> str:
    """
    Get tooltip text for source indicator.
    
    Args:
        source: MetricSource
        
    Returns:
        Polish tooltip text
    """
    if source == MetricSource.MANUAL:
        return "Wartość wprowadzona manualnie przez użytkownika"
    elif source == MetricSource.AUTO:
        return "Wartość obliczona automatycznie przez algorytm"
    else:
        return "Brak danych"


def apply_manual_overrides_to_thresholds(
    thresholds_dict: Dict[str, Any],
    manual_overrides: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply manual overrides to thresholds using resolve_metric().
    
    This is the SINGLE FUNCTION that should be used to apply manual overrides.
    ELIMINATES all inline `if manual > 0: use manual else: use auto` patterns.
    
    Args:
        thresholds_dict: Dict with auto-detected threshold values
        manual_overrides: Dict with manual values from session_state
        
    Returns:
        Dict with resolved values (manual if available, else auto)
    """
    # Define mapping: output_key -> (manual_key, auto_key_in_thresholds)
    mappings = [
        ("vt1_watts", "manual_vt1_watts", lambda t: t.get("vt1", {}).get("midpoint_watts") if isinstance(t.get("vt1"), dict) else t.get("vt1_watts")),
        ("vt2_watts", "manual_vt2_watts", lambda t: t.get("vt2", {}).get("midpoint_watts") if isinstance(t.get("vt2"), dict) else t.get("vt2_watts")),
        ("vt1_hr", "vt1_hr", lambda t: t.get("vt1", {}).get("midpoint_hr") if isinstance(t.get("vt1"), dict) else t.get("vt1_hr")),
        ("vt2_hr", "vt2_hr", lambda t: t.get("vt2", {}).get("midpoint_hr") if isinstance(t.get("vt2"), dict) else t.get("vt2_hr")),
        ("vt1_ve", "vt1_ve", lambda t: t.get("vt1", {}).get("midpoint_ve") if isinstance(t.get("vt1"), dict) else t.get("vt1_ve")),
        ("vt2_ve", "vt2_ve", lambda t: t.get("vt2", {}).get("midpoint_ve") if isinstance(t.get("vt2"), dict) else t.get("vt2_ve")),
        ("vt1_br", "vt1_br", lambda t: t.get("vt1", {}).get("midpoint_br") if isinstance(t.get("vt1"), dict) else t.get("vt1_br")),
        ("vt2_br", "vt2_br", lambda t: t.get("vt2", {}).get("midpoint_br") if isinstance(t.get("vt2"), dict) else t.get("vt2_br")),
        ("smo2_lt1", "smo2_lt1_m", lambda t: t.get("smo2_lt1")),
        ("smo2_lt2", "smo2_lt2_m", lambda t: t.get("smo2_lt2")),
        ("cp", "cp_input", lambda t: t.get("cp") or t.get("cp_watts")),
        ("cci_breakpoint", "cci_breakpoint_manual", lambda t: t.get("cci_breakpoint") or t.get("cci_breakpoint_watts")),
        ("ve_breakpoint", "ve_breakpoint_manual", lambda t: t.get("ve_breakpoint") or t.get("ve_breakpoint_watts")),
        ("reoxy_halftime", "reoxy_halftime_manual", lambda t: t.get("reoxy_halftime") or t.get("halftime_reoxy_sec")),
    ]
    
    result = {}
    sources = {}
    
    for output_key, manual_key, auto_getter in mappings:
        manual_val = manual_overrides.get(manual_key)
        auto_val = auto_getter(thresholds_dict)
        
        resolved = resolve_metric(output_key, manual_val, auto_val)
        result[output_key] = resolved.value
        sources[output_key] = resolved.source.value
    
    # Add _sources dict for tracking
    result["_sources"] = sources
    
    return result


# =============================================================================
# DUAL POWER FORMATTING (Watts + %FTP)
# =============================================================================

def format_power_dual(
    watts: float,
    reference_watts: float,
    reference_name: str = "FTP"
) -> str:
    """Format power with both absolute watts AND percentage of reference.
    
    SOLVES: Confusion between absolute values and percentages.
    Always shows BOTH for clarity.
    
    Args:
        watts: Power value in watts
        reference_watts: Reference power (FTP, CP, VT2, etc.)
        reference_name: Name of reference ("FTP", "CP", "VT2")
        
    Returns:
        Formatted string like "260 W (92% FTP)"
    
    Examples:
        >>> format_power_dual(260, 280, "FTP")
        "260 W (93% FTP)"
        
        >>> format_power_dual(350, 400, "CP")
        "350 W (88% CP)"
    """
    if not watts or not reference_watts or reference_watts == 0:
        if watts:
            return f"{int(watts)} W"
        return "---"
    
    pct = (watts / reference_watts) * 100
    return f"{int(watts)} W ({int(pct)}% {reference_name})"


def format_power_range_dual(
    low_watts: float,
    high_watts: float,
    reference_watts: float,
    reference_name: str = "FTP"
) -> str:
    """Format power range with both absolute watts AND percentage.
    
    Args:
        low_watts: Lower bound in watts
        high_watts: Upper bound in watts
        reference_watts: Reference power
        reference_name: Name of reference
        
    Returns:
        Formatted string like "220–280 W (79–100% FTP)"
    """
    if not low_watts or not high_watts or not reference_watts or reference_watts == 0:
        if low_watts and high_watts:
            return f"{int(low_watts)}–{int(high_watts)} W"
        return "---"
    
    pct_low = (low_watts / reference_watts) * 100
    pct_high = (high_watts / reference_watts) * 100
    
    return f"{int(low_watts)}–{int(high_watts)} W ({int(pct_low)}–{int(pct_high)}% {reference_name})"
