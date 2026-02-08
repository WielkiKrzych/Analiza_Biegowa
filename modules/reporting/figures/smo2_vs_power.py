"""
SmO₂ vs Power Chart Generator.

Generates SmO₂ saturation vs power scatter with LT1/LT2 range bands.
Input: Canonical JSON report
Output: PNG file

Chart shows:
- Raw scatter of SmO₂ vs Power (NO smoothing/interpolation)
- LT1/LT2 as HORIZONTAL RANGE BANDS if available
- Annotation about SmO₂ being a local signal
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


def generate_smo2_power_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional["pd.DataFrame"] = None
) -> bytes:
    """Generate SmO₂ vs Power chart with LT1/LT2 range bands."""
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
    time_series = report_data.get("time_series", {})
    thresholds = report_data.get("thresholds", {})
    metadata = report_data.get("metadata", {})
    smo2_context = report_data.get("smo2_context", {})
    
    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})
    
    # Try to get data from source_df first
    if source_df is not None and len(source_df) > 0:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        
        # Get power data
        power_col = next((c for c in ['watts', 'power', 'watts_smooth', 'watts_smooth_5s'] if c in df.columns), None)
        
        # Get smo2 data
        smo2_col = next((c for c in ['smo2', 'smo2_pct', 'muscle_oxygen', 'smo2_smooth'] if c in df.columns), None)
        
        if power_col and smo2_col:
            # Filter out NaN values
            mask = ~(df[power_col].isna() | df[smo2_col].isna())
            power_data = df.loc[mask, power_col].tolist()
            smo2_data = df.loc[mask, smo2_col].tolist()
        else:
            power_data, smo2_data = [], []
    else:
        # Fallback to time_series from JSON
        power_data = time_series.get("power_watts", [])
        smo2_data = time_series.get("smo2_pct", [])
    
    # Handle missing data
    if not power_data or not smo2_data:
        return create_empty_figure("Brak danych SmO₂", "SmO₂ vs Moc", output_path, **cfg)
    
    # Get SmO2 drop point from smo2_context
    drop_point = smo2_context.get("drop_point", {})
    lt1_watts = drop_point.get("midpoint_watts", 0) if drop_point else 0
    
    # MANUAL OVERRIDE: Check config for manual SmO2 LT1 (priority over saved)
    manual_overrides = cfg.get('manual_overrides', {})
    if manual_overrides.get('smo2_lt1_m') and manual_overrides['smo2_lt1_m'] > 0:
        lt1_watts = float(manual_overrides['smo2_lt1_m'])
    
    # Define LT ranges (±5% for visual band width)
    lt1_range = (lt1_watts * 0.95, lt1_watts * 1.05) if lt1_watts else None
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Raw scatter plot SmO2 vs Power (NO SMOOTHING)
    ax.scatter(power_data, smo2_data, c=get_color("smo2"), 
               alpha=0.4, s=12, label="SmO₂", zorder=3, edgecolors='none')
    
    # LT1 vertical range band (semi-transparent) - SmO2 drop point
    if lt1_range:
        ax.axvspan(lt1_range[0], lt1_range[1], 
                   alpha=0.2, color=get_color("vt1"), 
                   zorder=1, label=f"SmO₂ Drop: {int(lt1_watts)} W")
    
    # Axis labels
    ax.set_xlabel("Moc [W]", fontsize=font_size, fontweight='medium')
    ax.set_ylabel("SmO₂ [%]", fontsize=font_size, fontweight='medium')
    
    # Title
    ax.set_title("SmO₂ vs Moc", fontsize=title_size, fontweight='bold', pad=15)
    
    # Legend
    ax.legend(loc='upper right', fontsize=font_size - 1, 
              framealpha=0.9, edgecolor='none')
    
    # Apply common styling
    apply_common_style(fig, ax, **cfg)
    
    # Important annotation about SmO₂ interpretation
    ax.text(0.5, -0.12, 
            "ℹ️ SmO₂ jest sygnałem lokalnym – interpretować kontekstowo",
            ha='center', va='top', fontsize=9, style='italic',
            color=get_color("secondary"), transform=ax.transAxes)
    
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
