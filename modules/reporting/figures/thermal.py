"""
Thermal Analysis Charts Generator.

Generates:
1. Core Temperature vs Heat Strain Index (Time Series)
2. Efficiency Factor (W/HR) vs Core Temperature (Scatter with Trend)
"""
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from .common import (
    apply_common_style, 
    save_figure,
    create_empty_figure
)

def _find_column(df: pd.DataFrame, aliases: list) -> Optional[str]:
    """Find first existing column from aliases."""
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None

def generate_thermal_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate Core Temperature vs HSI chart (Time Series)."""
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
        if time_series and (time_series.get("core_temp") or time_series.get("hsi")):
            source_df = pd.DataFrame({
                'time': time_series.get("time_sec", []),
                'core_temperature': time_series.get("core_temp", []),
                'hsi': time_series.get("hsi", []),
            })
        else:
            return create_empty_figure("Brak danych źródłowych", "Termoregulacja", output_path, **cfg)

    # Resolve columns
    df = source_df.copy()
    temp_col = _find_column(df, ['core_temperature_smooth', 'core_temperature', 'core_temp', 'temp', 'temperature'])
    hsi_col = _find_column(df, ['hsi', 'heat_strain_index', 'HeatStrainIndex', 'heatstrainindex'])
    time_col = _find_column(df, ['time_min', 'time'])
    
    if not temp_col or not hsi_col:
        return create_empty_figure("Brak danych Temp/HSI", "Termoregulacja", output_path, **cfg)

    # Normalize time to minutes if needed
    if time_col == 'time':
        df['time_min'] = df['time'] / 60.0
        time_vals = df['time_min']
    else:
        time_vals = df[time_col]

    fig, ax1 = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Core Temp (Left Axis)
    l1, = ax1.plot(time_vals, df[temp_col], color='#ff7f0e', label="Temp. rdzenia", linewidth=2)
    ax1.set_xlabel("Czas [min]", fontsize=font_size)
    ax1.set_ylabel("Temperatura [°C]", fontsize=font_size, color='#ff7f0e')
    ax1.tick_params(axis='y', labelcolor='#ff7f0e')
    
    # Threshold lines for Temp
    ax1.axhline(y=38.5, color='red', linestyle='--', alpha=0.5, linewidth=1, label="Krytyczna (38.5°C)")
    ax1.axhline(y=37.5, color='green', linestyle=':', alpha=0.5, linewidth=1, label="Optymalna (37.5°C)")

    # HSI (Right Axis)
    ax2 = ax1.twinx()
    l2, = ax2.plot(time_vals, df[hsi_col], color='#d62728', linestyle=':', label="Wsk. Obciążenia Cieplnego", linewidth=2)
    ax2.set_ylabel("Wskaźnik Obciążenia Cieplnego (HSI)", fontsize=font_size, color='#d62728')
    ax2.tick_params(axis='y', labelcolor='#d62728')
    ax2.set_ylim(0, 12)  # HSI scale usually 0-10+

    # Title & Legend
    ax1.set_title("Termoregulacja: Temp. rdzenia vs HSI", fontsize=title_size, fontweight='bold')
    
    lines = [l1, l2]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', framealpha=0.9)
    
    apply_common_style(fig, ax1, **cfg)
    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)


def generate_efficiency_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None
) -> bytes:
    """Generate Efficiency Factor vs Temperature scatter plot."""
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
        if time_series and time_series.get("power_watts") and time_series.get("core_temp"):
            source_df = pd.DataFrame({
                'watts': time_series.get("power_watts", []),
                'heartrate': time_series.get("hr_bpm", []),
                'core_temperature': time_series.get("core_temp", []),
            })
        else:
            return create_empty_figure("Brak danych źródłowych", "Spadek Efektywności", output_path, **cfg)
        
    df = source_df.copy()
    temp_col = _find_column(df, ['core_temperature_smooth', 'core_temperature', 'core_temp'])
    hr_col = _find_column(df, ['heartrate', 'heartrate_smooth', 'hr'])
    pwr_col = _find_column(df, ['watts', 'watts_smooth', 'power'])
    
    if not (temp_col and hr_col and pwr_col):
        return create_empty_figure("Brak danych Power/HR/Temp", "Spadek Efektywności", output_path, **cfg)
        
    # Filter valid data
    mask = (df[pwr_col] > 10) & (df[hr_col] > 60)
    df_clean = df[mask].copy()
    
    if df_clean.empty:
        return create_empty_figure("Zbyt mało danych", "Spadek Efektywności", output_path, **cfg)

    # Calculate Efficiency (W/HR)
    df_clean['eff_raw'] = df_clean[pwr_col] / df_clean[hr_col]
    # Filter outliers
    df_clean = df_clean[df_clean['eff_raw'] < 6.0]
    
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Scatter points
    ax.scatter(df_clean[temp_col], df_clean['eff_raw'], 
                    c='#1f77b4', alpha=0.3, s=20, label="Punkty pomiarowe")
                    
    # Trend line
    try:
        z = np.polyfit(df_clean[temp_col], df_clean['eff_raw'], 1)
        p = np.poly1d(z)
        x_trend = np.linspace(df_clean[temp_col].min(), df_clean[temp_col].max(), 100)
        ax.plot(x_trend, p(x_trend), "r--", linewidth=2, label=f"Trend (Slope: {z[0]:.3f})")
    except:
        pass 

    ax.set_xlabel("Temperatura rdzenia [°C]", fontsize=font_size)
    ax.set_ylabel("Współczynnik Efektywności [W/bpm]", fontsize=font_size)
    ax.set_title("Spadek Efektywności (Cardiac Drift) vs Temperatura", fontsize=title_size, fontweight='bold')
    ax.legend(loc='upper right')
    
    apply_common_style(fig, ax, **cfg)
    plt.tight_layout()
    
    return save_figure(fig, output_path, **cfg)
