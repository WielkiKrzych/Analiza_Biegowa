"""Critical Speed and D′ from the running pace duration curve."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.pace import calculate_pace_duration_curve, fit_critical_speed_from_pdc
from modules.calculations.pace_utils import format_pace


def render_model_tab(df: pd.DataFrame) -> None:
    st.header("Prędkość krytyczna i D′")
    st.caption("Dopasowanie modelu dystans = CS × czas + D′ do najlepszych odcinków biegu.")

    fit = fit_critical_speed_from_pdc(df)
    if not fit["is_valid"]:
        st.info("Za mało wiarygodnych odcinków, by oszacować CS i D′.")
        return

    columns = st.columns(3)
    columns[0].metric("Tempo przy CS", f"{format_pace(fit['cs_pace_s_km'])} /km")
    columns[1].metric("D′", f"{fit['d_prime_m']:.0f} m")
    columns[2].metric("R²", f"{fit['r_squared']:.3f}")

    curve = calculate_pace_duration_curve(df, durations=list(range(60, 1801, 60)))
    times = [duration for duration, pace in curve.items() if pace is not None]
    figure = go.Figure()
    figure.add_scatter(x=times, y=[curve[t] / 60 for t in times], name="Najlepsze tempo")
    figure.add_scatter(
        x=times,
        y=[1000 / (fit["cs_m_s"] + fit["d_prime_m"] / t) / 60 for t in times],
        name="Model CS i D′",
    )
    figure.update_layout(
        xaxis_title="Długość odcinka [s]", yaxis=dict(title="Tempo [min/km]", autorange="reversed")
    )
    st.plotly_chart(figure, width="stretch")
