from typing import Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.metrics import calculate_trend
from modules.calculations.pace_utils import format_pace
from modules.config import Config

# ============================================================
# OPTIMIZATION: Pre-computed constants to avoid recalculation
# ============================================================
ZONE_LABELS = ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]
ZONE_COLORS = ["#808080", "#32CD32", "#FFD700", "#FF8C00", "#FF4500", "#8B0000"]
# O(1) lookup instead of O(k) list.index() calls
ZONE_COLOR_MAP: Dict[str, str] = dict(zip(ZONE_LABELS, ZONE_COLORS, strict=False))

# Pre-defined MMP windows (sorted by size for potential rolling optimization)
MMP_WINDOWS = {"5s": 5, "1m": 60, "5m": 300, "20m": 1200, "60m": 3600}


@st.cache_data
def _render_kpi_section(metrics: dict) -> None:
    """Present the same running metrics as the session summary."""
    st.subheader("Wskaźniki sesji")
    for column, (label, key, pattern) in zip(
        st.columns(4),
        (
            ("Średnie tempo", "avg_pace", None),
            ("Średnie GAP", "avg_gap", None),
            ("Średnie tętno", "avg_hr", "{:.0f} bpm"),
            ("Szac. VO2max", "vo2_max_est", "{:.1f}"),
        ),
        strict=True,
    ):
        value = metrics.get(key)
        if value is None:
            formatted = "brak"
        elif pattern is None:
            formatted = f"{format_pace(value)} /km"
        else:
            formatted = pattern.format(value)
        column.metric(label, formatted)
    st.caption("Szacunek VO2max na podstawie najlepszego tempa z 5 minut.")


def _render_hr_distribution(df_plot: pd.DataFrame) -> None:
    """Render the heart rate distribution histogram."""
    if "heartrate" not in df_plot.columns:
        return

    hr_valid = df_plot["heartrate"].dropna()
    if len(hr_valid) == 0:
        return

    # OPTIMIZATION: Use numpy for faster binning
    hr_rounded = np.round(hr_valid).astype(int)
    hr_min, hr_max = hr_rounded.min(), hr_rounded.max()
    bins = np.arange(hr_min, hr_max + 2)
    counts, edges = np.histogram(hr_rounded, bins=bins)

    # Filter out zero counts for cleaner display
    mask = counts > 0

    fig_hr = go.Figure(
        go.Bar(
            x=edges[:-1][mask],
            y=counts[mask],
            marker_color=Config.COLOR_HR,
            hovertemplate="<b>%{x} BPM</b><br>Czas: %{y} s<extra></extra>",
        )
    )
    fig_hr.update_layout(
        template="plotly_dark",
        height=250,
        xaxis_title="BPM",
        yaxis=dict(visible=False),
        bargap=0.1,
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_hr, width="stretch")


def _render_smo2_column(df_plot_resampled: pd.DataFrame) -> None:
    """Render the SmO2 chart with trend line in the left column."""
    st.subheader("SmO2")
    col_smo2 = (
        "smo2_smooth_ultra"
        if "smo2_smooth_ultra" in df_plot_resampled.columns
        else ("smo2_smooth" if "smo2_smooth" in df_plot_resampled.columns else None)
    )

    if not col_smo2:
        st.info("Brak danych SmO2")
        return

    fig_s = go.Figure()
    fig_s.add_trace(
        go.Scatter(
            x=df_plot_resampled["time_min"],
            y=df_plot_resampled[col_smo2],
            name="SmO2",
            line=dict(color="#ab63fa", width=2),
            hovertemplate="SmO2: %{y:.1f}%<extra></extra>",
        )
    )

    trend_y = calculate_trend(
        df_plot_resampled["time_min"].values, df_plot_resampled[col_smo2].values
    )
    if trend_y is not None:
        fig_s.add_trace(
            go.Scatter(
                x=df_plot_resampled["time_min"],
                y=trend_y,
                name="Trend",
                line=dict(color="white", dash="dash", width=1.5),
                hovertemplate="Trend: %{y:.1f}%<extra></extra>",
            )
        )

    fig_s.update_layout(
        template="plotly_dark",
        title="Lokalna Oksydacja (SmO2)",
        hovermode="x unified",
        yaxis=dict(title="SmO2 [%]", range=[0, 100]),
        legend=dict(orientation="h", y=1.1, x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        height=400,
    )
    st.plotly_chart(fig_s, width="stretch")

    st.info("""
    **💡 Hemodynamika Mięśniowa (SmO2) - Lokalny Monitoring:**

    SmO2 to "wskaźnik paliwa" bezpośrednio w pracującym mięśniu (zazwyczaj czworogłowym uda).
    * **Równowaga (Linia Płaska):** Podaż tlenu = Zapotrzebowanie. To stan zrównoważony (Steady State).
    * **Desaturacja (Spadek):** Popyt > Podaż. Wchodzisz w dług tlenowy. Jeśli dzieje się to przy stałej mocy -> zmęczenie metaboliczne.
    * **Reoksygenacja (Wzrost):** Odpoczynek. Szybkość powrotu do normy to doskonały wskaźnik wytrenowania (regeneracji).
    """)


def _render_hr_column(df_plot_resampled: pd.DataFrame) -> None:
    """Render the heart rate chart in the right column."""
    st.subheader("Tętno")
    if "heartrate_smooth" in df_plot_resampled.columns:
        fig_h = go.Figure()
        fig_h.add_trace(
            go.Scatter(
                x=df_plot_resampled["time_min"],
                y=df_plot_resampled["heartrate_smooth"],
                name="HR",
                fill="tozeroy",
                line=dict(color="#ef553b", width=2),
                hovertemplate="HR: %{y:.0f} BPM<extra></extra>",
            )
        )
        fig_h.update_layout(
            template="plotly_dark",
            title="Odpowiedź Sercowa (HR)",
            hovermode="x unified",
            yaxis=dict(title="HR [bpm]"),
            margin=dict(l=10, r=10, t=40, b=10),
            height=400,
        )
        st.plotly_chart(fig_h, width="stretch")
    else:
        st.info("Brak danych tętna (HR)")

    st.info("""
    **💡 Reakcja Sercowo-Naczyniowa (HR) - Globalny System:**

    Serce to pompa centralna. Jego reakcja jest **opóźniona** względem wysiłku.
    * **Lag (Opóźnienie):** W krótkich interwałach (np. 30s) tętno nie zdąży wzrosnąć, mimo że moc jest max. Nie steruj sprintami na tętno!
    * **Decoupling (Rozjazd):** Jeśli moc jest stała, a tętno rośnie (dryfuje) -> organizm walczy z przegrzaniem lub odwodnieniem.
    * **Recovery HR:** Jak szybko tętno spada po wysiłku? Szybki spadek = sprawne przywspółczulne układu nerwowego (dobra forma).
    """)


def _render_ventilation_section(
    df_plot_resampled: pd.DataFrame,
    vt1_vent: float,
    vt2_vent: float,
) -> None:
    """Render the ventilation (VE) and breathing rate (RR) chart with VT thresholds."""
    st.subheader("Wentylacja (VE) i Oddechy (RR)")

    fig_v = go.Figure()

    # 1. WENTYLACJA (Oś Lewa)
    if "tymeventilation_smooth" in df_plot_resampled.columns:
        fig_v.add_trace(
            go.Scatter(
                x=df_plot_resampled["time_min"],
                y=df_plot_resampled["tymeventilation_smooth"],
                name="VE",
                line=dict(color="#ffa15a", width=2),
                hovertemplate="VE: %{y:.1f} L/min<extra></extra>",
            )
        )

        # Trend VE
        trend_ve = calculate_trend(
            df_plot_resampled["time_min"].values, df_plot_resampled["tymeventilation_smooth"].values
        )
        if trend_ve is not None:
            fig_v.add_trace(
                go.Scatter(
                    x=df_plot_resampled["time_min"],
                    y=trend_ve,
                    name="Trend VE",
                    line=dict(color="#ffa15a", dash="dash", width=1.5),
                    hovertemplate="Trend: %{y:.1f} L/min<extra></extra>",
                )
            )

    # 2. ODDECHY / RR (Oś Prawa)
    if "tymebreathrate_smooth" in df_plot_resampled.columns:
        fig_v.add_trace(
            go.Scatter(
                x=df_plot_resampled["time_min"],
                y=df_plot_resampled["tymebreathrate_smooth"],
                name="RR",
                yaxis="y2",  # Druga oś
                line=dict(color="#19d3f3", dash="dot", width=2),
                hovertemplate="RR: %{y:.1f} /min<extra></extra>",
            )
        )

    # Linie Progi Wentylacyjne
    fig_v.add_hline(
        y=vt1_vent,
        line_dash="dot",
        line_color="green",
        annotation_text="VT1",
        annotation_position="bottom right",
    )
    fig_v.add_hline(
        y=vt2_vent,
        line_dash="dot",
        line_color="red",
        annotation_text="VT2",
        annotation_position="bottom right",
    )

    # LAYOUT (Unified Hover)
    fig_v.update_layout(
        template="plotly_dark",
        title="Mechanika Oddechu (Wydajność vs Częstość)",
        hovermode="x unified",
        # Oś Lewa
        yaxis=dict(title="Wentylacja [L/min]"),
        # Oś Prawa
        yaxis2=dict(title="Kadencja Oddechu [RR]", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.1, x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        height=450,
    )
    st.plotly_chart(fig_v, width="stretch")

    st.info("""
    **💡 Interpretacja: Mechanika Oddychania**

    * **Wzorzec Prawidłowy (Efektywność):** Wentylacja (VE) rośnie liniowo wraz z mocą, a częstość (RR) jest stabilna. Oznacza to głęboki, spokojny oddech.
    * **Wzorzec Niekorzystny (Płytki Oddech):** Bardzo wysokie RR (>40-50) przy stosunkowo niskim VE. Oznacza to "dyszenie" - powietrze wchodzi tylko do "martwej strefy" płuc, nie biorąc udziału w wymianie gazowej.
    * **Dryf Wentylacyjny:** Jeśli przy stałej mocy VE ciągle rośnie (rosnący trend pomarańczowej linii), oznacza to narastającą kwasicę (organizm próbuje wydmuchać CO2) lub zmęczenie mięśni oddechowych.
    * **Próg VT2 (RCP):** Punkt załamania, gdzie VE wystrzeliwuje pionowo w górę. To Twoja "czerwona linia" metaboliczna.
    """)


# ============================================================
# Public API
# ============================================================


def render_report_tab(df: pd.DataFrame, metrics: dict, vt1_vent: float, vt2_vent: float) -> None:
    st.header("Raport i wskaźniki sesji")
    _render_kpi_section(metrics)
    _render_hr_distribution(df)
    left, right = st.columns(2)
    with left:
        _render_smo2_column(df)
    with right:
        _render_hr_column(df)
    _render_ventilation_section(df, vt1_vent, vt2_vent)
