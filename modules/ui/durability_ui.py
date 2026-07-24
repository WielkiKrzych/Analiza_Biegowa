"""
Durability / Fatigue Resistance tab (running).

Durability = the ability to hold pace as fatigue accumulates. Computed from the
``pace`` column (seconds/km) when available: DI = pace_first_half / pace_second_half
* 100, so holding or improving pace late in the run gives DI >= 100. Falls back to
running power (``watts``) when pace is absent.
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def _pace_durability(df: pd.DataFrame) -> tuple:
    """Return (DI%, first_half_pace, second_half_pace) from the pace column."""
    pace = pd.to_numeric(df["pace"], errors="coerce")
    pace = pace[(pace >= 120) & (pace <= 1200)]  # 2:00–20:00 min/km moving samples
    if len(pace) < 120:
        return None, None, None
    mid = len(pace) // 2
    first = pace.iloc[:mid].mean()
    second = pace.iloc[mid:].mean()
    if not first or second <= 0:
        return None, None, None
    di = (first / second) * 100.0  # lower pace (faster) 2nd half => DI > 100
    return round(di, 1), round(first, 0), round(second, 0)


def _interpret(di: float) -> str:
    if di is None:
        return "❓ Brak danych"
    if di >= 100:
        return "🟢 Wybitna wytrzymałość — tempo utrzymane lub przyspieszone w 2. połowie"
    if di >= 97:
        return "🟢 Bardzo dobra wytrzymałość (spadek <3%)"
    if di >= 94:
        return "🟡 Dobra wytrzymałość (spadek 3–6%)"
    if di >= 90:
        return "🟠 Średnia wytrzymałość (spadek 6–10%) — dołóż długich wybiegań"
    return "🔴 Niska wytrzymałość (spadek >10%) — priorytet baza tlenowa i długie biegi"


def _fmt_pace(sec_per_km: float) -> str:
    if not sec_per_km or sec_per_km <= 0:
        return "—"
    m = int(sec_per_km // 60)
    s = int(round(sec_per_km - m * 60))
    if s == 60:
        m, s = m + 1, 0
    return f"{m}:{s:02d} min/km"


def render_durability_tab(
    df: Optional[pd.DataFrame] = None,
    df_resampled: Optional[pd.DataFrame] = None,
    metrics: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> None:
    """Render the running Durability / Fatigue Resistance tab."""
    st.header("🛡️ Wytrzymałość i Odporność na Zmęczenie")
    st.markdown(
        "Analiza zdolności do utrzymania **tempa** mimo narastającego zmęczenia. "
        "Kluczowa dla biegów długodystansowych — często lepiej przewiduje wynik niż samo "
        "tempo progowe."
    )

    if df is None or df.empty:
        st.info("Brak danych. Wgraj plik treningowy.")
        return

    use_pace = "pace" in df.columns
    if use_pace:
        di, first, second = _pace_durability(df)
        unit_fmt = _fmt_pace
        first_label, second_label = "Śr. tempo (1. połowa)", "Śr. tempo (2. połowa)"
    else:
        from modules.calculations.stamina import calculate_durability_index

        di, first, second = calculate_durability_index(df, min_duration_min=20)
        unit_fmt = lambda w: f"{w:.0f} W" if w else "—"  # noqa: E731
        first_label, second_label = "Śr. moc (1. połowa)", "Śr. moc (2. połowa)"

    if di is None:
        st.info("Potrzeba minimum ~20 minut ciągłego biegu, aby policzyć Indeks Wytrzymałości.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            "Indeks Wytrzymałości",
            f"{di:.1f}%",
            delta=f"{di - 100:.1f}%",
            delta_color="normal" if di >= 97 else "inverse",
            help="≥100% = tempo utrzymane/przyspieszone w 2. połowie",
        )
    c2.metric(first_label, unit_fmt(first))
    c3.metric(second_label, unit_fmt(second))
    with c4:
        loss = max(0.0, 100 - di)
        st.metric("Spadek", f"{loss:.1f}%", delta_color="inverse" if loss > 6 else "normal")

    st.info(f"**Interpretacja:** {_interpret(di)}")

    # Durability over time (rolling, pace-based)
    if use_pace:
        _render_pace_durability_curve(df)

    with st.expander("📖 Teoria wytrzymałości biegowej", expanded=False):
        st.markdown(
            """
        **Durability** to zdolność do minimalizowania spadku tempa mimo akumulacji zmęczenia
        (peryferyjnego, centralnego, termoregulacyjnego i deplecji glikogenu).

        **DI = (tempo_1.połowa / tempo_2.połowa) × 100** — wartość ≥100% oznacza, że tempo
        w drugiej połowie było równe lub szybsze niż w pierwszej.

        Normy (2020–2026):
        - **≥100%**: elita / negative split
        - **97–100%**: bardzo dobra
        - **94–97%**: dobra
        - **90–94%**: średnia
        - **<90%**: wymaga bazy tlenowej i długich wybiegań

        Trening: długie wybiegania w Z2, bloki „fatigue-resistance" (tempo pod koniec długiego
        biegu), fueling węglowodanowy > 60 g/h dla utrzymania mocy.
        """
        )


def _render_pace_durability_curve(df: pd.DataFrame) -> None:
    """Rolling durability index across the run using 5-minute windows."""
    if "time" not in df.columns and "time_min" not in df.columns:
        return
    pace = pd.to_numeric(df["pace"], errors="coerce")
    valid = (pace >= 120) & (pace <= 1200)
    if valid.sum() < 600:  # need ~10 min
        return

    baseline = pace[valid].iloc[: max(1, valid.sum() // 5)].mean()
    if not baseline or baseline <= 0:
        return

    win = 300  # 5 min at 1 Hz
    rolled = pace.where(valid).rolling(win, min_periods=win // 2).mean()
    di_series = (baseline / rolled) * 100.0

    x = (df["time_min"] if "time_min" in df.columns else df["time"] / 60.0).values
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=di_series.values,
            mode="lines",
            name="DI (krocząca)",
            line=dict(color="#FF9800", width=2),
            hovertemplate="Czas: %{x:.0f} min<br>DI: %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_hline(y=100, line_dash="dash", line_color="green", annotation_text="100% (utrzymane)")
    fig.add_hline(y=94, line_dash="dot", line_color="orange", annotation_text="94%")
    fig.update_layout(
        template="plotly_dark",
        title="Krocząca wytrzymałość (DI) w czasie biegu",
        xaxis_title="Czas [min]",
        yaxis_title="Indeks Wytrzymałości [%]",
        height=380,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    valid_di = di_series[np.isfinite(di_series)]
    if len(valid_di) > 0:
        s1, s2, s3 = st.columns(3)
        s1.metric("Śr. DI", f"{valid_di.mean():.1f}%")
        s2.metric("Min DI", f"{valid_di.min():.1f}%")
        s3.metric("Odch. std.", f"{valid_di.std():.1f}%")
