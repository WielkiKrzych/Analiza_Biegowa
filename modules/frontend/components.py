"""
Frontend Components Module.

Reusable UI components (widgets) for the application.
"""

from typing import Any, Dict

import streamlit as st


def _format_pace_mmss(pace_sec_per_km: float) -> str:
    """Format a pace given in seconds/km as ``m:ss`` (e.g. 315 -> ``5:15``)."""
    if not pace_sec_per_km or pace_sec_per_km <= 0:
        return "—"
    minutes = int(pace_sec_per_km // 60)
    seconds = int(round(pace_sec_per_km - minutes * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}"


class UIComponents:
    """Namespace for reusable UI components."""

    @staticmethod
    def show_breadcrumb(group: str, section: str = None) -> None:
        """Render a breadcrumb navigation aid."""
        if section:
            html = f"""
            <div class="breadcrumb-nav">
                🏠 Dashboard <span class="separator">›</span>
                {group} <span class="separator">›</span>
                <span class="current">{section}</span>
            </div>
            """
        else:
            html = f"""
            <div class="breadcrumb-nav">
                🏠 Dashboard <span class="separator">›</span>
                <span class="current">{group}</span>
            </div>
            """
        st.markdown(html, unsafe_allow_html=True)

    @staticmethod
    def render_sticky_header(data: Dict[str, Any]) -> None:
        """Render the sticky metrics header (running-first, dual-mode aware)."""
        if not data:
            return

        is_running = data.get("is_running", False)
        if is_running:
            intensity_label = "Avg Pace"
            intensity_value = _format_pace_mmss(data.get("avg_pace", 0))
            intensity_unit = "min/km"
            cadence_unit = "spm"
        else:
            intensity_label = "Avg Power"
            intensity_value = f"{data.get('avg_power', 0):.0f}"
            intensity_unit = "W"
            cadence_unit = "rpm"

        html = f"""
        <div class="sticky-metrics">
            <h4>⚡ Live Training Summary</h4>
            <div class="metric-row">
                <div class="metric-box">
                    <div class="label">{intensity_label}</div>
                    <div class="value">{intensity_value} <span class="unit">{intensity_unit}</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Avg HR</div>
                    <div class="value">{data.get("avg_hr", 0):.0f} <span class="unit">bpm</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Avg SmO2</div>
                    <div class="value">{data.get("avg_smo2", 0):.1f} <span class="unit">%</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Cadence</div>
                    <div class="value">{data.get("avg_cadence", 0):.0f} <span class="unit">{cadence_unit}</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Avg VE</div>
                    <div class="value">{data.get("avg_ve", 0):.0f} <span class="unit">L/min</span></div>
                </div>
                <div class="metric-box">
                    <div class="label">Duration</div>
                    <div class="value">{data.get("duration_min", 0):.0f} <span class="unit">min</span></div>
                </div>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
