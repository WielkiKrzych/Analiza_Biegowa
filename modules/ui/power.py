import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import hashlib
from typing import Dict, Any, Optional
from modules.config import Config
from modules.plots import apply_chart_style
from modules.calculations import (
    calculate_power_duration_curve,
    calculate_fatigue_resistance_index,
    count_match_burns,
    calculate_stamina_score,
    estimate_vlamax_from_pdc,
    get_stamina_interpretation,
    get_vlamax_interpretation,
    estimate_tte,
    calculate_durability_index,
    get_durability_interpretation,
)


def _hash_dataframe(df: pd.DataFrame) -> str:
    """Create a hash of DataFrame for cache key generation."""
    if df is None or df.empty:
        return "empty"
    # Use shape and sample of data for hash
    sample = df.head(100).to_json()
    shape_str = f"{df.shape}_{list(df.columns)}"
    return hashlib.md5(f"{shape_str}_{sample}".encode()).hexdigest()[:16]


def _hash_params(**kwargs) -> str:
    """Create a hash of parameters for cache key."""
    param_str = str(sorted(kwargs.items()))
    return hashlib.md5(param_str.encode()).hexdigest()[:16]


@st.cache_data(ttl=3600, show_spinner=False)
def _build_power_w_chart(df_resampled: pd.DataFrame, cp_input: int, w_prime_input: int) -> go.Figure:
    """Build power and W' balance chart (cached)."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_resampled["time_min"],
            y=df_resampled["watts_smooth"],
            name="Moc",
            fill="tozeroy",
            line=dict(color=Config.COLOR_POWER, width=1),
            hovertemplate="Moc: %{y:.0f} W<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_resampled["time_min"],
            y=df_resampled["w_prime_balance"],
            name="W' Bal",
            yaxis="y2",
            line=dict(color=Config.COLOR_HR, width=2),
            hovertemplate="W' Bal: %{y:.0f} J<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_dark",
        title="Zarządzanie Energią (Moc vs W')",
        hovermode="x unified",
        xaxis=dict(title="Czas [min]", tickformat=".0f", hoverformat=".0f"),
        yaxis=dict(title="Moc [W]"),
        yaxis2=dict(title="W' Balance [J]", overlaying="y", side="right", showgrid=False),
    )
    return fig


@st.cache_data(ttl=3600, show_spinner=False)
def _build_zones_chart(df_plot: pd.DataFrame, cp_input: int) -> Optional[go.Figure]:
    """Build power zones chart (cached)."""
    if "watts" not in df_plot.columns:
        return None
    
    bins = [
        0,
        0.55 * cp_input,
        0.75 * cp_input,
        0.90 * cp_input,
        1.05 * cp_input,
        1.20 * cp_input,
        10000,
    ]
    labels = [
        "Z1: Regeneracja",
        "Z2: Wytrzymałość",
        "Z3: Tempo",
        "Z4: Próg",
        "Z5: VO2Max",
        "Z6: Beztlenowa",
    ]
    colors = ["#A0A0A0", "#32CD32", "#FFD700", "#FF8C00", "#FF4500", "#8B0000"]
    df_z = df_plot.copy()
    df_z["Zone"] = pd.cut(df_z["watts"], bins=bins, labels=labels, right=False)
    pcts = (df_z["Zone"].value_counts().sort_index() / len(df_z) * 100).round(1)
    fig = px.bar(
        x=pcts.values,
        y=labels,
        orientation="h",
        text=pcts.apply(lambda x: f"{x}%"),
        color=labels,
        color_discrete_sequence=colors,
    )
    fig.update_layout(template="plotly_dark", showlegend=False)
    return apply_chart_style(fig)


@st.cache_data(ttl=3600, show_spinner=False)
def _calculate_power_metrics(df_plot: pd.DataFrame, cp_input: int, w_prime_input: int, rider_weight: float) -> Dict[str, Any]:
    """Calculate all power-related metrics (cached)."""
    pdc = {}
    if "watts" in df_plot.columns:
        pdc = calculate_power_duration_curve(df_plot)
    
    return {
        "pdc": pdc,
        "mmp_5s": pdc.get(5),
        "mmp_1min": pdc.get(60),
        "mmp_5min": pdc.get(300),
        "mmp_20min": pdc.get(1200),
    }


def _format_duration(seconds: int) -> str:
    """Format seconds to human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}" if secs else f"{mins}min"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h{mins:02d}" if mins else f"{hours}h"


def _format_tte(seconds: float) -> str:
    """Format TTE to human-readable string."""
    if seconds == float("inf"):
        return "∞ (sustainable)"
    elif seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"
    else:
        return ">1h"


def render_power_tab(
    df_plot, df_plot_resampled, cp_input, w_prime_input, rider_weight, vo2max_est=0
):
    st.subheader("Wykres Mocy i W'")
    # Use cached chart building
    fig_pw = _build_power_w_chart(df_plot_resampled, cp_input, w_prime_input)
    st.plotly_chart(fig_pw, use_container_width=True)

    st.info("""
    **💡 Interpretacja: Energia Beztlenowa (W' Balance)**

    Ten wykres pokazuje, ile "zapałek" masz jeszcze w pudełku.

    * **Czerwona Linia (W' Bal):** Poziom energii beztlenowej w Dżulach [J].
    * **Moc Krytyczna (CP):** To Twoja granica tlenowa (jak FTP, ale fizjologicznie precyzyjniejsza).

    **Jak to działa?**
    * **Moc < CP (Strefa Tlenowa):** Nie spalasz W'. Jeśli jechałeś mocno wcześniej, bateria się ładuje (czerwona linia rośnie).
    * **Moc > CP (Strefa Beztlenowa):** Zaczynasz "palić zapałki". Czerwona linia spada. Im mocniej depczesz, tym szybciej spada.
    * **W' = 0 J (Wyczerpanie):** "Odcina prąd". Nie jesteś w stanie utrzymać mocy powyżej CP ani sekundy dłużej. Musisz zwolnić, żeby zregenerować.

    **Scenariusze:**
    1.  **Interwały:** W' powinno spadać w trakcie powtórzenia (wysiłek) i rosnąć w przerwie (regeneracja). Jeśli nie wraca do 100% przed kolejnym startem, kumulujesz zmęczenie.
    2.  **Finisz:** Idealnie rozegrany wyścig to taki, gdzie W' spada do zera dokładnie na linii mety. Jeśli zostało Ci 10kJ, mogłeś finiszować mocniej. Jeśli spadło do zera 500m przed metą - przeszarżowałeś.
    3.  **Błędne CP:** Jeśli podczas spokojnej jazdy W' ciągle spada, Twoje CP jest ustawione za wysoko. Jeśli finiszujesz "w trupa", a W' pokazuje wciąż 50% - Twoje CP lub W' są niedoszacowane.
    """)

    st.subheader("Czas w Strefach Mocy (Time in Zones)")
    fig_z = _build_zones_chart(df_plot, cp_input)
    if fig_z is not None:
        st.plotly_chart(fig_z, use_container_width=True)

        st.info("""
        **💡 Interpretacja Treningowa:**
        * **Polaryzacja:** Dobry plan często ma dużo Z1/Z2 (baza) i trochę Z5/Z6 (bodziec), a mało "śmieciowych kilometrów" w Z3. Strefa Z3 to "szara strefa", która męczy, ale nie daje dużych korzyści adaptacyjnych, jednakże zużywa dużo glikogenu. Mimo tego, w triathlonie Z3 ma swoje miejsce (jazda na czas) i warto ją stosować taktycznie.
        * **Długie Wyścigi (Triathlon):** Większość czasu powinna być w Z2, z akcentami w Z4 (próg mleczanowy) i Z5 (VO2Max) dla poprawy wydolności. Spędzanie czasu w Z3 powinno być ograniczone ale taktyczne (np. jazda na czas).
        * **Sprinty i Criterium:** Więcej czasu w Z4/Z5/Z6, ale z odpowiednią regeneracją w Z1. Dużo interwałów wysokiej intensywności. Ważne jest, aby nie zaniedbywać Z2 dla budowy bazy tlenowej.
        * **Regeneracja:** Z1 to strefa regeneracyjna, idealna na dni odpoczynku lub bardzo lekkie sesje. Może pomóc w usuwaniu metabolitów i poprawie krążenia bez dodatkowego stresu. "Nie trenować" to też trening.
        * **Adaptacje Fizjologiczne:**
        * **Z1 (Szary):** Regeneracja i krążenie.
        * **Z2 (Zielony):** Kluczowe dla budowania mitochondriów i spalania tłuszczu. Podstawa wytrzymałości.
        * **Z3 (Żółty):** Mieszana strefa, poprawia ekonomię jazdy i tolerancję na wysiłek, ale może prowadzić do zmęczenia bez odpowiedniej regeneracji.
        * **Z4/Z5 (Pomarańczowy/Czerwony):** Budują tolerancję na mleczan i VO2Max, ale wymagają długiej regeneracji. Nie powinny dominować w planie treningowym.
        """)

        st.markdown("### 📚 Kompendium Fizjologii Stref (Deep Dive)")
        with st.expander("🟩 Z1/Z2: Fundament Tlenowy (< 75% CP)", expanded=True):
            st.markdown("""
            * **Metabolizm:** Dominacja Wolnych Kwasów Tłuszczowych (WKT). RER ~0.7-0.85. Oszczędność glikogenu.
            * **Fizjologia:**
                * Biogeneza mitochondriów (więcej "pieców" energetycznych).
                * Angiogeneza (tworzenie nowych naczyń włosowatych).
                * Wzrost aktywności enzymów oksydacyjnych.
            * **Biomechanika:** Rekrutacja głównie włókien wolnokurczliwych (Typ I).
            * **SmO2:** Stabilne, wysokie wartości (Równowaga Podaż=Popyt).
            * **Oddech (VT):** Poniżej VT1. Pełna konwersacja.
            * **Typowy Czas:** 1.5h - 6h+.
            """)

        with st.expander("🟨 Z3: Tempo / Sweet Spot (76-90% CP)"):
            st.markdown("""
            * **Metabolizm:** Miks węglowodanów i tłuszczów (RER ~0.85-0.95). Zaczyna się znaczne zużycie glikogenu.
            * **Fizjologia:** "Strefa Szara". Bodziec tlenowy, ale już z narastającym zmęczeniem.
            * **Zastosowanie:** Trening specyficzny pod 70.3 / Ironman (długie utrzymanie mocy).
            * **SmO2:** Stabilne, ale niższe niż w Z2. Możliwy powolny trend spadkowy.
            * **Oddech (VT):** Okolice VT1. Głęboki, rytmiczny oddech.
            * **Typowy Czas:** 45 min - 2.5h.
            """)

        with st.expander("🟧 Z4: Próg Mleczanowy (91-105% CP)"):
            st.markdown("""
            * **Metabolizm:** Dominacja glikogenu (RER ~1.0). Produkcja mleczanu równa się jego utylizacji (MLSS).
            * **Fizjologia:** Poprawa tolerancji na kwasicę. Zwiększenie magazynów glikogenu.
            * **Biomechanika:** Rekrutacja włókien pośrednich (Typ IIa).
            * **SmO2:** Granica równowagi. Utrzymuje się na stałym, niskim poziomie.
            * **Oddech (VT):** Pomiędzy VT1 a VT2. Oddech mocny, utrudniona mowa.
            * **Typowy Czas:** Interwały 8-30 min (łącznie do 60-90 min w sesji).
            """)

        with st.expander("🟥 Z5/Z6: VO2Max i Beztlenowa (> 106% CP)"):
            st.markdown("""
            * **Metabolizm:** Wyłącznie glikogen + Fosfokreatyna (PCr). RER > 1.1.
            * **Fizjologia:** Maksymalny pobór tlenu (pułap tlenowy). Szybkie narastanie długu tlenowego.
            * **Biomechanika:** Pełna rekrutacja wszystkich włókien (Typ IIx). Duży moment siły.
            * **SmO2:** Gwałtowny spadek (Desaturacja).
            * **Oddech (VT):** Powyżej VT2 (RCP). Hiperwentylacja.
            * **Typowy Czas:** Z5: 3-8 min. Z6: < 2 min.
            """)

    # Calculate PDC and metrics using cached function
    metrics = _calculate_power_metrics(df_plot, cp_input, w_prime_input, rider_weight)
    pdc = metrics["pdc"]
    mmp_5s = metrics["mmp_5s"]
    mmp_1min = metrics["mmp_1min"]
    mmp_5min = metrics["mmp_5min"]
    mmp_20min = metrics["mmp_20min"]

    # ===== KEY METRICS + TTE (NEW) =====
    st.subheader("📈 Kluczowe Metryki & Time to Exhaustion")

    col_km1, col_km2, col_km3, col_km4 = st.columns(4)

    with col_km1:
        if mmp_5s:
            tte_5s = estimate_tte(mmp_5s, cp_input, w_prime_input)
            st.metric(
                "⚡ MMP 5s",
                f"{mmp_5s:.0f} W",
                f"{mmp_5s / rider_weight:.1f} W/kg" if rider_weight > 0 else None,
            )
            st.caption(f"TTE: {_format_tte(tte_5s)}")
        else:
            st.metric("⚡ MMP 5s", "—")

    with col_km2:
        if mmp_1min:
            tte_1min = estimate_tte(mmp_1min, cp_input, w_prime_input)
            st.metric(
                "🔥 MMP 1min",
                f"{mmp_1min:.0f} W",
                f"{mmp_1min / rider_weight:.1f} W/kg" if rider_weight > 0 else None,
            )
            st.caption(f"TTE: {_format_tte(tte_1min)}")
        else:
            st.metric("🔥 MMP 1min", "—")

    with col_km3:
        if mmp_5min:
            tte_5min = estimate_tte(mmp_5min, cp_input, w_prime_input)
            st.metric(
                "💪 MMP 5min",
                f"{mmp_5min:.0f} W",
                f"{mmp_5min / rider_weight:.1f} W/kg" if rider_weight > 0 else None,
            )
            st.caption(f"TTE: {_format_tte(tte_5min)}")
        else:
            st.metric("💪 MMP 5min", "—")

    with col_km4:
        if mmp_20min:
            tte_20min = estimate_tte(mmp_20min, cp_input, w_prime_input)
            st.metric(
                "🏔️ MMP 20min",
                f"{mmp_20min:.0f} W",
                f"{mmp_20min / rider_weight:.1f} W/kg" if rider_weight > 0 else None,
            )
            st.caption(f"TTE: {_format_tte(tte_20min)}")
        else:
            st.metric("🏔️ MMP 20min", "—")

    st.divider()

    # ===== DURABILITY INDEX (NEW) =====
    st.subheader("🛡️ Durability Index")

    durability, avg_first, avg_second = calculate_durability_index(df_plot, min_duration_min=20)

    if durability is not None:
        durability_interp = get_durability_interpretation(durability)

        col_d1, col_d2, col_d3 = st.columns(3)

        with col_d1:
            delta_color = "normal" if durability >= 90 else "inverse"
            st.metric(
                "Durability Index",
                f"{durability:.1f}%",
                delta=f"{durability - 100:.1f}%" if durability < 100 else "+0%",
                delta_color=delta_color,
                help="Stosunek średniej mocy w 2. połowie do 1. połowy treningu",
            )

        with col_d2:
            st.metric("Śr. Moc (1. połowa)", f"{avg_first:.0f} W")

        with col_d3:
            st.metric("Śr. Moc (2. połowa)", f"{avg_second:.0f} W")

        st.info(f"**Interpretacja:** {durability_interp}")
    else:
        st.info("Potrzeba minimum 20 minut treningu do obliczenia Durability Index.")

    st.divider()

    # ===== STAMINA SCORE =====
    st.subheader("🏆 Stamina Score")

    if mmp_5min and mmp_20min and rider_weight > 0 and cp_input > 0:
        fri = calculate_fatigue_resistance_index(mmp_5min, mmp_20min)

        # Use provided VO2max or estimate from 5min power
        if vo2max_est <= 0:
            power_per_kg = mmp_5min / rider_weight
            vo2max_est = 16.61 + 8.87 * power_per_kg

        stamina = calculate_stamina_score(vo2max_est, fri, w_prime_input, cp_input, rider_weight)
        stamina_interp = get_stamina_interpretation(stamina)

        # VLamax estimation
        vlamax = estimate_vlamax_from_pdc(pdc, rider_weight)
        vlamax_interp = get_vlamax_interpretation(vlamax) if vlamax else "Niewystarczające dane"

        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            st.metric(
                "Stamina Score", f"{stamina:.0f}/100", help="Composite metric: VO2max + FRI + CP/kg"
            )
            st.caption(stamina_interp)

        with col_s2:
            st.metric(
                "Est. VO2max",
                f"{vo2max_est:.1f} ml/kg/min",
                help="Szacowane z 5-minutowej mocy max",
            )

        with col_s3:
            if vlamax:
                st.metric(
                    "Est. VLamax",
                    f"{vlamax:.2f} mmol/L/s",
                    help="Szacowane z kształtu krzywej mocy",
                )
                st.caption(vlamax_interp)
            else:
                st.metric("Est. VLamax", "—")

        with st.expander("📚 Jak interpretować te metryki?"):
            st.markdown("""
            ### Stamina Score (0-100)
            Composite metric łącząca wydolność tlenową, zdolność do utrzymania mocy i moc względną.
            
            | Score | Poziom |
            |-------|--------|
            | 80+ | World Tour / Pro Continental |
            | 65-80 | Elitarny amator |
            | 50-65 | Wytrenowany kolarz klubowy |
            | 35-50 | Amator średni |
            | <35 | Początkujący |
            
            ### Fatigue Resistance Index (FRI)
            Stosunek MMP20 do MMP5. Im bliżej 1.0, tym lepiej utrzymujesz moc w czasie.
            
            - **0.95+**: Wyjątkowa wytrzymałość (diesele jak Froome)
            - **0.90-0.95**: Poziom Pro
            - **0.85-0.90**: Dobrze wytrenowany amator
            - **<0.80**: Profil sprinterski
            
            ### VLamax (Estimated)
            Maksymalna szybkość produkcji mleczanu. Niższa wartość = lepsza wydolność tlenowa.
            
            - **>0.9**: Sprinter - wysoka glikoliza
            - **0.5-0.7**: All-rounder
            - **<0.4**: Climber/TT specialist
            """)
    else:
        st.info("Potrzeba danych CP, wagi i minimum 20 minut treningu do obliczenia Stamina Score.")
