"""
VE Profile Chart Generator.

Generates ventilation (VE) profile over time with VT1/VT2 thresholds.
Input: Canonical JSON report + Source DataFrame
Output: PNG file

Chart shows:
- Ventilation (VE) on Left Y-Axis
- Power (Watts) on Right Y-Axis (background)
- VT1 and VT2 vertical lines
- Footer with test_id and method version
"""
import matplotlib.pyplot as plt
from typing import Dict, Any, Optional
import pandas as pd

from .common import (
    save_figure,
    create_empty_figure,
    get_color
)

def generate_ve_profile_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate VE profile chart with Power overlay."""
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
        power_col = next((c for c in ['watts', 'power', 'watts_smooth', 'watts_smooth_5s'] if c in df.columns), None)
        time_col = next((c for c in ['time', 'seconds'] if c in df.columns), None)
        
        if ve_col and time_col:
            time_data = df[time_col].tolist()
            ve_data = df[ve_col].fillna(0).tolist()
            power_data = df[power_col].fillna(0).tolist() if power_col else []
        else:
            time_data, ve_data, power_data = [], [], []
    else:
        # Fallback to JSON time_series
        time_data = time_series.get("time_sec", [])
        ve_data = time_series.get("ve_lmin", [])
        power_data = time_series.get("power_watts", [])
        
    if not time_data or not ve_data:
        return create_empty_figure("Brak danych wentylacji", "Dynamika Wentylacji", output_path, **cfg)
    
    # Get threshold values
    thresholds = report_data.get("thresholds", {})
    vt1_data = thresholds.get("vt1", {})
    vt2_data = thresholds.get("vt2", {})
    
    vt1_watts = vt1_data.get("midpoint_watts", 0)
    vt2_watts = vt2_data.get("midpoint_watts", 0)
    
    vt1_time = None
    vt2_time = None
    
    if power_data and vt1_watts:
        for t, p in zip(time_data, power_data):
            if p >= vt1_watts:
                vt1_time = t
                break
                
    if power_data and vt2_watts:
        for t, p in zip(time_data, power_data):
            if p >= vt2_watts:
                vt2_time = t
                break

    # Create figure
    fig, ax1 = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Plot Power on Right Axis (Background)
    ax2 = ax1.twinx()
    if power_data:
        ax2.plot(time_data, power_data, color=get_color("power"), alpha=0.3, linewidth=1, label="Moc")
        ax2.fill_between(time_data, power_data, color=get_color("power"), alpha=0.05)
        ax2.set_ylabel("Moc [W]", color=get_color("power"), fontsize=font_size)
        ax2.tick_params(axis='y', labelcolor=get_color("power"))
    
    # Plot VE on Left Axis (Foreground)
    ax1.plot(time_data, ve_data, color=get_color("ve"), linewidth=2, label="VE (Wentylacja)")
    ax1.set_xlabel("Czas [s]", fontsize=font_size)
    ax1.set_ylabel("VE [L/min]", color=get_color("ve"), fontsize=font_size, fontweight='bold')
    ax1.tick_params(axis='y', labelcolor=get_color("ve"))
    
    # Vertical Lines for VT1/VT2
    if vt1_time:
        ax1.axvline(x=vt1_time, color=get_color("vt1"), linestyle='--', alpha=0.9, linewidth=1.5,
                   label=f"VT1: {int(vt1_watts)} W")
        ax1.text(vt1_time, max(ve_data)*0.95, f"VT1\n{int(vt1_watts)} W", 
                 color=get_color("vt1"), ha='center', va='top', fontweight='bold', 
                 bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
                 
    if vt2_time:
        ax1.axvline(x=vt2_time, color=get_color("vt2"), linestyle='--', alpha=0.9, linewidth=1.5,
                   label=f"VT2: {int(vt2_watts)} W")
        ax1.text(vt2_time, max(ve_data)*0.95, f"VT2\n{int(vt2_watts)} W", 
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
