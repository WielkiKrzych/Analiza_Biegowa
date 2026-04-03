"""
Summary charts: physiological data visualization sections (sections 3-7).

Contains chart renderers for SmO2/THb, Running Dynamics, O2Hb/HHb,
HRV, and VO2max uncertainty estimation.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

__all__ = [
    "_render_smo2_thb_chart",
    "_render_running_dynamics_section",
    "_render_o2hb_hhb_section",
    "_render_hrv_section",
    "_render_vo2max_uncertainty",
]


def _render_smo2_thb_chart(df_plot):
    """Renderowanie wykresu SmO2 vs THb w czasie."""
    if "smo2" not in df_plot.columns:
        st.info("Brak danych SmO2 w tym pliku.")
        return

    fig_smo2_thb = make_subplots(specs=[[{"secondary_y": True}]])

    time_x = df_plot["time"] if "time" in df_plot.columns else range(len(df_plot))

    # SmO2
    smo2_smooth = (
        df_plot["smo2"].rolling(5, center=True).mean() if "smo2" in df_plot.columns else None
    )
    if smo2_smooth is not None:
        fig_smo2_thb.add_trace(
            go.Scatter(
                x=time_x,
                y=smo2_smooth,
                name="SmO2 (%)",
                line=dict(color="#2ca02c", width=2),
                hovertemplate="SmO2: %{y:.1f}%<extra></extra>",
            ),
            secondary_y=False,
        )

    # THb
    if "thb" in df_plot.columns:
        thb_smooth = df_plot["thb"].rolling(5, center=True).mean()
        fig_smo2_thb.add_trace(
            go.Scatter(
                x=time_x,
                y=thb_smooth,
                name="THb (g/dL)",
                line=dict(color="#9467bd", width=2),
                hovertemplate="THb: %{y:.2f} g/dL<extra></extra>",
            ),
            secondary_y=True,
        )
    else:
        st.caption("ℹ️ Brak danych THb w pliku.")

    # TEMPO - Add pace with hh:mm:ss format
    if "pace" in df_plot.columns or "pace_smooth" in df_plot.columns:
        pace_col = "pace_smooth" if "pace_smooth" in df_plot.columns else "pace"
        pace_data = df_plot[pace_col].rolling(5, center=True).mean() / 60.0  # Convert to min/km
        # Format mm:ss/km for hover
        pace_hover = [
            f"{int(p)}:{int((p % 1) * 60):02d} /km" if pd.notna(p) else "--:--" for p in pace_data
        ]
        fig_smo2_thb.add_trace(
            go.Scatter(
                x=time_x,
                y=pace_data,
                name="Tempo (min/km)",
                line=dict(color="#00d4aa", width=2, dash="dot"),
                hovertemplate="Tempo: %{customdata}<extra></extra>",
                customdata=pace_hover,
            ),
            secondary_y=False,
        )
    fig_smo2_thb.update_layout(
        template="plotly_dark",
        height=350,
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    fig_smo2_thb.update_yaxes(title_text="SmO2 (%)", secondary_y=False)
    fig_smo2_thb.update_yaxes(title_text="THb (g/dL)", secondary_y=True)
    st.plotly_chart(fig_smo2_thb, use_container_width=True)

    # Oblicz statystyki SmO2 i THb
    if "smo2" in df_plot.columns:
        smo2_min = df_plot["smo2"].min()
        smo2_max = df_plot["smo2"].max()
        smo2_mean = df_plot["smo2"].mean()

        thb_min = df_plot["thb"].min() if "thb" in df_plot.columns else None
        thb_max = df_plot["thb"].max() if "thb" in df_plot.columns else None
        thb_mean = df_plot["thb"].mean() if "thb" in df_plot.columns else None

        # Wyświetl statystyki w ładnych ramkach (podobnie jak w sekcji 5 - Progi Wentylacyjne)
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(
                f"""
            <div style="padding:15px; border-radius:8px; border:2px solid #2ca02c; background-color: #222;">
                <h3 style="margin:0; color: #2ca02c;">🩸 SmO2</h3>
                <p style="margin:5px 0; color:#aaa;"><b>Min:</b> {smo2_min:.1f}%</p>
                <p style="margin:5px 0; color:#aaa;"><b>Max:</b> {smo2_max:.1f}%</p>
                <p style="margin:5px 0; color:#aaa;"><b>Śr:</b> {smo2_mean:.1f}%</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with col2:
            if thb_min is not None:
                st.markdown(
                    f"""
                <div style="padding:15px; border-radius:8px; border:2px solid #9467bd; background-color: #222;">
                    <h3 style="margin:0; color: #9467bd;">💉 THb</h3>
                    <p style="margin:5px 0; color:#aaa;"><b>Min:</b> {thb_min:.2f} g/dL</p>
                    <p style="margin:5px 0; color:#aaa;"><b>Max:</b> {thb_max:.2f} g/dL</p>
                    <p style="margin:5px 0; color:#aaa;"><b>Śr:</b> {thb_mean:.2f} g/dL</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )


def _render_running_dynamics_section(df_plot: pd.DataFrame):
    """Render Running Dynamics section with GCT, balance, VR, step length charts."""
    has_dynamics = any(
        col in df_plot.columns
        for col in ["stance_time", "stance_time_balance", "vertical_ratio", "step_length"]
    )
    if not has_dynamics:
        return

    st.subheader("4️⃣ Running Dynamics (Garmin FIT)")

    time_x = df_plot["time"] if "time" in df_plot.columns else pd.Series(range(len(df_plot)))

    fig_dyn = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=("GCT (ms)", "Balans L/P (%)", "Vertical Ratio (%)", "Długość Kroku (m)"),
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    # GCT
    gct_col = (
        "stance_time"
        if "stance_time" in df_plot.columns
        else ("gct" if "gct" in df_plot.columns else None)
    )
    if gct_col:
        gct_smooth = df_plot[gct_col].rolling(10, center=True).mean()
        fig_dyn.add_trace(
            go.Scatter(
                x=time_x,
                y=gct_smooth,
                name="GCT",
                line=dict(color="#FF6B6B", width=2),
                hovertemplate="GCT: %{y:.0f} ms<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # Balance
    if "stance_time_balance" in df_plot.columns:
        bal_smooth = df_plot["stance_time_balance"].rolling(15, center=True).mean()
        fig_dyn.add_trace(
            go.Scatter(
                x=time_x,
                y=bal_smooth,
                name="Balans",
                line=dict(color="#1ABC9C", width=2),
                hovertemplate="Balans: %{y:.1f}%<extra></extra>",
            ),
            row=1,
            col=2,
        )
        fig_dyn.add_hline(
            y=50.0, line_dash="dash", line_color="white", row=1, col=2, annotation_text="50%"
        )

    # Vertical Ratio
    if "vertical_ratio" in df_plot.columns:
        vr_smooth = df_plot["vertical_ratio"].rolling(10, center=True).mean()
        fig_dyn.add_trace(
            go.Scatter(
                x=time_x,
                y=vr_smooth,
                name="VR",
                line=dict(color="#E67E22", width=2),
                hovertemplate="VR: %{y:.1f}%<extra></extra>",
            ),
            row=2,
            col=1,
        )

    # Step Length
    if "step_length" in df_plot.columns:
        sl_smooth = df_plot["step_length"].rolling(10, center=True).mean()
        fig_dyn.add_trace(
            go.Scatter(
                x=time_x,
                y=sl_smooth,
                name="Step Length",
                line=dict(color="#9B59B6", width=2),
                hovertemplate="Krok: %{y:.3f} m<extra></extra>",
            ),
            row=2,
            col=2,
        )

    fig_dyn.update_layout(
        template="plotly_dark",
        height=600,
        showlegend=False,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_dyn, use_container_width=True)

    # Stats boxes
    cols = st.columns(4)
    if gct_col and gct_col in df_plot.columns:
        gct_data = df_plot[gct_col].dropna()
        cols[0].markdown(
            f"""<div style="padding:12px; border-radius:8px; border:2px solid #FF6B6B; background:#222;">
            <h4 style="margin:0; color:#FF6B6B;">⏱️ GCT</h4>
            <p style="margin:3px 0; color:#aaa;"><b>Śr:</b> {gct_data.mean():.0f} ms</p>
            <p style="margin:3px 0; color:#aaa;"><b>Min:</b> {gct_data.min():.0f} ms</p>
            <p style="margin:3px 0; color:#aaa;"><b>Max:</b> {gct_data.max():.0f} ms</p>
            </div>""",
            unsafe_allow_html=True,
        )

    if "stance_time_balance" in df_plot.columns:
        bal_data = df_plot["stance_time_balance"].dropna()
        asym = abs(bal_data.mean() - 50.0)
        cols[1].markdown(
            f"""<div style="padding:12px; border-radius:8px; border:2px solid #1ABC9C; background:#222;">
            <h4 style="margin:0; color:#1ABC9C;">⚖️ Balans L/P</h4>
            <p style="margin:3px 0; color:#aaa;"><b>Śr:</b> {bal_data.mean():.1f}%</p>
            <p style="margin:3px 0; color:#aaa;"><b>Asymetria:</b> {asym:.1f}%</p>
            <p style="margin:3px 0; color:#aaa;"><b>Zakres:</b> {bal_data.min():.1f} – {bal_data.max():.1f}%</p>
            </div>""",
            unsafe_allow_html=True,
        )

    if "vertical_ratio" in df_plot.columns:
        vr_data = df_plot["vertical_ratio"].dropna()
        cols[2].markdown(
            f"""<div style="padding:12px; border-radius:8px; border:2px solid #E67E22; background:#222;">
            <h4 style="margin:0; color:#E67E22;">📐 Vertical Ratio</h4>
            <p style="margin:3px 0; color:#aaa;"><b>Śr:</b> {vr_data.mean():.1f}%</p>
            <p style="margin:3px 0; color:#aaa;"><b>Min:</b> {vr_data.min():.1f}%</p>
            <p style="margin:3px 0; color:#aaa;"><b>Max:</b> {vr_data.max():.1f}%</p>
            </div>""",
            unsafe_allow_html=True,
        )

    if "step_length" in df_plot.columns:
        sl_data = df_plot["step_length"].dropna()
        cols[3].markdown(
            f"""<div style="padding:12px; border-radius:8px; border:2px solid #9B59B6; background:#222;">
            <h4 style="margin:0; color:#9B59B6;">📏 Długość Kroku</h4>
            <p style="margin:3px 0; color:#aaa;"><b>Śr:</b> {sl_data.mean():.3f} m</p>
            <p style="margin:3px 0; color:#aaa;"><b>Min:</b> {sl_data.min():.3f} m</p>
            <p style="margin:3px 0; color:#aaa;"><b>Max:</b> {sl_data.max():.3f} m</p>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")


def _render_o2hb_hhb_section(df_plot: pd.DataFrame):
    """Render O2Hb and HHb chart from FIT data."""
    if "o2hb" not in df_plot.columns and "hhb" not in df_plot.columns:
        return

    st.subheader("5️⃣ Hemoglobina: O2Hb i HHb (FIT)")

    fig_hb = make_subplots(specs=[[{"secondary_y": True}]])
    time_x = df_plot["time"] if "time" in df_plot.columns else pd.Series(range(len(df_plot)))

    if "o2hb" in df_plot.columns:
        o2hb_smooth = df_plot["o2hb"].rolling(5, center=True).mean()
        fig_hb.add_trace(
            go.Scatter(
                x=time_x,
                y=o2hb_smooth,
                name="O2Hb",
                line=dict(color="#e74c3c", width=2),
                hovertemplate="O2Hb: %{y:.1f} a.u.<extra></extra>",
            ),
            secondary_y=False,
        )

    if "hhb" in df_plot.columns:
        hhb_smooth = df_plot["hhb"].rolling(5, center=True).mean()
        fig_hb.add_trace(
            go.Scatter(
                x=time_x,
                y=hhb_smooth,
                name="HHb",
                line=dict(color="#3498db", width=2),
                hovertemplate="HHb: %{y:.1f} a.u.<extra></extra>",
            ),
            secondary_y=False,
        )

    # Add pace overlay
    if "pace" in df_plot.columns or "pace_smooth" in df_plot.columns:
        pace_col = "pace_smooth" if "pace_smooth" in df_plot.columns else "pace"
        pace_data = df_plot[pace_col].rolling(10, center=True).mean() / 60.0
        pace_hover = [
            f"{int(p)}:{int((p % 1) * 60):02d} /km" if pd.notna(p) else "--:--" for p in pace_data
        ]
        fig_hb.add_trace(
            go.Scatter(
                x=time_x,
                y=pace_data,
                name="Tempo",
                line=dict(color="#00d4aa", width=2, dash="dot"),
                hovertemplate="Tempo: %{customdata}<extra></extra>",
                customdata=pace_hover,
            ),
            secondary_y=True,
        )

    fig_hb.update_layout(
        template="plotly_dark",
        height=350,
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    fig_hb.update_yaxes(title_text="Hemoglobina [a.u.]", secondary_y=False)
    fig_hb.update_yaxes(title_text="Tempo [min/km]", autorange="reversed", secondary_y=True)
    st.plotly_chart(fig_hb, use_container_width=True)

    # Stats
    col1, col2 = st.columns(2)
    if "o2hb" in df_plot.columns:
        o2hb = df_plot["o2hb"].dropna()
        col1.markdown(
            f"""<div style="padding:15px; border-radius:8px; border:2px solid #e74c3c; background:#222;">
            <h3 style="margin:0; color: #e74c3c;">🔴 O2Hb (Oksyhemoglobina)</h3>
            <p style="margin:5px 0; color:#aaa;"><b>Min:</b> {o2hb.min():.1f} a.u.</p>
            <p style="margin:5px 0; color:#aaa;"><b>Max:</b> {o2hb.max():.1f} a.u.</p>
            <p style="margin:5px 0; color:#aaa;"><b>Śr:</b> {o2hb.mean():.1f} a.u.</p>
            </div>""",
            unsafe_allow_html=True,
        )

    if "hhb" in df_plot.columns:
        hhb = df_plot["hhb"].dropna()
        col2.markdown(
            f"""<div style="padding:15px; border-radius:8px; border:2px solid #3498db; background:#222;">
            <h3 style="margin:0; color: #3498db;">🔵 HHb (Deoksyhemoglobina)</h3>
            <p style="margin:5px 0; color:#aaa;"><b>Min:</b> {hhb.min():.1f} a.u.</p>
            <p style="margin:5px 0; color:#aaa;"><b>Max:</b> {hhb.max():.1f} a.u.</p>
            <p style="margin:5px 0; color:#aaa;"><b>Śr:</b> {hhb.mean():.1f} a.u.</p>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")


def _render_hrv_section(df_plot: pd.DataFrame):
    """Render per-second HRV (RMSSD) chart from FIT data."""
    if "hrv" not in df_plot.columns:
        return

    hrv_data = df_plot["hrv"].dropna()
    if len(hrv_data) < 10:
        return

    st.subheader("6️⃣ HRV (RMSSD per sekundę)")

    fig_hrv = make_subplots(specs=[[{"secondary_y": True}]])
    time_x = df_plot["time"] if "time" in df_plot.columns else pd.Series(range(len(df_plot)))

    hrv_smooth = df_plot["hrv"].rolling(30, center=True).mean()
    fig_hrv.add_trace(
        go.Scatter(
            x=time_x,
            y=hrv_smooth,
            name="HRV (RMSSD)",
            line=dict(color="#19d3f3", width=2),
            hovertemplate="RMSSD: %{y:.1f} ms<extra></extra>",
        ),
        secondary_y=False,
    )

    # Add HR overlay
    hr_col = next((c for c in ["heartrate", "hr"] if c in df_plot.columns), None)
    if hr_col:
        hr_smooth = df_plot[hr_col].rolling(10, center=True).mean()
        fig_hrv.add_trace(
            go.Scatter(
                x=time_x,
                y=hr_smooth,
                name="HR",
                line=dict(color="#ef553b", width=2, dash="dot"),
                hovertemplate="HR: %{y:.0f} bpm<extra></extra>",
            ),
            secondary_y=True,
        )

    fig_hrv.update_layout(
        template="plotly_dark",
        height=350,
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    fig_hrv.update_yaxes(title_text="RMSSD [ms]", secondary_y=False)
    fig_hrv.update_yaxes(title_text="HR [bpm]", secondary_y=True)
    st.plotly_chart(fig_hrv, use_container_width=True)

    # Stats
    col1, col2, col3 = st.columns(3)
    col1.metric("💓 AVG RMSSD", f"{hrv_data.mean():.1f} ms")
    col2.metric("Min RMSSD", f"{hrv_data.min():.1f} ms")
    col3.metric("Max RMSSD", f"{hrv_data.max():.1f} ms")

    st.info("""
    **💡 Interpretacja HRV (RMSSD) podczas biegu:**

    * **Wyższe RMSSD:** Lepszy tonus parasympatyczny, bieg w strefie tlenowej
    * **Spadek RMSSD:** Wzrost intensywności, dominacja współczulna
    * **RMSSD < 10 ms:** Wysoka intensywność, bieg powyżej progu
    * **Trend spadkowy:** Narastające zmęczenie podczas sesji
    """)

    st.markdown("---")


def _render_vo2max_uncertainty(df_plot: pd.DataFrame, rider_weight: float):
    """
    Estymacja VO2max z przedziałem ufności 95% (CI95%).

    Wzór Sitko et al. 2021: VO2max = 16.61 + 8.87 × 5' max power (W/kg)

    CI95% oparta na:
    - Zmienności mocy w ostatnich 5 minutach rampy (SD)
    - Stabilności odpowiedzi HR (CV)
    """

    # Walidacja danych
    if "watts" not in df_plot.columns:
        st.warning("⚠️ **Brak danych mocy** — nie można estymować VO2max.")
        return

    if rider_weight <= 0:
        st.warning("⚠️ **Nieprawidłowa waga zawodnika** — nie można estymować VO2max.")
        return

    # Oblicz maksymalną 5-minutową moc (MMP5) używając rolling window
    # Tak samo jak w głównej metryce VO2max
    if len(df_plot) < 300:
        st.warning("⚠️ **Za mało danych** (wymagane min. 5 minut) — nie można estymować VO2max.")
        return

    # Znajdź najlepszy 5-minutowy okres (tak jak w głównej metryce)
    rolling_5min = df_plot["watts"].rolling(window=300, min_periods=300).mean()
    best_5min_idx = rolling_5min.idxmax()
    mmp_5min = rolling_5min.max()

    # Pobierz dane z najlepszego 5-minutowego okresu do obliczenia SD i CV
    best_5min_start = max(0, best_5min_idx - 299)
    df_best5 = df_plot.iloc[best_5min_start : best_5min_idx + 1]

    # Obliczenia mocy dla najlepszego okresu
    power_mean = mmp_5min  # Średnia moc w najlepszym 5-min okresie
    power_sd = df_best5["watts"].std()
    power_cv = (power_sd / power_mean * 100) if power_mean > 0 else 0
    n = len(df_best5)

    # Estymacja VO2max (Sitko et al. 2021)
    power_per_kg = power_mean / rider_weight
    vo2max = 16.61 + 8.87 * power_per_kg

    # Obliczenie SE i CI95% dla VO2max
    # Propagacja błędu: SE_vo2 = 8.87 / kg * SE_power
    se_power = power_sd / np.sqrt(n)
    se_vo2 = 8.87 * se_power / rider_weight
    ci95_vo2 = 1.96 * se_vo2

    # Dodatkowa niepewność z HR response (jeśli dostępne)
    hr_penalty = 0
    hr_col = None
    for alias in ["hr", "heartrate", "heart_rate", "bpm"]:
        if alias in df_best5.columns:
            hr_col = alias
            break

    if hr_col:
        hr_mean = df_best5[hr_col].mean()
        hr_sd = df_best5[hr_col].std()
        hr_cv = (hr_sd / hr_mean * 100) if hr_mean > 0 else 0
        # Wysoki CV HR = większa niepewność
        if hr_cv > 5:
            hr_penalty = ci95_vo2 * 0.2  # +20% CI za niestabilne HR

    ci95_total = ci95_vo2 + hr_penalty

    # Confidence Weight: im mniejszy CI względem VO2max, tym wyższa waga
    confidence_weight = 1 / (1 + ci95_total / vo2max) if vo2max > 0 else 0
    confidence_pct = confidence_weight * 100

    # Klasyfikacja pewności
    if confidence_pct >= 80:
        conf_color = "#00cc96"
        conf_label = "WYSOKA"
    elif confidence_pct >= 60:
        conf_color = "#ffa15a"
        conf_label = "UMIARKOWANA"
    else:
        conf_color = "#ef553b"
        conf_label = "NISKA"

    # Wyświetlanie głównego wyniku
    st.markdown(
        f"""
    <div style="padding:20px; border-radius:12px; border:3px solid #17a2b8; background-color: #1a1a1a; text-align:center;">
        <h2 style="margin:0; color: #17a2b8;">VO₂max = {vo2max:.1f} ± {ci95_total:.1f} ml/kg/min</h2>
        <p style="margin:10px 0 0 0; color:#888; font-size:0.85em;">
            (CI95%: {vo2max - ci95_total:.1f} – {vo2max + ci95_total:.1f} ml/kg/min)
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Źródło disclaimer
    st.caption(
        "📌 **Źródło:** Estymacja modelowa (Sitko et al. 2021), nie pomiar bezpośredni. Używać orientacyjnie."
    )

    # Confidence Weight
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
        <div style="padding:15px; border-radius:8px; border:2px solid {conf_color}; background-color: #222; text-align:center;">
            <p style="margin:0; color:#aaa; font-size:0.9em;">Waga Pewności (Confidence Weight)</p>
            <h3 style="margin:5px 0; color: {conf_color};">{confidence_pct:.0f}% — {conf_label}</h3>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Szczegóły obliczeń
    with st.expander("📊 Szczegóły obliczeń", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("MMP5 (najlepsze 5 min)", f"{power_mean:.0f} W")
        c2.metric("SD mocy", f"{power_sd:.1f} W")
        c3.metric("CV mocy", f"{power_cv:.1f}%")

        if hr_col:
            c1, c2, c3 = st.columns(3)
            c1.metric("Średnie HR", f"{hr_mean:.0f} bpm")
            c2.metric("SD HR", f"{hr_sd:.1f} bpm")
            c3.metric("CV HR", f"{hr_cv:.1f}%")

        st.markdown(f"""
        | Parametr | Wartość |
        |----------|---------|
        | SE mocy | {se_power:.2f} W |
        | SE VO₂max | {se_vo2:.2f} ml/kg/min |
        | CI95% (moc) | ±{ci95_vo2:.2f} ml/kg/min |
        | Korekta HR | +{hr_penalty:.2f} ml/kg/min |
        | **CI95% całkowity** | **±{ci95_total:.2f} ml/kg/min** |
        """)

    # Teoria
    with st.expander("📖 Metodologia estymacji VO2max", expanded=False):
        st.markdown("""
        ### Formuła Sitko et al. 2021

        ```
        VO₂max = 16.61 + 8.87 × 5' max power (W/kg)
        ```

        Gdzie:
        - `5' max power (W/kg)` = maksymalna moc 5-minutowa na kg masy ciała [W/kg]
        - `kg` = masa ciała zawodnika [kg]

        ---

        ### Przedział ufności (CI95%)

        CI95% jest obliczany na podstawie:

        1. **Zmienność mocy (SD):**
           - Wysoka zmienność = większa niepewność estymacji
           - SE = SD / √n
           - CI = 1.96 × SE × 8.87 / kg

        2. **Stabilność HR:**
           - CV HR > 5% → dodatkowa korekta +20% CI
           - Niestabilne HR może wskazywać na nieustalony stan metaboliczny

        ---

        ### Waga Pewności (Confidence Weight)

        ```
        Weight = 1 / (1 + CI/VO₂max)
        ```

        Używana do skalowania pewności wniosków centralnych:
        - **≥80%** = Wysoka pewność, wyniki wiarygodne
        - **60-80%** = Umiarkowana pewność, interpretować ostrożnie
        - **<60%** = Niska pewność, traktować orientacyjnie

        ---

        *Uwaga: Jest to estymacja modelowa, nie zastępuje bezpośredniego pomiaru VO₂max w laboratorium.*
        """)
