"""
Summary timeline: training timeline chart and metrics panel.

Contains the cached training timeline chart builder and the comprehensive
metrics panel rendered below it (sections 1 and 1a of the summary tab).
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.config import Config


@st.cache_data(ttl=3600, show_spinner=False)
def _build_training_timeline_chart(df_plot: pd.DataFrame) -> Optional[go.Figure]:  # noqa: C901
    """Build training timeline chart with pace, HR, SmO2, VE (cached)."""
    fig = go.Figure()
    time_x = (
        df_plot["time_min"]
        if "time_min" in df_plot.columns
        else df_plot["time"] / 60
        if "time" in df_plot.columns
        else None
    )

    if time_x is None:
        return None

    # Build hh:mm:ss time strings for tooltips
    if "time" in df_plot.columns:
        _time_hms = [
            f"{int(t // 3600):02d}:{int((t % 3600) // 60):02d}:{int(t % 60):02d}"
            if pd.notna(t)
            else "--:--:--"
            for t in df_plot["time"]
        ]
    elif "time_min" in df_plot.columns:
        _time_hms = [
            f"{int(m // 60):02d}:{int(m % 60):02d}:00" if pd.notna(m) else "--:--:--"
            for m in df_plot["time_min"]
        ]
    else:
        _time_hms = ["--:--:--"] * len(time_x)

    # --- Prepare metric arrays for unified hover ---
    PACE_CAP_MIN = 10.0  # 10:00 /km cap in min/km
    pace_display: pd.Series | None = None
    if "pace_smooth" in df_plot.columns:
        pace_display = (df_plot["pace_smooth"] / 60.0).clip(upper=PACE_CAP_MIN)
    elif "pace" in df_plot.columns:
        pace_display = (df_plot["pace"].rolling(5, center=True).mean() / 60.0).clip(
            upper=PACE_CAP_MIN
        )

    hr_col = next((c for c in ["heartrate", "hr"] if c in df_plot.columns), None)

    smo2_vals = (
        df_plot["smo2"].rolling(10, center=True).mean() if "smo2" in df_plot.columns else None
    )
    ve_vals = (
        df_plot["tymeventilation"].rolling(10, center=True).mean()
        if "tymeventilation" in df_plot.columns
        else None
    )

    # --- Pace traces ---
    if pace_display is not None:
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=[PACE_CAP_MIN] * len(time_x),
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=pace_display,
                name="Tempo",
                fill="tonexty",
                fillcolor="rgba(0, 204, 150, 0.25)",
                line=dict(color=Config.COLOR_POWER, width=1),
                hovertemplate="<b>🕐 %{customdata[0]}</b><br>⏱️ Tempo: %{customdata[1]}<extra></extra>",
                customdata=[
                    [_time_hms[i], f"{int(p)}:{int((p % 1) * 60):02d}" if pd.notna(p) else "--:--"]
                    for i, p in enumerate(pace_display)
                ],
            )
        )

    # HR
    if hr_col:
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=df_plot[hr_col],
                name="HR",
                line=dict(color="#ef553b", width=1),
                hovertemplate="<b>🕐 %{customdata}</b><br>❤️ HR: %{y:.0f} bpm<extra></extra>",
                customdata=_time_hms,
            ),
        )

    # SmO2
    if smo2_vals is not None:
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=smo2_vals,
                name="SmO2",
                line=dict(color="#2ca02c", width=1),
                hovertemplate="<b>🕐 %{customdata}</b><br>🩸 SmO₂: %{y:.1f}%<extra></extra>",
                customdata=_time_hms,
            ),
        )

    # VE
    if ve_vals is not None:
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=ve_vals,
                name="VE",
                line=dict(color="#ffa15a", width=1),
                hovertemplate="<b>🕐 %{customdata}</b><br>🫁 VE: %{y:.1f} L/min<extra></extra>",
                customdata=_time_hms,
            ),
        )

    # Tick formatting: convert seconds to hh:mm:ss
    tick_vals = None
    tick_text = None
    if "time" in df_plot.columns:
        time_max_s = df_plot["time"].max()
        if pd.notna(time_max_s) and time_max_s > 0:
            interval = max(300, int(time_max_s / 8 / 300) * 300)
            tick_vals = list(range(0, int(time_max_s) + interval, interval))
            tick_text = []
            for t in tick_vals:
                h, remainder = divmod(t, 3600)
                m, s = divmod(remainder, 60)
                tick_text.append(f"{h:02d}:{m:02d}:{s:02d}")

    fig.update_layout(
        template="plotly_dark",
        hovermode="x unified",
        xaxis=dict(
            title="Czas [hh:mm:ss]",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
        ),
        yaxis=dict(title="Tempo [min/km]", side="left", autorange="reversed"),
        yaxis2=dict(title="HR [bpm]", overlaying="y", side="right", showgrid=False),
        yaxis3=dict(title="SmO2 [%]", overlaying="y", side="right", position=0.95, showgrid=False),
        yaxis4=dict(
            title="VE [L/min]", overlaying="y", side="right", position=0.98, showgrid=False
        ),
        height=500,
        legend=dict(orientation="h", y=-0.2),
    )
    if "watts" in df_plot and df_plot["watts"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=df_plot["watts"],
                name="Moc zmierzona [W]",
                yaxis="y5",
                visible="legendonly",
                mode="lines",
                hovertemplate="%{y:.0f} W<extra></extra>",
            )
        )
        fig.update_layout(yaxis5=dict(overlaying="y", side="right", showticklabels=False))
    return fig
