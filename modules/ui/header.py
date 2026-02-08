"""
Header UI Module.

Extracts sticky header and metric cards from app.py.
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any


def render_sticky_header(
    avg_power: float,
    avg_hr: float,
    avg_smo2: float,
    avg_cadence: float,
    avg_ve: float,
    duration_min: float
) -> None:
    """Render the sticky metrics header.
    
    Args:
        avg_power: Average power in watts
        avg_hr: Average heart rate in bpm
        avg_smo2: Average SmO2 in %
        avg_cadence: Average cadence in rpm
        avg_ve: Average ventilation in L/min
        duration_min: Duration in minutes
    """
    st.markdown(f"""
    <div class="sticky-metrics">
        <h4>⚡ Live Training Summary</h4>
        <div class="metric-row">
            <div class="metric-box">
                <div class="label">Avg Power</div>
                <div class="value">{avg_power:.0f} <span class="unit">W</span></div>
            </div>
            <div class="metric-box">
                <div class="label">Avg HR</div>
                <div class="value">{avg_hr:.0f} <span class="unit">bpm</span></div>
            </div>
            <div class="metric-box">
                <div class="label">Avg SmO2</div>
                <div class="value">{avg_smo2:.1f} <span class="unit">%</span></div>
            </div>
            <div class="metric-box">
                <div class="label">Cadence</div>
                <div class="value">{avg_cadence:.0f} <span class="unit">rpm</span></div>
            </div>
            <div class="metric-box">
                <div class="label">Avg VE</div>
                <div class="value">{avg_ve:.0f} <span class="unit">L/min</span></div>
            </div>
            <div class="metric-box">
                <div class="label">Duration</div>
                <div class="value">{duration_min:.0f} <span class="unit">min</span></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_metric_cards(
    np_val: float,
    tss: float,
    if_val: float,
    work_kj: float
) -> None:
    """Render the main metric cards row.
    
    Args:
        np_val: Normalized Power in watts
        tss: Training Stress Score
        if_val: Intensity Factor
        work_kj: Total work in kJ
    """
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "NP (Norm. Power)", 
        f"{np_val:.0f} W", 
        help="Normalized Power (Coggan Formula)"
    )
    m2.metric(
        "TSS", 
        f"{tss:.0f}", 
        help=f"IF: {if_val:.2f}"
    )
    m3.metric(
        "Praca [kJ]", 
        f"{work_kj:.0f}"
    )


def show_breadcrumb(group: str, section: str = None) -> None:
    """Display breadcrumb navigation.
    
    Args:
        group: Current tab group name
        section: Current sub-section name (optional)
    """
    if section:
        st.markdown(f'''
        <div class="breadcrumb-nav">
            🏠 Dashboard <span class="separator">›</span> 
            {group} <span class="separator">›</span> 
            <span class="current">{section}</span>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown(f'''
        <div class="breadcrumb-nav">
            🏠 Dashboard <span class="separator">›</span> 
            <span class="current">{group}</span>
        </div>
        ''', unsafe_allow_html=True)


# DEPRECATED: Moved to services.session_analysis
# Re-exported for backward compatibility


def extract_header_data(df: pd.DataFrame, metrics: Dict[str, Any]) -> Dict[str, float]:
    """Extract data needed for sticky header from DataFrame and metrics.
    
    Args:
        df: Session DataFrame
        metrics: Calculated metrics dict
        
    Returns:
        Dict with header display values
    """
    return {
        'avg_power': metrics.get('avg_watts', 0),
        'avg_hr': metrics.get('avg_hr', 0),
        'avg_smo2': df['smo2'].mean() if 'smo2' in df.columns else 0,
        'avg_cadence': metrics.get('avg_cadence', 0),
        'avg_ve': metrics.get('avg_vent', 0),
        'duration_min': len(df) / 60 if len(df) > 0 else 0
    }
