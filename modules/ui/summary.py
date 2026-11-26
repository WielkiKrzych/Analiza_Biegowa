"""Overview of a single run."""

import pandas as pd
import streamlit as st

from modules.calculations.pace_utils import format_pace

from .summary_timeline import _build_training_timeline_chart


def render_summary_tab(df: pd.DataFrame, metrics: dict) -> None:
    st.header("Podsumowanie treningu")
    fig = _build_training_timeline_chart(df)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")

    columns = st.columns(4)
    for column, label, name, formatter in zip(
        columns,
        ("Średnie tempo", "Średnie GAP", "Maksymalne tętno", "Szac. VO2max"),
        ("avg_pace", "avg_gap", "max_hr", "vo2_max_est"),
        (format_pace, format_pace, lambda hr: f"{hr:.0f} bpm", lambda vo2: f"{vo2:.1f}"),
        strict=True,
    ):
        value = metrics.get(name)
        column.metric(label, formatter(value) if value is not None else "brak")
