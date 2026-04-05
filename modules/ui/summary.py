"""
Moduł UI: Zakładka Podsumowanie (Summary)

Agreguje kluczowe wykresy i metryki z całego dashboardu w jednym miejscu.

Split into submodules:
- summary_helpers: NP, CP/W' estimation, DataFrame hashing
- summary_timeline: training timeline chart, metrics panel
- summary_charts: SmO2/THb, Running Dynamics, O2Hb/HHb, HRV, VO2max
- summary_analysis: durability, race prediction, BR, thermal, running effectiveness
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from modules.calculations.smo2_advanced import detect_smo2_thresholds_moxy
from modules.calculations.thresholds import analyze_step_test

from .summary_analysis import (
    _render_br_analysis_section,
    _render_durability_section,
    _render_race_prediction_section,
    _render_running_effectiveness_section,
    _render_thermal_analysis_section,
)
from .summary_charts import (
    _render_hrv_section,
    _render_o2hb_hhb_section,
    _render_running_dynamics_section,
    _render_smo2_thb_chart,
    _render_vo2max_uncertainty,
)
from .summary_helpers import _calculate_np, _estimate_cp_wprime, _hash_dataframe
from .summary_timeline import (
    _build_training_timeline_chart,
    _render_metrics_panel,
)

__all__ = [
    "render_summary_tab",
    "_build_training_timeline_chart",
    "_render_metrics_panel",
    "_render_smo2_thb_chart",
    "_render_running_dynamics_section",
    "_render_o2hb_hhb_section",
    "_render_hrv_section",
    "_render_vo2max_uncertainty",
    "_render_durability_section",
    "_render_race_prediction_section",
    "_render_br_analysis_section",
    "_render_thermal_analysis_section",
    "_render_running_effectiveness_section",
    "_hash_dataframe",
    "_calculate_np",
    "_estimate_cp_wprime",
]


def _resolve_hr_column(df_plot: pd.DataFrame) -> Optional[str]:
    for alias in ["hr", "heartrate", "heart_rate", "bpm"]:
        if alias in df_plot.columns:
            return alias
    return None


def _run_threshold_detection(
    df_plot: pd.DataFrame,
    hr_col: Optional[str],
    cp_input: int,
) -> None:
    threshold_result = analyze_step_test(
        df_plot,
        power_column="watts",
        ve_column="tymeventilation" if "tymeventilation" in df_plot.columns else None,
        smo2_column="smo2" if "smo2" in df_plot.columns else None,
        hr_column=hr_col,
        time_column="time",
    )

    if "smo2" in df_plot.columns:
        hr_max = int(df_plot[hr_col].max()) if hr_col else None
        detect_smo2_thresholds_moxy(
            df=df_plot,
            step_duration_sec=180,
            smo2_col="smo2",
            power_col="watts",
            hr_col=hr_col,
            time_col="time",
            cp_watts=cp_input if cp_input > 0 else None,
            hr_max=hr_max,
            vt1_watts=threshold_result.vt1_watts,
            rcp_onset_watts=threshold_result.vt2_watts,
        )


def _add_ve_trace(
    fig_ve_br: go.Figure,
    df_plot: pd.DataFrame,
    time_x_s: object,
) -> None:
    ve_data = df_plot["tymeventilation"].rolling(10, center=True).mean()
    fig_ve_br.add_trace(
        go.Scatter(
            x=time_x_s,
            y=ve_data,
            name="VE (L/min)",
            line=dict(color="#ffa15a", width=2),
            hovertemplate="VE: %{y:.1f} L/min<extra></extra>",
        ),
        secondary_y=False,
    )


def _add_br_trace(
    fig_ve_br: go.Figure,
    df_plot: pd.DataFrame,
    time_x_s: object,
    secondary: bool,
) -> None:
    br_data = df_plot["tymebreathrate"].rolling(10, center=True).mean()
    fig_ve_br.add_trace(
        go.Scatter(
            x=time_x_s,
            y=br_data,
            name="BR (oddech/min)",
            line=dict(color="#00cc96", width=2),
            hovertemplate="BR: %{y:.0f} /min<extra></extra>",
        ),
        secondary_y=secondary,
    )


def _add_pace_trace(
    fig_ve_br: go.Figure,
    df_plot: pd.DataFrame,
    time_x_s: object,
) -> None:
    if "pace" not in df_plot.columns and "pace_smooth" not in df_plot.columns:
        return
    pace_col = "pace_smooth" if "pace_smooth" in df_plot.columns else "pace"
    pace_data = df_plot[pace_col].rolling(10, center=True).mean() / 60.0
    pace_hover = [
        f"{int(p)}:{int((p % 1) * 60):02d} /km" if pd.notna(p) else "--:--" for p in pace_data
    ]
    fig_ve_br.add_trace(
        go.Scatter(
            x=time_x_s,
            y=pace_data,
            name="Tempo (min/km)",
            line=dict(color="#00d4aa", width=2, dash="dot"),
            hovertemplate="Tempo: %{customdata}<extra></extra>",
            customdata=pace_hover,
        ),
        secondary_y=True,
    )


def _render_ve_info_box(
    has_ve: bool,
    has_br: bool,
    df_plot: pd.DataFrame,
) -> None:
    col1, col2 = st.columns(2)

    with col1:
        if has_ve:
            ve_min = df_plot["tymeventilation"].min()
            ve_max = df_plot["tymeventilation"].max()
            ve_mean = df_plot["tymeventilation"].mean()
            st.markdown(
                f"""
            <div style="padding:15px; border-radius:8px; border:2px solid #ffa15a; background-color: #222;">
                <h3 style="margin:0; color: #ffa15a;">🫁 VE (Wentylacja)</h3>
                <p style="margin:5px 0; color:#aaa;"><b>Min:</b> {ve_min:.1f} L/min</p>
                <p style="margin:5px 0; color:#aaa;"><b>Max:</b> {ve_max:.1f} L/min</p>
                <p style="margin:5px 0; color:#aaa;"><b>Śr:</b> {ve_mean:.1f} L/min</p>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Brak danych VE (wentylacja) — brak czujnika Tymewear.")

    with col2:
        if has_br:
            br_min = df_plot["tymebreathrate"].min()
            br_max = df_plot["tymebreathrate"].max()
            br_mean = df_plot["tymebreathrate"].mean()
            br_source = "Garmin" if not has_ve else "Tymewear"
            st.markdown(
                f"""
            <div style="padding:15px; border-radius:8px; border:2px solid #00cc96; background-color: #222;">
                <h3 style="margin:0; color: #00cc96;">🌬️ BR (Oddechy) — {br_source}</h3>
                <p style="margin:5px 0; color:#aaa;"><b>Min:</b> {br_min:.0f} /min</p>
                <p style="margin:5px 0; color:#aaa;"><b>Max:</b> {br_max:.0f} /min</p>
                <p style="margin:5px 0; color:#aaa;"><b>Śr:</b> {br_mean:.0f} /min</p>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Brak danych BR (częstość oddechów).")


def _render_ve_br_chart(df_plot: pd.DataFrame) -> None:
    has_ve = "tymeventilation" in df_plot.columns
    has_br = "tymebreathrate" in df_plot.columns

    if not has_ve and not has_br:
        st.info("Brak danych wentylacji (VE/BR) w tym pliku.")
        return

    fig_ve_br = make_subplots(specs=[[{"secondary_y": True}]])
    time_x_s = df_plot["time"] if "time" in df_plot.columns else range(len(df_plot))

    if has_ve:
        _add_ve_trace(fig_ve_br, df_plot, time_x_s)

    if has_br:
        _add_br_trace(fig_ve_br, df_plot, time_x_s, secondary=not has_ve)

    _add_pace_trace(fig_ve_br, df_plot, time_x_s)

    fig_ve_br.update_layout(
        template="plotly_dark",
        height=350,
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    primary_label = "VE (L/min)" if has_ve else "BR (/min)"
    secondary_label = "BR (/min)" if has_ve else "Tempo"
    fig_ve_br.update_yaxes(title_text=primary_label, secondary_y=False)
    fig_ve_br.update_yaxes(title_text=secondary_label, secondary_y=True)
    st.plotly_chart(fig_ve_br, use_container_width=True)

    _render_ve_info_box(has_ve, has_br, df_plot)


def render_summary_tab(
    df_plot: pd.DataFrame,
    df_plot_resampled: pd.DataFrame,
    metrics: dict,
    training_notes,
    uploaded_file_name: str,
    cp_input: int,
    w_prime_input: int,
    rider_weight: float,
    vt1_watts: int = 0,
    vt2_watts: int = 0,
    lt1_watts: int = 0,
    lt2_watts: int = 0,
):
    """Renderowanie zakładki Podsumowanie z kluczowymi wykresami i metrykami."""
    st.header("📊 Podsumowanie Treningu")
    st.markdown("Wszystkie kluczowe wykresy i metryki w jednym miejscu.")

    df_plot = df_plot.rename(columns={c: str(c).lower().strip() for c in df_plot.columns})

    hr_col = _resolve_hr_column(df_plot)
    _run_threshold_detection(df_plot, hr_col, cp_input)

    st.subheader("1️⃣ Przebieg Treningu")
    fig_training = _build_training_timeline_chart(df_plot)
    if fig_training is not None:
        st.plotly_chart(fig_training, use_container_width=True)

    _render_metrics_panel(df_plot, metrics, cp_input, w_prime_input, rider_weight)

    st.markdown("---")
    st.subheader("2️⃣ Wentylacja (VE) i Oddechy (BR)")
    _render_ve_br_chart(df_plot)

    st.markdown("---")
    st.subheader("3️⃣ SmO2 vs THb w czasie")
    _render_smo2_thb_chart(df_plot)

    st.markdown("---")
    _render_running_dynamics_section(df_plot)
    _render_o2hb_hhb_section(df_plot)
    _render_hrv_section(df_plot)

    st.subheader("7️⃣ Estymacja VO2max z Niepewnością (CI95%)")
    _render_vo2max_uncertainty(df_plot, rider_weight)

    _render_durability_section(df_plot)
    _render_race_prediction_section(df_plot, rider_weight)
    _render_br_analysis_section(df_plot)
    _render_thermal_analysis_section(df_plot)
    _render_running_effectiveness_section(df_plot, rider_weight)
