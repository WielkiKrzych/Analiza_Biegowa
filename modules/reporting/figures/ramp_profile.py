"""
Ramp Profile Chart Generator.

Generates power profile over time with VT1/VT2 range bands.
Input: Canonical JSON report
Output: PNG file

Chart shows:
- Power trace over time
- VT1 and VT2 as HORIZONTAL RANGE BANDS (semi-transparent)
- No vertical "magic lines"
- Footer with test_id and method version
"""
import matplotlib.pyplot as plt
from typing import Dict, Any, Optional

from .common import (
    apply_common_style, 
    save_figure,
    create_empty_figure,
    get_color
)


def generate_ramp_profile_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional["pd.DataFrame"] = None
) -> bytes:
    """Generate ramp profile chart with VT1/VT2 as horizontal range bands."""
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

    # Extract data from source_df if available, otherwise from report
    time_series = report_data.get("time_series", {})
    thresholds = report_data.get("thresholds", {})
    metadata = report_data.get("metadata", {})
    
    # Try to get data from source_df first
    if source_df is not None and len(source_df) > 0:
        # Normalize column names
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        
        # Get time data
        if 'time' in df.columns:
            time_data = df['time'].tolist()
        elif 'seconds' in df.columns:
            time_data = df['seconds'].tolist()
        else:
            time_data = list(range(len(df)))
        
        # Get power data
        power_col = None
        for col in ['watts', 'power', 'watts_smooth', 'watts_smooth_5s']:
            if col in df.columns:
                power_col = col
                break
        
        if power_col:
            power_data = df[power_col].fillna(0).tolist()
        else:
            power_data = []
            
        # Get HR data
        hr_col = None
        for col in ['hr', 'heart_rate', 'heartrate', 'bpm', 'heart_rate_bpm']:
            if col in df.columns:
                hr_col = col
                break
        
        if hr_col:
            hr_data = df[hr_col].fillna(0).tolist()
        else:
            hr_data = []

    else:
        # Fallback to time_series from JSON
        time_data = time_series.get("time_sec", [])
        power_data = time_series.get("power_watts", [])
        hr_data = time_series.get("hr_bpm", [])
    
    # Handle missing data
    if not time_data or not power_data:
        return create_empty_figure("Brak danych mocy", "Profil Ramp Test", output_path, **cfg)
    
    # Get threshold values from thresholds dict (nested structure)
    vt1_data = thresholds.get("vt1", {})
    vt2_data = thresholds.get("vt2", {})
    vt1_watts = vt1_data.get("midpoint_watts", 0) if isinstance(vt1_data, dict) else 0
    vt2_watts = vt2_data.get("midpoint_watts", 0) if isinstance(vt2_data, dict) else 0
    
    # MANUAL OVERRIDE: Check config for manual values (priority over saved)
    manual_overrides = cfg.get('manual_overrides', {})
    if manual_overrides.get('manual_vt1_watts') and manual_overrides['manual_vt1_watts'] > 0:
        vt1_watts = float(manual_overrides['manual_vt1_watts'])
    if manual_overrides.get('manual_vt2_watts') and manual_overrides['manual_vt2_watts'] > 0:
        vt2_watts = float(manual_overrides['manual_vt2_watts'])
    
    # Define VT ranges (±5% for visual band width)
    vt1_range = (vt1_watts * 0.95, vt1_watts * 1.05) if vt1_watts else None
    vt2_range = (vt2_watts * 0.95, vt2_watts * 1.05) if vt2_watts else None
    
    # Convert time to minutes
    time_min = [t / 60 for t in time_data]
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Power trace (Axis 1)
    l1, = ax.plot(time_min, power_data, color=get_color("power"), 
            linewidth=1.5, label="Moc", zorder=3)
    ax.fill_between(time_min, power_data, alpha=0.15, 
                    color=get_color("power"), zorder=2)
    
    # HR trace (Axis 2) - THICKER AND ON TOP for visibility over power fill
    if hr_data:
        ax2 = ax.twinx()
        l2, = ax2.plot(time_min, hr_data, color=get_color("hr"), linestyle="-", 
                       label="HR", alpha=0.9, linewidth=2.5, zorder=10)  # Thicker, solid, on top
        ax2.set_ylabel("HR [bpm]", color=get_color("hr"), fontsize=font_size)
        ax2.tick_params(axis='y', labelcolor=get_color("hr"))
        ax2.spines['right'].set_color(get_color("hr"))
    
    # VT1 horizontal band (semi-transparent)
    if vt1_range:
        ax.axhspan(vt1_range[0], vt1_range[1], 
                   alpha=0.25, color=get_color("vt1"), 
                   zorder=1, label=f"VT1: {int(vt1_watts)} W")
        # Add center line for clarity
        ax.axhline(y=vt1_watts, color=get_color("vt1"), 
                   linewidth=1, linestyle=':', alpha=0.7, zorder=2)
    
    # VT2 horizontal band (semi-transparent)
    if vt2_range:
        ax.axhspan(vt2_range[0], vt2_range[1], 
                   alpha=0.25, color=get_color("vt2"), 
                   zorder=1, label=f"VT2: {int(vt2_watts)} W")
        # Add center line for clarity
        ax.axhline(y=vt2_watts, color=get_color("vt2"), 
                   linewidth=1, linestyle=':', alpha=0.7, zorder=2)
    
    # Axis labels
    ax.set_xlabel("Czas [min]", fontsize=font_size, fontweight='medium')
    ax.set_ylabel("Moc [W]", fontsize=font_size, fontweight='medium')
    
    # Title
    test_date = metadata.get("test_date", "")
    ax.set_title(f"Profil Ramp Test – {test_date}", 
                 fontsize=title_size, fontweight='bold', pad=15)
    
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc='upper left', fontsize=font_size - 1, 
              framealpha=0.9, edgecolor='none')
    
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
