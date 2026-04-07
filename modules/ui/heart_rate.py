from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_HR_ALIASES = ("heart_rate", "heart rate", "bpm", "tętno", "heartrate", "heart_rate_bpm")


def _parse_time(t_str: str) -> int | None:
    try:
        parts = list(map(int, t_str.split(":")))
    except (ValueError, TypeError):
        return None
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:
        return parts[0]
    return None


def _format_time(seconds: int | float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _normalize_hr_column(df: pd.DataFrame) -> pd.DataFrame | None:
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    if "hr" in df.columns:
        return df
    for alias in _HR_ALIASES:
        if alias in df.columns:
            df = df.rename(columns={alias: "hr"})
            return df
    return None


def _select_time_range(df: pd.DataFrame) -> pd.DataFrame | None:
    min_time: int | float = df["time"].min()
    max_time: int | float = df["time"].max()

    st.markdown("#### Wybierz zakres analizy")
    c1, c2 = st.columns(2)
    start_str = c1.text_input("Start (hh:mm:ss/mm:ss)", value=_format_time(min_time))
    end_str = c2.text_input("Koniec (hh:mm:ss/mm:ss)", value=_format_time(max_time))

    start_s = _parse_time(start_str)
    end_s = _parse_time(end_str)

    if start_s is None or end_s is None:
        st.error("Nieprawidłowy format czasu. Użyj formatu HH:MM:SS lub MM:SS")
        return None
    if start_s >= end_s:
        st.error("Czas końcowy musi być większy niż startowy.")
        return None

    mask = (df["time"] >= start_s) & (df["time"] <= end_s)
    df_segment = df.loc[mask]

    if df_segment.empty:
        st.info("Brak danych w wybranym zakresie.")
        return None

    duration = end_s - start_s
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    st.caption(f"Analizowany fragment: {minutes} min {seconds} s")
    return df_segment


def _render_hr_metrics(df_segment: pd.DataFrame) -> float:
    avg_hr: float = df_segment["hr"].mean()
    min_hr: float = df_segment["hr"].min()
    max_hr: float = df_segment["hr"].max()

    with st.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Średnie HR", f"{avg_hr:.0f} bpm")
        c2.metric("Min HR", f"{min_hr:.0f} bpm")
        c3.metric("Max HR", f"{max_hr:.0f} bpm")

    st.markdown("---")
    return avg_hr


def _render_hr_chart(df_segment: pd.DataFrame, avg_hr: float) -> None:
    df_segment = df_segment.copy()
    df_segment["hr_smooth"] = df_segment["hr"].rolling(window=10, center=True, min_periods=1).mean()
    df_segment["time_str"] = pd.to_datetime(df_segment["time"], unit="s").dt.strftime("%H:%M:%S")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_segment["time"],
            y=df_segment["hr_smooth"],
            mode="lines",
            name="HR (10s avg)",
            line=dict(color="#d62728", width=2),
            customdata=df_segment["time_str"],
            hovertemplate=(
                "<b>🕐 Czas:</b> %{customdata} (%{x}s)<br><b>❤️ HR (10s):</b> %{y:.1f} bpm<extra></extra>"
            ),
        )
    )
    fig.add_hline(
        y=avg_hr,
        line_dash="dash",
        line_color="white",
        opacity=0.5,
        annotation_text="Avg",
        annotation_position="bottom right",
    )
    fig.update_layout(
        title="Wykres Tętna (HR) - Średnia Krocząca 10s",
        xaxis_title="Czas (s)",
        yaxis_title="Tętno (bpm)",
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_hr_tab(df):
    st.markdown("### ❤️ Analiza Tętna")

    if df is None or df.empty:
        st.error("Brak danych.")
        return

    df_chart = _normalize_hr_column(df)
    if df_chart is None:
        st.warning("⚠️ Brak danych tętna (HR) w wczytanym pliku.")
        with st.expander("Pokaż dostępne kolumny"):
            cols = df.columns.str.lower().str.strip().tolist()
            st.write(cols)
        return

    if "time" not in df_chart.columns:
        df_chart["time"] = np.arange(len(df_chart))

    df_segment = _select_time_range(df_chart)
    if df_segment is None:
        return

    avg_hr = _render_hr_metrics(df_segment)
    _render_hr_chart(df_segment, avg_hr)
