"""
Biomechanics Figure Generator for Ramp Test PDF Reports.
Generates Cadence/Torque time series and Torque-SmO2 relationship charts.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any, Optional

from .common import get_color, apply_common_style, save_figure, create_empty_figure


def generate_biomech_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional["pd.DataFrame"] = None
) -> bytes:
    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})
    
    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        # Standardize column names safely
        df = df.rename(columns={c: c.lower() for c in df.columns})
        col_map = {
            'heartrate': 'hr', 'heart_rate': 'hr', 'bpm': 'hr',
            'watts': 'power', 'power': 'power', 'watts_smooth': 'power',
            'cadence': 'cad_raw', 'cad': 'cad_raw',
            'smo2': 'smo2', 'smo2_smooth': 'smo2'
        }
        df = df.rename(columns=col_map)
        
        # If we have multiple columns with the same name, take the first one
        df = df.loc[:, ~df.columns.duplicated()]
        
        if 'power' in df.columns and 'cad_raw' in df.columns:
            # Smooth data
            df['cadence'] = df['cad_raw'].rolling(window=10, min_periods=1, center=True).mean()
            
            # Calculate Torque
            df['torque'] = df.apply(
                lambda row: row['power'] / (row['cadence'] * 2 * np.pi / 60) if row['cadence'] > 20 else 0,
                axis=1
            )
            df['torque_smooth'] = df['torque'].rolling(window=15, min_periods=1, center=True).mean()
            
            power_data = df['power'].tolist()
            cadence_data = df['cadence'].tolist()
            torque_data = df['torque_smooth'].tolist()
            
            # Time axis
            if 'time_sec' in df.columns:
                time_min = (df['time_sec'] / 60).tolist()
            elif 'seconds' in df.columns:
                time_min = (df['seconds'] / 60).tolist()
            elif 'time' in df.columns:
                time_min = (df['time'] / 60).tolist()
            else:
                time_min = (df.index / 60).tolist()
        else:
            time_min, cadence_data, torque_data = [], [], []
    else:
        # Fallback to JSON time_series
        power_vals = time_series.get("power_watts", [])
        cadence_vals = time_series.get("cadence_rpm", [])
        time_sec = time_series.get("time_sec", [])
        
        if power_vals and cadence_vals and time_sec:
            time_min = [t / 60 for t in time_sec]
            cadence_data = pd.Series(cadence_vals).rolling(window=10, min_periods=1, center=True).mean().tolist()
            
            # Calculate Torque from JSON data
            torque_data = []
            for p, c in zip(power_vals, cadence_data):
                t = p / (c * 2 * np.pi / 60) if c > 20 else 0
                torque_data.append(t)
            
            torque_data = pd.Series(torque_data).rolling(window=15, min_periods=1, center=True).mean().tolist()
        else:
            time_min, cadence_data, torque_data = [], [], []

    # Prepare config
    cfg = config.__dict__ if hasattr(config, "__dict__") else (config or {})
    
    if not time_min or not torque_data:
        return create_empty_figure("Brak danych mocy/kadencji dla biomechaniki", "Biomechanika", output_path, **cfg)

    # Use the prepared data
    df_plot = pd.DataFrame({
        'time_min': time_min,
        'cadence': cadence_data,
        'torque_smooth': torque_data
    })

    # Prepare config
    cfg = config.__dict__ if hasattr(config, "__dict__") else (config or {})
    figsize = cfg.get("figsize", (10, 6))

    # 2. Create Plot
    fig, ax1 = plt.subplots(figsize=figsize)
    
    # Torque (Primary Y-axis) - Magenta/Pink style
    color_torque = "#e377c2"
    ax1.plot(df_plot['time_min'], df_plot['torque_smooth'], color=color_torque, label='Moment (Torque)', linewidth=1.5)
    ax1.set_xlabel('Czas [min]')
    ax1.set_ylabel('Moment Obrotowy [Nm]', color=color_torque)
    ax1.tick_params(axis='y', labelcolor=color_torque)
    
    # Cadence (Secondary Y-axis) - Cyan/Blue style
    ax2 = ax1.twinx()
    color_cad = "#19d3f3"
    ax2.plot(df_plot['time_min'], df_plot['cadence'], color=color_cad, label='Kadencja', linewidth=1.2, alpha=0.7)
    ax2.set_ylabel('Kadencja [RPM]', color=color_cad)
    ax2.tick_params(axis='y', labelcolor=color_cad)
    
    # Metadata / Footer
    session_id = report_data.get("metadata", {}).get("session_id", "unknown")[:8]
    fig.text(0.01, 0.01, f"ID: {session_id} | Biomechanika (Torque vs Cadence)", 
             ha='left', va='bottom', fontsize=8, color=get_color("secondary"), style='italic')

    apply_common_style(fig, ax1, title="Analiza Przekazu Mocy (Siła vs Szybkość)", **cfg)
    ax1.grid(True, alpha=0.3)
    
    return save_figure(fig, output_path, **cfg)


def generate_torque_smo2_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional["pd.DataFrame"] = None
) -> bytes:
    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})
    
    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        # Required columns
        power_col = next((c for c in ['watts', 'power', 'watts_smooth'] if c in df.columns), None)
        cad_col = next((c for c in ['cadence', 'cad'] if c in df.columns), None)
        smo2_col = next((c for c in ['smo2', 'smo2_smooth', 'smo2_pct'] if c in df.columns), None)
        
        if all([power_col, cad_col, smo2_col]):
            power_vals = df[power_col].tolist()
            cadence_vals = df[cad_col].tolist()
            smo2_vals = df[smo2_col].tolist()
        else:
            power_vals, cadence_vals, smo2_vals = [], [], []
    else:
        # Fallback to JSON
        power_vals = time_series.get("power_watts", [])
        cadence_vals = time_series.get("cadence_rpm", [])
        smo2_vals = time_series.get("smo2_pct", [])

    # Prepare config
    cfg = config.__dict__ if hasattr(config, "__dict__") else (config or {})

    if not all([power_vals, cadence_vals, smo2_vals]):
        return create_empty_figure("Brak danych (Power, Cad, SmO2) dla Torque-SmO2", "Fizjologia Okluzji", output_path, **cfg)

    # Prepare DataFrame for binning
    df_calc = pd.DataFrame({
        'power': power_vals,
        'cadence': cadence_vals,
        'smo2': smo2_vals
    })

    # Calculate Torque
    df_calc['torque'] = df_calc.apply(
        lambda row: row['power'] / (row['cadence'] * 2 * np.pi / 60) if row['cadence'] > 30 else 0,
        axis=1
    )
    
    # Filter valid data (exclude coasting/zeros)
    mask = (df_calc['torque'] > 2) & (df_calc['smo2'] > 2)
    df_clean = df_calc[mask].copy()
    
    if len(df_clean) < 20:
        return create_empty_figure("Za mało punktów danych do analizy Torque-SmO2", "Fizjologia Okluzji", output_path, **cfg)

    # Binning by Torque (every 2 Nm)
    df_clean['torque_bin'] = (df_clean['torque'] // 2 * 2).astype(int)
    bin_stats = df_clean.groupby('torque_bin')['smo2'].agg(['mean', 'std', 'count']).reset_index()
    bin_stats = bin_stats[bin_stats['count'] > 5] # Min 5 samples per bin
    
    if bin_stats.empty:
        return create_empty_figure("Brak statystyki w koszykach momentu", output_path)

    # Plot
    cfg = config.__dict__ if hasattr(config, "__dict__") else (config or {})
    figsize = cfg.get("figsize", (10, 6))
    fig, ax = plt.subplots(figsize=figsize)
    
    # Mean line
    color_main = "#FF4B4B"
    ax.plot(bin_stats['torque_bin'], bin_stats['mean'], marker='o', color=color_main, 
            linewidth=2.5, label='Średnie SmO2', zorder=3)
    
    # STD Fill
    ax.fill_between(bin_stats['torque_bin'], 
                    bin_stats['mean'] - bin_stats['std'], 
                    bin_stats['mean'] + bin_stats['std'], 
                    color=color_main, alpha=0.15, label='Odchylenie (±1SD)', zorder=2)
    
    ax.set_xlabel('Moment Obrotowy [Nm]')
    ax.set_ylabel('SmO2 [%]')
    ax.set_ylim(0, 100)
    
    session_id = report_data.get("metadata", {}).get("session_id", "unknown")[:8]
    fig.text(0.01, 0.01, f"ID: {session_id} | Fizjologia Okluzji (Analiza Koszykowa)", 
             ha='left', va='bottom', fontsize=8, color=get_color("secondary"), style='italic')

    apply_common_style(fig, ax, title="Agregacja: Wpływ Siły (Momentu) na Tlen (SmO2)", **cfg)
    ax.grid(True, alpha=0.3)
    
    return save_figure(fig, output_path, **cfg)
