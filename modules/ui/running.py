"""
Running-specific UI components.

Charts, metrics, and visualizations for running analysis.
"""

from typing import Dict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.pace import (
    calculate_fatigue_resistance_index_pace,
    calculate_pace_duration_curve,
    calculate_pace_zones_time,
    classify_running_phenotype,
    get_fri_interpretation_pace,
    get_phenotype_description,
)
from modules.calculations.pace_utils import format_pace
from modules.plots import apply_chart_style


def _mean_pace(series: pd.Series) -> float:
    """Time-weighted average pace = total distance / total time.

    The arithmetic mean of pace (sec/km) is NOT the average pace: it
    over-weights slow samples. E.g. 30 min at 4:00 + 30 min at 6:00 averages
    to 4:48/km (distance/time), not 5:00/km. Averaging in speed space and
    converting back gives the correct, device-consistent value.
    """
    paces = pd.to_numeric(series, errors="coerce")
    paces = paces[paces > 0].dropna()
    if paces.empty:
        return 0.0
    mean_speed = float((1000.0 / paces).mean())
    return 1000.0 / mean_speed if mean_speed > 0 else 0.0


def calculate_pace_summary_stats(df: pd.DataFrame, threshold_pace: float) -> Dict:
    """Calculate summary statistics for pace data."""
    stats: Dict = {}

    if "pace" in df.columns:
        paces = df["pace"].dropna()
        moving = paces[paces > 0]
        stats["avg_pace"] = _mean_pace(paces)
        # min = fastest, max = slowest; ignore stopped samples (pace <= 0)
        stats["min_pace"] = float(moving.min()) if not moving.empty else 0.0
        stats["max_pace"] = float(moving.max()) if not moving.empty else 0.0

    if "gap" in df.columns:
        stats["avg_gap"] = _mean_pace(df["gap"])

    if "pace" in df.columns:
        stats["time_in_zones"] = calculate_pace_zones_time(df, threshold_pace)

    return stats


# ===========================================================================
# PRIVATE HELPERS — sections extracted from render_running_tab
# ===========================================================================


def _build_time_x_ticks(x_data: "pd.Series | pd.Index") -> tuple[list[int], list[str]]:
    """Build HH:MM:SS formatted tick values for the time axis."""
    x_min_val = float(x_data.min()) if hasattr(x_data, "min") else 0
    x_max_val = float(x_data.max()) if hasattr(x_data, "max") else 60
    x_tick_step = max(1, int((x_max_val - x_min_val) / 10))
    x_tickvals = list(range(int(x_min_val), int(x_max_val) + 1, x_tick_step))
    x_ticktext: list[str] = []
    for m in x_tickvals:
        total_sec = int(m * 60)
        hrs = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        if hrs > 0:
            x_ticktext.append(f"{hrs}:{mins:02d}:{secs:02d}")
        else:
            x_ticktext.append(f"{mins}:{secs:02d}")
    return x_tickvals, x_ticktext


def _render_pace_chart(df_plot: pd.DataFrame, threshold_pace: float) -> None:
    """Render Section 1: Pace chart with D' balance, GAP overlay, and interpretation."""
    st.subheader("Tempo i GAP")

    fig_pace = go.Figure()

    time_col = "time_min" if "time_min" in df_plot.columns else df_plot.index
    x_data = df_plot[time_col] if isinstance(time_col, str) else time_col

    PACE_CAP = 600  # 10:00/km
    pace_smooth = df_plot.get("pace_smooth", df_plot["pace"]).where(df_plot["pace"].gt(0))
    pace_clipped = pace_smooth.clip(upper=PACE_CAP)

    fig_pace.add_trace(
        go.Scatter(
            x=x_data,
            y=[PACE_CAP] * len(x_data),
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig_pace.add_trace(
        go.Scatter(
            x=x_data,
            y=pace_clipped,
            name="Tempo",
            fill="tonexty",
            fillcolor="rgba(52, 152, 219, 0.3)",
            line=dict(color="#3498db", width=1.5),
            hovertemplate="Tempo: %{customdata}<extra></extra>",
            customdata=[format_pace(p) for p in pace_clipped],
        )
    )

    if "gap" in df_plot.columns:
        gap_smooth = df_plot["gap"].rolling(window=10, min_periods=1, center=True).mean()
        gap_clipped = gap_smooth.clip(upper=PACE_CAP)
        fig_pace.add_trace(
            go.Scatter(
                x=x_data,
                y=gap_clipped,
                name="GAP",
                line=dict(color="#2ecc71", width=1.5, dash="dash"),
                hovertemplate="GAP: %{customdata}<extra></extra>",
                customdata=[format_pace(p) for p in gap_clipped],
            )
        )

    fig_pace.add_hline(
        y=threshold_pace,
        line_dash="dot",
        line_color="red",
        annotation_text=f"Próg ({format_pace(threshold_pace)})",
        annotation_position="top left",
    )

    pace_min_val = max(120, int(pace_clipped.min() // 30 * 30))
    y_tickvals = list(range(pace_min_val, PACE_CAP + 1, 30))
    y_ticktext = [format_pace(v) for v in y_tickvals]

    x_tickvals, x_ticktext = _build_time_x_ticks(x_data)

    fig_pace.update_layout(
        template="plotly_dark",
        title="Zarządzanie Tempem (Pace & GAP)",
        hovermode="x unified",
        xaxis=dict(title="Czas", tickvals=x_tickvals, ticktext=x_ticktext),
        yaxis=dict(
            title="Tempo [min/km]",
            autorange="reversed",
            tickvals=y_tickvals,
            ticktext=y_ticktext,
            range=[PACE_CAP, pace_min_val],
        ),
        margin=dict(l=10, r=10, t=40, b=10),
        height=450,
    )
    st.plotly_chart(apply_chart_style(fig_pace), width="stretch")

    st.info("""
    **💡 Interpretacja: Zarządzanie Tempem**

    * **Niebieska linia (Tempo):** Aktualne tempo biegu (min/km). Im niżej na wykresie = szybciej.
    * **Zielona przerywana (GAP):** Grade-Adjusted Pace — tempo skorygowane o profil terenu.
    * **Czerwona linia (Próg):** Twoje tempo progowe.

    **Jak to czytać?**
    * **Tempo < Próg (powyżej linii):** Biegasz poniżej progu — strefa tlenowa. Regeneracja D'.
    * **Tempo > Próg (poniżej linii):** Biegasz powyżej progu — spalasz D'. Im szybciej, tym szybciej się wyczerpiesz.
    * **GAP vs Tempo:** Jeśli GAP jest szybsze niż tempo — biegasz pod górę. Jeśli wolniejsze — w dół.
    """)


def _render_pace_zones(df_plot: pd.DataFrame, threshold_pace: float) -> None:
    """Render Section 2: Pace zones bar chart with time-in-zone interpretation."""
    st.subheader("⏱️ Czas w Strefach Tempa")

    zones_time = calculate_pace_zones_time(df_plot, threshold_pace)
    if not zones_time:
        st.info("Brak wystarczających danych tempa do obliczenia stref.")
        return

    def _format_time_mmss(minutes: float) -> str:
        total_sec = int(minutes * 60)
        mins = total_sec // 60
        secs = total_sec % 60
        return f"{mins}:{secs:02d}"

    zones_list = list(zones_time.keys())
    times_min = [zones_time[z] / 60 for z in zones_list]
    colors = ["#3498db", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#9b59b6"]
    time_labels = [_format_time_mmss(t) for t in times_min]

    fig_z = go.Figure(
        data=[
            go.Bar(
                x=[t for t in times_min],
                y=zones_list,
                orientation="h",
                text=time_labels,
                textposition="auto",
                marker_color=colors[: len(zones_list)],
            )
        ]
    )

    x_max = max(times_min) if times_min else 10
    x_tickvals = list(range(0, int(x_max) + 5, 5))
    x_ticktext = [_format_time_mmss(t) for t in x_tickvals]

    fig_z.update_layout(
        template="plotly_dark",
        title="Czas w Strefach Tempa",
        showlegend=False,
        xaxis=dict(
            title="Czas [mm:ss]",
            tickvals=x_tickvals,
            ticktext=x_ticktext,
        ),
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
    )

    st.info("""
    **💡 Interpretacja Stref Tempa:**

    * **Z1 Recovery (>115% progu):** Regeneracja, rozgrzewka, schładzanie.
    * **Z2 Aerobic (105-115%):** Budowa bazy tlenowej. Fundament.
    * **Z3 Tempo (95-105%):** Strefa progowa. Efektywna, ale wymagająca.
    * **Z4 Threshold (88-95%):** Powyżej progu. Trening tolerancji na mleczan.
    * **Z5 Interval (75-88%):** Interwały VO2max.
    * **Z6 Repetition (<75%):** Sprinterskie powtórzenia. Maksymalna prędkość.

    **Polaryzacja 80/20:** Dobrze zaprojektowany plan treningowy to ~80% Z1-Z2 i ~20% Z4-Z6.
    """)


def _render_pdc_metrics_and_chart(
    pdc: dict[int, float | None],
    valid_pdc: dict[int, float],
    threshold_pace: float,
) -> None:
    """Render PDC best-pace metrics, the PDC chart, and FRI index."""
    best_1min = pdc.get(60)
    best_5min = pdc.get(300)
    best_10min = pdc.get(600)
    best_20min = pdc.get(1200)

    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    col_p1.metric("⚡ Best 1min", (format_pace(best_1min) + " /km") if best_1min else "—")
    col_p2.metric("🔥 Best 5min", (format_pace(best_5min) + " /km") if best_5min else "—")
    col_p3.metric("💪 Best 10min", (format_pace(best_10min) + " /km") if best_10min else "—")
    col_p4.metric("🏔️ Best 20min", (format_pace(best_20min) + " /km") if best_20min else "—")

    durations_min = [d / 60 for d in valid_pdc.keys()]
    paces = list(valid_pdc.values())
    pace_labels = [format_pace(p) for p in paces]

    fig_pdc = go.Figure()
    fig_pdc.add_trace(
        go.Scatter(
            x=durations_min,
            y=paces,
            mode="lines+markers",
            name="Best Pace",
            line=dict(color="#3498db", width=3),
            marker=dict(size=8, color="#3498db", line=dict(width=1, color="white")),
            hovertemplate="Czas: %{x:.0f} min<br>Tempo: %{customdata}<extra></extra>",
            customdata=pace_labels,
        )
    )
    fig_pdc.add_hline(
        y=threshold_pace,
        line_dash="dot",
        line_color="red",
        annotation_text=f"Próg ({format_pace(threshold_pace)})",
    )

    pdc_min = max(120, int(min(paces) // 30 * 30))
    pdc_max = int(max(paces) // 30 * 30) + 30
    pdc_tickvals = list(range(pdc_min, pdc_max + 1, 30))
    pdc_ticktext = [format_pace(v) for v in pdc_tickvals]

    fig_pdc.update_layout(
        template="plotly_dark",
        title="Pace Duration Curve",
        xaxis=dict(title="Czas [min]", type="log"),
        yaxis=dict(
            title="Tempo [min/km]",
            autorange="reversed",
            tickvals=pdc_tickvals,
            ticktext=pdc_ticktext,
        ),
        height=400,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(apply_chart_style(fig_pdc), width="stretch")

    fri = calculate_fatigue_resistance_index_pace(pdc)
    if fri > 0:
        fri_interp = get_fri_interpretation_pace(fri)
        st.info(f"**Fatigue Resistance Index (FRI):** {fri:.3f} — {fri_interp}")


def _render_phenotype(
    pdc: dict[int, float | None] | None,
    runner_weight: float,
) -> None:
    """Render Section 6: Runner phenotype classification with VO2max estimation."""
    st.subheader("🧬 Profil Biegacza (Fenotyp)")

    if not pdc:
        st.info("Za mało danych do klasyfikacji fenotypu.")
        return

    phenotype = classify_running_phenotype(pdc, runner_weight)
    emoji, name, description = get_phenotype_description(phenotype)

    st.markdown(
        f"""
    <div style="background: linear-gradient(90deg, rgba(52, 152, 219, 0.2), transparent);
                padding: 15px 20px; border-radius: 12px; margin-bottom: 15px;">
        <span style="font-size: 2em;">{emoji}</span>
        <span style="font-size: 1.3em; font-weight: bold; margin-left: 10px;">{name}</span>
        <br/>
        <span style="font-size: 1em; color: #c9d1d9;">{description}</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    with st.expander("📚 Jak interpretować fenotyp biegacza?"):
        st.markdown("""
        ### Typy biegaczy

        | Fenotyp | Charakterystyka | Silne strony | Treningi kluczowe |
        |---------|----------------|--------------|-------------------|
        | ⚡ Sprinter | Szybki na 400m-1km, duży spadek na dłuższych | Sprint, 800m | Progi, tempo runs |
        | 🏃 Średnie dystanse | 5K-10K specialist | Szybkość + wytrzymałość | Interwały VO2max |
        | 🏃‍♂️ Maratończyk | Małe spadki na długich dystansach | Ekonomia, wytrzymałość | Tempo długie, baza |
        | 🦶 Ultra-biegacz | Niesamowita wytrzymałość | Wytrwałość, psychika | Objętość, back-to-back |
        | 🔄 Wszechstronny | Zbalansowany profil | Adaptacja | Periodyzacja |

        """)


# ===========================================================================
# MAIN TAB RENDERER
# ===========================================================================


def render_running_tab(df_plot, threshold_pace, runner_weight):
    """
    Main Running analysis tab — pace-based equivalent of render_power_tab.

    Delegates to section-specific private helpers for readability and
    reduced cyclomatic complexity.
    """
    has_pace = "pace" in df_plot.columns

    if not has_pace:
        st.warning(
            "⚠️ Brak danych tempa (pace) w pliku. "
            "Zakładka Running wymaga kolumny `pace` lub `speed`."
        )
        return

    # Pace chart and zones
    _render_pace_chart(df_plot, threshold_pace)

    # 2. Pace zones
    _render_pace_zones(df_plot, threshold_pace)

    stats = calculate_pace_summary_stats(df_plot, threshold_pace)
    if stats.get("avg_pace"):
        st.metric("Średnie tempo", format_pace(stats["avg_pace"]) + " /km")

    st.subheader("Krzywa tempa (PDC)")
    pdc = calculate_pace_duration_curve(df_plot)
    valid_pdc = {duration: pace for duration, pace in pdc.items() if pace is not None}
    if valid_pdc:
        _render_pdc_metrics_and_chart(pdc, valid_pdc, threshold_pace)
    else:
        st.info("Za mało danych do obliczenia krzywej tempa.")
    _render_phenotype(pdc, runner_weight)
