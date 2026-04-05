import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from modules.calculations.pace_utils import format_pace, pace_to_speed, speed_to_pace


def _compute_best_efforts(
    pace_data: pd.Series, valid_durations: list[int]
) -> tuple[list[float], list[float]]:
    """Compute best average speed and cumulative distance for each duration window."""
    speed_values: list[float] = []
    distance_values: list[float] = []

    for d in valid_durations:
        rolling_pace = pace_data.rolling(window=d).mean()
        best_pace = rolling_pace.min()

        if not pd.isna(best_pace) and best_pace > 0:
            avg_speed = pace_to_speed(best_pace)
            speed_values.append(avg_speed)
            distance_values.append(avg_speed * d)

    return speed_values, distance_values


def _compute_theory_curve(
    modeled_cs: float, modeled_d_prime: float
) -> tuple[np.ndarray, list[float]]:
    """Compute theoretical pace-duration curve from CS model parameters."""
    x_theory = np.arange(60, 1800, 60)
    y_theory_pace: list[float] = []

    for t in x_theory:
        if t > 0:
            speed_theory = modeled_cs + (modeled_d_prime / t)
            pace_theory = speed_to_pace(speed_theory) if speed_theory > 0 else float("inf")
            y_theory_pace.append(pace_theory)
        else:
            y_theory_pace.append(float("inf"))

    return x_theory, y_theory_pace


def _compute_actual_pdc(pace_data: pd.Series, n_points: int) -> tuple[list[int], list[float]]:
    """Compute actual pace-duration curve from rolling means."""
    x_actual: list[int] = []
    y_actual: list[float] = []
    x_theory = np.arange(60, 1800, 60)

    for t in x_theory:
        if t < n_points:
            val = pace_data.rolling(t).mean().min()
            if pd.notna(val):
                y_actual.append(val)
                x_actual.append(t)

    return x_actual, y_actual


def render_model_tab(df_plot, cp_input, w_prime_input):
    st.header("Matematyczny Model CS (Critical Speed Estimation)")
    st.markdown(
        "Estymacja Twojego CS i D' na podstawie krzywej tempa (PDC) z tego treningu. Używamy modelu liniowego: `Dystans = CS * t + D'`."
    )

    durations = [180, 300, 600, 900, 1200]
    valid_durations = [d for d in durations if d < len(df_plot)]

    if len(valid_durations) < 3:
        st.warning(
            "Trening jest zbyt krótki, by zbudować wiarygodny model CS (wymagane wysiłki > 3 min)."
        )
        return

    pace_data = df_plot["pace"].ffill().bfill()
    speed_values, distance_values = _compute_best_efforts(pace_data, valid_durations)

    if len(speed_values) < 3:
        st.warning(
            "Za mało punktów do wiarygodnej regresji. Wymagane min. 3 różne długości odcinków."
        )
        return

    slope, intercept, r_value, _p_value, _std_err = stats.linregress(
        valid_durations[: len(distance_values)], distance_values
    )

    modeled_cs = slope
    modeled_d_prime = intercept
    r_squared = r_value**2
    cs_pace = speed_to_pace(modeled_cs)

    c_res1, c_res2, c_res3 = st.columns(3)

    c_res1.metric(
        "Estymowane CS (z pliku)",
        format_pace(cs_pace) + " /km",
        help="Prędkość Krytyczna wyliczona z Twoich najszybszych odcinków w tym pliku.",
    )

    c_res2.metric(
        "Estymowane D'",
        f"{modeled_d_prime:.0f} m",
        help="Pojemność beztlenowa (dystans nad CS) wyliczona z modelu.",
    )

    c_res3.metric(
        "Jakość Dopasowania (R²)",
        f"{r_squared:.4f}",
        delta_color="normal" if r_squared > 0.98 else "inverse",
        help="Jak bardzo Twoje wyniki pasują do teoretycznej krzywej. >0.98 = Bardzo wiarygodne.",
    )

    st.markdown("---")

    x_theory, y_theory_pace = _compute_theory_curve(modeled_cs, modeled_d_prime)
    x_actual, y_actual = _compute_actual_pdc(pace_data, len(df_plot))

    fig_model = go.Figure()

    fig_model.add_trace(
        go.Scatter(
            x=np.array(x_actual) / 60,
            y=y_actual,
            mode="markers",
            name="PDC (Plik)",
            marker=dict(color="#00cc96", size=8),
            hovertemplate="%{y:.0f} s/km",
        )
    )

    fig_model.add_trace(
        go.Scatter(
            x=x_theory / 60,
            y=y_theory_pace,
            mode="lines",
            name=f"Model: {format_pace(cs_pace)}/km",
            line=dict(color="#ef553b", dash="dash"),
            hovertemplate="%{y:.0f} s/km",
        )
    )

    fig_model.update_layout(
        template="plotly_dark",
        title="Pace Duration Curve: Rzeczywistość vs Model",
        xaxis_title="Czas trwania [mm:ss]",
        yaxis_title="Tempo [s/km]",
        yaxis=dict(autorange="reversed"),
        hovermode="x unified",
        height=500,
    )
    st.plotly_chart(fig_model, use_container_width=True)

    st.info("""
    **📊 Interpretacja Modelu:**

    Ten algorytm próbuje dopasować Twoje wysiłki do fizjologicznego prawa prędkości krytycznej.

    * **CS (Critical Speed):** To tempo, które teoretycznie możesz utrzymać bardzo długo. Wyświetlane jako min:sec/km.
    * **D' (D-prime):** To dodatkowy dystans (w metrach), który możesz przebiec powyżej CS, zanim się zmęczysz.
    * **R² (R-kwadrat):** Jeśli jest niskie (< 0.95), oznacza to, że Twój bieg był nieregularny i model nie może znaleźć jednej linii pasującej do wyników.
    """)
