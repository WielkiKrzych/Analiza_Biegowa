"""
Drift Maps UI Module.

Displays Pace-HR-SmO2 scatter plots and drift analysis at constant pace.
"""
import json

import pandas as pd
import streamlit as st

from modules.physio_maps import (
    analyze_drift_pace_hr,
    detect_constant_pace_segments,
    scatter_pace_hr,
    scatter_pace_smo2,
    trend_at_constant_pace,
)


def _format_min_to_mmss(decimal_min: float) -> str:
    """Helper to convert decimal minutes to mm:ss string."""
    total_seconds = int(decimal_min * 60)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

def render_drift_maps_tab(df_plot: pd.DataFrame) -> None:
    """Render the Drift Maps tab in Performance section.
    
    Args:
        df_plot: Session DataFrame with pace, hr, and optionally smo2 data
    """
    st.header("📊 Drift Maps: Tempo-HR-SmO₂")

    st.markdown("""
    Analiza relacji między tempem, tętnem i saturacją mięśniową (SmO₂).
    **Drift HR** wskazuje na zmęczenie sercowo-naczyniowe, 
    **spadek SmO₂** sugeruje narastający deficyt tlenowy.
    """)

    # Check data availability
    has_hr = any(col in df_plot.columns for col in ['heartrate', 'hr', 'heart_rate', 'HeartRate'])
    has_smo2 = any(col in df_plot.columns for col in ['smo2', 'SmO2', 'muscle_oxygen'])
    has_pace = any(col in df_plot.columns for col in ['pace', 'pace_sec_per_km', 'tempo'])

    if not has_hr:
        st.warning("Brak danych HR - nie można wygenerować wykresów.")
        return

    if not has_pace:
        st.warning("Brak danych tempa - nie można wygenerować wykresów.")
        return

    # ===== SCATTER PLOTS =====
    st.subheader("🔵 Scatter Plots")

    col1, col2 = st.columns(2)

    with col1:
        fig_pace_hr = scatter_pace_hr(df_plot, title="Tempo vs HR")
        if fig_pace_hr:
            st.plotly_chart(fig_pace_hr, use_container_width=True)
        else:
            st.info("Za mało danych do wygenerowania wykresu Tempo vs HR.")

    with col2:
        if has_smo2:
            fig_pace_smo2 = scatter_pace_smo2(df_plot, title="Tempo vs SmO₂")
            if fig_pace_smo2:
                st.plotly_chart(fig_pace_smo2, use_container_width=True)
            else:
                st.info("Za mało danych SmO₂ do wygenerowania wykresu.")
        else:
            st.info("📉 Brak danych SmO₂ - wykres niedostępny.")

    st.divider()

    # ===== CONSTANT PACE SEGMENT ANALYSIS =====
    st.subheader("📏 Analiza Dryfu przy Stałym Temie")

    # Detect segments
    segments = detect_constant_pace_segments(df_plot, tolerance_pct=10, min_duration_sec=120)

    # Get pace column for manual input
    pace_col = None
    for col in ['pace', 'pace_sec_per_km', 'tempo']:
        if col in df_plot.columns:
            pace_col = col
            break

    if not segments:
        st.info("Nie wykryto segmentów stałego tempa (min. 2 minuty, ±10%).")

        # Manual pace input fallback
        st.markdown("**Ręczny wybór tempa:**")
        col_manual1, col_manual2 = st.columns(2)
        with col_manual1:
            default_pace = int(df_plot[pace_col].median()) if pace_col else 300
            pace_target_sec = st.number_input(
                "Docelowe tempo [s/km]",
                min_value=120,
                max_value=900,
                value=default_pace,
                step=10,
                key="drift_pace_target"
            )
        with col_manual2:
            tolerance = st.slider(
                "Tolerancja [%]",
                min_value=5,
                max_value=20,
                value=10,
                key="drift_tolerance"
            )

        fig_drift, drift_metrics = trend_at_constant_pace(
            df_plot, pace_target_sec, tolerance_pct=tolerance
        )

        if fig_drift:
            st.plotly_chart(fig_drift, use_container_width=True)
            _display_drift_metrics(drift_metrics)
        else:
            pace_min = pace_target_sec / 60.0
            st.warning(f"Brak danych w zakresie {pace_min:.2f} min/km ±{tolerance}%.")
    else:
        # Segment selector
        segment_options = [
            f"{i+1}. {(seg[2]/60.0):.2f} min/km ({_format_min_to_mmss((seg[1]-seg[0])/60)})"
            for i, seg in enumerate(segments)
        ]

        selected_idx = st.selectbox(
            "Wybierz segment stałego tempa:",
            range(len(segments)),
            format_func=lambda x: segment_options[x],
            key="segment_selector"
        )

        selected_segment = segments[selected_idx]
        pace_target_sec = selected_segment[2]

        col_opts1, col_opts2 = st.columns(2)
        with col_opts1:
            tolerance = st.slider(
                "Tolerancja [%]",
                min_value=5,
                max_value=20,
                value=10,
                key="drift_tolerance_seg"
            )

        fig_drift, drift_metrics = trend_at_constant_pace(
            df_plot, pace_target_sec, tolerance_pct=tolerance
        )

        if fig_drift:
            st.plotly_chart(fig_drift, use_container_width=True)
            _display_drift_metrics(drift_metrics)
        else:
            st.warning("Nie można obliczyć dryfu dla wybranego segmentu.")

    st.divider()

    # ===== OVERALL METRICS JSON (Hidden in Expander) =====
    with st.expander("📋 Metryki Sesji (JSON)"):
        overall_metrics = analyze_drift_pace_hr(df_plot)

        col_json1, col_json2 = st.columns([2, 1])

        with col_json1:
            st.json(overall_metrics)

        with col_json2:
            st.download_button(
                "📥 Pobierz JSON",
                data=json.dumps(overall_metrics, indent=2),
                file_name="drift_metrics.json",
                mime="application/json",
                key="download_drift_json"
            )

    # Interpretation
    with st.expander("📚 Interpretacja metryk"):
        st.markdown("""
        ### HR Drift Slope (bpm/min)
        - **> 0.5 bpm/min**: Znaczący drift - pogarszająca się wydolność sercowo-naczyniowa
        - **0.2 - 0.5 bpm/min**: Umiarkowany drift - normalne zmęczenie
        - **< 0.2 bpm/min**: Minimalny drift - dobra kondycja aerobowa
        
        ### SmO₂ Slope (%/min)
        - **< -0.3 %/min**: Postępujący deficyt tlenowy - przekroczenie progu
        - **-0.1 do -0.3 %/min**: Umiarkowany spadek - praca na granicy wydolności
        - **> -0.1 %/min**: Stabilna saturacja - praca w strefie tlenowej
        
        ### Korelacja Tempo-HR
        - **r > 0.7**: Silna zależność - typowa odpowiedź fizjologiczna
        - **r 0.4-0.7**: Umiarkowana zależność
        - **r < 0.4**: Słaba zależność - może wskazywać na problemy z danymi
        """)


def _display_drift_metrics(metrics) -> None:
    """Display drift metrics in a formatted way."""
    if metrics is None:
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        hr_drift = metrics.hr_drift_slope
        if hr_drift is not None:
            delta_color = "inverse" if hr_drift > 0.5 else "normal"
            st.metric(
                "HR Drift",
                f"{hr_drift:.2f} bpm/min",
                delta="znaczący" if hr_drift > 0.5 else "normalny",
                delta_color=delta_color
            )
        else:
            st.metric("HR Drift", "—")

    with col2:
        smo2_slope = metrics.smo2_slope
        if smo2_slope is not None:
            delta_color = "inverse" if smo2_slope < -0.3 else "normal"
            st.metric(
                "SmO₂ Slope",
                f"{smo2_slope:.2f} %/min",
                delta="spadek" if smo2_slope < -0.1 else "stabilny",
                delta_color=delta_color
            )
        else:
            st.metric("SmO₂ Slope", "—")

    with col3:
        st.metric(
            "Czas segmentu",
            _format_min_to_mmss(metrics.segment_duration_min)
        )

    with col4:
        # Display pace instead of power
        avg_pace_min = metrics.avg_pace / 60.0 if hasattr(metrics, 'avg_pace') else None
        if avg_pace_min is not None:
            st.metric(
                "Śr. tempo",
                f"{avg_pace_min:.2f} min/km"
            )
        else:
            st.metric("Śr. tempo", "—")
