import pandas as pd
import streamlit as st

from modules.calculations.repeatability import (
    calculate_repeatability_metrics,
    compare_session_to_baseline,
)


def _build_history_entry(
    h_vt1: int,
    h_vt2: int,
    h_tau: float,
    h_hr_vt1: int,
    h_hr_vt2: int,
    h_vo2: float,
) -> dict:
    raw: dict[str, float | int] = {
        "VT1_Watts": h_vt1,
        "VT2_Watts": h_vt2,
        "SmO2_Tau": h_tau,
        "HR_VT1": h_hr_vt1,
        "HR_VT2": h_hr_vt2,
        "VO2max": h_vo2,
    }
    return {k: v for k, v in raw.items() if v > 0}


def _build_display_rows(
    baseline_stats: dict,
    target_analysis_result: dict | None,
) -> list[dict]:
    display_data: list[dict] = []

    for metric, stats in baseline_stats.items():
        current_val = target_analysis_result.get(metric) if target_analysis_result else None

        row: dict = {
            "Metric": metric,
            "Baseline (Mean)": f"{stats['mean']:.1f}",
            "CV (%)": f"{stats['cv']:.1f}%",
            "Stability": stats["class"],
        }

        if current_val is None:
            row.update({"Current Session": "-", "Diff (%)": "-", "Result": "-"})
            display_data.append(row)
            continue

        row["Current Session"] = f"{current_val:.1f}"

        comp_res = compare_session_to_baseline({metric: current_val}, baseline_stats)
        details = comp_res.get(metric, {})
        pct_diff = details.get("pct_diff", 0)
        is_sig = details.get("is_significant", False)

        row["Diff (%)"] = f"{pct_diff:+.1f}%"
        row["Result"] = _comparison_status_emoji(is_sig, pct_diff)

        display_data.append(row)

    return display_data


def _comparison_status_emoji(is_significant: bool, pct_diff: float) -> str:
    if not is_significant:
        return "✅ Stable"
    if abs(pct_diff) > 5:
        return "⚠️ Significant Change"
    return "❗ Possible Change"


def _render_interpretation(display_data: list[dict]) -> None:
    unstable_metrics = [d["Metric"] for d in display_data if "Unstable" in d["Stability"]]
    changed_metrics = [
        d["Metric"]
        for d in display_data
        if "Bound" in str(d.get("Result", "")) or "Change" in str(d.get("Result", ""))
    ]

    if unstable_metrics:
        st.error(
            f"**Uwaga - Niska Powtarzalność Metryk:** {', '.join(unstable_metrics)}. "
            "Te wskaźniki mają wysoką zmienność (CV > 10%) i mogą być niewiarygodne "
            "do sterowania obciążeniem."
        )
    else:
        st.success("Wszystkie metryki historyczne wykazują dobrą lub umiarkowaną stabilność.")

    if changed_metrics:
        st.warning(
            f"**Wykryto zmianę adaptacyjną:** {', '.join(changed_metrics)}. "
            "Wartość bieżąca odbiega od bazy w sposób istotny statystycznie."
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

    if "history_metrics" not in st.session_state:
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
            new_entry = _build_history_entry(h_vt1, h_vt2, h_tau, h_hr_vt1, h_hr_vt2, h_vo2)
            if new_entry:
                st.session_state.history_metrics.append(new_entry)
                st.success("Dodano sesję!")
            else:
                st.warning("Wpisz przynajmniej jedną wartość.")

    # Display History Table
    if st.session_state.history_metrics:
        st.caption(f"Liczba sesji w historii: {len(st.session_state.history_metrics)}")
        st.dataframe(pd.DataFrame(st.session_state.history_metrics))

        if st.button("🗑️ Wyczyść Historię"):
            st.session_state.history_metrics = []
            st.rerun()
    else:
        st.info("Brak danych historycznych. Dodaj je powyżej, aby zobaczyć analizę.")

    st.divider()

    # 2. Comparison Analysis
    if not st.session_state.history_metrics:
        if target_analysis_result:
            st.info("Wprowadź dane historyczne, aby porównać bieżące wyniki.")
        return

    st.subheader("2. Wyniki Analizy Stabilności")

    baseline_stats = calculate_repeatability_metrics(st.session_state.history_metrics)
    display_data = _build_display_rows(baseline_stats, target_analysis_result)
    st.dataframe(pd.DataFrame(display_data), hide_index=True)

    # Visual Summary
    st.markdown("### 📊 Interpretacja")
    _render_interpretation(display_data)
