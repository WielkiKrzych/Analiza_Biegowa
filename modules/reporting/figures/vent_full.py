"""
Full Ventilation Chart Generator.

Generates:
1. Ventilation Dynamics (VE vs Pace over Time)
   - Left Axis: VE (L/min)
   - Right Axis: Pace (min/km)
"""
import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict, Any, Optional

from .common import (
    apply_common_style, 
    save_figure,
    create_empty_figure,
    get_color
)

def _find_column(df: pd.DataFrame, aliases: list) -> Optional[str]:
    """Find first existing column from aliases."""
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None

def _sec_to_min(pace_sec: float) -> float:
    """Convert pace from sec/km to min/km for axis display."""
    return pace_sec / 60.0 if pace_sec and pace_sec > 0 else 0

def generate_full_vent_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate Ventilation Dynamics Chart (Time Series)."""
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
    
    if source_df is None or source_df.empty:
        empty_result = create_empty_figure("Brak danych źródłowych", "Dynamika Wentylacji", output_path, **cfg)
        return empty_result if output_path else empty_result.to_image(format='png')

    # Resolve columns
    df = source_df.copy()
    ve_col = _find_column(df, ['tymeventilation', 've', 'ventilation', 've_smooth'])
    pace_col = _find_column(df, ['pace', 'pace_smooth', 'pace_sec_per_km', 'tempo'])
    time_col = _find_column(df, ['time_min', 'time'])
    
    if not ve_col:
        empty_result = create_empty_figure("Brak danych Wentylacji", "Dynamika Wentylacji", output_path, **cfg)
        return empty_result if output_path else empty_result.to_image(format='png')

    # Normalize time
    if time_col == 'time':
        df['time_min'] = df['time'] / 60.0
        time_vals = df['time_min']
    else:
        time_vals = df[time_col]
        
    fig, ax1 = plt.subplots(figsize=figsize, dpi=dpi)
    
    # VE (Left Axis - Primary)
    l1, = ax1.plot(time_vals, df[ve_col], color=get_color("vt1"), label="VE (L/min)", linewidth=2)
    ax1.set_xlabel("Czas [min]", fontsize=font_size)
    ax1.set_ylabel("Wentylacja [L/min]", fontsize=font_size, color=get_color("vt1"))
    ax1.tick_params(axis='y', labelcolor=get_color("vt1"))
    
    # Pace (Right Axis - Secondary)
    if pace_col:
        ax2 = ax1.twinx()
        # Convert pace to min/km for display
        pace_min_km = df[pace_col].apply(_sec_to_min)
        l2, = ax2.plot(time_vals, pace_min_km, color=get_color("pace"), linestyle='-', alpha=0.3, label="Tempo (min/km)", linewidth=1)
        ax2.set_ylabel("Tempo [min/km]", fontsize=font_size, color=get_color("pace"))
        ax2.tick_params(axis='y', labelcolor=get_color("pace"))
        ax2.grid(False)
        # Invert Y-axis (lower pace = faster)
        ax2.invert_yaxis()
        
        lines = [l1, l2]
    else:
        lines = [l1]
        
    # Title & Legend
    ax1.set_title("Dynamika Wentylacji vs Tempo", fontsize=title_size, fontweight='bold')
    
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', framealpha=0.9)
    
    apply_common_style(fig, ax1, **cfg)
    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)
