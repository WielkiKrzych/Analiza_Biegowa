"""
Training Load UI - Performance Management Chart (PMC).
Visualizes fitness (CTL), fatigue (ATL), and form (TSB).
"""

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from modules.training_load import TrainingLoadManager


def render_training_load_tab():
    """Render the Training Load / PMC tab."""
    st.header("📊 Training Load (PMC)")

    manager = TrainingLoadManager()
    session_count = manager.store.get_session_count()

    if session_count == 0:
        st.info("""
        **Brak danych historycznych.**

        Wgraj pliki treningowe aby rozpocząć śledzenie obciążenia.
        System automatycznie zapisuje każdą sesję do bazy danych.
        """)
        return

    # Time range selector
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        days = st.selectbox(
            "Zakres czasowy",
            options=[30, 60, 90, 180, 365],
            index=2,  # Default 90 days
            format_func=lambda x: f"{x} dni",
        )

    # Calculate training load
    history = manager.calculate_load(days=days)

    if not history:
        st.warning("Za mało danych do obliczenia obciążenia treningowego.")
        return

    # Current form display
    current = history[-1]

    with col2:
        st.metric(
            "Aktualna Forma (TSB)",
            f"{current.tsb:.0f}",
            delta=current.form_status,
            delta_color="off",
        )

    with col3:
        # Recommended TSS for today
        min_tss, max_tss = manager.get_recommended_tss()
        st.info(f"🎯 **Zalecany TSS dziś:** {min_tss:.0f} - {max_tss:.0f}")

    # Key metrics row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "CTL (Fitness)", f"{current.ctl:.0f}", help="Chronic Training Load - Twoja baza fitness"
    )
    m2.metric(
        "ATL (Zmęczenie)", f"{current.atl:.0f}", help="Acute Training Load - Aktualne zmęczenie"
    )
    m3.metric("TSB (Forma)", f"{current.tsb:.0f}", help="Training Stress Balance = CTL - ATL")

    ramp_rate = manager.calculate_ramp_rate()
    ramp_color = "normal" if 3 <= ramp_rate <= 7 else ("inverse" if ramp_rate > 10 else "off")
    m4.metric(
        "Ramp Rate",
        f"{ramp_rate:.1f}%/tydzień",
        delta="Optymalne 3-7%" if 3 <= ramp_rate <= 7 else "⚠️ Sprawdź" if ramp_rate > 10 else None,
        delta_color=ramp_color,
    )

    st.divider()

    # PMC Chart
    st.subheader("Performance Management Chart")

    # Convert to DataFrame for plotting
    df = pd.DataFrame(
        [{"date": h.date, "tss": h.tss, "atl": h.atl, "ctl": h.ctl, "tsb": h.tsb} for h in history]
    )
    df["date"] = pd.to_datetime(df["date"])

    # Create dual-axis chart
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # TSS bars
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["tss"],
            name="TSS",
            marker_color="rgba(100, 100, 100, 0.5)",
            hovertemplate="TSS: %{y:.0f}<extra></extra>",
        ),
        secondary_y=False,
    )

    # CTL (Fitness) line
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["ctl"],
            name="CTL (Fitness)",
            line=dict(color="#00cc96", width=3),
            hovertemplate="CTL: %{y:.1f}<extra></extra>",
        ),
        secondary_y=False,
    )

    # ATL (Fatigue) line
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["atl"],
            name="ATL (Zmęczenie)",
            line=dict(color="#ef553b", width=2, dash="dot"),
            hovertemplate="ATL: %{y:.1f}<extra></extra>",
        ),
        secondary_y=False,
    )

    # TSB (Form) area on secondary axis
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["tsb"],
            name="TSB (Forma)",
            fill="tozeroy",
            line=dict(color="#636efa", width=2),
            fillcolor="rgba(99, 110, 250, 0.3)",
            hovertemplate="TSB: %{y:.1f}<extra></extra>",
        ),
        secondary_y=True,
    )

    # Add zero line for TSB
    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3, secondary_y=True)

    # Form zones
    fig.add_hrect(
        y0=5,
        y1=25,
        fillcolor="green",
        opacity=0.1,
        line_width=0,
        annotation_text="Peak Zone",
        secondary_y=True,
    )
    fig.add_hrect(
        y0=-30,
        y1=-10,
        fillcolor="red",
        opacity=0.1,
        line_width=0,
        annotation_text="Risk Zone",
        secondary_y=True,
    )

    fig.update_layout(
        template="plotly_dark",
        height=450,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
        yaxis_title="TSS / CTL / ATL",
        yaxis2_title="TSB (Forma)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Training Planner
    st.divider()
    st.subheader("🗓️ Planowanie Tygodnia")

    with st.expander("Symuluj wpływ planowanego treningu", expanded=False):
        st.write("Wprowadź planowane TSS na kolejne dni:")

        cols = st.columns(7)
        planned_tss = []
        day_names = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Ndz"]
        today_idx = datetime.now().weekday()

        for i, col in enumerate(cols):
            day_idx = (today_idx + i + 1) % 7
            with col:
                tss = st.number_input(
                    day_names[day_idx],
                    min_value=0,
                    max_value=500,
                    value=50 if i < 5 else 100,
                    key=f"planned_tss_{i}",
                )
                planned_tss.append(tss)

        if st.button("🔮 Przewiduj formę"):
            predictions = manager.predict_future_form(planned_tss)

            if predictions:
                pred_df = pd.DataFrame(
                    [{"date": p.date, "tsb": p.tsb, "status": p.form_status} for p in predictions]
                )

                st.write("**Przewidywana forma:**")
                for _, row in pred_df.iterrows():
                    st.write(f"📅 {row['date']}: TSB = {row['tsb']:.0f} → {row['status']}")

    # Sessions history
    st.divider()
    st.subheader("📋 Historia Sesji")

    sessions = manager.store.get_sessions(days=days)
    if sessions:
        session_df = pd.DataFrame(
            [
                {
                    "Data": s.date,
                    "Plik": s.filename[:30] + "..." if len(s.filename) > 30 else s.filename,
                    "Czas (min)": s.duration_sec // 60,
                    "TSS": f"{s.tss:.0f}",
                    "NP": f"{s.np:.0f} W",
                    "Avg HR": f"{s.avg_hr:.0f} bpm",
                }
                for s in sessions[:20]  # Limit to 20 most recent
            ]
        )
        st.dataframe(session_df, use_container_width=True, hide_index=True)
    else:
        st.info("Brak zapisanych sesji w wybranym okresie.")
