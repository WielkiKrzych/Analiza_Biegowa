"""Longest continuous effort around a target running pace."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.pace_utils import pace_to_speed, speed_to_pace
from modules.tte import compute_tte, format_tte


def _estimate_threshold_pace(pace: pd.Series) -> float:
    """Estimate threshold pace (sec/km) as the fastest 20-min rolling avg × 1.05.

    Slower pace = higher seconds, so threshold (sustainable) pace is a bit slower
    (larger number) than the best 20-min effort.
    """
    p = pd.to_numeric(pace, errors="coerce")
    p = p.where((p >= 120) & (p <= 1200))
    window = 20 * 60
    if p.notna().sum() >= window:
        best20 = p.rolling(window, min_periods=window // 2).mean().min()
        if best20 and best20 > 0:
            return float(best20 * 1.05)
    mean_p = float(p.dropna().mean()) if p.notna().any() else 0.0
    return mean_p


def _fmt_pace(sec_per_km: float) -> str:
    if not sec_per_km or sec_per_km <= 0:
        return "-"
    m = int(sec_per_km // 60)
    s = int(round(sec_per_km - m * 60))
    if s == 60:
        m, s = m + 1, 0
    return f"{m}:{s:02d}"


def _rating(tte_seconds: int) -> str:
    if tte_seconds >= 3600:
        return "🏆 Elitarny"
    if tte_seconds >= 1800:
        return "💪 Dobry"
    if tte_seconds >= 600:
        return "📈 Rozwijający się"
    return "🔄 Do poprawy"


# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------


def render_tte_tab(df_plot: pd.DataFrame, threshold_pace: float) -> None:
    st.header("Czas utrzymania tempa (TTE)")
    st.caption("Najdłuższy ciągły odcinek w podanym zakresie prędkości progowej.")
    left, right = st.columns(2)
    target_pct = left.slider("Docelowy % prędkości progowej", 70, 120, 100, 5, key="tte_pct")
    tol_pct = right.slider("Tolerancja [%]", 1, 10, 5, 1, key="tte_tol")
    _render_pace_tte(df_plot, threshold_pace, target_pct, tol_pct)


def _render_pace_tte(
    df_plot: pd.DataFrame, threshold_pace: float, target_pct: int, tol_pct: int
) -> None:
    if not threshold_pace or threshold_pace <= 0:
        threshold_pace = _estimate_threshold_pace(df_plot["pace"])
        st.caption(f"ℹ️ Tempo progowe oszacowane z sesji: **{_fmt_pace(threshold_pace)} min/km**.")
    if not threshold_pace or threshold_pace <= 0:
        st.info("Brak wiarygodnych danych tempa.")
        return

    # Work in speed space so "hold intensity within a band" is symmetric.
    speed = pd.to_numeric(df_plot["pace"], errors="coerce").apply(
        lambda p: pace_to_speed(p) if pd.notna(p) and p > 0 else 0.0
    )
    threshold_speed = pace_to_speed(threshold_pace)

    tte_seconds = compute_tte(
        speed, target_pct=target_pct, threshold=threshold_speed, tol_pct=tol_pct
    )

    target_speed = threshold_speed * (target_pct / 100.0)
    speed_min = target_speed * (1 - tol_pct / 100.0)
    speed_max = target_speed * (1 + tol_pct / 100.0)
    # Faster speed = lower pace, so the pace band inverts.
    pace_fast = speed_to_pace(speed_max)
    pace_slow = speed_to_pace(speed_min)

    c1, c2, c3 = st.columns(3)
    c1.metric("Maksymalny TTE", format_tte(tte_seconds))
    c2.metric(
        "Zakres tempa",
        f"{_fmt_pace(pace_fast)}-{_fmt_pace(pace_slow)}",
        help=f"{target_pct}% tempa progowego ± {tol_pct}%",
    )
    c3.metric("Ocena", _rating(tte_seconds))

    _render_series_chart(
        df_plot,
        "pace",
        pace_fast,
        pace_slow,
        "Tempo",
        "Tempo [min/km]",
        f"{target_pct}% progu ± {tol_pct}%",
        invert_y=True,
    )


# ---------------------------------------------------------------------------
# Shared chart
# ---------------------------------------------------------------------------


def _render_series_chart(
    df_plot: pd.DataFrame,
    col: str,
    band_low: float,
    band_high: float,
    series_name: str,
    y_title: str,
    band_label: str,
    invert_y: bool = False,
) -> None:
    if "time_min" in df_plot.columns:
        x = df_plot["time_min"]
    elif "time" in df_plot.columns:
        x = df_plot["time"] / 60.0
    else:
        x = list(range(len(df_plot)))

    y = pd.to_numeric(df_plot[col], errors="coerce")
    if col == "pace":
        y = y.where((y >= 120) & (y <= 1200)) / 60.0  # show pace in minutes/km
        band_low = band_low / 60.0
        band_high = band_high / 60.0

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            name=series_name,
            line=dict(color="#1f77b4", width=1),
            hovertemplate=f"{series_name}: %{{y:.2f}}<extra></extra>",
        )
    )
    fig.add_hrect(
        y0=min(band_low, band_high),
        y1=max(band_low, band_high),
        fillcolor="rgba(0, 255, 0, 0.1)",
        line=dict(color="green", width=1, dash="dash"),
        annotation_text=f"Zakres TTE ({band_label})",
        annotation_position="top left",
    )
    yaxis = dict(title=y_title)
    if invert_y:
        yaxis["autorange"] = "reversed"  # faster (lower) pace on top
    fig.update_layout(
        template="plotly_dark",
        title=f"Rozkład: {series_name} z zakresem TTE",
        hovermode="x unified",
        xaxis=dict(title="Czas [min]"),
        yaxis=yaxis,
        height=430,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)
