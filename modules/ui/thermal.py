"""Temperature channels and recorded CORE heat strain."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.thermal import (
    HeatStrain,
    calculate_core_temp_zones_time,
    calculate_thermal_drift_rate,
)

_TEMPERATURE_CHANNELS = {
    "core_temperature": "Temperatura centralna",
    "skin_temperature": "Temperatura skóry",
    "ambient_temperature": "Temperatura otoczenia",
}


def _render_core_temperature(df: pd.DataFrame) -> None:
    if "core_temperature" not in df or not df["core_temperature"].notna().any():
        return

    series = df["core_temperature"].dropna()
    zones = calculate_core_temp_zones_time(series)
    st.subheader("Strefy temperatury centralnej")
    figure = go.Figure(go.Bar(x=list(zones.values()), y=list(zones), orientation="h"))
    figure.update_layout(xaxis_title="Czas [s]")
    st.plotly_chart(figure, use_container_width=True)

    drift = calculate_thermal_drift_rate(series, df.loc[series.index, "time"])
    if drift is not None:
        st.metric("Zmiana temperatury centralnej", f"{drift:+.2f} °C/h")


def _render_core_hsi(df: pd.DataFrame, hsi: HeatStrain | None) -> None:
    st.subheader("Heat Strain Index z CORE")
    if hsi is None:
        st.info("Brak poprawnych pomiarów HSI z CORE.")
        return

    figure = go.Figure(
        go.Scatter(
            x=df["time_min"],
            y=df["heat_strain_index"],
            name="HSI z CORE",
            mode="lines+markers",
            connectgaps=False,
            marker={"size": 3},
        )
    )
    figure.update_layout(xaxis_title="Czas [min]", yaxis=dict(title="HSI", range=[0, 10]))
    st.plotly_chart(figure, use_container_width=True)
    peak, mean = st.columns(2)
    peak.metric("Maksimum HSI", f"{hsi['peak']:.1f}")
    mean.metric(
        "Średni HSI ważony czasem", f"{hsi['mean']:.1f}" if hsi["mean"] is not None else "brak"
    )

    durations = hsi["zone_seconds"]
    if sum(durations.values()) > 0:
        st.table(
            pd.DataFrame(
                {
                    "Strefa HSI": list(durations),
                    "Czas [s]": [round(value, 1) for value in durations.values()],
                }
            )
        )


def render_thermal_tab(df: pd.DataFrame, hsi: HeatStrain | None) -> None:
    st.header("Temperatura i obciążenie cieplne")
    figure = go.Figure()
    for name, label in _TEMPERATURE_CHANNELS.items():
        if name in df and df[name].notna().any():
            figure.add_scatter(x=df["time_min"], y=df[name], name=label, mode="lines")
    if figure.data:
        figure.update_layout(xaxis_title="Czas [min]", yaxis_title="Temperatura [°C]")
        st.plotly_chart(figure, use_container_width=True)
    _render_core_temperature(df)
    _render_core_hsi(df, hsi)
