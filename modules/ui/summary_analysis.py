"""
Summary analysis: advanced physiological analysis sections (sections 8-12).

Contains renderers for durability/decoupling, race prediction, BR analysis,
thermal analysis, and running effectiveness/biomechanics.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.br_analysis import (
    calculate_br_decoupling,
    calculate_br_zones_time,
    detect_vt_from_br,
)
from modules.calculations.durability import (
    calculate_aerobic_decoupling,
    calculate_durability_index,
    detect_decoupling_onset,
)
from modules.calculations.race_predictor import format_time, multi_model_predict
from modules.calculations.running_effectiveness import (
    calculate_gct_asymmetry_index,
    calculate_leg_spring_stiffness,
    calculate_running_effectiveness,
)
from modules.calculations.thermal import (
    calculate_core_temp_zones_time,
    calculate_thermal_drift_rate,
)

__all__ = [
    "_render_durability_section",
    "_render_race_prediction_section",
    "_render_br_analysis_section",
    "_render_thermal_analysis_section",
    "_render_running_effectiveness_section",
]


def _render_durability_section(df_plot):
    """Section 8: Durability & aerobic decoupling analysis."""
    st.subheader("8️⃣ Wytrzymalosc i Decoupling")

    has_pace = "pace" in df_plot.columns
    has_hr = "heartrate" in df_plot.columns
    if not (has_pace and has_hr):
        st.info("Brak danych tempa i HR do analizy decoupling.")
        return

    decoupling = calculate_aerobic_decoupling(df_plot["pace"], df_plot["heartrate"])
    durability = calculate_durability_index(df_plot["pace"], df_plot["heartrate"])

    # Decoupling onset detection
    onset = detect_decoupling_onset(df_plot["pace"], df_plot["heartrate"])

    c1, c2, c3, c4 = st.columns(4)

    # Color based on classification
    dec_colors = {
        "excellent": "#27AE60",
        "good": "#2ECC71",
        "moderate": "#F39C12",
        "poor": "#E74C3C",
    }
    dec_colors.get(decoupling.get("classification", ""), "#808080")

    c1.metric(
        "Pa:HR Decoupling",
        f"{decoupling['decoupling_pct']:.1f}%",
        delta=decoupling["classification"],
        delta_color="off",
    )
    c2.metric(
        "Durability Score",
        f"{durability['durability_score']:.0f}/100",
        delta=durability["classification"],
        delta_color="off",
    )
    c3.metric("Pace CV", f"{durability['pace_cv_pct']:.1f}%")
    onset_str = (
        f"{onset.get('onset_time_sec', 0) // 60:.0f} min" if onset.get("onset_time_sec") else "brak"
    )
    c4.metric("Onset driftu", onset_str)

    # EF trend chart
    if "ef_series" in onset and onset["ef_series"] is not None:
        ef_series = onset["ef_series"].dropna()
        if len(ef_series) > 60:
            fig_ef = go.Figure()
            time_min = np.arange(len(ef_series)) / 60.0
            fig_ef.add_trace(
                go.Scatter(
                    x=time_min,
                    y=ef_series.values,
                    name="Efficiency Factor",
                    line=dict(color="#3498db", width=2),
                )
            )
            if onset.get("onset_time_sec"):
                fig_ef.add_vline(
                    x=onset["onset_time_sec"] / 60,
                    line_dash="dash",
                    line_color="#E74C3C",
                    annotation_text="Onset driftu",
                )
            fig_ef.update_layout(
                template="plotly_dark",
                height=250,
                xaxis_title="Czas [min]",
                yaxis_title="EF (speed/HR)",
                margin=dict(l=20, r=20, t=30, b=20),
            )
            st.plotly_chart(fig_ef, use_container_width=True)

    st.caption(f"Interpretacja: {decoupling.get('interpretation', '')}")

    st.markdown("---")


def _render_race_prediction_section(df_plot, rider_weight):
    """Section 9: Multi-model race prediction."""
    st.subheader("9️⃣ Predykcja Czasow Wyscigowych")

    # Need distance and time to predict
    total_distance_km = 0.0
    total_time_sec = len(df_plot)
    if "distance" in df_plot.columns:
        dist_vals = df_plot["distance"].dropna()
        if len(dist_vals) > 0:
            max_dist = dist_vals.iloc[-1]
            total_distance_km = max_dist / 1000.0 if max_dist > 100 else max_dist

    if total_distance_km < 1.0:
        st.info("Brak danych dystansu do predykcji.")
        return

    if "time" in df_plot.columns:
        total_time_sec = df_plot["time"].iloc[-1] - df_plot["time"].iloc[0]

    predictions = multi_model_predict(total_distance_km, total_time_sec)
    vdot = predictions.get("vdot", 0)

    c1, c2 = st.columns([1, 3])
    with c1:
        st.metric("VDOT", f"{vdot:.1f}")
        st.caption("Jack Daniels")

    with c2:
        # Build prediction table
        rows = []
        for dist_name in ["5K", "10K", "Half Marathon", "Marathon"]:
            p = predictions.get(dist_name, {})
            if isinstance(p, dict):
                riegel_t = format_time(p.get("riegel", 0)) if p.get("riegel") else "--"
                vdot_t = format_time(p.get("vdot", 0)) if p.get("vdot") else "--"
                consensus_t = format_time(p.get("consensus", 0)) if p.get("consensus") else "--"
                rows.append(
                    {
                        "Dystans": dist_name,
                        "Riegel": riegel_t,
                        "VDOT": vdot_t,
                        "Consensus": consensus_t,
                    }
                )
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    with st.expander("Metody predykcji"):
        st.markdown("""
        - **Riegel**: `T2 = T1 × (D2/D1)^exp` — klasyczny model skalowania (George 2017)
        - **VDOT**: Formuła Danielsa z frakcją utylizacji O2
        - **Consensus**: Średnia ważona (VDOT 0.4, Riegel 0.3, CS 0.3)
        """)

    st.markdown("---")


def _render_br_analysis_section(df_plot):
    """Section 10: Breathing rate zones and analysis."""
    st.subheader("🔟 Analiza Czestosci Oddechow (BR)")

    if "tymebreathrate" not in df_plot.columns:
        st.info("Brak danych BR (breathing rate).")
        return

    br_zones = calculate_br_zones_time(df_plot["tymebreathrate"])

    # BR zones bar chart
    zone_names = list(br_zones.keys())
    zone_values = [float(v) / 60.0 for v in br_zones.values()]  # Convert to minutes
    zone_colors = ["#3498db", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"]

    fig_br = go.Figure(
        data=[
            go.Bar(
                x=zone_names,
                y=zone_values,
                marker_color=zone_colors[: len(zone_names)],
                text=[f"{v:.1f} min" for v in zone_values],
                textposition="auto",
            )
        ]
    )
    fig_br.update_layout(
        template="plotly_dark",
        height=250,
        yaxis_title="Czas [min]",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig_br, use_container_width=True)

    # VT detection from BR (if ramp/step test)
    vt_result = detect_vt_from_br(
        df_plot["tymebreathrate"],
        hr_series=df_plot.get("heartrate"),
        pace_series=df_plot.get("pace"),
    )
    if vt_result.get("vt1_br") is not None:
        c1, c2 = st.columns(2)
        c1.metric("VT1 (BR)", f"{vt_result['vt1_br']:.0f} /min")
        c2.metric(
            "VT2 (BR)",
            f"{vt_result.get('vt2_br', 0):.0f} /min" if vt_result.get("vt2_br") else "--",
        )

    # BR decoupling (if HR available)
    if "heartrate" in df_plot.columns:
        br_dec = calculate_br_decoupling(df_plot["tymebreathrate"], df_plot["heartrate"])
        st.caption(
            f"BR:HR Decoupling: {br_dec['decoupling_pct']:.1f}% — {br_dec.get('interpretation', '')}"
        )

    st.markdown("---")


def _render_thermal_analysis_section(df_plot):
    """Section 11: Core temperature zone analysis and thermal drift."""
    st.subheader("1️⃣1️⃣ Analiza Termiczna")

    if "core_temperature" not in df_plot.columns:
        st.info("Brak danych core temperature.")
        return

    # Thermal zones time
    zones_time = calculate_core_temp_zones_time(df_plot["core_temperature"])

    # Thermal drift
    time_col = df_plot["time"] if "time" in df_plot.columns else None
    drift = calculate_thermal_drift_rate(df_plot["core_temperature"], time_col)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Start", f"{drift.get('start_temp', 0):.1f} °C")
    c2.metric("Max", f"{df_plot['core_temperature'].max():.1f} °C")
    c3.metric("Drift", f"{drift.get('drift_c_per_hour', 0):.2f} °C/h")
    c4.metric("Status", drift.get("classification", "unknown"))

    # Core temp timeline with zone coloring
    if time_col is not None:
        fig_temp = go.Figure()
        time_min = time_col / 60.0 if time_col.max() > 100 else time_col

        # Zone background bands
        zone_defs = [
            (36.0, 38.0, "rgba(39,174,96,0.15)", "Normal"),
            (38.0, 38.5, "rgba(243,156,18,0.15)", "Elevated"),
            (38.5, 39.0, "rgba(230,126,34,0.2)", "Heat Training"),
            (39.0, 39.5, "rgba(231,76,60,0.2)", "Caution"),
            (39.5, 41.0, "rgba(142,68,173,0.2)", "Danger"),
        ]
        for y0, y1, color, label in zone_defs:
            fig_temp.add_hrect(
                y0=y0,
                y1=y1,
                fillcolor=color,
                line_width=0,
                annotation_text=label,
                annotation_position="top left",
            )

        # Temperature trace
        core_smooth = df_plot["core_temperature"].rolling(30, min_periods=1).mean()
        fig_temp.add_trace(
            go.Scatter(
                x=time_min,
                y=core_smooth,
                name="Core Temp",
                line=dict(color="#E74C3C", width=2),
                hovertemplate="🌡️ Core: %{y:.1f} °C<extra></extra>",
            )
        )

        fig_temp.update_layout(
            template="plotly_dark",
            height=280,
            xaxis_title="Czas [min]",
            yaxis_title="Core Temperature [°C]",
            yaxis_range=[36.5, min(40.0, df_plot["core_temperature"].max() + 0.5)],
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_temp, use_container_width=True)

    # Zones time breakdown
    zone_labels = list(zones_time.keys())
    zone_mins = [float(v) / 60.0 for v in zones_time.values()]
    if any(v > 0 for v in zone_mins):
        fig_zones = go.Figure(
            data=[
                go.Bar(
                    x=zone_labels,
                    y=zone_mins,
                    marker_color=["#27AE60", "#F39C12", "#E67E22", "#E74C3C", "#8E44AD"],
                    text=[f"{v:.1f}" for v in zone_mins],
                    textposition="auto",
                )
            ]
        )
        fig_zones.update_layout(
            template="plotly_dark",
            height=200,
            yaxis_title="Czas [min]",
            margin=dict(l=20, r=20, t=10, b=20),
        )
        st.plotly_chart(fig_zones, use_container_width=True)

    st.caption(f"Interpretacja: {drift.get('interpretation', '')}")
    st.markdown("---")


def _render_running_effectiveness_section(df_plot, rider_weight):
    """Section 12: Running Effectiveness, GCT Asymmetry, Leg Spring Stiffness."""
    st.subheader("1️⃣2️⃣ Efektywnosc Biegu i Biomechanika")

    has_any = False

    # Running Effectiveness (needs power + speed)
    if "watts" in df_plot.columns and (
        "velocity_smooth" in df_plot.columns or "pace" in df_plot.columns
    ):
        has_any = True
        speed_col = "velocity_smooth" if "velocity_smooth" in df_plot.columns else None
        if speed_col:
            avg_speed = df_plot[speed_col].mean()
        else:
            pace_valid = df_plot["pace"].replace(0, np.nan).dropna()
            avg_speed = (1000.0 / pace_valid).mean() if len(pace_valid) > 0 else 0

        avg_power = df_plot["watts"].mean()
        re = calculate_running_effectiveness(avg_speed, avg_power, rider_weight)

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Running Effectiveness",
            f"{re:.3f}" if re > 0 else "--",
            help="RE = speed (m/s) / specific power (W/kg). Higher = more efficient.",
        )
        c2.metric("AVG Speed", f"{avg_speed:.2f} m/s")
        c3.metric("AVG Power", f"{avg_power:.0f} W ({avg_power / rider_weight:.1f} W/kg)")

    # GCT Asymmetry
    if "stance_time_balance" in df_plot.columns:
        has_any = True
        asym = calculate_gct_asymmetry_index(df_plot["stance_time_balance"])

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "GCT Balance",
            f"{asym['mean_balance']:.1f}%",
            help="50% = perfect symmetry",
        )
        c2.metric(
            "Asymmetry",
            f"{asym['asymmetry_pct']:.1f}%",
            delta=asym["classification"],
            delta_color="off",
        )
        c3.metric(
            "Est. Metabolic Cost",
            f"+{asym['metabolic_cost_pct']:.1f}%",
            help="Szacowany dodatkowy koszt metaboliczny z asymetrii (Seminati 2020)",
        )

    # Leg Spring Stiffness
    if "stance_time" in df_plot.columns and "verticaloscillation" in df_plot.columns:
        has_any = True
        gct_mean = df_plot["stance_time"].mean()
        vo_mean = df_plot["verticaloscillation"].mean()
        lss = calculate_leg_spring_stiffness(gct_mean, vo_mean, rider_weight)

        c1, c2 = st.columns(2)
        c1.metric(
            "Vertical Stiffness (kvert)",
            f"{lss['kvert_kn_m']:.1f} kN/m",
            delta=lss["classification"],
            delta_color="off",
        )
        c2.metric("GCT / VO", f"{gct_mean:.0f} ms / {vo_mean:.1f} cm")

    if not has_any:
        st.info("Brak danych biomechy (moc, stance_time, balance).")
