"""Aerobic efficiency based on running speed and heart rate."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.durability import calculate_aerobic_decoupling, detect_decoupling_onset


def render_aerobic_efficiency_tab(df: pd.DataFrame) -> None:
    st.header("Efektywność tlenowa")
    if "heartrate" not in df:
        st.info("Potrzebne są jednoczesne pomiary tempa i tętna.")
        return

    result = calculate_aerobic_decoupling(df["pace"], df["heartrate"])
    if not np.isfinite(result["decoupling_pct"]):
        st.info("Za mało próbek ruchu i tętna do obliczenia Pa:HR.")
        return

    onset = detect_decoupling_onset(df["pace"], df["heartrate"])
    onset_sec = onset["onset_time_sec"]
    columns = st.columns(2)
    columns[0].metric("Dryf Pa:HR", f"{result['decoupling_pct']:.1f}%")
    columns[1].metric(
        "Początek dryfu", f"{onset_sec / 60:.1f} min" if onset_sec is not None else "brak"
    )

    efficiency = onset["ef_series"].dropna()
    if not efficiency.empty:
        fig = go.Figure(
            go.Scatter(x=df.loc[efficiency.index, "time_min"], y=efficiency, name="Prędkość / HR")
        )
        if onset_sec is not None:
            fig.add_vline(x=onset_sec / 60, line_dash="dash")
        fig.update_layout(xaxis_title="Czas [min]", yaxis_title="Prędkość / HR [m/s/bpm]")
        st.plotly_chart(fig, use_container_width=True)
