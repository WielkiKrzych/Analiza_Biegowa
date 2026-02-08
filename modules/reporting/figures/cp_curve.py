"""
Power-Duration Curve (CP Curve) Chart Generator.

Generates MMP scatter with CP model overlay on logarithmic time axis.
Input: Canonical JSON report
Output: PNG file

Chart shows:
- X axis: Time (logarithmic scale)
- Y axis: Power (W)
- MMP points from session
- CP model curve overlay
- Key duration markers (1min, 5min, 20min)
- Critical Power horizontal line
- Footer with test_id and method version
"""
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, Optional, List

from .common import (
    apply_common_style, 
    save_figure,
    create_empty_figure,
    get_color
)


# Key durations to highlight (in seconds)
KEY_DURATIONS = [
    (60, "1 min"),
    (300, "5 min"),
    (1200, "20 min"),
]


def generate_cp_curve_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None
) -> bytes:
    """Generate Power-Duration Curve chart with CP model and key markers."""
    # Handle config as dict if passed, or use defaults
    if hasattr(config, '__dict__'):
        cfg = config.__dict__
    elif isinstance(config, dict):
        cfg = config
    else:
        cfg = {}

    figsize = cfg.get('figsize', (10, 6))
    dpi = cfg.get('dpi', 150)
    font_size = cfg.get('font_size', 10)
    title_size = cfg.get('title_size', 14)
    method_version = cfg.get('method_version', '1.0.0')

    # Extract data
    pdc_data = report_data.get("power_duration_curve", {})
    cp_model = report_data.get("cp_model", {})
    metadata = report_data.get("metadata", {})
    
    durations = pdc_data.get("durations_sec", [])
    powers = pdc_data.get("powers_watts", [])
    
    cp_watts = cp_model.get("cp_watts", 0)
    w_prime_j = cp_model.get("w_prime_joules", 0)
    
    # Handle missing data
    if not durations or not powers:
        return create_empty_figure("Brak danych PDC", "Power-Duration Curve", output_path, **cfg)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # MMP points (using seconds for plotting, will format later)
    ax.scatter(durations, powers, c=get_color("power"), 
               s=60, zorder=5, label="Twoje MMP", 
               edgecolors='white', linewidths=1)
    
    # CP model curve
    if cp_watts > 0 and w_prime_j > 0:
        t_model = np.logspace(np.log10(30), np.log10(max(durations) if durations else 3600), 100)
        p_model = [cp_watts + (w_prime_j / t) for t in t_model]
        ax.plot(t_model, p_model, color=get_color("cp"), 
                linewidth=2, linestyle='--',
                label=f"Model CP ({cp_watts} W)")
        
        # CP horizontal line
        ax.axhline(y=cp_watts, color=get_color("cp"), 
                   linewidth=1.5, linestyle=':', alpha=0.7, zorder=2)
    
    # Key duration markers (1min, 5min, 20min)
    for dur_sec, dur_label in KEY_DURATIONS:
        if dur_sec <= max(durations):
            # Find closest power value at this duration
            power_at_dur = _interpolate_power(durations, powers, dur_sec)
            if power_at_dur:
                ax.axvline(x=dur_sec, color=get_color("secondary"), 
                           linewidth=1, linestyle=':', alpha=0.5, zorder=1)
                ax.scatter([dur_sec], [power_at_dur], c=get_color("power"), 
                           s=100, zorder=6, marker='D', edgecolors='white', linewidths=1.5)
                ax.annotate(f"{dur_label}\n{power_at_dur:.0f} W", 
                            xy=(dur_sec, power_at_dur),
                            xytext=(dur_sec * 1.15, power_at_dur + 15),
                            fontsize=font_size - 1,
                            ha='left', va='bottom',
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='none'))
    
    # Set logarithmic X scale
    ax.set_xscale('log')
    
    # Custom X axis formatter (seconds to readable labels)
    ax.set_xticks([30, 60, 120, 300, 600, 1200, 1800, 3600])
    ax.set_xticklabels(['30s', '1min', '2min', '5min', '10min', '20min', '30min', '60min'])
    
    # Axis labels
    ax.set_xlabel("Czas (skala logarytmiczna)", fontsize=font_size, fontweight='medium')
    ax.set_ylabel("Moc [W]", fontsize=font_size, fontweight='medium')
    
    # Title
    ax.set_title("Power-Duration Curve (PDC)", 
                 fontsize=title_size, fontweight='bold', pad=15)
    
    # Legend
    ax.legend(loc='upper right', fontsize=font_size - 1, 
              framealpha=0.9, edgecolor='none')
    
    # W' and CP annotation box
    if cp_watts > 0:
        info_text = f"CP = {cp_watts} W"
        if w_prime_j > 0:
            info_text += f"\nW' = {w_prime_j/1000:.1f} kJ"
        ax.text(0.02, 0.98, info_text, 
                fontsize=font_size,
                transform=ax.transAxes, va='top', ha='left',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8, edgecolor='none'))
    
    # Apply common styling
    apply_common_style(fig, ax, **cfg)
    
    # Footer with test_id and method version
    session_id = metadata.get("session_id", "unknown")[:8]
    fig.text(0.01, 0.01, f"ID: {session_id}", 
             ha='left', va='bottom', fontsize=8, 
             color=get_color("secondary"), style='italic')
    fig.text(0.99, 0.01, f"v{method_version}", 
             ha='right', va='bottom', fontsize=8, 
             color=get_color("secondary"), style='italic')
    
    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)


def _interpolate_power(durations: List[float], powers: List[float], target_sec: float) -> Optional[float]:
    """Interpolate power value at a specific duration.
    
    Args:
        durations: List of durations in seconds
        powers: List of power values
        target_sec: Target duration to interpolate
        
    Returns:
        Interpolated power or None if out of range
    """
    if not durations or not powers:
        return None
    
    # Find closest duration
    if target_sec < min(durations) or target_sec > max(durations):
        return None
    
    # Simple linear interpolation
    for i in range(len(durations) - 1):
        if durations[i] <= target_sec <= durations[i + 1]:
            # Linear interpolation
            t1, t2 = durations[i], durations[i + 1]
            p1, p2 = powers[i], powers[i + 1]
            ratio = (target_sec - t1) / (t2 - t1) if t2 != t1 else 0
            return p1 + ratio * (p2 - p1)
    
    # Exact match
    if target_sec in durations:
        return powers[durations.index(target_sec)]
    
    return None


# Alias for backward compatibility
generate_pdc_chart = generate_cp_curve_chart
