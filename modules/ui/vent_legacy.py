"""Ventilation legacy raw data analysis tools."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def _render_legacy_tools(interval_data):
    """Render legacy raw data analysis tools."""
    with st.expander("🔧 Szczegółowa Analiza (Surowe Dane)", expanded=False):
        st.markdown("### Surowe Dane i Korelacje")

        if "watts" in interval_data.columns:
            interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                "%H:%M:%S"
            )

            fig_scatter = go.Figure()
            fig_scatter.add_trace(
                go.Scatter(
                    x=interval_data["watts"],
                    y=interval_data["tymeventilation"],
                    customdata=interval_time_str,
                    mode="markers",
                    marker=dict(
                        size=6,
                        color=interval_data["time"],
                        colorscale="Viridis",
                        showscale=True,
                        colorbar=dict(title="Czas (s)"),
                    ),
                    name="VE vs Power",
                    hovertemplate="<b>Czas:</b> %{customdata}<br><b>Moc:</b> %{x:.0f} W<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
                )
            )
            fig_scatter.update_layout(
                title="Korelacja: VE vs Moc",
                xaxis_title="Moc [W]",
                yaxis_title="VE (L/min)",
                height=400,
                hovermode="closest",
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        if "tymebreathrate" in interval_data.columns:
            st.subheader("Częstość Oddechów (Breathing Rate)")

            interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                "%H:%M:%S"
            )

            fig_br = go.Figure()
            fig_br.add_trace(
                go.Scatter(
                    x=interval_data["time"],
                    y=interval_data["tymebreathrate"],
                    customdata=interval_time_str,
                    mode="lines",
                    name="BR",
                    line=dict(color="#00cc96", width=2),
                    hovertemplate="<b>Czas:</b> %{customdata}<br><b>BR:</b> %{y:.1f} /min<extra></extra>",
                )
            )
            fig_br.update_layout(
                title="Breathing Rate",
                xaxis_title="Czas",
                yaxis_title="BR (/min)",
                height=300,
                hovermode="x unified",
            )
            st.plotly_chart(fig_br, use_container_width=True)

        st.subheader("Wentylacja Minutowa (VE)")

        interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime("%H:%M:%S")

        fig_ve = go.Figure()
        fig_ve.add_trace(
            go.Scatter(
                x=interval_data["time"],
                y=interval_data["tymeventilation"],
                customdata=interval_time_str,
                mode="lines",
                name="VE",
                line=dict(color="#ffa15a", width=2),
                hovertemplate="<b>Czas:</b> %{customdata}<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
            )
        )
        fig_ve.update_layout(
            title="Minute Ventilation (VE)",
            xaxis_title="Czas",
            yaxis_title="VE (L/min)",
            height=300,
            hovermode="x unified",
        )
        st.plotly_chart(fig_ve, use_container_width=True)
