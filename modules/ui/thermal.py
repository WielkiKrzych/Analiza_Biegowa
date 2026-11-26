from typing import Optional

import plotly.graph_objects as go
import streamlit as st

from modules.calculations.thermal import (
    calculate_core_temp_zones_time,
    calculate_thermal_drift_rate,
)


@st.cache_data(ttl=3600, show_spinner=False)
def _build_thermal_chart(df_plot) -> Optional[go.Figure]:
    """Build thermal regulation chart (cached)."""
    fig = go.Figure()

    # 1. CORE TEMP (Oś Lewa)
    if "core_temperature_smooth" in df_plot.columns:
        fig.add_trace(
            go.Scatter(
                x=df_plot["time_min"],
                y=df_plot["core_temperature_smooth"],
                name="Core Temp",
                line=dict(color="#ff7f0e", width=2),
                hovertemplate="🌡️ Temp: %{y:.2f}°C<extra></extra>",
            )
        )

    # 2. HSI - HEAT STRAIN INDEX (Oś Prawa)
    if "hsi" in df_plot.columns:
        fig.add_trace(
            go.Scatter(
                x=df_plot["time_min"],
                y=df_plot["hsi"],
                name="HSI",
                yaxis="y2",
                line=dict(color="#d62728", width=2, dash="dot"),
                hovertemplate="🌡️ HSI: %{y:.1f}<extra></extra>",
            )
        )

    fig.add_hline(
        y=38.5,
        line_dash="dash",
        line_color="red",
        opacity=0.5,
        annotation_text="Krytyczna (38.5°C)",
        annotation_position="top left",
    )
    fig.add_hline(
        y=37.5,
        line_dash="dot",
        line_color="green",
        opacity=0.5,
        annotation_text="Optymalna (37.5°C)",
        annotation_position="bottom left",
    )

    # Convert time_min to hh:mm:ss format for x-axis
    import numpy as np

    time_vals = (
        df_plot["time_min"].values
        if hasattr(df_plot["time_min"], "values")
        else np.array(df_plot["time_min"])
    )
    tick_step = 5  # every 5 minutes
    tick_vals = np.arange(0, time_vals.max() + tick_step, tick_step)
    tick_text = [f"{int(m // 60):02d}:{int(m % 60):02d}:00" for m in tick_vals]

    fig.update_layout(
        template="plotly_dark",
        title="Termoregulacja: Temperatura Głęboka vs Indeks Zmęczenia (HSI)",
        hovermode="x unified",
        xaxis=dict(
            title="Czas [hh:mm:ss]",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
        ),
        yaxis=dict(title="Core Temp [°C]"),
        yaxis2=dict(
            title="HSI [0-10]", overlaying="y", side="right", showgrid=False, range=[0, 12]
        ),
        legend=dict(orientation="h", y=1.1, x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        height=450,
    )

    return fig


def _find_column(df, aliases: list) -> Optional[str]:
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None


def _render_core_temp_zones(df_plot) -> None:
    temp_col_name = _find_column(
        df_plot, ["core_temperature_smooth", "core_temperature", "core_temp"]
    )
    if not temp_col_name:
        return

    st.subheader("🌡️ Strefy Temperatury Głębokiej")
    temp_series = df_plot[temp_col_name].dropna()
    if len(temp_series) <= 60:
        st.divider()
        return

    zones_time = calculate_core_temp_zones_time(temp_series)
    total_sec = sum(zones_time.values())
    if total_sec > 0:
        zone_colors = {
            "Optimal (<38.0°C)": "#2ecc71",
            "Elevated (38.0-38.5°C)": "#f1c40f",
            "High (38.5-39.0°C)": "#e67e22",
            "Critical (39.0-39.5°C)": "#e74c3c",
            "Dangerous (>39.5°C)": "#9b59b6",
        }
        zone_names = list(zones_time.keys())
        zone_pcts = [zones_time[z] / total_sec * 100 for z in zone_names]
        zone_cols = [zone_colors.get(z, "#808080") for z in zone_names]
        fig_tz = go.Figure(
            data=[
                go.Bar(
                    x=zone_pcts,
                    y=zone_names,
                    orientation="h",
                    marker_color=zone_cols,
                    text=[f"{p:.0f}%" for p in zone_pcts],
                    textposition="auto",
                )
            ]
        )
        fig_tz.update_layout(
            template="plotly_dark",
            title="Czas w strefach temperatury głębokiej",
            xaxis_title="% czasu",
            height=250,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_tz, use_container_width=True)

    drift = calculate_thermal_drift_rate(temp_series)
    if drift.get("is_valid"):
        col_dr1, col_dr2, col_dr3 = st.columns(3)
        col_dr1.metric(
            "Drift Rate",
            f"{drift['drift_c_per_hour']:.2f} °C/h",
            help="Szybkość wzrostu temperatury — marker hydratacji i sprawności termoregulacyjnej",
        )
        col_dr2.metric("R²", f"{drift['r_squared']:.2f}")
        col_dr3.metric("Klasyfikacja", drift["classification"])

    st.divider()


def render_thermal_tab(df_plot):
    st.header("Wydajność Chłodzenia i Koszt Termiczny")

    st.divider()

    fig_t = _build_thermal_chart(df_plot)
    if fig_t is not None:
        st.plotly_chart(fig_t, use_container_width=True)

    _render_core_temp_zones(df_plot)

    st.header("Cardiac Drift vs Temperatura")
