"""
Full Ventilation Chart Generator.

Generates:
1. Ventilation Dynamics (VE vs Power over Time)
   - Left Axis: VE (L/min)
   - Right Axis: Power (W)
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
        return create_empty_figure("Brak danych źródłowych", "Dynamika Wentylacji", output_path, **cfg)

    # Resolve columns
    df = source_df.copy()
    ve_col = _find_column(df, ['tymeventilation', 've', 'ventilation', 've_smooth'])
    pwr_col = _find_column(df, ['watts', 'watts_smooth', 'power'])
    time_col = _find_column(df, ['time_min', 'time'])
    
    if not ve_col:
        return create_empty_figure("Brak danych Wentylacji", "Dynamika Wentylacji", output_path, **cfg)

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
    
    # Power (Right Axis - Secondary)
    if pwr_col:
        ax2 = ax1.twinx()
        l2, = ax2.plot(time_vals, df[pwr_col], color=get_color("power"), linestyle='-', alpha=0.3, label="Moc (W)", linewidth=1)
        ax2.set_ylabel("Moc [W]", fontsize=font_size, color=get_color("power"))
        ax2.tick_params(axis='y', labelcolor=get_color("power"))
        ax2.grid(False) 
        
        lines = [l1, l2]
    else:
        lines = [l1]
        
    # Title & Legend
    ax1.set_title("Dynamika Wentylacji vs Moc", fontsize=title_size, fontweight='bold')
    
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', framealpha=0.9)
    
    apply_common_style(fig, ax1, **cfg)
    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)
