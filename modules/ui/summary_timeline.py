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
    hr_vals = df_plot[hr_col] if hr_col else None

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
    return fig


def _col_mean(df_plot: pd.DataFrame, col: str) -> float:
    return df_plot[col].mean() if col in df_plot.columns else 0


def _col_min(df_plot: pd.DataFrame, col: str) -> float:
    return df_plot[col].min() if col in df_plot.columns else 0


def _col_max(df_plot: pd.DataFrame, col: str) -> float:
    return df_plot[col].max() if col in df_plot.columns else 0


def _compute_distance_km(df_plot: pd.DataFrame) -> float:
    if "distance" not in df_plot.columns:
        return 0.0
    dist_vals = df_plot["distance"].dropna()
    if len(dist_vals) == 0:
        return 0.0
    return dist_vals.iloc[-1] / 1000.0 if dist_vals.max() > 100 else dist_vals.iloc[-1]


def _compute_avg_pace_str(df_plot: pd.DataFrame) -> str:
    if "pace" not in df_plot.columns:
        return "--"
    pace_valid = df_plot["pace"].replace(0, np.nan).dropna()
    if len(pace_valid) == 0:
        return "--"
    avg_speed = (1000.0 / pace_valid).mean()
    if avg_speed <= 0:
        return "--"
    avg_pace_s = 1000.0 / avg_speed
    return f"{int(avg_pace_s // 60)}:{int(avg_pace_s % 60):02d} /km"


def _fmt(value: float, fmt_str: str) -> str:
    return fmt_str.format(value) if value else "--"


def _render_core_metrics(
    df_plot: pd.DataFrame,
    metrics: dict,
    duration_min: float,
) -> None:
    total_distance_km = _compute_distance_km(df_plot)
    avg_pace_str = _compute_avg_pace_str(df_plot)
    avg_power = _col_mean(df_plot, "watts")
    np_power = _calculate_np(df_plot["watts"]) if "watts" in df_plot.columns else 0
    work_kj = df_plot["watts"].sum() / 1000.0 if "watts" in df_plot.columns else 0

    hr_col = _resolve_hr_col(df_plot)
    avg_hr = df_plot[hr_col].mean() if hr_col else 0
    max_hr = df_plot[hr_col].max() if hr_col else 0

    avg_smo2 = _col_mean(df_plot, "smo2")
    min_smo2 = _col_min(df_plot, "smo2")
    avg_core = _col_mean(df_plot, "core_temperature")
    max_core = _col_max(df_plot, "core_temperature")

    est_vo2max = metrics.get("vo2_max_est", 0) if metrics else 0
    est_vlamax = metrics.get("vlamax_est", 0) if metrics else 0
    est_cp, est_w_prime = _estimate_cp_wprime(df_plot)

    st.markdown("### 📈 Metryki Treningowe")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⏱️ Czas", f"{duration_min:.1f} min")
    c2.metric("📏 Dystans", f"{total_distance_km:.2f} km" if total_distance_km > 0 else "--")
    c3.metric("🏃 AVG Tempo", avg_pace_str)
    c4.metric("⚡ AVG Power", _fmt(avg_power, "{:.0f} W"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("❤️ AVG HR", _fmt(avg_hr, "{:.0f} bpm"))
    c2.metric("❤️ MAX HR", _fmt(max_hr, "{:.0f} bpm"))
    c3.metric("📊 NP", _fmt(np_power, "{:.0f} W"))
    c4.metric("🔋 Praca", _fmt(work_kj, "{:.0f} kJ"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🩸 AVG SmO2", _fmt(avg_smo2, "{:.1f}%"))
    c2.metric("🩸 MIN SmO2", _fmt(min_smo2, "{:.1f}%"))
    c3.metric("🌡️ AVG Core", _fmt(avg_core, "{:.1f} °C"))
    c4.metric("🌡️ MAX Core", _fmt(max_core, "{:.1f} °C"))

    avg_ve = _col_mean(df_plot, "tymeventilation")
    if avg_ve:
        min_ve = _col_min(df_plot, "tymeventilation")
        max_ve = _col_max(df_plot, "tymeventilation")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🫁 AVG VE", f"{avg_ve:.1f} L/min")
        c2.metric("🫁 MIN VE", f"{min_ve:.1f} L/min")
        c3.metric("🫁 MAX VE", f"{max_ve:.1f} L/min")
        c4.empty()

    avg_br = _col_mean(df_plot, "tymebreathrate")
    if avg_br:
        min_br = _col_min(df_plot, "tymebreathrate")
        max_br = _col_max(df_plot, "tymebreathrate")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💨 AVG BR", f"{avg_br:.0f} /min")
        c2.metric("💨 MIN BR", f"{min_br:.0f} /min")
        c3.metric("💨 MAX BR", f"{max_br:.0f} /min")
        c4.empty()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 Est. VO2max", _fmt(est_vo2max, "{:.1f} ml/kg/min"))
    c2.metric("🧬 Est. VLamax", _fmt(est_vlamax, "{:.2f} mmol/L/s"))
    c3.metric("⚡ Est. CP", _fmt(est_cp, "{:.0f} W"))
    c4.metric("🔋 Est. W'", _fmt(est_w_prime, "{:.0f} J"))


def _resolve_hr_col(df_plot: pd.DataFrame) -> Optional[str]:
    if "heartrate" in df_plot.columns:
        return "heartrate"
    if "hr" in df_plot.columns:
        return "hr"
    return None


def _render_optional_metric(
    col, df_plot: pd.DataFrame, col_name: str, label: str, unit: str
) -> None:
    if col_name not in df_plot.columns:
        col.empty()
        return
    data = df_plot[col_name].dropna()
    if len(data) > 0:
        col.metric(label, f"{data.mean():.1f} {unit}")
    else:
        col.empty()


def _render_running_dynamics(df_plot: pd.DataFrame) -> None:
    dynamics_cols = ["stance_time", "stance_time_balance", "vertical_ratio", "step_length"]
    if not any(c in df_plot.columns for c in dynamics_cols):
        return

    st.markdown("### 🦶 Running Dynamics (Garmin FIT)")
    c1, c2, c3, c4 = st.columns(4)

    gct_col = (
        "stance_time"
        if "stance_time" in df_plot.columns
        else "gct"
        if "gct" in df_plot.columns
        else None
    )
    if gct_col:
        c1.metric("⏱️ AVG GCT", f"{df_plot[gct_col].mean():.0f} ms")
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
        c3.metric("📐 Vertical Ratio", f"{df_plot['vertical_ratio'].mean():.1f}%")
    else:
        c3.empty()

    if "step_length" in df_plot.columns:
        c4.metric("📏 Długość kroku", f"{df_plot['step_length'].mean():.3f} m")
    else:
        c4.empty()


def _render_extra_fit_data(df_plot: pd.DataFrame) -> None:
    extras_cols = ["hrv", "temperature", "o2hb", "hhb"]
    if not any(c in df_plot.columns for c in extras_cols):
        return

    st.markdown("### 🔬 Dane Dodatkowe (FIT)")
    c1, c2, c3, c4 = st.columns(4)

    _render_optional_metric(c1, df_plot, "hrv", "💓 AVG HRV (RMSSD)", "ms")
    _render_optional_metric(c3, df_plot, "o2hb", "🔴 AVG O2Hb", "a.u.")
    _render_optional_metric(c4, df_plot, "hhb", "🔵 AVG HHb", "a.u.")

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


def _render_metrics_panel(df_plot, metrics, cp_input, w_prime_input, rider_weight):
    duration_min = len(df_plot) / 60 if len(df_plot) > 0 else 0

    _render_core_metrics(df_plot, metrics, duration_min)
    _render_running_dynamics(df_plot)
    _render_extra_fit_data(df_plot)
