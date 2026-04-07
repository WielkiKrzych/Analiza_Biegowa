"""
Threshold Analysis and Training Plan Generator UI.

Provides:
- Step test analysis with VT1/VT2/LT1/LT2 detection
- Time range selection for step test portion
- Personalized training zones
- 4-week microcycle plan generator
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.thresholds import (
    analyze_step_test,
    calculate_training_zones_from_thresholds,
)


def render_threshold_analysis_tab(
    target_df, training_notes, uploaded_file_name, cp_input, ftp_input, max_hr_input
):
    """Render the threshold analysis and training plan tab."""
    st.header("🎯 Analiza Progów & Plan Treningowy")
    st.markdown(
        "Automatyczna detekcja progów wentylacyjnych i metabolicznych z testu schodkowego oraz generowanie planu treningowego."
    )

    if target_df is None or target_df.empty:
        st.error("Brak danych. Wgraj plik CSV z testem schodkowym.")
        return

    col_info = _detect_columns(target_df)
    if col_info is None:
        return

    intensity_col, intensity_label = _resolve_intensity_col(col_info)

    total_duration_sec, total_duration_min = _compute_duration(target_df)

    # =================================================================
    # SECTION 1: Power Preview & Time Range Selection
    # =================================================================
    st.subheader("📊 Wybór Zakresu Testu Schodkowego")
    st.markdown(
        "**Zaznacz zakres czasowy samego testu schodkowego** (bez rozgrzewki i schłodzenia)"
    )

    _render_preview_chart(target_df, col_info, intensity_col, intensity_label)

    test_start_sec, test_end_sec = _render_time_range_selector(total_duration_min)

    st.divider()

    # =================================================================
    # SECTION 2: Test Configuration
    # =================================================================
    _render_test_config(col_info, total_duration_min)

    st.divider()

    # =================================================================
    # SECTION 3: Threshold Detection
    # =================================================================
    st.subheader("📈 Detekcja Progów")

    step_duration = st.session_state.get("step_duration", 3)

    if st.button("🔍 Analizuj Test", type="primary"):
        with st.spinner("Analizuję test schodkowy..."):
            if "time" in target_df.columns:
                min_time = target_df["time"].min()
                mask = (target_df["time"] >= min_time + test_start_sec) & (
                    target_df["time"] <= min_time + test_end_sec
                )
            else:
                mask = (target_df.index >= test_start_sec) & (target_df.index <= test_end_sec)

            test_df = target_df[mask].copy()

            if len(test_df) < 100:
                st.error(
                    f"Za mało danych w wybranym zakresie ({len(test_df)} rekordów). Rozszerz zakres."
                )
            else:
                result = analyze_step_test(df=test_df, step_duration_sec=step_duration * 60)
                st.session_state["threshold_result"] = result

    # Display results
    if "threshold_result" in st.session_state:
        _display_threshold_results(st.session_state["threshold_result"])

    st.divider()

    # =================================================================
    # SECTION 4: Training Zones
    # =================================================================
    _render_training_zones(cp_input, ftp_input, max_hr_input)


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------


class _ColumnInfo:
    __slots__ = ("has_ve", "has_smo2", "has_watts", "has_pace", "has_hr", "hr_col", "pace_col")

    def __init__(
        self,
        has_ve: bool,
        has_smo2: bool,
        has_watts: bool,
        has_pace: bool,
        has_hr: bool,
        hr_col: Optional[str],
        pace_col: Optional[str],
    ):
        self.has_ve = has_ve
        self.has_smo2 = has_smo2
        self.has_watts = has_watts
        self.has_pace = has_pace
        self.has_hr = has_hr
        self.hr_col = hr_col
        self.pace_col = pace_col


def _detect_columns(target_df: pd.DataFrame) -> Optional[_ColumnInfo]:
    has_ve = "tymeventilation" in target_df.columns
    has_smo2 = "smo2" in target_df.columns
    has_watts = "watts" in target_df.columns
    has_pace = "pace" in target_df.columns or "pace_s" in target_df.columns
    has_hr = "hr" in target_df.columns or "heartrate" in target_df.columns
    hr_col = (
        "hr"
        if "hr" in target_df.columns
        else "heartrate"
        if "heartrate" in target_df.columns
        else None
    )
    pace_col = (
        "pace"
        if "pace" in target_df.columns
        else "pace_s"
        if "pace_s" in target_df.columns
        else None
    )

    if not has_watts and not has_pace:
        st.error(
            "Brak danych mocy (kolumna 'watts') ani tempa (kolumna 'pace'). Analiza niemożliwa."
        )
        return None

    return _ColumnInfo(has_ve, has_smo2, has_watts, has_pace, has_hr, hr_col, pace_col)


def _resolve_intensity_col(col_info: _ColumnInfo) -> tuple:
    if col_info.has_watts:
        return "watts", "Moc (W)"
    return col_info.pace_col, "Tempo (s/km)"


def _compute_duration(target_df: pd.DataFrame) -> tuple:
    if "time" in target_df.columns:
        total_sec = int(target_df["time"].max() - target_df["time"].min())
    else:
        total_sec = len(target_df)
    return total_sec, max(1, total_sec // 60)


# ---------------------------------------------------------------------------
# Section 1: Preview chart
# ---------------------------------------------------------------------------


def _render_preview_chart(
    target_df: pd.DataFrame,
    col_info: _ColumnInfo,
    intensity_col: str,
    intensity_label: str,
) -> None:
    fig = go.Figure()

    if "time" in target_df.columns:
        x_data = target_df["time"] / 60
    else:
        x_data = [x / 60 for x in range(len(target_df))]

    fig.add_trace(
        go.Scatter(
            x=x_data,
            y=target_df[intensity_col],
            name=intensity_label,
            fill="tozeroy",
            line=dict(color="#00d4aa", width=1),
            fillcolor="rgba(0, 212, 170, 0.3)",
        )
    )

    if col_info.has_hr and col_info.hr_col in target_df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=target_df[col_info.hr_col],
                name="HR",
                yaxis="y2",
                line=dict(color="#ff6b6b", width=1, dash="dot"),
            )
        )

    fig.update_layout(
        height=200,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(title="Czas (min)", showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(title=intensity_label, showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        yaxis2=dict(title="HR (bpm)", overlaying="y", side="right"),
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=1.15),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 1: Time range selector
# ---------------------------------------------------------------------------


def _render_time_range_selector(total_duration_min: int) -> tuple:
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        test_start_min = st.number_input(
            "⏱️ Start testu (min)",
            min_value=0,
            max_value=total_duration_min - 1,
            value=min(10, total_duration_min // 4),
            step=1,
            help="Minuta rozpoczęcia testu schodkowego (pomiń rozgrzewkę)",
        )
    with col2:
        test_end_min = st.number_input(
            "🏁 Koniec testu (min)",
            min_value=test_start_min + 1,
            max_value=total_duration_min,
            value=min(test_start_min + 30, total_duration_min),
            step=1,
            help="Minuta zakończenia testu schodkowego (przed schłodzeniem)",
        )
    with col3:
        st.metric("Czas testu", f"{test_end_min - test_start_min} min")

    return test_start_min * 60, test_end_min * 60


# ---------------------------------------------------------------------------
# Section 2: Test config
# ---------------------------------------------------------------------------


def _render_test_config(col_info: _ColumnInfo, total_duration_min: int) -> None:
    st.subheader("⚙️ Konfiguracja Testu")

    col1, col2 = st.columns(2)
    with col1:
        step_duration = st.slider(
            "Czas trwania stopnia (min)",
            min_value=1,
            max_value=5,
            value=3,
            step=1,
            help="Standardowy ramp test to 3 minuty na stopień",
        )
        st.caption(f"Oczekiwana liczba stopni: ~{total_duration_min // step_duration}")

    with col2:
        _render_data_availability(col_info)


def _render_data_availability(col_info: _ColumnInfo) -> None:
    items = []
    items.append("✅ Wentylacja (VE)" if col_info.has_ve else "❌ Wentylacja (VE)")
    items.append("✅ SmO2" if col_info.has_smo2 else "❌ SmO2")
    items.append("✅ Tętno (HR)" if col_info.has_hr else "❌ Tętno (HR)")
    st.markdown("**Dostępne dane:**")
    st.markdown(" | ".join(items))


# ---------------------------------------------------------------------------
# Section 3: Threshold detection
# ---------------------------------------------------------------------------


def _render_threshold_detection(
    target_df: pd.DataFrame, test_start_sec: int, test_end_sec: int
) -> None:
    st.subheader("📈 Detekcja Progów")

    if st.button("🔍 Analizuj Test", type="primary"):
        _run_step_test_analysis(target_df, test_start_sec, test_end_sec)

    if "threshold_result" in st.session_state:
        _display_threshold_results(st.session_state["threshold_result"])


def _run_step_test_analysis(
    target_df: pd.DataFrame, test_start_sec: int, test_end_sec: int
) -> None:
    with st.spinner("Analizuję test schodkowy..."):
        if "time" in target_df.columns:
            min_time = target_df["time"].min()
            mask = (target_df["time"] >= min_time + test_start_sec) & (
                target_df["time"] <= min_time + test_end_sec
            )
        else:
            mask = (target_df.index >= test_start_sec) & (target_df.index <= test_end_sec)

        test_df = target_df[mask].copy()

        if len(test_df) < 100:
            st.error(
                f"Za mało danych w wybranym zakresie ({len(test_df)} rekordów). Rozszerz zakres."
            )
        else:
            result = analyze_step_test(df=test_df, step_duration_sec=step_duration * 60)
            st.session_state["threshold_result"] = result


def _display_threshold_results(result) -> None:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        _render_threshold_metric(
            col1, "🟢 VT1 (Próg Tlenowy)", result.vt1_watts, "W", result.vt1_hr
        )
    with col2:
        _render_threshold_metric(
            col2, "🔴 VT2 (Próg Beztlenowy)", result.vt2_watts, "W", result.vt2_hr
        )
    with col3:
        _render_simple_metric(col3, "🟡 LT1 (SmO2)", result.smo2_1_watts, "W")
    with col4:
        _render_simple_metric(col4, "🟠 LT2 (SmO2)", result.smo2_2_watts, "W")

    if result.analysis_notes:
        with st.expander("📋 Notatki z analizy"):
            for note in result.analysis_notes:
                st.info(note)


def _render_threshold_metric(col, label: str, value, unit: str, hr_value) -> None:
    if value:
        col.metric(label, f"{value:.0f} {unit}")
        if hr_value:
            st.caption(f"@ {hr_value:.0f} bpm")
    else:
        col.metric(label.replace(" (Próg Tlenowy)", "").replace(" (Próg Beztlenowy)", ""), "—")


def _render_simple_metric(col, label: str, value, unit: str) -> None:
    if value:
        col.metric(label, f"{value:.0f} {unit}")
    else:
        col.metric(label, "—")


# ---------------------------------------------------------------------------
# Section 4: Training zones
# ---------------------------------------------------------------------------


def _render_training_zones(cp_input, ftp_input, max_hr_input) -> None:
    st.subheader("🎨 Strefy Treningowe")

    use_detected = st.checkbox(
        "Użyj wykrytych progów", value=True, disabled="threshold_result" not in st.session_state
    )

    vt1_for_zones, vt2_for_zones = _resolve_zone_thresholds(use_detected, ftp_input)

    zones = calculate_training_zones_from_thresholds(
        vt1_for_zones, vt2_for_zones, cp_input, max_hr_input
    )

    zone_data = _build_zone_table(zones)
    st.dataframe(pd.DataFrame(zone_data), use_container_width=True, hide_index=True)
    _render_zones_bar(zones["power_zones"])


def _resolve_zone_thresholds(use_detected: bool, ftp_input) -> tuple:
    if use_detected and "detected_vt1" in st.session_state:
        return int(st.session_state["detected_vt1"]), int(st.session_state["detected_vt2"])

    col1, col2 = st.columns(2)
    with col1:
        vt1 = st.number_input("VT1 (W)", min_value=50, max_value=500, value=int(ftp_input * 0.75))
    with col2:
        vt2 = st.number_input("VT2 (W)", min_value=50, max_value=600, value=ftp_input)
    return vt1, vt2


def _build_zone_table(zones: dict) -> list:
    zone_data = []
    for zone_name, (low, high) in zones["power_zones"].items():
        hr_range = zones["hr_zones"].get(zone_name, (None, None))
        zone_data.append(
            {
                "Strefa": zone_name.replace("_", " "),
                "Moc (W)": f"{low} - {high}",
                "Tętno (bpm)": f"{hr_range[0]} - {hr_range[1]}" if hr_range[0] else "—",
                "Opis": zones["zone_descriptions"].get(zone_name, ""),
            }
        )
    return zone_data


def _render_zones_bar(power_zones: dict):
    """Render a colored bar showing power zones."""
    colors = ["#3498db", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#9b59b6"]
    fig = go.Figure()

    for i, (zone, (low, high)) in enumerate(power_zones.items()):
        fig.add_trace(
            go.Bar(
                y=["Strefy Mocy"],
                x=[high - low],
                name=zone.replace("_", " "),
                orientation="h",
                marker_color=colors[i],
                text=f"{zone.split('_')[0]}<br>{low}-{high}W",
                textposition="inside",
                hovertemplate=f"🏷️ <b>{zone.replace('_', ' ')}</b><br>{low}-{high}W<extra></extra>",
            )
        )

    fig.update_layout(
        barmode="stack",
        height=100,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        xaxis=dict(title="Moc (W)", showgrid=False),
        yaxis=dict(showticklabels=False),
    )
    st.plotly_chart(fig, use_container_width=True)
