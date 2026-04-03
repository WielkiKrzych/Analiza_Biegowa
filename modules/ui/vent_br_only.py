"""Ventilation BR-only analysis — when VE data is absent but BR exists."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def _render_br_only_section(target_df):
    """Render BR-only analysis when VE data is absent but BR exists.

    Returns True if this section was rendered (caller should return early).
    Returns False if caller should continue with full VE analysis.
    """
    has_ve = "tymeventilation" in target_df.columns
    has_br = "tymebreathrate" in target_df.columns

    if has_ve or not has_br:
        return False

    from modules.calculations.br_analysis import calculate_br_zones_time, detect_vt_from_br

    target_df = target_df.copy()
    br_series = target_df["tymebreathrate"].dropna()

    st.subheader("🫁 Analiza Częstości Oddechów (BR)")
    st.caption(
        "Dane z zegarka (Garmin/COROS). Brak pełnej wentylacji (VE) — analiza oparta wyłącznie na BR."
    )

    if len(br_series) > 60:
        col_b1, col_b2, col_b3 = st.columns(3)
        col_b1.metric("Śr. BR", f"{br_series.mean():.0f} oddechów/min")
        col_b2.metric("Max BR", f"{br_series.max():.0f} oddechów/min")
        col_b3.metric("Min BR", f"{br_series.min():.0f} oddechów/min")

        # BR zones
        zones_time = calculate_br_zones_time(br_series)
        total_sec = sum(zones_time.values())
        if total_sec > 0:
            zone_names = list(zones_time.keys())
            zone_pcts = [zones_time[z] / total_sec * 100 for z in zone_names]
            zone_colors = ["#2ecc71", "#3498db", "#f1c40f", "#e67e22", "#e74c3c"]

            fig_brz = go.Figure(
                data=[
                    go.Bar(
                        x=zone_pcts,
                        y=zone_names,
                        orientation="h",
                        marker_color=zone_colors[: len(zone_names)],
                        text=[f"{p:.0f}%" for p in zone_pcts],
                        textposition="auto",
                    )
                ]
            )
            fig_brz.update_layout(
                template="plotly_dark",
                title="Czas w strefach BR (npj Digital Medicine 2024)",
                xaxis_title="% czasu",
                height=250,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_brz, use_container_width=True)

        # VT detection from BR
        vt_result = detect_vt_from_br(br_series)
        if vt_result.get("vt1_index") is not None:
            col_vt1, col_vt2 = st.columns(2)
            vt1_time = vt_result["vt1_index"]
            col_vt1.metric(
                "VT1 (z BR)",
                f"{vt1_time // 60}:{vt1_time % 60:02d}",
                help="Próg wentylacyjny 1 wykryty z punktu załamania BR",
            )
            if vt_result.get("vt2_index") is not None:
                vt2_time = vt_result["vt2_index"]
                col_vt2.metric(
                    "VT2 (z BR)",
                    f"{vt2_time // 60}:{vt2_time % 60:02d}",
                    help="Próg wentylacyjny 2 wykryty z drugiego punktu załamania BR",
                )
            else:
                col_vt2.metric("VT2 (z BR)", "Nie wykryto")

        # BR time series chart
        if "time" in target_df.columns:
            br_smooth = br_series.rolling(window=15, center=True, min_periods=1).median()
            time_min = target_df["time"].iloc[: len(br_smooth)] / 60.0

            fig_br_ts = go.Figure()
            fig_br_ts.add_trace(
                go.Scatter(
                    x=time_min,
                    y=br_smooth.values,
                    name="BR (oddechów/min)",
                    line=dict(color="#3498db", width=2),
                )
            )
            fig_br_ts.update_layout(
                template="plotly_dark",
                title="Częstość oddechów w czasie",
                xaxis_title="Czas [min]",
                yaxis_title="BR [oddechów/min]",
                height=350,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_br_ts, use_container_width=True)
    else:
        st.info("Za mało danych BR do analizy (min. 60 próbek).")

    return True
