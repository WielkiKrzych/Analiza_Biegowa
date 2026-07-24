"""Banister Performance Prediction UI tab (running, RSS-driven).

Ported from the cycling analyzer and adapted for running: training load is
Running Stress Score (RSS), rendered with native Streamlit charts (no shared
UI helpers required).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from modules.calculations.banister import (
    BanisterModel,
    default_banister_model,
    optimize_peaking,
    predict_performance,
)
from modules.db import SessionStore


def render_banister_tab(*args, **kwargs) -> None:
    st.subheader("🎯 Banister — Prognoza Wyników")
    st.caption("Model impuls-odpowiedź Banistera do prognozowania formy i planowania taperu")

    store = SessionStore()

    _render_model_params()
    _render_prediction_chart(store)
    _render_peaking_calculator(store)
    _render_theory()


def _render_model_params() -> None:
    with st.expander("⚙️ Parametry modelu", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            k1 = st.slider("k1 (współczynnik fitness)", 0.1, 3.0, 1.0, 0.1, key="ban_k1")
            tau1 = st.slider("τ1 — fitness decay (dni)", 14, 60, 42, 1, key="ban_tau1")
        with col2:
            k2 = st.slider("k2 (współczynnik zmęczenia)", 0.1, 5.0, 2.0, 0.1, key="ban_k2")
            tau2 = st.slider("τ2 — fatigue decay (dni)", 3, 21, 7, 1, key="ban_tau2")

        st.session_state["banister_model"] = BanisterModel(k1=k1, k2=k2, tau1=tau1, tau2=tau2)


def _get_model() -> BanisterModel:
    return st.session_state.get("banister_model", default_banister_model())


def _get_rss_history(store) -> list:
    records = store.get_sessions(days=60)
    if not records:
        return []

    rss_by_date: dict = {}
    for r in records:
        date_str = r.date if isinstance(r.date, str) else r.date.strftime("%Y-%m-%d")
        rss = getattr(r, "tss", 0) or 0
        rss_by_date[date_str] = rss_by_date.get(date_str, 0) + rss

    today = datetime.now().date()
    start = today - timedelta(days=59)
    rss_list = []
    for i in range(60):
        d = start + timedelta(days=i)
        rss_list.append(rss_by_date.get(d.strftime("%Y-%m-%d"), 0.0))

    return rss_list


def _render_prediction_chart(store) -> None:
    st.markdown("### 📈 Prognoza wydajności")

    rss_history = _get_rss_history(store)
    if not rss_history:
        st.info("ℹ️ Brak danych treningowych. Wgraj sesje, aby zobaczyć prognozę.")
        return

    days_ahead = st.slider("Dni prognozy", 7, 28, 14, key="ban_days_ahead")
    model = _get_model()

    planned = _get_planned_rss(days_ahead)
    full_rss = rss_history + planned

    preds = predict_performance(model, full_rss, days_ahead=0)
    future_preds = predict_performance(model, full_rss, days_ahead=days_ahead)

    all_preds = preds + future_preds[len(preds) :]

    dates = [p.date for p in all_preds]
    perf = [p.predicted_performance for p in all_preds]
    ctl = [p.ctl for p in all_preds]

    hist_end = len(rss_history)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates[:hist_end],
            y=perf[:hist_end],
            name="Wydajność (historia)",
            line=dict(color="#3498db", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates[hist_end - 1 :],
            y=perf[hist_end - 1 :],
            name="Wydajność (prognoza)",
            line=dict(color="#e74c3c", width=2, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=ctl,
            name="CTL (fitness)",
            line=dict(color="#2ecc71", width=1.5),
            opacity=0.6,
        )
    )

    fig.update_layout(
        template="plotly_dark",
        title="Banister — Prognoza wydajności",
        xaxis_title="Data",
        yaxis_title="Wydajność (a.u.)",
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)


def _get_planned_rss(days: int) -> list:
    cols = st.columns(min(days, 7))
    planned = []
    today = datetime.now().date()

    for i in range(days):
        if i < 7:
            with cols[i]:
                val = st.number_input(
                    (today + timedelta(days=i + 1)).strftime("%m/%d"),
                    min_value=0,
                    max_value=400,
                    value=0,
                    key=f"ban_plan_{i}",
                )
                planned.append(float(val))
        else:
            planned.append(0.0)

    return planned


def _render_peaking_calculator(store) -> None:
    st.markdown("### 🏔️ Kalkulator taperu (peaking)")

    from modules.calculations.pmc import get_current_pmc_summary

    summary = get_current_pmc_summary(store)
    if not summary:
        st.info("Brak danych PMC. Wgraj sesje treningowe.")
        return

    col1, col2 = st.columns(2)
    with col1:
        race_date = st.date_input("Data zawodów", key="ban_race_date")
    with col2:
        taper_weeks = st.slider("Tygodnie taperu", 1, 4, 2, key="ban_taper_weeks")

    if race_date is None:
        return

    days_out = taper_weeks * 7
    recs = optimize_peaking(
        current_ctl=summary["ctl"],
        current_atl=summary["atl"],
        target_date=datetime.combine(race_date, datetime.min.time()),
        days_out=days_out,
    )

    dates = [r.date for r in recs]
    rss_vals = [r.recommended_tss for r in recs]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=dates,
            y=rss_vals,
            name="Rekomendowany RSS",
            marker_color="#e74c3c",
            opacity=0.7,
        )
    )
    fig.add_hline(
        y=summary["ctl"],
        line_dash="dash",
        line_color="#3498db",
        annotation_text=f"CTL = {summary['ctl']:.0f}",
    )

    fig.update_layout(
        template="plotly_dark",
        title="Plan taperu — rekomendowany RSS",
        xaxis_title="Data",
        yaxis_title="RSS",
        height=350,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Szczegóły taperu"):
        for r in recs:
            st.markdown(f"**{r.date}** — RSS: {r.recommended_tss:.0f} | {r.notes}")


def _render_theory() -> None:
    with st.expander("📖 Teoria — Model Banistera"):
        st.markdown(
            """
        **Model impuls-odpowiedź Banistera** (1975) opisuje relację między treningiem a wydajnością:

        - **Fitness(n)** = k₁ × Σ RSS(i) × exp(−(n−i)/τ₁)
        - **Fatigue(n)** = k₂ × Σ RSS(i) × exp(−(n−i)/τ₂)
        - **Performance** = P₀ + Fitness − Fatigue

        | Parametr | Domyślny | Znaczenie |
        |----------|----------|-----------|
        | k₁ | 1.0 | Wpływ treningu na fitness |
        | k₂ | 2.0 | Wpływ treningu na zmęczenie |
        | τ₁ | 42 dni | Decay fitness (analogia CTL) |
        | τ₂ | 7 dni | Decay zmęczenia (analogia ATL) |

        **Taper** (Mujika & Padilla 2003): redukcja objętości 40-60% przy utrzymaniu intensywności.
        """
        )
