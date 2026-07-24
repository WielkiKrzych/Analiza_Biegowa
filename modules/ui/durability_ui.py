"""
Durability / Fatigue Resistance tab (running) — dual metric.

Durability = the ability to hold intensity as fatigue accumulates. Computed on
TWO independent variables when available:
  • Pace-based:  DI = pace_first_half / pace_second_half * 100  (faster 2nd half => >100)
  • Power-based: DI = watts_second_half / watts_first_half * 100 (higher 2nd half => >100)
Whatever is present is shown; when both pace and running power exist, both are
rendered side by side so fatigue can be read from tempo AND power independently.
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------


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


def _power_durability(df: pd.DataFrame) -> tuple:
    """Return (DI%, first_half_watts, second_half_watts) from the watts column."""
    from modules.calculations.stamina import calculate_durability_index

    return calculate_durability_index(df, min_duration_min=20)


def _interpret(di: float) -> str:
    if di is None:
        return "❓ Brak danych"
    if di >= 100:
        return "🟢 Wybitna wytrzymałość — intensywność utrzymana lub wyższa w 2. połowie"
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


def _fmt_watts(w: float) -> str:
    return f"{w:.0f} W" if w else "—"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_durability_tab(
    df: Optional[pd.DataFrame] = None,
    df_resampled: Optional[pd.DataFrame] = None,
    metrics: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> None:
    """Render the running Durability tab on pace AND power in parallel."""
    st.header("🛡️ Wytrzymałość i Odporność na Zmęczenie")
    st.markdown(
        "Analiza zdolności do utrzymania intensywności mimo narastającego zmęczenia — "
        "liczona równolegle **wg tempa** i **wg mocy biegowej**. Kluczowa dla biegów "
        "długodystansowych; często lepiej przewiduje wynik niż samo tempo progowe."
    )

    if df is None or df.empty:
        st.info("Brak danych. Wgraj plik treningowy.")
        return

    has_pace = "pace" in df.columns
    has_power = "watts" in df.columns

    if not has_pace and not has_power:
        st.info("Brak kolumny `pace` i `watts` — nie można policzyć wytrzymałości.")
        return

    if has_pace and has_power:
        tab_pace, tab_power = st.tabs(["⏱️ Wg tempa", "🔋 Wg mocy"])
        with tab_pace:
            _render_pace_section(df)
        with tab_power:
            _render_power_section(df)
    elif has_pace:
        _render_pace_section(df)
        st.caption("ℹ️ Brak mocy biegowej (watts) — analiza mocy niedostępna (np. Stryd).")
    else:
        _render_power_section(df)
        st.caption("ℹ️ Brak kolumny `pace` — analiza wg tempa niedostępna.")

    with st.expander("📖 Teoria wytrzymałości biegowej", expanded=False):
        st.markdown(
            """
        **Durability** to zdolność do minimalizowania spadku intensywności mimo akumulacji
        zmęczenia (peryferyjnego, centralnego, termoregulacyjnego i deplecji glikogenu).

        - **Wg tempa:** DI = (tempo_1.połowa / tempo_2.połowa) × 100 — ≥100% = negatywny split.
        - **Wg mocy:** DI = (moc_2.połowa / moc_1.połowa) × 100 — ≥100% = moc utrzymana/wyższa.

        Tempo i moc mogą się rozjeżdżać: np. przy podbiegach lub wietrze tempo spada, choć moc
        jest utrzymana — dlatego warto patrzeć na obie zmienne.

        Normy: **≥100%** elita / negatywny split · **97–100%** bardzo dobra · **94–97%** dobra ·
        **90–94%** średnia · **<90%** wymaga bazy tlenowej i długich wybiegań.
        """
        )


def _render_metric_row(di, first, second, first_label, second_label, fmt, help_txt) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            "Indeks Wytrzymałości",
            f"{di:.1f}%",
            delta=f"{di - 100:.1f}%",
            delta_color="normal" if di >= 97 else "inverse",
            help=help_txt,
        )
    c2.metric(first_label, fmt(first))
    c3.metric(second_label, fmt(second))
    with c4:
        loss = max(0.0, 100 - di)
        st.metric("Spadek", f"{loss:.1f}%", delta_color="inverse" if loss > 6 else "normal")
    st.info(f"**Interpretacja:** {_interpret(di)}")


def _render_pace_section(df: pd.DataFrame) -> None:
    di, first, second = _pace_durability(df)
    if di is None:
        st.info("Potrzeba ~20 minut ciągłego biegu z danymi tempa.")
        return
    _render_metric_row(
        di,
        first,
        second,
        "Śr. tempo (1. połowa)",
        "Śr. tempo (2. połowa)",
        _fmt_pace,
        "≥100% = tempo utrzymane/przyspieszone w 2. połowie",
    )
    _render_curve(df, "pace", invert=True, title="Krocząca wytrzymałość tempa (DI)")


def _render_power_section(df: pd.DataFrame) -> None:
    di, first, second = _power_durability(df)
    if di is None:
        st.info("Potrzeba ~20 minut ciągłego biegu z danymi mocy (watts).")
        return
    _render_metric_row(
        di,
        first,
        second,
        "Śr. moc (1. połowa)",
        "Śr. moc (2. połowa)",
        _fmt_watts,
        "≥100% = moc utrzymana/wyższa w 2. połowie",
    )
    _render_curve(df, "watts", invert=False, title="Krocząca wytrzymałość mocy (DI)")


def _render_curve(df: pd.DataFrame, col: str, invert: bool, title: str) -> None:
    """Rolling durability index across the run (5-min windows).

    invert=True for pace (lower is better → DI = baseline/rolled).
    invert=False for power (higher is better → DI = rolled/baseline).
    """
    if "time" not in df.columns and "time_min" not in df.columns:
        return
    series = pd.to_numeric(df[col], errors="coerce")
    if col == "pace":
        valid = (series >= 120) & (series <= 1200)
    else:
        valid = series > 0
    if valid.sum() < 600:  # ~10 min
        return

    baseline = series[valid].iloc[: max(1, int(valid.sum()) // 5)].mean()
    if not baseline or baseline <= 0:
        return

    win = 300  # 5 min at 1 Hz
    rolled = series.where(valid).rolling(win, min_periods=win // 2).mean()
    di_series = (baseline / rolled) * 100.0 if invert else (rolled / baseline) * 100.0

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
        title=title,
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
