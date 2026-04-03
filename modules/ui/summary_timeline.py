"""
Summary timeline: training timeline chart and metrics panel.

Contains the cached training timeline chart builder and the comprehensive
metrics panel rendered below it (sections 1 and 1a of the summary tab).
"""

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.config import Config

from .summary_helpers import _calculate_np, _estimate_cp_wprime

__all__ = ["_build_training_timeline_chart", "_render_metrics_panel"]


@st.cache_data(ttl=3600, show_spinner=False)
def _build_training_timeline_chart(df_plot: pd.DataFrame) -> Optional[go.Figure]:
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

    # Use pace instead of power for running
    # With reversed Y-axis, fill="tozeroy" fills UP to 0 (top). Use invisible
    # baseline at slow-pace cap and fill="tonexty" to shade downward correctly.
    PACE_CAP_MIN = 10.0  # 10:00 /km cap in min/km
    if "pace_smooth" in df_plot.columns:
        pace_display = (df_plot["pace_smooth"] / 60.0).clip(upper=PACE_CAP_MIN)
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
                hovertemplate="Tempo: %{customdata}<extra></extra>",
                customdata=[
                    f"{int(p)}:{int((p % 1) * 60):02d}" if pd.notna(p) else "--:--"
                    for p in pace_display
                ],
            )
        )
    elif "pace" in df_plot.columns:
        pace_display = (df_plot["pace"].rolling(5, center=True).mean() / 60.0).clip(
            upper=PACE_CAP_MIN
        )
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
                hovertemplate="Tempo: %{customdata}<extra></extra>",
                customdata=[
                    f"{int(p)}:{int((p % 1) * 60):02d}" if pd.notna(p) else "--:--"
                    for p in pace_display
                ],
            )
        )

    # HR
    hr_col = next((c for c in ["heartrate", "hr"] if c in df_plot.columns), None)
    if hr_col:
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=df_plot[hr_col],
                name="HR",
                line=dict(color="#ef553b", width=1),
                hovertemplate="HR: %{y:.0f} bpm<extra></extra>",
            ),
        )

    # SmO2
    if "smo2" in df_plot.columns:
        smo2_smooth = df_plot["smo2"].rolling(10, center=True).mean()
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=smo2_smooth,
                name="SmO2",
                line=dict(color="#2ca02c", width=1),
                hovertemplate="SmO2: %{y:.1f}%<extra></extra>",
            ),
        )

    # VE
    if "tymeventilation" in df_plot.columns:
        ve_smooth = df_plot["tymeventilation"].rolling(10, center=True).mean()
        fig.add_trace(
            go.Scatter(
                x=time_x,
                y=ve_smooth,
                name="VE",
                line=dict(color="#ffa15a", width=1),
                hovertemplate="VE: %{y:.1f} L/min<extra></extra>",
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
    return fig


def _render_metrics_panel(df_plot, metrics, cp_input, w_prime_input, rider_weight):
    """Renderowanie panelu z metrykami pod wykresem przebiegu treningu."""

    # Oblicz metryki z danych
    duration_min = len(df_plot) / 60 if len(df_plot) > 0 else 0

    # Distance (from 'distance' column — cumulative meters)
    total_distance_km = 0.0
    if "distance" in df_plot.columns:
        dist_vals = df_plot["distance"].dropna()
        if len(dist_vals) > 0:
            total_distance_km = (
                dist_vals.iloc[-1] / 1000.0 if dist_vals.max() > 100 else dist_vals.iloc[-1]
            )

    # Pace (convert via speed domain for correct averaging)
    avg_pace_str = "--"
    if "pace" in df_plot.columns:
        pace_valid = df_plot["pace"].replace(0, np.nan).dropna()
        if len(pace_valid) > 0:
            speed_vals = 1000.0 / pace_valid
            avg_speed = speed_vals.mean()
            if avg_speed > 0:
                avg_pace_s = 1000.0 / avg_speed
                avg_pace_str = f"{int(avg_pace_s // 60)}:{int(avg_pace_s % 60):02d} /km"

    # Power
    avg_power = df_plot["watts"].mean() if "watts" in df_plot.columns else 0
    np_power = _calculate_np(df_plot["watts"]) if "watts" in df_plot.columns else 0
    work_kj = df_plot["watts"].sum() / 1000.0 if "watts" in df_plot.columns else 0

    # HR
    hr_col = (
        "heartrate" if "heartrate" in df_plot.columns else "hr" if "hr" in df_plot.columns else None
    )
    avg_hr = df_plot[hr_col].mean() if hr_col else 0
    df_plot[hr_col].min() if hr_col else 0
    max_hr = df_plot[hr_col].max() if hr_col else 0

    # SmO2
    avg_smo2 = df_plot["smo2"].mean() if "smo2" in df_plot.columns else 0
    min_smo2 = df_plot["smo2"].min() if "smo2" in df_plot.columns else 0
    df_plot["smo2"].max() if "smo2" in df_plot.columns else 0

    # VE
    avg_ve = df_plot["tymeventilation"].mean() if "tymeventilation" in df_plot.columns else 0
    min_ve = df_plot["tymeventilation"].min() if "tymeventilation" in df_plot.columns else 0
    max_ve = df_plot["tymeventilation"].max() if "tymeventilation" in df_plot.columns else 0

    # BR
    avg_br = df_plot["tymebreathrate"].mean() if "tymebreathrate" in df_plot.columns else 0
    min_br = df_plot["tymebreathrate"].min() if "tymebreathrate" in df_plot.columns else 0
    max_br = df_plot["tymebreathrate"].max() if "tymebreathrate" in df_plot.columns else 0

    # Core temperature
    avg_core = df_plot["core_temperature"].mean() if "core_temperature" in df_plot.columns else 0
    max_core = df_plot["core_temperature"].max() if "core_temperature" in df_plot.columns else 0

    # Estymacje
    est_vo2max = metrics.get("vo2_max_est", 0) if metrics else 0
    est_vlamax = metrics.get("vlamax_est", 0) if metrics else 0

    # Estymacja CP/W' z danych
    est_cp, est_w_prime = _estimate_cp_wprime(df_plot)

    # Wyświetlanie w 4 kolumnach
    st.markdown("### 📈 Metryki Treningowe")

    # Wiersz 1: Czas, Dystans, Tempo, Praca/Moc
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⏱️ Czas", f"{duration_min:.1f} min")
    c2.metric("📏 Dystans", f"{total_distance_km:.2f} km" if total_distance_km > 0 else "--")
    c3.metric("🏃 AVG Tempo", avg_pace_str)
    c4.metric("⚡ AVG Power", f"{avg_power:.0f} W" if avg_power else "--")

    # Wiersz 2: HR + NP + praca
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("❤️ AVG HR", f"{avg_hr:.0f} bpm" if avg_hr else "--")
    c2.metric("❤️ MAX HR", f"{max_hr:.0f} bpm" if max_hr else "--")
    c3.metric("📊 NP", f"{np_power:.0f} W" if np_power else "--")
    c4.metric("🔋 Praca", f"{work_kj:.0f} kJ" if work_kj else "--")

    # Wiersz 3: SmO2 + Core Temp
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🩸 AVG SmO2", f"{avg_smo2:.1f}%" if avg_smo2 else "--")
    c2.metric("🩸 MIN SmO2", f"{min_smo2:.1f}%" if min_smo2 else "--")
    c3.metric("🌡️ AVG Core", f"{avg_core:.1f} °C" if avg_core else "--")
    c4.metric("🌡️ MAX Core", f"{max_core:.1f} °C" if max_core else "--")

    # Wiersz 4: VE (only if present)
    if avg_ve:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🫁 AVG VE", f"{avg_ve:.1f} L/min")
        c2.metric("🫁 MIN VE", f"{min_ve:.1f} L/min")
        c3.metric("🫁 MAX VE", f"{max_ve:.1f} L/min")
        c4.empty()

    # Wiersz 5: BR (only if present)
    if avg_br:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💨 AVG BR", f"{avg_br:.0f} /min")
        c2.metric("💨 MIN BR", f"{min_br:.0f} /min")
        c3.metric("💨 MAX BR", f"{max_br:.0f} /min")
        c4.empty()

    # Wiersz 6: Estymacje
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 Est. VO2max", f"{est_vo2max:.1f} ml/kg/min" if est_vo2max else "--")
    c2.metric("🧬 Est. VLamax", f"{est_vlamax:.2f} mmol/L/s" if est_vlamax else "--")
    c3.metric("⚡ Est. CP", f"{est_cp:.0f} W" if est_cp else "--")
    c4.metric("🔋 Est. W'", f"{est_w_prime:.0f} J" if est_w_prime else "--")

    # Wiersz 7: Running Dynamics (FIT)
    has_dynamics = any(
        col in df_plot.columns
        for col in ["stance_time", "stance_time_balance", "vertical_ratio", "step_length"]
    )
    if has_dynamics:
        st.markdown("### 🦶 Running Dynamics (Garmin FIT)")
        c1, c2, c3, c4 = st.columns(4)

        if "stance_time" in df_plot.columns:
            gct_mean = df_plot["stance_time"].mean()
            c1.metric("⏱️ AVG GCT", f"{gct_mean:.0f} ms")
        elif "gct" in df_plot.columns:
            gct_mean = df_plot["gct"].mean()
            c1.metric("⏱️ AVG GCT", f"{gct_mean:.0f} ms")
        else:
            c1.empty()

        if "stance_time_balance" in df_plot.columns:
            bal = df_plot["stance_time_balance"].mean()
            imbalance = abs(bal - 50.0)
            c2.metric(
                "⚖️ Balans L/P",
                f"{bal:.1f}%",
                delta=f"{imbalance:.1f}% asymetrii",
                delta_color="inverse" if imbalance > 2.0 else "off",
            )
        else:
            c2.empty()

        if "vertical_ratio" in df_plot.columns:
            vr = df_plot["vertical_ratio"].mean()
            c3.metric("📐 Vertical Ratio", f"{vr:.1f}%")
        else:
            c3.empty()

        if "step_length" in df_plot.columns:
            sl = df_plot["step_length"].mean()
            c4.metric("📏 Długość kroku", f"{sl:.3f} m")
        else:
            c4.empty()

    # Wiersz 8: HRV, Temperature, O2Hb/HHb
    has_extras = any(col in df_plot.columns for col in ["hrv", "temperature", "o2hb", "hhb"])
    if has_extras:
        st.markdown("### 🔬 Dane Dodatkowe (FIT)")
        c1, c2, c3, c4 = st.columns(4)

        if "hrv" in df_plot.columns:
            hrv_data = df_plot["hrv"].dropna()
            if len(hrv_data) > 0:
                c1.metric("💓 AVG HRV (RMSSD)", f"{hrv_data.mean():.1f} ms")
            else:
                c1.empty()
        else:
            c1.empty()

        if "temperature" in df_plot.columns:
            temp_data = df_plot["temperature"].dropna()
            if len(temp_data) > 0:
                c2.metric(
                    "🌡️ AVG Temp",
                    f"{temp_data.mean():.1f} °C",
                    delta=f"max {temp_data.max():.0f} °C",
                    delta_color="off",
                )
            else:
                c2.empty()
        else:
            c2.empty()

        if "o2hb" in df_plot.columns:
            o2hb_data = df_plot["o2hb"].dropna()
            if len(o2hb_data) > 0:
                c3.metric("🔴 AVG O2Hb", f"{o2hb_data.mean():.1f} a.u.")
            else:
                c3.empty()
        else:
            c3.empty()

        if "hhb" in df_plot.columns:
            hhb_data = df_plot["hhb"].dropna()
            if len(hhb_data) > 0:
                c4.metric("🔵 AVG HHb", f"{hhb_data.mean():.1f} a.u.")
            else:
                c4.empty()
        else:
            c4.empty()
