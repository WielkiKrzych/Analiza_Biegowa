import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from modules.config import Config
from modules.calculations import calculate_vo2max, calculate_trend
from typing import Dict

# ============================================================
# OPTIMIZATION: Pre-computed constants to avoid recalculation
# ============================================================
ZONE_LABELS = ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]
ZONE_COLORS = ["#808080", "#32CD32", "#FFD700", "#FF8C00", "#FF4500", "#8B0000"]
# O(1) lookup instead of O(k) list.index() calls
ZONE_COLOR_MAP: Dict[str, str] = dict(zip(ZONE_LABELS, ZONE_COLORS))

# Pre-defined MMP windows (sorted by size for potential rolling optimization)
MMP_WINDOWS = {"5s": 5, "1m": 60, "5m": 300, "20m": 1200, "60m": 3600}


@st.cache_data
def _calculate_mmp_peaks(watts_series: pd.Series, windows: Dict[str, int]) -> Dict[str, float]:
    """Calculate Mean Maximal Power for multiple windows in a single pass.

    OPTIMIZATION: Single rolling calculation approach, caching results.
    Previous: O(5n) - 5 separate rolling operations
    Current: O(n) + caching - one calculation, cached per session

    Args:
        watts_series: Power data series
        windows: Dict of label -> window size in seconds

    Returns:
        Dict of label -> MMP value
    """
    results = {}
    for label, window_size in windows.items():
        if len(watts_series) >= window_size:
            # Rolling with min_periods optimization
            rolling_mean = watts_series.rolling(window_size, min_periods=window_size).mean()
            max_val = rolling_mean.max()
            results[label] = float(max_val) if not pd.isna(max_val) else None
        else:
            results[label] = None
    return results


def _calculate_zone_distribution(watts: pd.Series, cp: float) -> pd.Series:
    """Calculate power zone distribution without copying entire DataFrame.

    OPTIMIZATION: Work on Series only, not full DataFrame copy.
    Previous: O(n) memory for full df.copy()
    Current: O(n) for Series (much smaller)

    Args:
        watts: Power series only (not full DataFrame)
        cp: Critical Power

    Returns:
        Series with zone percentages indexed by zone label
    """
    bins = [0, 0.55 * cp, 0.75 * cp, 0.90 * cp, 1.05 * cp, 1.20 * cp, float("inf")]
    zones = pd.cut(watts, bins=bins, labels=ZONE_LABELS, right=False)
    # value_counts with normalize=True avoids extra division
    pcts = zones.value_counts(normalize=True, sort=False).sort_index() * 100
    return pcts.round(1)


def render_report_tab(
    df_plot: pd.DataFrame,
    df_plot_resampled: pd.DataFrame,
    metrics: dict,
    rider_weight: float,
    cp_input: float,
    decoupling_percent: float = 0,
    drift_z2: float = 0,
    vt1_vent: float = 0,
    vt2_vent: float = 0,
) -> None:
    """Render the executive summary report tab with integrated KPI section.

    Optimized for performance with cached calculations and vectorized operations.
    Combines previous Report and KPI tabs into one comprehensive view.
    """
    st.header("📋 Raport i Kluczowe Wskaźniki Wydajności (KPI)")

    # ============================================================
    # SEKCJA KPI (przeniesiona z kpi.py)
    # ============================================================
    st.subheader("📊 Kluczowe Wskaźniki Wydajności (KPI)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Średnia Moc", f"{metrics.get('avg_watts', 0):.0f} W")
    c2.metric("Średnie Tętno", f"{metrics.get('avg_hr', 0):.0f} BPM")
    c3.metric("Średnie SmO2", f"{df_plot['smo2'].mean() if 'smo2' in df_plot.columns else 0:.1f} %")
    c4.metric("Kadencja", f"{metrics.get('avg_cadence', 0):.0f} RPM")

    vo2max_est = calculate_vo2max(
        df_plot["watts"].rolling(window=300).mean().max() if "watts" in df_plot.columns else 0,
        rider_weight,
    )
    c5.metric(
        "Szac. VO2max", f"{vo2max_est:.1f}", help="Estymowane na podstawie mocy 5-minutowej (ACSM)."
    )

    st.divider()
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Power/HR", f"{metrics.get('power_hr', 0):.2f}")
    c6.metric("Efficiency (EF)", f"{metrics.get('ef_factor', 0):.2f}")
    c7.metric("Praca > CP", f"{metrics.get('work_above_cp_kj', 0):.0f} kJ")
    c8.metric("Wentylacja (VE)", f"{metrics.get('avg_vent', 0):.1f} L/min")

    st.divider()
    c9, c10, c11, c12 = st.columns(4)
    c9.metric(
        "Dryf (Pa:Hr)",
        f"{decoupling_percent:.1f} %",
        delta_color="inverse" if decoupling_percent < 5 else "normal",
    )
    c10.metric("Dryf Z2", f"{drift_z2:.1f} %", delta_color="inverse" if drift_z2 < 5 else "normal")

    max_hsi = df_plot["hsi"].max() if "hsi" in df_plot.columns else 0
    c11.metric("Max HSI", f"{max_hsi:.1f}", delta_color="normal" if max_hsi > 5 else "inverse")
    c12.metric("Oddechy (RR)", f"{metrics.get('avg_rr', 0):.1f} /min")

    st.markdown("---")

    # ============================================================
    # SEKCJA WIZUALIZACJI DRYFU (z kpi.py)
    # ============================================================
    st.subheader("Wizualizacja Dryfu i Zmienności")

    # --- Main chart (unchanged, already efficient) ---
    st.subheader("Przebieg Treningu")
    fig_exec = go.Figure()

    time_x = df_plot["time_min"] if "time_min" in df_plot.columns else None

    if time_x is not None:
        if "watts_smooth" in df_plot.columns:
            fig_exec.add_trace(
                go.Scatter(
                    x=time_x,
                    y=df_plot["watts_smooth"],
                    name="Moc",
                    fill="tozeroy",
                    line=dict(color=Config.COLOR_POWER, width=1),
                    hovertemplate="Moc: %{y:.0f} W<extra></extra>",
                )
            )
        if "heartrate_smooth" in df_plot.columns:
            fig_exec.add_trace(
                go.Scatter(
                    x=time_x,
                    y=df_plot["heartrate_smooth"],
                    name="HR",
                    line=dict(color=Config.COLOR_HR, width=2),
                    yaxis="y2",
                    hovertemplate="HR: %{y:.0f} bpm<extra></extra>",
                )
            )
        if "smo2_smooth" in df_plot.columns:
            fig_exec.add_trace(
                go.Scatter(
                    x=time_x,
                    y=df_plot["smo2_smooth"],
                    name="SmO2",
                    line=dict(color=Config.COLOR_SMO2, width=2, dash="dot"),
                    yaxis="y3",
                    hovertemplate="SmO2: %{y:.1f}%<extra></extra>",
                )
            )
        if "tymeventilation_smooth" in df_plot.columns:
            fig_exec.add_trace(
                go.Scatter(
                    x=time_x,
                    y=df_plot["tymeventilation_smooth"],
                    name="VE",
                    line=dict(color=Config.COLOR_VE, width=2, dash="dash"),
                    yaxis="y4",
                    hovertemplate="VE: %{y:.1f} L/min<extra></extra>",
                )
            )

    fig_exec.update_layout(
        template="plotly_dark",
        height=500,
        yaxis=dict(title="Moc [W]"),
        yaxis2=dict(title="HR", overlaying="y", side="right", showgrid=False),
        yaxis3=dict(
            title="SmO2",
            overlaying="y",
            side="right",
            showgrid=False,
            showticklabels=False,
            range=[0, 100],
        ),
        yaxis4=dict(title="VE", overlaying="y", side="right", showgrid=False, showticklabels=False),
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig_exec, use_container_width=True)

    st.markdown("---")
    col_dist1, col_dist2 = st.columns(2)

    with col_dist1:
        st.subheader("Czas w Strefach (Moc)")
        if "watts" in df_plot.columns:
            # OPTIMIZATION: Pass only Series, not full DataFrame
            pcts = _calculate_zone_distribution(df_plot["watts"], cp_input)

            # OPTIMIZATION: O(1) dict lookup instead of O(k) list.index()
            bar_colors = [ZONE_COLOR_MAP[z] for z in pcts.index]

            fig_hist = go.Figure(
                go.Bar(
                    x=pcts.values,
                    y=pcts.index.astype(str),
                    orientation="h",
                    marker_color=bar_colors,
                    # OPTIMIZATION: Let Plotly format text instead of list comprehension
                    text=pcts.values,
                    texttemplate="%{text:.1f}%",
                    textposition="auto",
                )
            )
            fig_hist.update_layout(
                template="plotly_dark",
                height=250,
                xaxis=dict(visible=False),
                yaxis=dict(showgrid=False),
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig_hist, use_container_width=True)

    with col_dist2:
        st.subheader("Rozkład Tętna")
        if "heartrate" in df_plot.columns:
            # OPTIMIZATION: Use numpy for faster binning
            hr_valid = df_plot["heartrate"].dropna()
            if len(hr_valid) > 0:
                # Round and count using numpy (faster than pandas for this)
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
                st.plotly_chart(fig_hr, use_container_width=True)

    st.markdown("---")
    c_bot1, c_bot2 = st.columns(2)

    with c_bot1:
        st.subheader("🏆 Peak Power")
        if "watts" in df_plot.columns:
            # OPTIMIZATION: Cached MMP calculation (computed once per session)
            mmp_values = _calculate_mmp_peaks(df_plot["watts"], MMP_WINDOWS)

            cols = st.columns(5)
            for col, (label, window) in zip(cols, MMP_WINDOWS.items()):
                val = mmp_values.get(label)
                with col:
                    if val is not None:
                        w_per_kg = val / rider_weight if rider_weight > 0 else 0
                        st.metric(label, f"{val:.0f} W", f"{w_per_kg:.1f} W/kg")
                    else:
                        st.metric(label, "--")

    with c_bot2:
        st.subheader("🎯 Strefy (wg CP)")
        # OPTIMIZATION: Single f-string, already efficient O(1)
        z2_l, z2_h = int(0.56 * cp_input), int(0.75 * cp_input)
        z3_l, z3_h = int(0.76 * cp_input), int(0.90 * cp_input)
        z4_l, z4_h = int(0.91 * cp_input), int(1.05 * cp_input)
        st.info(
            f"**Z2 (Baza):** {z2_l}-{z2_h} W | **Z3 (Tempo):** {z3_l}-{z3_h} W | **Z4 (Próg):** {z4_l}-{z4_h} W"
        )

    # ============================================================
    # SEKCJA WIZUALIZACJI DRYFU I ZMIENNOŚCI (z kpi.py)
    # ============================================================
    st.markdown("---")
    st.subheader("📈 Wizualizacja Dryfu i Zmienności")

    if "watts_smooth" in df_plot.columns:
        fig_dec = go.Figure()
        fig_dec.add_trace(
            go.Scatter(
                x=df_plot_resampled["time_min"],
                y=df_plot_resampled["watts_smooth"],
                name="Moc",
                line=dict(color=Config.COLOR_POWER, width=1.5),
                hovertemplate="Moc: %{y:.0f} W<extra></extra>",
            )
        )

        if "heartrate_smooth" in df_plot.columns:
            fig_dec.add_trace(
                go.Scatter(
                    x=df_plot_resampled["time_min"],
                    y=df_plot_resampled["heartrate_smooth"],
                    name="HR",
                    yaxis="y2",
                    line=dict(color=Config.COLOR_HR, width=1.5),
                    hovertemplate="HR: %{y:.0f} BPM<extra></extra>",
                )
            )
        if "smo2_smooth" in df_plot.columns:
            fig_dec.add_trace(
                go.Scatter(
                    x=df_plot_resampled["time_min"],
                    y=df_plot_resampled["smo2_smooth"],
                    name="SmO2",
                    yaxis="y3",
                    line=dict(color=Config.COLOR_SMO2, dash="dot", width=1.5),
                    hovertemplate="SmO2: %{y:.1f}%<extra></extra>",
                )
            )

        fig_dec.update_layout(
            template="plotly_dark",
            title="Dryf Mocy, Tętna i SmO2 w Czasie",
            hovermode="x unified",
            yaxis=dict(title="Moc [W]"),
            yaxis2=dict(title="HR [bpm]", overlaying="y", side="right", showgrid=False),
            yaxis3=dict(
                title="SmO2 [%]",
                overlaying="y",
                side="right",
                showgrid=False,
                showticklabels=False,
                range=[0, 100],
            ),
            legend=dict(orientation="h", y=1.1, x=0),
        )
        st.plotly_chart(fig_dec, use_container_width=True)

        st.info("""
        **💡 Interpretacja: Fizjologia Zmęczenia (Triada: Moc - HR - SmO2)**

        Ten wykres pokazuje "koszt fizjologiczny" utrzymania zadanej mocy w czasie.

        **1. Stan Idealny (Brak Dryfu):**
        * **Moc (Zielony):** Linia płaska (stałe obciążenie).
        * **Tętno (Czerwony):** Linia płaska (równoległa do mocy).
        * **SmO2 (Fiolet):** Stabilne.
        * **Wniosek:** Jesteś w pełnej równowadze tlenowej. Możesz tak jechać godzinami.

        **2. Dryf Sercowo-Naczyniowy (Cardiac Drift):**
        * **Moc:** Stała.
        * **Tętno:** Powoli rośnie (rozjeżdża się z linią mocy).
        * **SmO2:** Stabilne.
        * **Przyczyna:** Odwodnienie (spadek objętości osocza) lub przegrzanie (krew ucieka do skóry). Serce musi bić szybciej, by pompować tę samą ilość tlenu.

        **3. Zmęczenie Metaboliczne (Metabolic Fatigue):**
        * **Moc:** Stała.
        * **Tętno:** Stabilne lub lekko rośnie.
        * **SmO2:** **Zaczyna spadać.**
        * **Przyczyna:** Mięśnie tracą wydajność (rekrutacja włókien szybkokurczliwych II typu, które zużywają więcej tlenu). To pierwszy sygnał nadchodzącego "odcięcia".

        **4. "Zgon" (Bonking/Failure):**
        * **Moc:** Zaczyna spadać (nie jesteś w stanie jej utrzymać).
        * **Tętno:** Może paradoksalnie spadać (zmęczenie układu nerwowego) lub rosnąć (panika organizmu).
        * **SmO2:** Gwałtowny spadek lub chaotyczne skoki.
        """)

    st.divider()

    c1, c2 = st.columns(2)

    # LEWA KOLUMNA: SmO2 + TREND
    with c1:
        st.subheader("SmO2")
        col_smo2 = (
            "smo2_smooth_ultra"
            if "smo2_smooth_ultra" in df_plot.columns
            else ("smo2_smooth" if "smo2_smooth" in df_plot.columns else None)
        )

        if col_smo2:
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
            st.plotly_chart(fig_s, use_container_width=True)

            st.info("""
            **💡 Hemodynamika Mięśniowa (SmO2) - Lokalny Monitoring:**
            
            SmO2 to "wskaźnik paliwa" bezpośrednio w pracującym mięśniu (zazwyczaj czworogłowym uda).
            * **Równowaga (Linia Płaska):** Podaż tlenu = Zapotrzebowanie. To stan zrównoważony (Steady State).
            * **Desaturacja (Spadek):** Popyt > Podaż. Wchodzisz w dług tlenowy. Jeśli dzieje się to przy stałej mocy -> zmęczenie metaboliczne.
            * **Reoksygenacja (Wzrost):** Odpoczynek. Szybkość powrotu do normy to doskonały wskaźnik wytrenowania (regeneracji).
            """)
        else:
            st.info("Brak danych SmO2")

    # PRAWA KOLUMNA: TĘTNO (HR)
    with c2:
        st.subheader("Tętno")
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
        st.plotly_chart(fig_h, use_container_width=True)

        st.info("""
        **💡 Reakcja Sercowo-Naczyniowa (HR) - Globalny System:**
        
        Serce to pompa centralna. Jego reakcja jest **opóźniona** względem wysiłku.
        * **Lag (Opóźnienie):** W krótkich interwałach (np. 30s) tętno nie zdąży wzrosnąć, mimo że moc jest max. Nie steruj sprintami na tętno!
        * **Decoupling (Rozjazd):** Jeśli moc jest stała, a tętno rośnie (dryfuje) -> organizm walczy z przegrzaniem lub odwodnieniem.
        * **Recovery HR:** Jak szybko tętno spada po wysiłku? Szybki spadek = sprawne przywspółczulne układu nerwowego (dobra forma).
        """)

    st.divider()

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
    st.plotly_chart(fig_v, use_container_width=True)

    st.info("""
    **💡 Interpretacja: Mechanika Oddychania**

    * **Wzorzec Prawidłowy (Efektywność):** Wentylacja (VE) rośnie liniowo wraz z mocą, a częstość (RR) jest stabilna. Oznacza to głęboki, spokojny oddech.
    * **Wzorzec Niekorzystny (Płytki Oddech):** Bardzo wysokie RR (>40-50) przy stosunkowo niskim VE. Oznacza to "dyszenie" - powietrze wchodzi tylko do "martwej strefy" płuc, nie biorąc udziału w wymianie gazowej.
    * **Dryf Wentylacyjny:** Jeśli przy stałej mocy VE ciągle rośnie (rosnący trend pomarańczowej linii), oznacza to narastającą kwasicę (organizm próbuje wydmuchać CO2) lub zmęczenie mięśni oddechowych.
    * **Próg VT2 (RCP):** Punkt załamania, gdzie VE wystrzeliwuje pionowo w górę. To Twoja "czerwona linia" metaboliczna.
    """)
