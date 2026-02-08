"""
Manual Overrides Module - SINGLE SOURCE OF TRUTH.

This module provides a centralized structure for all manual threshold values.
ABSOLUTE RULE: If user enters a manual value, algorithms MUST NOT override it.

Usage:
    from modules.manual_overrides import get_manual_overrides, resolve_value
    
    overrides = get_manual_overrides()
    final_vt1 = resolve_value(overrides.vt1, auto_detected_vt1)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import streamlit as st


@dataclass
class ManualOverrides:
    """
    Container for all manually entered threshold values.
    
    RULE: If a value is not None and > 0, it MUST be used over any auto-detected value.
    Auto-detected values are ONLY fallback when manual value is None or 0.
    """
    # Ventilatory Thresholds (Watts)
    vt1: Optional[float] = None
    vt2: Optional[float] = None
    
    # SmO2 Thresholds (Watts)
    smo2_lt1: Optional[float] = None
    smo2_lt2: Optional[float] = None
    
    # Physiological Parameters
    vo2max: Optional[float] = None
    cp: Optional[float] = None
    ftp: Optional[float] = None
    vlamax: Optional[float] = None
    
    # Heart Rate Thresholds
    hr_thresholds: Dict[str, Any] = field(default_factory=dict)
    
    # Additional Metrics
    reoxy_halftime: Optional[float] = None
    cci_breakpoint: Optional[float] = None
    ve_breakpoint: Optional[float] = None
    
    # VT Supporting Data (HR, VE, BR)
    vt1_hr: Optional[int] = None
    vt2_hr: Optional[int] = None
    vt1_ve: Optional[float] = None
    vt2_ve: Optional[float] = None
    vt1_br: Optional[int] = None
    vt2_br: Optional[int] = None
    
    # Test Protocol (for PDF section 1.2)
    test_start_power: Optional[int] = None
    test_end_power: Optional[int] = None
    test_duration: Optional[str] = None


def get_manual_overrides() -> ManualOverrides:
    """
    Load manual overrides from st.session_state.
    
    This is the SINGLE SOURCE OF TRUTH for all manual values.
    Call this function whenever you need manual overrides.
    
    Returns:
        ManualOverrides dataclass populated from session_state
    """
    def _get(key: str, default=None):
        """Safely get value from session_state, treating 0 as None."""
        val = st.session_state.get(key, default)
        if val is None or val == 0:
            return None
        return val
    
    return ManualOverrides(
        # VT1/VT2 from Manual Thresholds tab
        vt1=_get("manual_vt1_watts"),
        vt2=_get("manual_vt2_watts"),
        
        # SmO2 from Manual SmO2 tab
        smo2_lt1=_get("smo2_lt1_m"),
        smo2_lt2=_get("smo2_lt2_m"),
        
        # From Sidebar
        cp=_get("cp_in") or _get("cp_input"),
        vo2max=_get("manual_vo2max"),
        ftp=_get("manual_ftp"),
        vlamax=_get("manual_vlamax"),
        
        # HR Thresholds
        hr_thresholds={
            "vt1": _get("vt1_hr"),
            "vt2": _get("vt2_hr"),
            "max_hr": _get("max_hr"),
        },
        
        # Additional metrics
        reoxy_halftime=_get("reoxy_halftime_manual"),
        cci_breakpoint=_get("cci_breakpoint_manual"),
        ve_breakpoint=_get("ve_breakpoint_manual"),
        
        # VT Supporting Data
        vt1_hr=_get("vt1_hr"),
        vt2_hr=_get("vt2_hr"),
        vt1_ve=_get("vt1_ve"),
        vt2_ve=_get("vt2_ve"),
        vt1_br=_get("vt1_br"),
        vt2_br=_get("vt2_br"),
        
        # Test Protocol
        test_start_power=_get("test_start_power"),
        test_end_power=_get("test_end_power"),
        test_duration=st.session_state.get("test_duration"),
    )


def resolve_value(manual: Optional[float], auto: Optional[float]) -> Optional[float]:
    """
    Resolve final value with MANUAL PRIORITY.
    
    ABSOLUTE RULE:
    - If manual is set (not None and > 0) → return manual
    - Else → return auto (fallback)
    
    Args:
        manual: User-entered manual value (priority)
        auto: Algorithm-detected value (fallback)
        
    Returns:
        The final value to use (manual if available, else auto)
    """
    if manual is not None and manual > 0:
        return manual
    return auto


def to_dict(overrides: ManualOverrides) -> Dict[str, Any]:
    """
    Convert ManualOverrides to dict for passing to functions.
    
    Uses the legacy key names for backward compatibility.
    """
    return {
        # VT1/VT2 - legacy keys
        "manual_vt1_watts": overrides.vt1,
        "manual_vt2_watts": overrides.vt2,
        "vt1_hr": overrides.vt1_hr,
        "vt2_hr": overrides.vt2_hr,
        "vt1_ve": overrides.vt1_ve,
        "vt2_ve": overrides.vt2_ve,
        "vt1_br": overrides.vt1_br,
        "vt2_br": overrides.vt2_br,
        
        # SmO2
        "smo2_lt1_m": overrides.smo2_lt1,
        "smo2_lt2_m": overrides.smo2_lt2,
        
        # Physio
        "cp_input": overrides.cp,
        "vo2max": overrides.vo2max,
        "ftp": overrides.ftp,
        "vlamax": overrides.vlamax,
        
        # Additional
        "reoxy_halftime_manual": overrides.reoxy_halftime,
        "cci_breakpoint_manual": overrides.cci_breakpoint,
        "ve_breakpoint_manual": overrides.ve_breakpoint,
        
        # Test Protocol (for PDF section 1.2)
        "test_start_power": overrides.test_start_power,
        "test_end_power": overrides.test_end_power,
        "test_duration": overrides.test_duration,
    }
