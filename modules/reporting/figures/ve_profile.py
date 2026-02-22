"""
VE Profile Chart Generator.

Generates ventilation (VE) profile over time with VT1/VT2 thresholds.
Input: Canonical JSON report + Source DataFrame
Output: PNG file

Chart shows:
- Ventilation (VE) on Left Y-Axis
- Pace (min/km) on Right Y-Axis (background)
- VT1 and VT2 vertical lines
- Footer with test_id and method version
"""
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, Optional
import pandas as pd

from .common import (
    save_figure,
    create_empty_figure,
    get_color
)


def _sec_to_min(pace_sec: float) -> float:
    """Convert pace from sec/km to min/km for axis display."""
    return pace_sec / 60.0 if pace_sec and pace_sec > 0 else 0


def generate_ve_profile_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate VE profile chart with Pace overlay."""
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
    
    # Extract data from source_df or time_series fallback
    time_series = report_data.get("time_series", {})
    
    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        
        ve_col = next((c for c in ['tymeventilation', 've', 'ventilation', 've_smooth'] if c in df.columns), None)
        pace_col = next((c for c in ['pace', 'pace_smooth', 'pace_sec_per_km', 'tempo'] if c in df.columns), None)
        time_col = next((c for c in ['time', 'seconds'] if c in df.columns), None)
        
        if ve_col and time_col:
            time_data = df[time_col].tolist()
            ve_data = df[ve_col].fillna(0).tolist()
            # Convert pace to min/km
            pace_sec_data = df[pace_col].fillna(0).tolist() if pace_col else []
            pace_data = [_sec_to_min(p) for p in pace_sec_data] if pace_col else []
        else:
            time_data, ve_data, pace_data = [], [], []
    else:
        # Fallback to JSON time_series
        time_data = time_series.get("time_sec", [])
        ve_data = time_series.get("ve_lmin", [])
        pace_sec = time_series.get("pace_sec_per_km", time_series.get("pace", []))
        pace_data = [_sec_to_min(p) for p in pace_sec] if pace_sec else []
        
    if not time_data or not ve_data:
        empty_result = create_empty_figure("Brak danych wentylacji", "Dynamika Wentylacji", output_path, **cfg)
        return empty_result if output_path else empty_result.to_image(format='png')
    
    # Get threshold values - convert watts to pace if needed
    thresholds = report_data.get("thresholds", {})
    vt1_data = thresholds.get("vt1", {})
    vt2_data = thresholds.get("vt2", {})
    
    # Try pace-based thresholds first, fallback to watts
    vt1_pace_sec = vt1_data.get("midpoint_pace_sec", 0)
    vt2_pace_sec = vt2_data.get("midpoint_pace_sec", 0)
    
    vt1_time = None
    vt2_time = None
    vt1_pace_min = _sec_to_min(vt1_pace_sec) if vt1_pace_sec else None
    vt2_pace_min = _sec_to_min(vt2_pace_sec) if vt2_pace_sec else None
    
    # Find time when pace reaches threshold
    if pace_data and vt1_pace_sec:
        for t, p_sec in zip(time_data, time_series.get("pace_sec_per_km", time_series.get("pace", []))):
            if p_sec >= vt1_pace_sec:
                vt1_time = t
                break
                
    if pace_data and vt2_pace_sec:
        for t, p_sec in zip(time_data, time_series.get("pace_sec_per_km", time_series.get("pace", []))):
            if p_sec >= vt2_pace_sec:
                vt2_time = t
                break

    # Convert time to minutes for x-axis
    time_min = [t / 60 for t in time_data]
    vt1_time_min = vt1_time / 60 if vt1_time else None
    vt2_time_min = vt2_time / 60 if vt2_time else None

    # Create figure
    fig, ax1 = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Plot Pace on Right Axis (Background)
    ax2 = ax1.twinx()
    if pace_data:
        ax2.plot(time_min, pace_data, color=get_color("pace"), alpha=0.3, linewidth=1, label="Tempo")
        ax2.fill_between(time_min, pace_data, color=get_color("pace"), alpha=0.05)
        ax2.set_ylabel("Tempo [min/km]", color=get_color("pace"), fontsize=font_size)
        ax2.tick_params(axis='y', labelcolor=get_color("pace"))
        # Invert Y-axis (lower pace = faster)
        ax2.invert_yaxis()
    
    # Plot VE on Left Axis (Foreground)
    ax1.plot(time_min, ve_data, color=get_color("ve"), linewidth=2, label="VE (Wentylacja)")
    
    # Set x-axis ticks to hh:mm:ss format
    time_max = max(time_min)
    tick_step = 5  # 5 minute intervals
    tick_vals = np.arange(0, time_max + tick_step, tick_step)
    tick_labels = [f"{int(m//60):02d}:{int(m%60):02d}:00" for m in tick_vals]
    ax1.set_xticks(tick_vals)
    ax1.set_xticklabels(tick_labels)
    
    ax1.set_xlabel("Czas [hh:mm:ss]", fontsize=font_size)
    ax1.set_ylabel("VE [L/min]", color=get_color("ve"), fontsize=font_size, fontweight='bold')
    ax1.tick_params(axis='y', labelcolor=get_color("ve"))
    
    # Vertical Lines for VT1/VT2
    if vt1_time_min and vt1_pace_min:
        ax1.axvline(x=vt1_time_min, color=get_color("vt1"), linestyle='--', alpha=0.9, linewidth=1.5,
                   label=f"VT1: {vt1_pace_min:.2f} min/km")
        ax1.text(vt1_time_min, max(ve_data)*0.95, f"VT1\n{vt1_pace_min:.2f}", 
                 color=get_color("vt1"), ha='center', va='top', fontweight='bold', 
                 bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
                  
    if vt2_time_min and vt2_pace_min:
        ax1.axvline(x=vt2_time_min, color=get_color("vt2"), linestyle='--', alpha=0.9, linewidth=1.5,
                   label=f"VT2: {vt2_pace_min:.2f} min/km")
        ax1.text(vt2_time_min, max(ve_data)*0.95, f"VT2\n{vt2_pace_min:.2f}", 
                 color=get_color("vt2"), ha='center', va='top', fontweight='bold',
                 bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # Title
    metadata = report_data.get("metadata", {})
    test_date = metadata.get("test_date", "")
    ax1.set_title(f"Dynamika Wentylacji (VE) – {test_date}", 
                 fontsize=title_size, fontweight='bold', pad=15)
                 
    # Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=font_size - 1)
    
    # Common style bits
    ax1.grid(True, alpha=0.3, linestyle=':')
    ax1.spines['top'].set_visible(False)
    ax2.spines['top'].set_visible(False)
    
    # Footer
    session_id = metadata.get("session_id", "unknown")[:8]
    fig.text(0.01, 0.01, f"ID: {session_id}", 
             ha='left', va='bottom', fontsize=8, 
             color=get_color("secondary"), style='italic')

    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)
