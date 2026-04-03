"""
Running-specific UI components.

Charts, metrics, and visualizations for running analysis.
"""

from typing import Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.dual_mode import calculate_normalized_pace, calculate_running_stress_score
from modules.calculations.pace import (
    calculate_fatigue_resistance_index_pace,
    calculate_pace_duration_curve,
    calculate_pace_zones_time,
    classify_running_phenotype,
    estimate_vo2max_from_pace,
    get_fri_interpretation_pace,
    get_phenotype_description,
)
from modules.calculations.pace_utils import format_pace
from modules.plots import apply_chart_style


def format_pace_for_display(pace_sec_per_km: float) -> str:
    """Format pace for UI display."""
    return format_pace(pace_sec_per_km)


def get_pace_zone_color(pace: float, threshold_pace: float) -> str:
    """Get color for pace zone."""
    if threshold_pace <= 0:
        return "#808080"
    ratio = pace / threshold_pace

    if ratio > 1.15:
        return "#3498db"  # Blue - Recovery
    elif ratio > 1.05:
        return "#2ecc71"  # Green - Aerobic
    elif ratio > 0.95:
        return "#f1c40f"  # Yellow - Tempo
    elif ratio > 0.88:
        return "#e67e22"  # Orange - Threshold
    else:
        return "#e74c3c"  # Red - Interval/Repetition


def calculate_pace_summary_stats(df: pd.DataFrame, threshold_pace: float) -> Dict:
    """Calculate summary statistics for pace data."""
    stats = {}

    if "pace" in df.columns:
        paces = df["pace"].dropna()
        stats["avg_pace"] = float(paces.mean())
        stats["min_pace"] = float(paces.min())
        stats["max_pace"] = float(paces.max())

    if "gap" in df.columns:
        gaps = df["gap"].dropna()
        stats["avg_gap"] = float(gaps.mean())

    if "pace" in df.columns:
        stats["time_in_zones"] = calculate_pace_zones_time(df, threshold_pace)

    return stats


def render_pace_chart(df: pd.DataFrame, threshold_pace: float):
    """Render pace chart with zones."""
    if "pace" not in df.columns:
        st.warning("Brak danych tempa")
        return

    PACE_CAP = 600
    fig = go.Figure()

    pace_data = df["pace"].clip(upper=PACE_CAP)

    fig.add_trace(go.Scatter(
        x=df.index, y=[PACE_CAP] * len(df),
        mode='lines', line=dict(width=0),
        showlegend=False, hoverinfo='skip',
    ))
    fig.add_trace(go.Scatter(
        x=df.index,
        y=pace_data,
        name='Tempo',
        fill='tonexty',
        fillcolor='rgba(52, 152, 219, 0.3)',
        line=dict(color='#3498db', width=1.5),
        hovertemplate="Tempo: %{customdata}<extra></extra>",
        customdata=[format_pace(p) for p in pace_data],
    ))

    if "gap" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["gap"].clip(upper=PACE_CAP),
            mode='lines',
            name='GAP',
            line=dict(color='#2ecc71', width=2, dash='dash')
        ))

    fig.add_hline(
        y=threshold_pace,
        line_dash="dot",
        line_color="red",
        annotation_text=f"Próg ({format_pace(threshold_pace)})"
    )

    pace_min_val = max(120, int(pace_data.min() // 30 * 30))
    y_tickvals = list(range(pace_min_val, PACE_CAP + 1, 30))
    y_ticktext = [format_pace(v) for v in y_tickvals]

    fig.update_layout(
        title="Tempo podczas biegu",
        xaxis_title="Czas",
        yaxis=dict(
            title="Tempo [min/km]",
            autorange="reversed",
            tickvals=y_tickvals,
            ticktext=y_ticktext,
            range=[PACE_CAP, pace_min_val],
        ),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_pace_zones_bar(time_in_zones: Dict[str, int]):
    """Render bar chart of time in pace zones."""
    if not time_in_zones:
        return

    zones = list(time_in_zones.keys())
    times = [time_in_zones[z] / 60 for z in zones]

    colors = ["#3498db", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#9b59b6"]

    fig = go.Figure(data=[
        go.Bar(x=zones, y=times, marker_color=colors[:len(zones)])
    ])

    fig.update_layout(
        title="Czas w strefach tempa",
        yaxis_title="Czas (min)",
        xaxis_title="Strefa"
    )

    st.plotly_chart(fig, use_container_width=True)


def render_running_metrics_cards(
    avg_pace: float,
    threshold_pace: float,
    distance_km: float,
    rss: float
):
    """Render running metrics cards."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Srednie tempo",
            format_pace_for_display(avg_pace),
            help=f"Prog: {format_pace_for_display(threshold_pace)}"
        )

    with col2:
        st.metric("Dystans", f"{distance_km:.2f} km")

    with col3:
        st.metric("RSS", f"{rss:.0f}", help="Running Stress Score")

    with col4:
        if threshold_pace > 0:
            intensity = threshold_pace / avg_pace if avg_pace > 0 else 0
            st.metric("IF", f"{intensity:.2f}", help="Intensity Factor")


# ===========================================================================
# MAIN TAB RENDERER
# ===========================================================================

def _format_duration(seconds: int) -> str:
    """Format seconds to human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}" if secs else f"{mins}min"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h{mins:02d}" if mins else f"{hours}h"


def render_running_tab(df_plot, threshold_pace, runner_weight):
    """
    Main Running analysis tab — pace-based equivalent of render_power_tab.
    
    Sections:
    1. Pace chart with D' balance
    2. Pace zones (time in zones)
    3. Key pace metrics + Pace Duration Curve
    4. Durability Index (pace-based)
    5. Runner phenotype classification
    """
    has_pace = "pace" in df_plot.columns

    if not has_pace:
        st.warning("⚠️ Brak danych tempa (pace) w pliku. "
                   "Zakładka Running wymaga kolumny `pace` lub `speed`.")
        return

    # ==================== 1. PACE + D' BALANCE ====================
    st.subheader("🏃 Wykres Tempa i D' Balance")

    fig_pace = go.Figure()

    time_col = "time_min" if "time_min" in df_plot.columns else df_plot.index
    x_data = df_plot[time_col] if isinstance(time_col, str) else time_col

    PACE_CAP = 600  # 10:00/km
    pace_smooth = df_plot["pace"].rolling(window=10, min_periods=1, center=True).mean()
    pace_clipped = pace_smooth.clip(upper=PACE_CAP)

    # Invisible baseline for Garmin-style fill from slow pace downward
    fig_pace.add_trace(go.Scatter(
        x=x_data, y=[PACE_CAP] * len(x_data),
        mode='lines', line=dict(width=0),
        showlegend=False, hoverinfo='skip',
    ))
    fig_pace.add_trace(go.Scatter(
        x=x_data,
        y=pace_clipped,
        name="Tempo",
        fill="tonexty",
        fillcolor="rgba(52, 152, 219, 0.3)",
        line=dict(color="#3498db", width=1.5),
        hovertemplate="Tempo: %{customdata}<extra></extra>",
        customdata=[format_pace(p) for p in pace_clipped],
    ))

    if "gap" in df_plot.columns:
        gap_smooth = df_plot["gap"].rolling(window=10, min_periods=1, center=True).mean()
        gap_clipped = gap_smooth.clip(upper=PACE_CAP)
        fig_pace.add_trace(go.Scatter(
            x=x_data,
            y=gap_clipped,
            name="GAP",
            line=dict(color="#2ecc71", width=1.5, dash="dash"),
            hovertemplate="GAP: %{customdata}<extra></extra>",
            customdata=[format_pace(p) for p in gap_clipped],
        ))

    fig_pace.add_hline(
        y=threshold_pace,
        line_dash="dot",
        line_color="red",
        annotation_text=f"Próg ({format_pace(threshold_pace)})",
        annotation_position="top left",
    )

    # mm:ss Y-axis ticks
    pace_min_val = max(120, int(pace_clipped.min() // 30 * 30))
    tick_step = 30
    y_tickvals = list(range(pace_min_val, PACE_CAP + 1, tick_step))
    y_ticktext = [format_pace(v) for v in y_tickvals]

    # HH:MM:SS X-axis ticks
    x_min_val = float(x_data.min()) if hasattr(x_data, 'min') else 0
    x_max_val = float(x_data.max()) if hasattr(x_data, 'max') else 60
    x_tick_step = max(1, int((x_max_val - x_min_val) / 10))
    x_tickvals = list(range(int(x_min_val), int(x_max_val) + 1, x_tick_step))
    x_ticktext = []
    for m in x_tickvals:
        total_sec = int(m * 60)
        hrs = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        if hrs > 0:
            x_ticktext.append(f"{hrs}:{mins:02d}:{secs:02d}")
        else:
            x_ticktext.append(f"{mins}:{secs:02d}")

    fig_pace.update_layout(
        template="plotly_dark",
        title="Zarządzanie Tempem (Pace & GAP)",
        hovermode="x unified",
        xaxis=dict(title="Czas", tickvals=x_tickvals, ticktext=x_ticktext),
        yaxis=dict(
            title="Tempo [min/km]",
            autorange="reversed",
            tickvals=y_tickvals,
            ticktext=y_ticktext,
            range=[PACE_CAP, pace_min_val],
        ),
        margin=dict(l=10, r=10, t=40, b=10),
        height=450,
    )
    st.plotly_chart(apply_chart_style(fig_pace), use_container_width=True)

    st.info("""
    **💡 Interpretacja: Zarządzanie Tempem**

    * **Niebieska linia (Tempo):** Aktualne tempo biegu (min/km). Im niżej na wykresie = szybciej.
    * **Zielona przerywana (GAP):** Grade-Adjusted Pace — tempo skorygowane o profil terenu.
    * **Czerwona linia (Próg):** Twoje tempo progowe.
    
    **Jak to czytać?**
    * **Tempo < Próg (powyżej linii):** Biegasz poniżej progu — strefa tlenowa. Regeneracja D'.
    * **Tempo > Próg (poniżej linii):** Biegasz powyżej progu — spalasz D'. Im szybciej, tym szybciej się wyczerpiesz.
    * **GAP vs Tempo:** Jeśli GAP jest szybsze niż tempo — biegasz pod górę. Jeśli wolniejsze — w dół.
    """)

    # ==================== 2. PACE ZONES ====================
    st.subheader("⏱️ Czas w Strefach Tempa")

    zones_time = calculate_pace_zones_time(df_plot, threshold_pace)

    if zones_time:
        zones_list = list(zones_time.keys())
        times_min = [zones_time[z] / 60 for z in zones_list]
        colors = ["#3498db", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#9b59b6"]

        # FIX: Format time as mm:ss
        def format_time_mmss(minutes: float) -> str:
            total_sec = int(minutes * 60)
            mins = total_sec // 60
            secs = total_sec % 60
            return f"{mins}:{secs:02d}"

        time_labels = [format_time_mmss(t) for t in times_min]

        fig_z = go.Figure(data=[
            go.Bar(
                x=[t for t in times_min],
                y=zones_list,
                orientation="h",
                text=time_labels,  # FIX: Show mm:ss format
                textposition="auto",
                marker_color=colors[:len(zones_list)],
            )
        ])

        # FIX: Convert x-axis tick values to mm:ss labels
        x_max = max(times_min) if times_min else 10
        x_tickvals = list(range(0, int(x_max) + 5, 5))
        x_ticktext = [format_time_mmss(t) for t in x_tickvals]

        fig_z.update_layout(
            template="plotly_dark",
            title="Czas w Strefach Tempa",  # FIX: Add title (was undefined)
            showlegend=False,
            xaxis=dict(
                title="Czas [mm:ss]",
                tickvals=x_tickvals,
                ticktext=x_ticktext,
            ),
            height=300,
            margin=dict(l=10, r=10, t=40, b=10),
        )

        st.info("""
        **💡 Interpretacja Stref Tempa:**
        
        * **Z1 Recovery (>115% progu):** Regeneracja, rozgrzewka, schładzanie.
        * **Z2 Aerobic (105-115%):** Budowa bazy tlenowej. Fundament.
        * **Z3 Tempo (95-105%):** Strefa progowa. Efektywna, ale wymagająca.
        * **Z4 Threshold (88-95%):** Powyżej progu. Trening tolerancji na mleczan.
        * **Z5 Interval (75-88%):** Interwały VO2max.
        * **Z6 Repetition (<75%):** Sprinterskie powtórzenia. Maksymalna prędkość.
        
        **Polaryzacja 80/20:** Dobrze zaprojektowany plan treningowy to ~80% Z1-Z2 i ~20% Z4-Z6.
        """)
    else:
        st.info("Brak wystarczających danych tempa do obliczenia stref.")

    # ==================== 3. RSS + KEY METRICS ====================
    st.subheader("📊 Kluczowe Metryki Biegowe")

    # Use actual time column for duration (not row count, which is only valid at 1Hz)
    if "time" in df_plot.columns and len(df_plot) > 1:
        duration_sec = float(df_plot["time"].iloc[-1] - df_plot["time"].iloc[0])
    else:
        duration_sec = len(df_plot)
    np_pace = calculate_normalized_pace(df_plot)
    rss = calculate_running_stress_score(df_plot, threshold_pace, duration_sec)

    # Distance — prefer real cumulative distance from CSV
    if "distance" in df_plot.columns and df_plot["distance"].max() > 0:
        distance_km = float(df_plot["distance"].max()) / 1000.0
    else:
        distance_km = 0.0

    # Avg pace — total_time / total_distance (not arithmetic mean of per-second pace)
    if distance_km > 0:
        avg_pace = duration_sec / distance_km
    else:
        avg_pace = float(df_plot["pace"].mean())

    intensity_factor = threshold_pace / np_pace if np_pace > 0 else 0

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Tempo Normalizowane", format_pace(np_pace),
                  help="Tempo znormalizowane algorytmem 4-potęgowym (jak NP dla mocy)")
    col_m2.metric("RSS", f"{rss:.0f}",
                  help=f"Running Stress Score (IF: {intensity_factor:.2f})")
    col_m3.metric("Średnie Tempo", format_pace(avg_pace))
    col_m4.metric("Dystans", f"{distance_km:.2f} km")

    # ==================== 4. PACE DURATION CURVE ====================
    st.subheader("📈 Pace Duration Curve (PDC)")

    pdc = calculate_pace_duration_curve(df_plot)

    if pdc:
        valid_pdc = {d: p for d, p in pdc.items() if p is not None}

        if valid_pdc:
            # Key metrics from PDC
            best_1min = pdc.get(60)
            best_5min = pdc.get(300)
            best_10min = pdc.get(600)
            best_20min = pdc.get(1200)

            col_p1, col_p2, col_p3, col_p4 = st.columns(4)

            with col_p1:
                if best_1min:
                    st.metric("⚡ Best 1min", format_pace(best_1min) + " /km")
                else:
                    st.metric("⚡ Best 1min", "—")

            with col_p2:
                if best_5min:
                    st.metric("🔥 Best 5min", format_pace(best_5min) + " /km")
                else:
                    st.metric("🔥 Best 5min", "—")

            with col_p3:
                if best_10min:
                    st.metric("💪 Best 10min", format_pace(best_10min) + " /km")
                else:
                    st.metric("💪 Best 10min", "—")

            with col_p4:
                if best_20min:
                    st.metric("🏔️ Best 20min", format_pace(best_20min) + " /km")
                else:
                    st.metric("🏔️ Best 20min", "—")

            # PDC chart
            durations_min = [d / 60 for d in valid_pdc.keys()]
            paces = list(valid_pdc.values())
            pace_labels = [format_pace(p) for p in paces]

            fig_pdc = go.Figure()
            fig_pdc.add_trace(go.Scatter(
                x=durations_min,
                y=paces,
                mode="lines+markers",
                name="Best Pace",
                line=dict(color="#3498db", width=3),
                marker=dict(size=8, color="#3498db", line=dict(width=1, color="white")),
                hovertemplate="Czas: %{x:.0f} min<br>Tempo: %{customdata}<extra></extra>",
                customdata=pace_labels,
            ))

            # Threshold line
            fig_pdc.add_hline(
                y=threshold_pace,
                line_dash="dot",
                line_color="red",
                annotation_text=f"Próg ({format_pace(threshold_pace)})",
            )

            pdc_min = max(120, int(min(paces) // 30 * 30))
            pdc_max = int(max(paces) // 30 * 30) + 30
            pdc_tickvals = list(range(pdc_min, pdc_max + 1, 30))
            pdc_ticktext = [format_pace(v) for v in pdc_tickvals]

            fig_pdc.update_layout(
                template="plotly_dark",
                title="Pace Duration Curve",
                xaxis=dict(title="Czas [min]", type="log"),
                yaxis=dict(
                    title="Tempo [min/km]",
                    autorange="reversed",
                    tickvals=pdc_tickvals,
                    ticktext=pdc_ticktext,
                ),
                height=400,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(apply_chart_style(fig_pdc), use_container_width=True)

            # FRI
            fri = calculate_fatigue_resistance_index_pace(pdc)
            if fri > 0:
                fri_interp = get_fri_interpretation_pace(fri)
                st.info(f"**Fatigue Resistance Index (FRI):** {fri:.3f} — {fri_interp}")
    else:
        st.info("Brak wystarczających danych do obliczenia PDC.")

    st.divider()

    # ==================== 5. DURABILITY & DECOUPLING ====================
    st.subheader("🛡️ Wytrzymalosc i Decoupling (Pa:HR)")

    min_duration_min = 20
    has_hr = "heartrate" in df_plot.columns
    if duration_sec >= min_duration_min * 60 and has_pace and has_hr:
        from modules.calculations.durability import (
            calculate_aerobic_decoupling,
            calculate_durability_index,
            detect_decoupling_onset,
        )

        decoupling = calculate_aerobic_decoupling(df_plot["pace"], df_plot["heartrate"])
        dur_idx = calculate_durability_index(df_plot["pace"], df_plot["heartrate"])
        onset = detect_decoupling_onset(df_plot["pace"], df_plot["heartrate"])

        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        col_d1.metric(
            "Pa:HR Decoupling",
            f"{decoupling['decoupling_pct']:.1f}%",
            delta=decoupling["classification"],
            delta_color="off",
            help="<5% = excellent aerobic base (Friel/TrainingPeaks)",
        )
        col_d2.metric(
            "Durability Score",
            f"{dur_idx['durability_score']:.0f}/100",
            delta=dur_idx["classification"],
            delta_color="off",
            help="Jones 2024 — composite fatigue resistance metric",
        )
        col_d3.metric("Pace CV", f"{dur_idx['pace_cv_pct']:.1f}%")
        onset_str = f"{onset.get('onset_time_sec', 0) // 60:.0f} min" if onset.get("onset_time_sec") else "brak"
        col_d4.metric("Onset Driftu", onset_str, help="Smyth 2025 — moment rozpoczęcia driftu")

        # EF trend chart
        if "ef_series" in onset and onset["ef_series"] is not None:
            ef_s = onset["ef_series"].dropna()
            if len(ef_s) > 60:
                fig_ef = go.Figure()
                t_min = np.arange(len(ef_s)) / 60.0
                fig_ef.add_trace(go.Scatter(
                    x=t_min, y=ef_s.values,
                    name="EF (speed/HR)", line=dict(color="#3498db", width=2),
                ))
                if onset.get("onset_time_sec"):
                    fig_ef.add_vline(
                        x=onset["onset_time_sec"] / 60,
                        line_dash="dash", line_color="#E74C3C",
                        annotation_text="Onset",
                    )
                fig_ef.update_layout(
                    template="plotly_dark", height=250,
                    xaxis_title="Czas [min]", yaxis_title="Efficiency Factor",
                    margin=dict(l=20, r=20, t=30, b=20),
                )
                st.plotly_chart(fig_ef, use_container_width=True)

        st.caption(f"{decoupling.get('interpretation', '')}")

    elif duration_sec >= min_duration_min * 60 and has_pace:
        # Fallback: simple pace split without HR
        half = len(df_plot) // 2
        avg_pace_first = df_plot["pace"].iloc[:half].mean()
        avg_pace_second = df_plot["pace"].iloc[half:].mean()
        if avg_pace_first > 0:
            durability = (avg_pace_first / avg_pace_second) * 100
        else:
            durability = 100.0
        col_d1, col_d2, col_d3 = st.columns(3)
        delta_color = "normal" if durability >= 97 else "inverse"
        col_d1.metric("Durability", f"{durability:.1f}%", delta=f"{durability - 100:.1f}%", delta_color=delta_color)
        col_d2.metric("1. polowa", format_pace(avg_pace_first))
        col_d3.metric("2. polowa", format_pace(avg_pace_second))
    else:
        st.info(f"Potrzeba minimum {min_duration_min} minut biegu z HR do analizy decoupling.")

    st.divider()

    # ==================== 6. PHENOTYPE CLASSIFICATION ====================
    st.subheader("🧬 Profil Biegacza (Fenotyp)")

    if pdc:
        phenotype = classify_running_phenotype(pdc, runner_weight)
        emoji, name, description = get_phenotype_description(phenotype)

        st.markdown(f"""
        <div style="background: linear-gradient(90deg, rgba(52, 152, 219, 0.2), transparent); 
                    padding: 15px 20px; border-radius: 12px; margin-bottom: 15px;">
            <span style="font-size: 2em;">{emoji}</span>
            <span style="font-size: 1.3em; font-weight: bold; margin-left: 10px;">{name}</span>
            <br/>
            <span style="font-size: 1em; color: #c9d1d9;">{description}</span>
        </div>
        """, unsafe_allow_html=True)

        # VO2max estimation from best ~6min pace (PDC 300-360s)
        best_pace_5min = pdc.get(300)
        if best_pace_5min:
            vo2max_est = estimate_vo2max_from_pace(best_pace_5min, runner_weight)
            if vo2max_est > 0:
                st.metric("Est. VO2max", f"{vo2max_est:.1f} ml/kg/min",
                         help="Szacowane na podstawie najlepszego tempa 5-minutowego (formuła Danielsa)")

        with st.expander("📚 Jak interpretować fenotyp biegacza?"):
            st.markdown("""
            ### Typy biegaczy
            
            | Fenotyp | Charakterystyka | Silne strony | Treningi kluczowe |
            |---------|----------------|--------------|-------------------|
            | ⚡ Sprinter | Szybki na 400m-1km, duży spadek na dłuższych | Sprint, 800m | Progi, tempo runs |
            | 🏃 Średnie dystanse | 5K-10K specialist | Szybkość + wytrzymałość | Interwały VO2max |
            | 🏃‍♂️ Maratończyk | Małe spadki na długich dystansach | Ekonomia, wytrzymałość | Tempo długie, baza |
            | 🦶 Ultra-biegacz | Niesamowita wytrzymałość | Wytrwałość, psychika | Objętość, back-to-back |
            | 🔄 Wszechstronny | Zbalansowany profil | Adaptacja | Periodyzacja |
            
            ### VO2max — poziomy
            | VO2max (ml/kg/min) | Mężczyźni | Kobiety |
            |---|---|---|
            | 75+ | Światowa klasa | Światowa klasa |
            | 60-75 | Bardzo dobry | Elitarny |
            | 50-60 | Dobry amator | Bardzo dobry |
            | 40-50 | Przeciętny | Dobry |
            | <40 | Początkujący | Przeciętny |
            """)
    else:
        st.info("Za mało danych do klasyfikacji fenotypu.")
