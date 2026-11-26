"""Carbohydrate use and intake during a run."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_nutrition_tab(df: pd.DataFrame, threshold_pace: float, weight: float) -> None:
    st.header("Żywienie w biegu")
    st.caption("Symulacja kosztu biegu i bilansu węglowodanów na podstawie tempa i masy.")
    left, right = st.columns(2)
    intake = left.number_input("Spożycie węglowodanów [g/h]", 0, 200, 60)
    glycogen = right.number_input("Początkowe zapasy glikogenu [g]", 0, 1000, 400)

    pace = df["pace"].where(df["pace"].gt(0))
    speed = (3600 / pace).fillna(0)
    intensity = (threshold_pace / pace).fillna(0)
    fraction = np.interp(intensity, [0.6, 0.8, 1.0, 1.3], [0.50, 0.65, 0.80, 0.95])
    burn_rate = weight * speed * 1.05 * fraction / 4
    burned = burn_rate.cumsum() / 3600
    supplied = df["time"] * intake / 3600
    remaining = glycogen + supplied - burned

    columns = st.columns(3)
    columns[0].metric("Szacowane zużycie", f"{burned.iloc[-1]:.0f} g")
    columns[1].metric("Spożycie", f"{supplied.iloc[-1]:.0f} g")
    columns[2].metric("Bilans końcowy", f"{remaining.iloc[-1]:.0f} g")

    fig = go.Figure()
    fig.add_scatter(x=df["time_min"], y=burned, name="Zużyte")
    fig.add_scatter(x=df["time_min"], y=supplied, name="Spożyte")
    fig.add_scatter(x=df["time_min"], y=remaining, name="Bilans glikogenu")
    fig.update_layout(xaxis_title="Czas [min]", yaxis_title="Węglowodany [g]")
    st.plotly_chart(fig, use_container_width=True)
