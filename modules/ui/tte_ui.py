"""
TTE (Time-to-Exhaustion) UI Module — running.

Displays TTE analysis for the current session at a chosen % of Critical Power
(running power). Adapted from the cycling analyzer: FTP → CP, cycling race
context → running context.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.tte import (
    TTEResult,
    compute_tte_result,
    export_tte_json,
    format_tte,
)


def _estimate_cp(watts: pd.Series) -> float:
    """Estimate running Critical Power as best 20-min average × 0.95.

    Falls back to the overall mean when the session is shorter than 20 minutes.
    """
    w = pd.to_numeric(watts, errors="coerce").fillna(0.0)
    window = 20 * 60  # 20 min at 1 Hz
    if len(w) >= window:
        best20 = w.rolling(window).mean().max()
        if best20 and best20 > 0:
            return float(best20 * 0.95)
    mean_w = float(w[w > 0].mean()) if (w > 0).any() else 0.0
    return mean_w


def render_tte_tab(
    df_plot: pd.DataFrame, cp: float = 0.0, uploaded_file_name: str = "manual_upload"
) -> None:
    """Render the TTE analysis tab.

    Args:
        df_plot: Session data with a running-power ``watts`` column.
        cp: Critical Power (running power at threshold), watts.
        uploaded_file_name: Original filename for record matching.
    """
    st.header("⏱️ Time-to-Exhaustion (TTE)")
    st.markdown(
        """
    Analiza maksymalnego czasu, przez który utrzymałeś zadaną moc biegową.
    TTE mierzy Twoją zdolność do utrzymania intensywności na poziomie progu (CP).
    """
    )

    if "watts" not in df_plot.columns:
        st.error("Brak danych mocy biegowej (watts) w pliku — wymagany np. Stryd.")
        return

    if not cp or cp <= 0:
        cp = _estimate_cp(df_plot["watts"])
        st.caption(f"ℹ️ CP nie podano — oszacowano z sesji: **{cp:.0f} W** (best 20 min × 0.95).")

    st.subheader("⚙️ Konfiguracja")
    col1, col2 = st.columns(2)
    with col1:
        target_pct = st.slider(
            "Docelowy % CP",
            min_value=70,
            max_value=120,
            value=100,
            step=5,
            help="Procent Critical Power, który chcesz analizować",
        )
    with col2:
        tol_pct = st.slider(
            "Tolerancja [%]",
            min_value=1,
            max_value=10,
            value=5,
            step=1,
            help="Dopuszczalne odchylenie od docelowej mocy",
        )

    power_series = df_plot["watts"]
    result = compute_tte_result(power_series, target_pct=target_pct, ftp=cp, tol_pct=tol_pct)

    st.subheader("📊 Wyniki Sesji")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "Maksymalny TTE",
            format_tte(result.tte_seconds),
            help="Najdłuższy ciągły czas utrzymania mocy w zadanym zakresie",
        )
    with c2:
        st.metric(
            "Zakres Mocy",
            f"{result.target_power_min:.0f} - {result.target_power_max:.0f} W",
            help=f"{target_pct}% CP ± {tol_pct}%",
        )
    with c3:
        if result.tte_seconds >= 3600:
            status = "🏆 Elitarny"
        elif result.tte_seconds >= 1800:
            status = "💪 Dobry"
        elif result.tte_seconds >= 600:
            status = "📈 Rozwijający się"
        else:
            status = "🔄 Do poprawy"
        st.metric("Ocena", status)

    _render_power_distribution_chart(df_plot, result)

    st.divider()
    with st.expander("📥 Eksport JSON"):
        json_data = export_tte_json(result)
        st.code(json_data, language="json")
        st.download_button(
            "Pobierz JSON",
            data=json_data,
            file_name=f"tte_{result.session_id}.json",
            mime="application/json",
        )

    with st.expander("📖 Time-to-Exhaustion (TTE) — Teoria i Fizjologia (bieganie)", expanded=False):
        st.markdown(
            """
### Definicja

**TTE** to maksymalny czas utrzymania zadanej intensywności przed wyczerpaniem. W bieganiu
TTE przy 100% CP mierzy **wytrzymałość progową** — jak długo utrzymasz moc/tempo na granicy
metabolizmu tlenowego i beztlenowego.

### Interpretacja TTE @ 100% CP (bieg)

| Poziom | TTE | Interpretacja |
|---|---|---|
| Początkujący | 15-25 min | Słaba wytrzymałość progowa |
| Amator | 25-40 min | Baza tlenowa w budowie |
| Zaawansowany | 40-55 min | Efektywny klirens mleczanu, dobra ekonomia biegu |
| Elitarny | 55+ min | Wysoka tolerancja progowa (poziom krajowy) |

### Mechanizmy ograniczające TTE
1. **Wyczerpanie D'** (dystansowy odpowiednik W') — skończona pojemność powyżej CS/CP.
2. **Akumulacja metabolitów** — spadek pH hamuje enzymy, spada siła skurczu.
3. **VO₂ slow component** — powyżej CP VO₂ dryfuje do VO₂max, SmO₂ spada do minimum.
4. **Zmęczenie centralne** — spadek rekrutacji jednostek motorycznych.

### TTE a dystanse biegowe
- **5 km:** biegany blisko/nieco powyżej CP — TTE @ ~105% CP.
- **10 km:** ~95-100% CP.
- **Półmaraton:** ~88-92% CP — durability + fueling stają się kluczowe.
- **Maraton:** ~80-85% CP — TTE mniej istotne niż odporność na zmęczenie i glikogen.

### Trening poprawiający TTE
| Typ | Mechanizm | Efekt |
|---|---|---|
| Interwały VO₂max (5×3min @ 110-120% CP) | ↑VO₂max, kinetyka VO₂ | +10-20% |
| Tempo/próg (2×20min @ 88-94% CP) | ↑próg mleczanowy, ekonomia | +15-25% |
| Długie wybiegania Z2 | kapilaryzacja, mitochondria | +5-15% |
        """
        )


def _render_power_distribution_chart(df_plot: pd.DataFrame, result: TTEResult) -> None:
    """Render running-power distribution chart with TTE range highlighted."""
    if "time_min" in df_plot.columns:
        x = df_plot["time_min"]
    elif "time" in df_plot.columns:
        x = df_plot["time"] / 60.0
    else:
        x = list(range(len(df_plot)))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df_plot["watts"],
            name="Moc biegowa",
            line=dict(color="#1f77b4", width=1),
            fill="tozeroy",
            fillcolor="rgba(31, 119, 180, 0.2)",
            hovertemplate="Moc: %{y:.0f} W<extra></extra>",
        )
    )
    fig.add_hrect(
        y0=result.target_power_min,
        y1=result.target_power_max,
        fillcolor="rgba(0, 255, 0, 0.1)",
        line=dict(color="green", width=1, dash="dash"),
        annotation_text=f"Zakres TTE ({result.target_pct}% ± {result.tolerance_pct}%)",
        annotation_position="top left",
    )
    fig.update_layout(
        template="plotly_dark",
        title="Rozkład Mocy Biegowej z Zakresem TTE",
        hovermode="x unified",
        xaxis=dict(title="Czas [min]", tickformat=".0f", hoverformat=".0f"),
        yaxis=dict(title="Moc [W]", tickformat=".0f"),
        height=450,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)
