import pandas as pd
import streamlit as st

from modules.calculations.repeatability import (
    calculate_repeatability_metrics,
    compare_session_to_baseline,
)


def render_comparison_tab(target_analysis_result: dict = None):
    """
    Render UI for comparing current session metrics with previous sessions or baseline.
    
    Args:
        target_analysis_result: Dict containing current session metrics (e.g., from Threshold analysis).
                                Structure: {'VT1_Watts': 200, 'VT2_Watts': 300, ...}
    """
    st.header("📈 Analiza Powtarzalności (Repeatability)")
    st.markdown("""
    Porównaj bieżącą sesję z poprzednimi, aby ocenić stabilność adaptacji.
    Algorytm oblicza **CV (Współczynnik Zmienności)** i identyfikuje metryki, które są **Niestabilne**.
    """)

    # 1. Input Previous Data
    st.subheader("1. Wprowadź Dane Historyczne (Ostatnie 3-5 sesji)")

    # Initialize session state for history if not exists
    if 'history_metrics' not in st.session_state:
        # Default with some dummy examples if empty? No, start empty.
        st.session_state.history_metrics = []

    with st.expander("➕ Dodaj Sesję Historyczną", expanded=True):
        c1, c2, c3 = st.columns(3)
        h_vt1 = c1.number_input("VT1 (W)", value=0, step=5, key="h_vt1")
        h_vt2 = c2.number_input("VT2 (W)", value=0, step=5, key="h_vt2")
        h_tau = c3.number_input("SmO2 Tau (s)", value=0.0, step=1.0, key="h_tau")

        c4, c5, c6 = st.columns(3)
        h_hr_vt1 = c4.number_input("HR @ VT1", value=0, step=1, key="h_hr_vt1")
        h_hr_vt2 = c5.number_input("HR @ VT2", value=0, step=1, key="h_hr_vt2")
        h_vo2 = c6.number_input("VO2max (ml/kg)", value=0.0, step=0.1, key="h_vo2")

        if st.button("Dodaj do Historii"):
            new_entry = {}
            if h_vt1 > 0: new_entry['VT1_Watts'] = h_vt1
            if h_vt2 > 0: new_entry['VT2_Watts'] = h_vt2
            if h_tau > 0: new_entry['SmO2_Tau'] = h_tau
            if h_hr_vt1 > 0: new_entry['HR_VT1'] = h_hr_vt1
            if h_hr_vt2 > 0: new_entry['HR_VT2'] = h_hr_vt2
            if h_vo2 > 0: new_entry['VO2max'] = h_vo2

            if new_entry:
                st.session_state.history_metrics.append(new_entry)
                st.success("Dodano sesję!")
            else:
                st.warning("Wpisz przynajmniej jedną wartość.")

    # Display History Table
    if st.session_state.history_metrics:
        st.caption(f"Liczba sesji w historii: {len(st.session_state.history_metrics)}")
        history_df = pd.DataFrame(st.session_state.history_metrics)
        st.dataframe(history_df)

        if st.button("🗑️ Wyczyść Historię"):
            st.session_state.history_metrics = []
            st.rerun()
    else:
        st.info("Brak danych historycznych. Dodaj je powyżej, aby zobaczyć analizę.")

    st.divider()

    # 2. Comparison Analysis
    if st.session_state.history_metrics:
        st.subheader("2. Wyniki Analizy Stabilności")

        # Calculate Baseline Stats (CV, Mean)
        baseline_stats = calculate_repeatability_metrics(st.session_state.history_metrics)

        # Prepare Comparison Data
        # Flatten stats for display table
        display_data = []

        for metric, stats in baseline_stats.items():
            current_val = target_analysis_result.get(metric, None) if target_analysis_result else None

            row = {
                "Metric": metric,
                "Baseline (Mean)": f"{stats['mean']:.1f}",
                "CV (%)": f"{stats['cv']:.1f}%",
                "Stability": stats['class']
            }

            # Comparison Logic
            status_emoji = ""
            if current_val is not None:
                row["Current Session"] = f"{current_val:.1f}"

                # Use comparison function
                comp_res = compare_session_to_baseline({metric: current_val}, baseline_stats)
                details = comp_res.get(metric, {})
                pct_diff = details.get('pct_diff', 0)
                is_sig = details.get('is_significant', False)
                status_text = details.get('status', 'Stable')

                row["Diff (%)"] = f"{pct_diff:+.1f}%"

                if is_sig:
                    status_emoji = "⚠️ Significant Change" if abs(pct_diff) > 5 else "❗ Possible Change"
                else:
                    status_emoji = "✅ Stable"

                row["Result"] = status_emoji
            else:
                row["Current Session"] = "-"
                row["Diff (%)"] = "-"
                row["Result"] = "-"

            display_data.append(row)

        comp_df = pd.DataFrame(display_data)
        st.dataframe(comp_df, hide_index=True)

        # Visual Summary
        st.markdown("### 📊 Interpretacja")

        unstable_metrics = [d['Metric'] for d in display_data if "Unstable" in d['Stability']]
        changed_metrics = [d['Metric'] for d in display_data if "Bound" in str(d.get('Result', '')) or "Change" in str(d.get('Result', ''))]

        if unstable_metrics:
            st.error(f"**Uwaga - Niska Powtarzalność Metryk:** {', '.join(unstable_metrics)}. Te wskaźniki mają wysoką zmienność (CV > 10%) i mogą być niewiarygodne do sterowania obciążeniem.")
        else:
            st.success("Wszystkie metryki historyczne wykazują dobrą lub umiarkowaną stabilność.")

        if changed_metrics:
            st.warning(f"**Wykryto zmianę adaptacyjną:** {', '.join(changed_metrics)}. Wartość bieżąca odbiega od bazy w sposób istotny statystycznie.")

    elif target_analysis_result:
        st.info("Wprowadź dane historyczne, aby porównać bieżące wyniki.")

