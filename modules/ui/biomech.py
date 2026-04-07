from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from modules.calculations.pace_utils import pace_array_to_speed_array
from modules.calculations.running_dynamics import (
    calculate_cadence_stats,
    calculate_gct_stats,
    calculate_stride_metrics,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_time_col(df: pd.DataFrame) -> str | None:
    """Return the best available time column name, or None."""
    for col in ("time_min", "time"):
        if col in df.columns:
            return col
    return None


def _make_hhmmss_ticks(time_vals: np.ndarray, step: int = 5) -> tuple[np.ndarray, list[str]]:
    """Generate tick positions and hh:mm:ss labels for a time axis."""
    tick_vals = np.arange(0, time_vals.max() + step, step)
    tick_text = [f"{int(m // 60):02d}:{int(m % 60):02d}:00" for m in tick_vals]
    return tick_vals, tick_text


def _apply_dark_layout(
    fig: go.Figure,
    title: str,
    tick_vals: np.ndarray,
    tick_text: list[str],
    y_title: str,
    height: int = 400,
) -> None:
    """Apply the common dark-theme layout used across all biomech charts."""
    fig.update_layout(
        template="plotly_dark",
        title=title,
        hovermode="x unified",
        xaxis=dict(
            title="Czas [hh:mm:ss]",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
        ),
        yaxis_title=y_title,
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1, x=0),
    )


def _add_trend_line(
    fig: go.Figure,
    df: pd.DataFrame,
    time_col: str,
    value_col: str,
) -> None:
    """Add a linear regression trend line to *fig* if enough valid points exist."""
    valid_mask = ~np.isnan(df[value_col])
    if valid_mask.sum() <= 100:
        return
    try:
        slope, intercept, _, _, _ = stats.linregress(
            df.loc[valid_mask, time_col], df.loc[valid_mask, value_col]
        )
        trend = intercept + slope * df[time_col]
        fig.add_trace(
            go.Scatter(
                x=df[time_col],
                y=trend,
                name="Trend",
                line=dict(color="white", dash="dash"),
                hoverinfo="skip",
            )
        )
    except (ValueError, TypeError):
        pass


def _time_values(df: pd.DataFrame, time_col: str) -> np.ndarray:
    """Extract the time column as a numpy array."""
    series = df[time_col]
    return series.values if hasattr(series, "values") else np.array(series)


# ---------------------------------------------------------------------------
# Section renderers (private)
# ---------------------------------------------------------------------------


def _render_cadence_section(df_plot: pd.DataFrame) -> None:
    """Render the Cadence (SPM) section."""
    st.subheader("🏃 Kadencja Biegowa (SPM)")

    cad_col: str | None = None
    for col in ("cadence_smooth", "cadence", "spm"):
        if col in df_plot.columns:
            cad_col = col
            break

    if not cad_col:
        st.divider()
        return

    cad_data = df_plot[cad_col].dropna().values
    cad_stats: dict[str, Any] = calculate_cadence_stats(cad_data)

    if cad_stats.get("mean_spm", 0) <= 0:
        st.divider()
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Średnia Kadencja", f"{cad_stats['mean_spm']:.0f} SPM")
    c2.metric("Min Kadencja", f"{cad_stats.get('min_spm', '-')}")
    c3.metric("Max Kadencja", f"{cad_stats.get('max_spm', '-')}")
    c4.metric("CV", f"{cad_stats.get('cv_pct', 0):.1f}%")

    time_col = _resolve_time_col(df_plot)
    if time_col is not None:
        fig_cad = go.Figure()

        cad_smooth = df_plot[cad_col].rolling(10, center=True).mean()
        fig_cad.add_trace(
            go.Scatter(
                x=df_plot[time_col],
                y=cad_smooth,
                name="Kadencja",
                line=dict(color="#00D4FF", width=2),
                hovertemplate="👟 Kadencja: %{y:.0f} SPM<extra></extra>",
            )
        )

        _add_trend_line(fig_cad, df_plot, time_col, cad_col)

        fig_cad.add_hline(
            y=170,
            line_dash="dot",
            line_color="green",
            annotation_text="Opt min",
            annotation_position="right",
        )
        fig_cad.add_hline(
            y=185,
            line_dash="dot",
            line_color="green",
            annotation_text="Opt max",
            annotation_position="right",
        )

        tick_vals, tick_text = _make_hhmmss_ticks(_time_values(df_plot, time_col))
        _apply_dark_layout(fig_cad, "Kadencja w czasie", tick_vals, tick_text, "Kadencja [SPM]")
        st.plotly_chart(fig_cad, use_container_width=True)

    st.info("""
    **💡 Interpretacja Kadencji:**

    * **Optymalna: 170-185 SPM** - większość biegaczy osiąga najlepszą efektywność
    * **< 160 SPM:** Zbyt wolna - zwiększa obciążenie stawów i ryzyko kontuzji
    * **160-170 SPM:** Niska-moderowana - możliwa poprawa
    * **185-190 SPM:** Wysoka - często u elite
    * **> 190 SPM:** Bardzo wysoka - może wskazywać na krótki krok

    **Wskazówka:** Zwiększenie kadencji o 5-10% może zmniejszyć obciążenie stawów bez utraty prędkości.
    """)
    st.divider()


def _render_gct_section(df_plot: pd.DataFrame) -> None:
    """Render the Ground Contact Time (GCT) section."""
    st.subheader("⏱️ Ground Contact Time (GCT)")

    gct_col: str | None = None
    gct_is_real = False
    for col in ("stance_time", "ground_contact", "gct", "GroundContactTime"):
        if col in df_plot.columns:
            gct_col = col
            gct_is_real = col in ("stance_time", "ground_contact")
            break

    if not gct_col:
        st.info("ℹ️ Brak danych GCT - wymagany czujnik biegowy (np. Garmin HRM-Run, Stryd)")
        st.divider()
        return

    gct_data = df_plot[gct_col].dropna().values
    gct_stats: dict[str, Any] = calculate_gct_stats(gct_data)

    if gct_stats.get("mean_ms", 0) <= 0:
        st.divider()
        return

    g1, g2, g3 = st.columns(3)
    g1.metric("Średnie GCT", f"{gct_stats['mean_ms']:.0f} ms")
    g2.metric("Min GCT", f"{gct_stats.get('min_ms', '-')}")
    g3.metric("Max GCT", f"{gct_stats.get('max_ms', '-')}")

    classification = gct_stats.get("classification", "unknown")
    class_labels: dict[str, str] = {
        "excellent": "🟢 Excellent (<200ms)",
        "good": "🟢 Dobry (200-220ms)",
        "average": "🟡 Średni (220-240ms)",
        "needs-improvement": "🔴 Wymaga poprawy (>240ms)",
    }
    st.metric("Klasyfikacja", class_labels.get(classification, classification))

    time_col = _resolve_time_col(df_plot)
    if time_col is not None:
        fig_gct = go.Figure()

        gct_smooth = df_plot[gct_col].rolling(10, center=True).mean()
        fig_gct.add_trace(
            go.Scatter(
                x=df_plot[time_col],
                y=gct_smooth,
                name="GCT",
                line=dict(color="#FF6B6B", width=2),
                hovertemplate="🦶 GCT: %{y:.0f} ms<extra></extra>",
            )
        )

        fig_gct.add_hrect(y0=0, y1=200, fillcolor="green", opacity=0.1, line_width=0)
        fig_gct.add_hrect(y0=200, y1=220, fillcolor="limegreen", opacity=0.1, line_width=0)
        fig_gct.add_hrect(y0=220, y1=240, fillcolor="yellow", opacity=0.1, line_width=0)
        fig_gct.add_hrect(y0=240, y1=400, fillcolor="red", opacity=0.1, line_width=0)

        tick_vals, tick_text = _make_hhmmss_ticks(_time_values(df_plot, time_col))
        _apply_dark_layout(
            fig_gct, "Ground Contact Time w czasie", tick_vals, tick_text, "GCT [ms]"
        )
        st.plotly_chart(fig_gct, use_container_width=True)

    st.info("""
    **💡 Interpretacja GCT:**

    * **< 200 ms:** Excellent - typowe dla elite, bardzo efektywny kontakt z podłożem
    * **200-220 ms:** Dobry - solidny poziom amatorski
    * **220-240 ms:** Średni - miejsce na poprawę
    * **> 240 ms:** Wymaga poprawy - długi kontakt = utrata energii

    **Krótsze GCT = lepsza sprężystość i ekonomia biegu**
    """)
    if not gct_is_real:
        st.caption(
            "⚠️ GCT estymowane z kadencji (duty cycle ~65%). Dla dokładnych pomiarów użyj Garmin HRM-Run lub Stryd."
        )
    else:
        st.caption("✅ GCT z czujnika (Garmin FIT) — dane rzeczywiste.")
    st.divider()


def _render_stance_balance_section(df_plot: pd.DataFrame) -> None:
    """Render the Stance Time Balance (L/P) section."""
    if "stance_time_balance" not in df_plot.columns:
        return

    st.subheader("⚖️ Balans Kontaktu z Podłożem (L/P)")

    balance_data = df_plot["stance_time_balance"].dropna()
    if len(balance_data) == 0:
        st.divider()
        return

    avg_balance = float(balance_data.mean())
    min_balance = float(balance_data.min())
    max_balance = float(balance_data.max())
    imbalance = abs(avg_balance - 50.0)

    b1, b2, b3, b4 = st.columns(4)
    b1.metric(
        "Średni Balans",
        f"{avg_balance:.1f}%",
        help="50% = idealny. >50% = prawa noga dłużej na ziemi",
    )
    b2.metric("Min", f"{min_balance:.1f}%")
    b3.metric("Max", f"{max_balance:.1f}%")

    if imbalance < 1.0:
        b4.metric("Asymetria", f"{imbalance:.1f}%", delta="Idealny")
    elif imbalance < 2.0:
        b4.metric("Asymetria", f"{imbalance:.1f}%", delta="Dobry")
    else:
        b4.metric("Asymetria", f"{imbalance:.1f}%", delta="Uwaga", delta_color="inverse")

    time_col = _resolve_time_col(df_plot)
    if time_col is not None:
        fig_bal = go.Figure()
        bal_smooth = df_plot["stance_time_balance"].rolling(15, center=True).mean()
        fig_bal.add_trace(
            go.Scatter(
                x=df_plot[time_col],
                y=bal_smooth,
                name="Balans L/P",
                line=dict(color="#1ABC9C", width=2),
                hovertemplate="⚖️ Balans: %{y:.1f}%<extra></extra>",
            )
        )
        fig_bal.add_hline(
            y=50.0,
            line_dash="dash",
            line_color="white",
            annotation_text="50% (idealny)",
            annotation_position="right",
        )
        fig_bal.add_hrect(y0=49.0, y1=51.0, fillcolor="green", opacity=0.1, line_width=0)

        tick_vals, tick_text = _make_hhmmss_ticks(df_plot[time_col].values)
        _apply_dark_layout(
            fig_bal,
            "Balans kontaktu z podłożem (L/P)",
            tick_vals,
            tick_text,
            "Balans [%]",
            height=350,
        )
        st.plotly_chart(fig_bal, use_container_width=True)

    st.info("""
    **💡 Interpretacja Balansu L/P:**

    * **49-51%:** Idealny — symetryczny bieg
    * **48-52%:** Akceptowalny — minimalna asymetria
    * **< 48% lub > 52%:** Wymaga uwagi — ryzyko kontuzji po stronie dominującej

    **Wskazówka:** Asymetria > 2% może wskazywać na kompensację bólową lub różnicę siłową.
    """)
    st.divider()


def _render_vertical_ratio_section(df_plot: pd.DataFrame) -> None:
    """Render the Vertical Ratio section."""
    if "vertical_ratio" not in df_plot.columns:
        return

    st.subheader("📐 Vertical Ratio (Stosunek Oscylacji do Kroku)")

    vr_data = df_plot["vertical_ratio"].dropna()
    if len(vr_data) == 0:
        st.divider()
        return

    avg_vr = float(vr_data.mean())
    min_vr = float(vr_data.min())
    max_vr = float(vr_data.max())

    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Średni VR", f"{avg_vr:.1f}%")
    v2.metric("Min VR", f"{min_vr:.1f}%")
    v3.metric("Max VR", f"{max_vr:.1f}%")

    if avg_vr < 6.0:
        v4.metric("Klasyfikacja", "Excellent")
    elif avg_vr < 8.0:
        v4.metric("Klasyfikacja", "Dobry")
    elif avg_vr < 10.0:
        v4.metric("Klasyfikacja", "Średni")
    else:
        v4.metric("Klasyfikacja", "Wymaga poprawy")

    time_col = _resolve_time_col(df_plot)
    if time_col is not None:
        fig_vr = go.Figure()
        vr_smooth = df_plot["vertical_ratio"].rolling(10, center=True).mean()
        fig_vr.add_trace(
            go.Scatter(
                x=df_plot[time_col],
                y=vr_smooth,
                name="Vertical Ratio",
                line=dict(color="#E67E22", width=2),
                hovertemplate="📐 VR: %{y:.1f}%<extra></extra>",
            )
        )
        fig_vr.add_hrect(y0=0, y1=6, fillcolor="green", opacity=0.08, line_width=0)
        fig_vr.add_hrect(y0=6, y1=8, fillcolor="yellow", opacity=0.08, line_width=0)
        fig_vr.add_hrect(y0=8, y1=15, fillcolor="red", opacity=0.08, line_width=0)

        tick_vals, tick_text = _make_hhmmss_ticks(df_plot[time_col].values)
        _apply_dark_layout(
            fig_vr,
            "Vertical Ratio w czasie",
            tick_vals,
            tick_text,
            "VR [%]",
            height=350,
        )
        st.plotly_chart(fig_vr, use_container_width=True)

    st.info("""
    **💡 Interpretacja Vertical Ratio:**

    Vertical Ratio = Oscylacja Pionowa / Długość Kroku × 100%

    * **< 6%:** Excellent — efektywne przekazywanie energii do przodu
    * **6-8%:** Dobry — solidna technika
    * **8-10%:** Średni — zbyt dużo energii traconej w pionie
    * **> 10%:** Wymaga poprawy — "bouncing" runner

    **Niższy VR = więcej energii idzie do przodu zamiast w górę.**
    """)
    st.divider()


def _render_stride_length_section(
    df_plot: pd.DataFrame,
    runner_height: int,
) -> None:
    """Render the Stride Length section."""
    st.subheader("📏 Długość Kroku (Stride Length)")

    has_real_step = "step_length" in df_plot.columns and df_plot["step_length"].notna().sum() > 10
    can_estimate = "cadence" in df_plot.columns and "pace" in df_plot.columns

    if not has_real_step and not can_estimate:
        st.info("ℹ️ Do obliczenia długości kroku wymagane dane kadencji i tempa")
        st.divider()
        return

    if has_real_step:
        sl_data = df_plot["step_length"].dropna()
        avg_sl = float(sl_data.mean())
        height_m = runner_height / 100
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Średnia długość kroku", f"{avg_sl:.3f} m")
        s2.metric("Ratio do wzrostu", f"{avg_sl / height_m:.2f}")
        s3.metric("Min / Max", f"{sl_data.min():.2f} / {sl_data.max():.2f} m")
        s4.metric("Źródło", "Garmin FIT")
    else:
        stride_metrics = calculate_stride_metrics(df_plot, runner_height)
        if stride_metrics:
            s1, s2, s3 = st.columns(3)
            s1.metric("Średnia długość kroku", f"{stride_metrics['stride_length_m']:.2f} m")
            s2.metric("Ratio do wzrostu", f"{stride_metrics['height_ratio']:.2f}")
            s3.metric("Próbki", stride_metrics["samples"])

    if has_real_step:
        valid_mask = df_plot["step_length"].notna()
        df_stride = df_plot[valid_mask].copy()
    else:
        valid_mask = (df_plot["cadence"] > 50) & (df_plot["cadence"] < 300) & (df_plot["pace"] > 0)
        df_stride = df_plot[valid_mask].copy()
        if not df_stride.empty:
            speed_m_s = pace_array_to_speed_array(df_stride["pace"].values)
            cadence_spm = df_stride["cadence"].values
            df_stride["step_length"] = speed_m_s * 2 * 60 / cadence_spm

    if df_stride.empty or "step_length" not in df_stride.columns:
        st.divider()
        return

    time_col = _resolve_time_col(df_stride)
    if time_col is None:
        st.divider()
        return

    fig_stride = go.Figure()
    stride_smooth = df_stride["step_length"].rolling(10, center=True).mean()

    fig_stride.add_trace(
        go.Scatter(
            x=df_stride[time_col],
            y=stride_smooth,
            name="Długość kroku",
            line=dict(color="#9B59B6", width=2),
            hovertemplate="📏 Krok: %{y:.2f} m<extra></extra>",
        )
    )

    tick_vals, tick_text = _make_hhmmss_ticks(_time_values(df_stride, time_col))
    _apply_dark_layout(
        fig_stride,
        "Długość kroku w czasie",
        tick_vals,
        tick_text,
        "Długość kroku [m]",
        height=350,
    )
    st.plotly_chart(fig_stride, use_container_width=True)

    st.info("""
    **💡 Interpretacja długości kroku:**

    * **Ratio do wzrostu 0.9-1.1:** Typowy zakres
    * **Większy krok ≠ szybszy bieg** - zależy od kadencji
    * **Optymalna kombinacja:** Wyższa kadencja + umiarkowany krok

    **Wzór:** Stride Length = Speed (m/s) × 2 × 60 / Cadence (SPM)
    """)
    st.divider()


def _render_running_effectiveness_section(
    df_plot: pd.DataFrame,
    runner_weight: float,
) -> None:
    """Render the Running Effectiveness (RE) section."""
    st.subheader("⚡ Running Effectiveness (RE)")

    if "watts" not in df_plot.columns or "pace" not in df_plot.columns:
        st.info("ℹ️ Do obliczenia RE wymagane dane mocy (watts) i tempa (pace)")
        st.divider()
        return

    valid_mask = (df_plot["watts"] > 50) & (df_plot["pace"] > 0)
    df_re = df_plot[valid_mask].copy()

    if df_re.empty:
        st.divider()
        return

    speed_m_s = pace_array_to_speed_array(df_re["pace"].values)
    power_w = df_re["watts"].values
    power_per_kg = power_w / runner_weight

    df_re["re"] = np.where(power_per_kg > 0, speed_m_s / power_per_kg, np.nan)

    avg_re: float = float(df_re["re"].mean())

    re1, re2, re3 = st.columns(3)
    re1.metric(
        "Średnie RE",
        f"{avg_re:.3f} m/s/W/kg",
        help="RE = prędkość (m/s) / moc (W/kg)",
    )

    time_col = _resolve_time_col(df_re)
    if time_col is not None and time_col in df_re.columns:
        valid_re = df_re.dropna(subset=["re"])
        if len(valid_re) > 100:
            slope, intercept, _, _, _ = stats.linregress(valid_re[time_col], valid_re["re"])
            total_drift = slope * (valid_re[time_col].iloc[-1] - valid_re[time_col].iloc[0])
            re2.metric(
                "Trend RE",
                f"{total_drift:+.3f}",
                delta_color="inverse" if total_drift < 0 else "normal",
            )

    if avg_re > 1.0:
        re3.metric("Klasyfikacja", "🟢 Bardzo dobra")
    elif avg_re > 0.85:
        re3.metric("Klasyfikacja", "🟡 Dobra")
    else:
        re3.metric("Klasyfikacja", "🔴 Wymaga poprawy")

    if time_col is not None and time_col in df_re.columns:
        fig_re = go.Figure()

        re_smooth = df_re["re"].rolling(15, center=True).mean()
        fig_re.add_trace(
            go.Scatter(
                x=df_re[time_col],
                y=re_smooth,
                name="RE",
                line=dict(color="#F39C12", width=2),
                hovertemplate="💪 RE: %{y:.3f}<extra></extra>",
            )
        )

        fig_re.add_hline(
            y=1.0,
            line_dash="dash",
            line_color="green",
            annotation_text="RE = 1.0 (dobre)",
        )

        tick_vals, tick_text = _make_hhmmss_ticks(_time_values(df_re, time_col))
        _apply_dark_layout(
            fig_re,
            "Running Effectiveness w czasie",
            tick_vals,
            tick_text,
            "RE [m/s/W/kg]",
            height=350,
        )
        st.plotly_chart(fig_re, use_container_width=True)

    st.info("""
    **💡 Interpretacja Running Effectiveness:**

    * **RE > 1.0:** Bardzo dobra efektywność - prędkość dobrze przekłada się na moc
    * **RE 0.85-1.0:** Dobra efektywność
    * **RE < 0.85:** Możliwość poprawy techniki biegu

    **Wzór:** RE = Prędkość (m/s) / Moc (W/kg)
    """)
    st.divider()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_biomech_tab(df_plot: pd.DataFrame, df_plot_resampled: pd.DataFrame) -> None:
    """Render the Biomechanical Stress tab."""
    st.header("Biomechaniczny Stres")

    sport_type = st.session_state.get("sport_type", "unknown")
    is_running = sport_type == "running" or "pace" in df_plot.columns

    if is_running:
        runner_weight = st.session_state.get("rider_weight", 70.0)
        runner_height = st.session_state.get("runner_height", 175)

        _render_cadence_section(df_plot)
        _render_gct_section(df_plot)
        _render_stance_balance_section(df_plot)
        _render_vertical_ratio_section(df_plot)
        _render_stride_length_section(df_plot, runner_height)
        _render_running_effectiveness_section(df_plot, runner_weight)

    _render_vertical_oscillation_section(df_plot, df_plot_resampled)


def _render_vertical_oscillation_section(
    df_plot: pd.DataFrame,
    df_plot_resampled: pd.DataFrame,
) -> None:
    """Render Vertical Oscillation analysis section."""
    st.divider()
    st.subheader("📊 Vertical Oscillation (Oscylacja Pionowa)")

    vo_col: str | None = None
    for col in ("verticaloscillation", "VerticalOscillation", "vo", "oscillation"):
        if col in df_plot.columns:
            vo_col = col
            break

    if vo_col is None:
        st.info("""
        ℹ️ **Brak danych Vertical Oscillation**

        Aby uzyskać analizę oscylacji pionowej, potrzebujesz czujnika biegowego
        (np. Garmin HRM-Run, Stryd, lub inny czujnik z pomiarem VO).

        **Brakująca kolumna:** `VerticalOscillation` (oscylacja pionowa w cm)
        """)
        return

    from modules.calculations.running_dynamics import (
        analyze_vo_efficiency,
        calculate_running_effectiveness_from_vo,
        calculate_vo_stats,
    )

    vo_data = df_plot[vo_col].values
    vo_stats: dict[str, Any] = calculate_vo_stats(vo_data)

    if not vo_stats:
        st.warning("Brak wystarczających danych VO do analizy.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Średnie VO", f"{vo_stats.get('mean_vo', 0):.1f} cm")
    col2.metric("Min VO", f"{vo_stats.get('min_vo', 0):.1f} cm")
    col3.metric("Max VO", f"{vo_stats.get('max_vo', 0):.1f} cm")
    col4.metric("CV", f"{vo_stats.get('cv_vo', 0):.1f}%")

    fig_vo = go.Figure()

    time_col = _resolve_time_col(df_plot)
    if time_col is not None:
        vo_smooth = df_plot[vo_col].rolling(5, center=True).mean()
        fig_vo.add_trace(
            go.Scatter(
                x=df_plot[time_col],
                y=vo_smooth,
                name="VO",
                line=dict(color="#ff6b6b", width=2),
                hovertemplate="📊 VO: %{y:.1f} cm<extra></extra>",
            )
        )

        _add_trend_line(fig_vo, df_plot, time_col, vo_col)

    tick_vals, tick_text = _make_hhmmss_ticks(_time_values(df_plot, time_col or "time_min"))
    _apply_dark_layout(
        fig_vo,
        "Vertical Oscillation w czasie",
        tick_vals,
        tick_text,
        "VO [cm]",
    )
    st.plotly_chart(fig_vo, use_container_width=True)

    cad_col = _resolve_cadence_col(df_plot)
    if cad_col is not None:
        _render_vo_cadence_scatter(df_plot, vo_data, vo_col, cad_col, analyze_vo_efficiency)

    if "pace" in df_plot.columns:
        _render_vo_pace_effectiveness(df_plot, vo_stats, calculate_running_effectiveness_from_vo)

    st.info("""
    **💡 Interpretacja Vertical Oscillation:**

    **Co to jest?**
    VO to odległość o jaką centrum masy podnosi się i opuszcza podczas biegu.

    **Normy (dla biegaczy):**
    - **< 6 cm:** Bardzo efektywny bieg (elite)
    - **6-8 cm:** Dobra efektywność
    - **8-10 cm:** Średnia efektywność
    - **> 10 cm:** Wysoka oscylacja - "bouncing"

    **Dla rowerzystów:**
    VO jest naturalnie niższa (siedzenie). Wartości > 3 cm przy pedałowaniu
    mogą wskazywać na "podskakiwanie" na siodełku.

    **Korelacja z kadencją:**
    Wyższa kadencja zazwyczaj = niższa VO (mniej "bouncing").
    Szukaj optymalnego punktu gdzie VO jest minimalna przy komfortowej kadencji.
    """)


def _resolve_cadence_col(df_plot: pd.DataFrame) -> str | None:
    """Return the best available cadence column name, or None."""
    for col in ("cadence_smooth", "cadence", "spm"):
        if col in df_plot.columns:
            return col
    return None


def _render_vo_cadence_scatter(
    df_plot: pd.DataFrame,
    vo_data: np.ndarray,
    vo_col: str,
    cad_col: str,
    analyze_vo_efficiency: Any,
) -> None:
    """Render VO vs cadence scatter plot with optimal cadence hint."""
    efficiency = analyze_vo_efficiency(vo_data, df_plot[cad_col].values)

    if efficiency.get("optimal_cadence"):
        st.success(
            f"🎯 **Optymalna kadencja:** {efficiency['optimal_cadence']} SPM (najniższa oscylacja)"
        )

    fig_scatter = go.Figure()
    fig_scatter.add_trace(
        go.Scatter(
            x=df_plot[cad_col],
            y=df_plot[vo_col],
            mode="markers",
            marker=dict(size=4, opacity=0.5, color="#ff6b6b"),
            name="VO vs Cadence",
            hovertemplate="👟 Cadence: %{x:.0f} SPM<br>📊 VO: %{y:.1f} cm<extra></extra>",
        )
    )
    fig_scatter.update_layout(
        template="plotly_dark",
        title="VO vs Kadencja",
        xaxis_title="Cadence [SPM/RPM]",
        yaxis_title="VO [cm]",
        height=400,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)


def _render_vo_pace_effectiveness(
    df_plot: pd.DataFrame,
    vo_stats: dict[str, Any],
    calculate_running_effectiveness_from_vo: Any,
) -> None:
    """Render VO-based running effectiveness metrics when pace data is available."""
    st.subheader("🏃 Efektywność Biegu z VO")

    runner_height = st.session_state.get("runner_height", 180)
    avg_pace = df_plot["pace"].mean()
    avg_vo = vo_stats["mean_vo"]

    effectiveness = calculate_running_effectiveness_from_vo(avg_pace, avg_vo, runner_height)

    if effectiveness:
        col1, col2, col3 = st.columns(3)
        col1.metric("VO % wzrostu", f"{effectiveness['vo_percent_height']:.1f}%")
        col2.metric("Efektywność", f"{effectiveness['effectiveness_score']:.0f}/100")
        col3.metric("Klasyfikacja", effectiveness["classification"])
