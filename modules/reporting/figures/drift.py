"""
Drift Analysis Scatter Charts Generator.

Generates:
1. Power vs HR Scatter (Decoupling Map)
2. Power vs SmO2 Scatter (Muscle Oxygen Map)
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

def generate_power_hr_scatter(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate Power vs Heart Rate scatter plot with time coloring."""
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
    
    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})
    
    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        hr_col = _find_column(df, ['heartrate', 'heartrate_smooth', 'hr', 'heart_rate'])
        pwr_col = _find_column(df, ['watts', 'watts_smooth', 'power', 'Power', 'watts_smooth_5s'])
        time_col = _find_column(df, ['time_min', 'time', 'seconds'])
        
        if hr_col and pwr_col:
            mask = (df[pwr_col] > 10) & (df[hr_col] > 30)
            df_clean = df[mask].copy()
            power_data = df_clean[pwr_col].tolist()
            hr_data = df_clean[hr_col].tolist()
            c_vals = df_clean[time_col].tolist() if time_col else None
        else:
            power_data, hr_data, c_vals = [], [], None
    else:
        # Fallback to JSON time_series
        power_data = time_series.get("power_watts", [])
        hr_data = time_series.get("hr_bpm", [])
        c_vals = time_series.get("time_sec", [])
    
    if not hr_data or not power_data:
        return create_empty_figure("Brak danych Power/HR", "Power vs HR", output_path, **cfg)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Scatter with time coloring
    if c_vals and len(c_vals) == len(power_data):
        sc = ax.scatter(power_data, hr_data, 
                       c=c_vals, cmap='viridis', alpha=0.5, s=20)
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label('Czas')
    else:
        ax.scatter(power_data, hr_data, 
                   c=get_color("power"), alpha=0.5, s=20)
        
    ax.set_xlabel("Moc [W]", fontsize=font_size)
    ax.set_ylabel("HR [bpm]", fontsize=font_size)
    ax.set_title("Relacja: Moc vs Tętno (Decoupling)", fontsize=title_size, fontweight='bold')
    
    apply_common_style(fig, ax, **cfg)
    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)


def generate_power_smo2_scatter(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate Power vs SmO2 scatter plot with time coloring."""
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
    
    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})
    
    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        smo2_col = _find_column(df, ['smo2', 'SmO2', 'muscle_oxygen', 'smo2_smooth', 'smo2_pct'])
        pwr_col = _find_column(df, ['watts', 'watts_smooth', 'power', 'Power', 'watts_smooth_5s'])
        time_col = _find_column(df, ['time_min', 'time', 'seconds'])
        
        if smo2_col and pwr_col:
            mask = (df[pwr_col] > 10) & (df[smo2_col] > 0)
            df_clean = df[mask].copy()
            power_data = df_clean[pwr_col].tolist()
            smo2_data = df_clean[smo2_col].tolist()
            c_vals = df_clean[time_col].tolist() if time_col else None
        else:
            power_data, smo2_data, c_vals = [], [], None
    else:
        # Fallback to JSON time_series
        power_data = time_series.get("power_watts", [])
        smo2_data = time_series.get("smo2_pct", [])
        c_vals = time_series.get("time_sec", [])
        
    if not power_data or not smo2_data:
        return create_empty_figure("Brak danych Power/SmO2", "Power vs SmO2", output_path, **cfg)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Scatter with time coloring
    if c_vals and len(c_vals) == len(power_data):
        sc = ax.scatter(power_data, smo2_data, 
                       c=c_vals, cmap='inferno', alpha=0.5, s=20) 
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label('Czas')
    else:
        ax.scatter(power_data, smo2_data, 
                   c=get_color("smo2"), alpha=0.5, s=20)
        
    ax.set_xlabel("Moc [W]", fontsize=font_size)
    ax.set_ylabel("SmO₂ [%]", fontsize=font_size)
    ax.set_title("Relacja: Moc vs Saturacja Mięśniowa", fontsize=title_size, fontweight='bold')
    
    apply_common_style(fig, ax, **cfg)
    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)


def generate_drift_heatmap(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None,
    mode: str = "hr" # "hr" or "smo2"
) -> bytes:
    """Generate Decoupling Heatmap (Density map of Power vs Physiological signal)."""
    if hasattr(config, '__dict__'):
        cfg = config.__dict__
    elif isinstance(config, dict):
        cfg = config
    else:
        cfg = {}

    figsize = cfg.get('figsize', (10, 6))
    dpi = cfg.get('dpi', 150)
    
    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})
    
    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        pwr_col = _find_column(df, ['watts', 'power', 'Power', 'watts_smooth'])
        
        if mode == "hr":
            target_col = _find_column(df, ['heartrate', 'hr', 'heartrate_smooth'])
        else:
            target_col = _find_column(df, ['smo2', 'SmO2', 'muscle_oxygen', 'smo2_smooth', 'smo2_pct'])

        if pwr_col and target_col:
            mask = (df[pwr_col] > 20) & (df[target_col] > 0)
            df_clean = df[mask].copy()
            power_data = df_clean[pwr_col].tolist()
            target_data = df_clean[target_col].tolist()
        else:
            power_data, target_data = [], []
    else:
        # Fallback to JSON time_series
        power_data = time_series.get("power_watts", [])
        if mode == "hr":
            target_data = time_series.get("hr_bpm", [])
        else:
            target_data = time_series.get("smo2_pct", [])

    if mode == "hr":
        cmap = 'magma'
        label = "HR [bpm]"
        title = "Mapa Dryfu: Moc vs Tętno"
    else:
        cmap = 'viridis'
        label = "SmO2 [%]"
        title = "Mapa Oksydacji: Moc vs Saturacja"

    if not power_data or not target_data or len(power_data) < 100:
        return create_empty_figure(f"Za mało danych dla mapy gęstości {mode.upper()}", "Mapa Dryfu", output_path, **cfg)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Hexbin for heatmap effect
    hb = ax.hexbin(power_data, target_data, 
                   gridsize=30, cmap=cmap, mincnt=1, marginals=False)
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label('Gęstość (liczba próbek)')
    
    ax.set_xlabel("Moc [W]")
    ax.set_ylabel(label)
    ax.set_title(title, fontweight='bold', pad=15)
    
    apply_common_style(fig, ax, **cfg)
    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)
