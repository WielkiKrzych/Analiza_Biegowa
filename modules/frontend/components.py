"""
Frontend Components Module.

Reusable UI components (widgets) for the application.
"""
import streamlit as st
from typing import Dict, Any

class UIComponents:
    """Namespace for reusable UI components."""

    @staticmethod
    def show_breadcrumb(group: str, section: str = None) -> None:
        """Render a breadcrumb navigation aid."""
        if section:
            html = f'''
            <div class="breadcrumb-nav">
                🏠 Dashboard <span class="separator">›</span> 
                {group} <span class="separator">›</span> 
                <span class="current">{section}</span>
            </div>
            '''
        else:
            html = f'''
            <div class="breadcrumb-nav">
                🏠 Dashboard <span class="separator">›</span> 
                <span class="current">{group}</span>
            </div>
            '''
        st.markdown(html, unsafe_allow_html=True)

    @staticmethod
    def render_sticky_header(data: Dict[str, Any]) -> None:
        """Render the sticky metrics header."""
        if not data:
            return
            
        html = f"""
        <div class="sticky-metrics">
            <h4>⚡ Live Training Summary</h4>
            <div class="metric-row">
                <div class="metric-box">
                    <div class="label">Avg Power</div>
                    <div class="value">{data.get('avg_power', 0):.0f} <span class="unit">W</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Avg HR</div>
                    <div class="value">{data.get('avg_hr', 0):.0f} <span class="unit">bpm</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Avg SmO2</div>
                    <div class="value">{data.get('avg_smo2', 0):.1f} <span class="unit">%</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Cadence</div>
                    <div class="value">{data.get('avg_cadence', 0):.0f} <span class="unit">rpm</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Avg VE</div>
                    <div class="value">{data.get('avg_ve', 0):.0f} <span class="unit">L/min</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Duration</div>
                    <div class="value">{data.get('duration_min', 0):.0f} <span class="unit">min</span></div>
                </div>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
