"""
Limiters Analysis Chart Generator.

Generates:
1. Metabolic Profile Radar Chart (5min Peak Window)
   - Dimensions: Heart, Lungs, Muscles, Power
"""
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from .common import (
    save_figure,
    create_empty_figure
)

def _find_column(df: pd.DataFrame, aliases: list) -> Optional[str]:
    """Find first existing column from aliases."""
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None

def generate_radar_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate Metabolic Profile Radar Chart (5min Peak Window)."""
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
    
    # Try to build DataFrame from time_series if source_df not available
    if source_df is None or source_df.empty:
        time_series = report_data.get("time_series", {})
        if time_series and time_series.get("power_watts"):
            source_df = pd.DataFrame({
                'watts': time_series.get("power_watts", []),
                'heartrate': time_series.get("hr_bpm", []),
                'smo2': time_series.get("smo2_pct", []),
                'tymeventilation': time_series.get("ve_lmin", time_series.get("ve_lpm", [])),
            })
        else:
            return create_empty_figure("Brak danych źródłowych", "Profil Metaboliczny", output_path, **cfg)

    # Resolve columns
    df = source_df.copy()
    pwr_col = _find_column(df, ['watts', 'watts_smooth', 'power', 'Power'])
    
    if not pwr_col:
        return create_empty_figure("Brak danych Mocy", "Profil Metaboliczny", output_path, **cfg)

    # Rolling 5min (300s)
    window_sec = 300
    df['rolling_watts'] = df[pwr_col].rolling(window=window_sec, min_periods=window_sec).mean()
    
    if df['rolling_watts'].isna().all():
        return create_empty_figure("Za krótki trening (<5min)", "Profil Metaboliczny", output_path, **cfg)
    
    peak_idx = df['rolling_watts'].idxmax()
    start_idx = max(0, peak_idx - window_sec + 1)
    df_peak = df.iloc[start_idx:peak_idx+1]
    
    # --- Metrics Calculation ---
    # 1. Heart (% HRmax)
    hr_col = _find_column(df, ['heartrate', 'hr'])
    max_hr = report_data.get("metadata", {}).get("max_hr")
    
    if not max_hr:
         max_hr = 190.0
         
    if hr_col and max_hr:
        peak_hr_avg = df_peak[hr_col].mean()
        pct_hr = min(100, (peak_hr_avg / max_hr * 100))
    else:
        pct_hr = 0
        
    # 2. Lungs (% VEmax)
    ve_col = _find_column(df, ['tymeventilation', 've', 'ventilation'])
    vt2_ve = 0
    try:
        thresholds = report_data.get("thresholds", {})
        vt2 = thresholds.get("vt2_result", thresholds.get("vt2", {}))
        vt2_ve = vt2.get("ve", 0)
    except:
        pass
    
    if ve_col:
        ve_max_user = vt2_ve * 1.1 if vt2_ve > 0 else df[ve_col].max()
        peak_ve_avg = df_peak[ve_col].mean()
        pct_ve = min(100, (peak_ve_avg / ve_max_user * 100) if ve_max_user > 0 else 0)
    else:
        pct_ve = 0
        
    # 3. Muscles (% Desaturation)
    smo2_col = _find_column(df, ['smo2', 'SmO2'])
    if smo2_col:
        peak_smo2_avg = df_peak[smo2_col].mean()
        pct_smo2 = min(100, 100 - peak_smo2_avg) # Utilization
    else:
        pct_smo2 = 0
        
    # 4. Power (% CP)
    cp_watts = report_data.get("cp_model", {}).get("cp_watts", 0)
    peak_w_avg = df_peak[pwr_col].mean()
    pct_power = min(120, (peak_w_avg / cp_watts * 100) if cp_watts and cp_watts > 0 else 0)
    
    # --- Plotting ---
    categories = ['Serce\n(% HRmax)', 'Płuca\n(% VEmax)', 'Mięśnie\n(% Desat)', 'Moc\n(% CP)']
    values = [pct_hr, pct_ve, pct_smo2, pct_power]
    
    # Close the loop
    values_closed = values + [values[0]]
    angles = np.linspace(0, 2*np.pi, len(categories), endpoint=False).tolist()
    angles += [angles[0]]
    
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw=dict(polar=True))
    
    # Draw polygon
    ax.plot(angles, values_closed, color='#00cc96', linewidth=2)
    ax.fill(angles, values_closed, color='#00cc96', alpha=0.25)
    
    # Labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=font_size)
    
    # Y-grids
    ax.set_ylim(0, 100)
    plt.yticks([20, 40, 60, 80, 100], color="grey", size=8)
    
    # Title
    plt.tight_layout()
    return save_figure(fig, output_path, **cfg)


def generate_vlamax_balance_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate VO2max vs VLaMax Balance Schema (Metabolic Profiling)."""
    if hasattr(config, '__dict__'):
        cfg = config.__dict__
    elif isinstance(config, dict):
        cfg = config
    else:
        cfg = {}

    figsize = cfg.get('figsize', (10, 4))
    
    # 1. Extraction of Ratios (following UI logic)
    # We need 1min, 5min, 20min power or proxy from report_data
    mmp_5min = report_data.get("metrics", {}).get("mmp_5min", 0)
    mmp_20min = report_data.get("metrics", {}).get("mmp_20min", 0)
    
    # Fallback 1: if not in metrics, try to calculate from source_df
    if (not mmp_5min or not mmp_20min) and source_df is not None and not source_df.empty:
        df = source_df.copy()
        pwr_col = _find_column(df, ['watts', 'power'])
        if pwr_col:
            mmp_5min = df[pwr_col].rolling(300, min_periods=60).mean().max()
            mmp_20min = df[pwr_col].rolling(1200, min_periods=300).mean().max()
    
    # Fallback 2: if source_df unavailable, try time_series from report_data
    if (not mmp_5min or not mmp_20min):
        time_series = report_data.get("time_series", {})
        power_watts = time_series.get("power_watts", [])
        if power_watts and len(power_watts) > 300:
            # pd is already imported at module level
            power_series = pd.Series(power_watts)
            mmp_5min = power_series.rolling(300, min_periods=60).mean().max()
            if len(power_watts) > 1200:
                mmp_20min = power_series.rolling(1200, min_periods=300).mean().max()
            elif len(power_watts) > 600:
                # Use 10min MMP as proxy for shorter tests
                mmp_20min = power_series.rolling(600, min_periods=300).mean().max()
            
    if not mmp_20min or mmp_20min == 0 or pd.isna(mmp_20min):
        return create_empty_figure("Brak danych (MMP 20 min)", "Profil Metaboliczny", output_path, **cfg)

    ratio = mmp_5min / mmp_20min
    
    # Classification logic
    if ratio > 1.08:
        profile = "Sprinter / Puncheur"
        desc = "Wysoki VLaMax (>0.5 mmol/L/s)"
        color = "#ff6b6b"
        marker_pos = 0.8 # Right side
    elif ratio < 0.95:
        profile = "Climber / TT Specialist"
        desc = "Niski VLaMax (<0.4 mmol/L/s)"
        color = "#4ecdc4"
        marker_pos = 0.2 # Left side
    else:
        profile = "All-Rounder"
        marker_pos = 0.5 # Middle
        desc = "Zbalansowany VLaMax (0.4-0.5 mmol/L/s)"
        color = "#ffd93d"

    # Plotting Schema
    fig, ax = plt.subplots(figsize=figsize)
    
    # Draw a scale line
    ax.axhline(0, color='grey', linewidth=2, zorder=1)
    
    # Base segments
    ax.plot([0, 0.35], [0, 0], color="#4ecdc4", linewidth=8, alpha=0.3, label="Time Trial / Diesel")
    ax.plot([0.35, 0.65], [0, 0], color="#ffd93d", linewidth=8, alpha=0.3, label="All-Rounder")
    ax.plot([0.65, 1.0], [0, 0], color="#ff6b6b", linewidth=8, alpha=0.3, label="Sprinter / Puncheur")
    
    # Add Marker
    ax.scatter([marker_pos], [0], color=color, s=200, edgecolor='white', zorder=5, label=f"Twój Profil: {profile}")
    
    # Labels
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-1, 1)
    ax.axis('off')
    
    ax.text(marker_pos, 0.15, f"{profile}", ha='center', va='bottom', fontweight='bold', fontsize=12, color=color)
    ax.text(marker_pos, -0.4, desc, ha='center', va='top', fontsize=10, style='italic')
    
    ax.text(0, -0.15, "DOMINACJA TLENOWA\n(Niski VLaMax)", ha='center', va='top', fontsize=8, color="#4ecdc4")
    ax.text(1.0, -0.15, "DOMINACJA BEZTLENOWA\n(Wysoki VLaMax)", ha='center', va='top', fontsize=8, color="#ff6b6b")

    # Title
    ax.set_title(f"Balans Metaboliczny: VO2max vs VLaMax (Ratio: {ratio:.2f})", 
                 pad=10, fontweight='bold')
    
    # Legend
    # ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=8)

    return save_figure(fig, output_path, **cfg)
