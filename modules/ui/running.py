"""
Running-specific UI components.

Charts, metrics, and visualizations for running analysis.
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from modules.calculations.pace_utils import format_pace
from modules.calculations.pace import calculate_pace_zones_time


def format_pace_for_display(pace_sec_per_km: float) -> str:
    """Format pace for UI display."""
    return format_pace(pace_sec_per_km)


def get_pace_zone_color(pace: float, threshold_pace: float) -> str:
    """Get color for pace zone."""
    if threshold_pace <= 0:
        return "#808080"
    ratio = pace / threshold_pace
    
    if ratio > 1.15:
        return "#3498db"  # Blue - Recovery
    elif ratio > 1.05:
        return "#2ecc71"  # Green - Aerobic
    elif ratio > 0.95:
        return "#f1c40f"  # Yellow - Tempo
    elif ratio > 0.88:
        return "#e67e22"  # Orange - Threshold
    else:
        return "#e74c3c"  # Red - Interval/Repetition


def calculate_pace_summary_stats(df: pd.DataFrame, threshold_pace: float) -> Dict:
    """Calculate summary statistics for pace data."""
    stats = {}
    
    if "pace" in df.columns:
        paces = df["pace"].dropna()
        stats["avg_pace"] = float(paces.mean())
        stats["min_pace"] = float(paces.min())
        stats["max_pace"] = float(paces.max())
    
    if "gap" in df.columns:
        gaps = df["gap"].dropna()
        stats["avg_gap"] = float(gaps.mean())
    
    if "pace" in df.columns:
        stats["time_in_zones"] = calculate_pace_zones_time(df, threshold_pace)
    
    return stats


def render_pace_chart(df: pd.DataFrame, threshold_pace: float):
    """Render pace chart with zones."""
    if "pace" not in df.columns:
        st.warning("Brak danych tempa")
        return
    
    fig = go.Figure()
    
    # Pace line
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["pace"],
        mode='lines',
        name='Tempo',
        line=dict(color='#3498db', width=2)
    ))
    
    # GAP line if available
    if "gap" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["gap"],
            mode='lines',
            name='GAP',
            line=dict(color='#2ecc71', width=2, dash='dash')
        ))
    
    # Threshold line
    fig.add_hline(
        y=threshold_pace,
        line_dash="dot",
        line_color="red",
        annotation_text="Prog"
    )
    
    fig.update_layout(
        title="Tempo podczas biegu",
        yaxis_title="Tempo (s/km)",
        xaxis_title="Czas",
        yaxis=dict(autorange="reversed")
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_pace_zones_bar(time_in_zones: Dict[str, int]):
    """Render bar chart of time in pace zones."""
    if not time_in_zones:
        return
    
    zones = list(time_in_zones.keys())
    times = [time_in_zones[z] / 60 for z in zones]
    
    colors = ["#3498db", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#9b59b6"]
    
    fig = go.Figure(data=[
        go.Bar(x=zones, y=times, marker_color=colors[:len(zones)])
    ])
    
    fig.update_layout(
        title="Czas w strefach tempa",
        yaxis_title="Czas (min)",
        xaxis_title="Strefa"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_running_metrics_cards(
    avg_pace: float,
    threshold_pace: float,
    distance_km: float,
    rss: float
):
    """Render running metrics cards."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Srednie tempo",
            format_pace_for_display(avg_pace),
            help=f"Prog: {format_pace_for_display(threshold_pace)}"
        )
    
    with col2:
        st.metric("Dystans", f"{distance_km:.2f} km")
    
    with col3:
        st.metric("RSS", f"{rss:.0f}", help="Running Stress Score")
    
    with col4:
        if threshold_pace > 0:
            intensity = threshold_pace / avg_pace if avg_pace > 0 else 0
            st.metric("IF", f"{intensity:.2f}", help="Intensity Factor")
