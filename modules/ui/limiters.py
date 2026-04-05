import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from typing import Optional


def render_limiters_tab(df_plot, cp_input, vt2_vent):
    st.header("Analiza Limiterów Fizjologicznych (INSCYD-style)")
    st.markdown(
        "Identyfikujemy Twoje ograniczenia metaboliczne i typ zawodniczy na podstawie danych treningowych."
    )

    # Normalize columns
    df_plot.columns = df_plot.columns.str.lower().str.strip()

    # Handle HR aliases
    if "hr" not in df_plot.columns:
        for alias in ["heartrate", "heart_rate", "bpm"]:
            if alias in df_plot.columns:
                df_plot.rename(columns={alias: "hr"}, inplace=True)
                break

    has_hr = "hr" in df_plot.columns
    has_ve = any(c in df_plot.columns for c in ["tymeventilation", "ve", "ventilation"])
    has_smo2 = "smo2" in df_plot.columns
    has_watts = "watts" in df_plot.columns

    # Sport detection: running uses pace, cycling uses watts
    is_running = "pace" in df_plot.columns and "watts" not in df_plot.columns

    if is_running:
        _render_running_mode(df_plot)
    elif has_watts:
        _render_cycling_mode(df_plot, cp_input, vt2_vent, has_hr, has_ve, has_smo2)
    else:
        st.error("Brakuje danych mocy (Watts) do analizy limiterów.")


# ---------------------------------------------------------------------------
# RUNNING MODE helpers
# ---------------------------------------------------------------------------


def _classify_runner_phenotype(pace_ratio: float) -> tuple:
    """Return (profile_label, profile_color, strength, weakness, phenotype)."""
    if pace_ratio < 1.03:
        return (
            "🏃 Maratończyk / Ultra",
            "#4ecdc4",
            "Doskonała wytrzymałość, utrzymuje tempo na długich dystansach",
            "Może brakować dynamiki na krótkich odcinkach",
            "marathoner",
        )
    if pace_ratio < 1.06:
        return (
            "⚖️ Wszechstronny biegacz",
            "#ffd93d",
            "Zbalansowany profil, dobry na różnych dystansach",
            "Brak dominującej specjalizacji",
            "all_rounder",
        )
    if pace_ratio < 1.10:
        return (
            "🏃‍♂️ Średniak (5K-10K)",
            "#45b7d1",
            "Dobre połączenie szybkości i wytrzymałości",
            "Może słabnąć na dystansach powyżej 10K",
            "middle_distance",
        )
    return (
        "⚡ Sprinter / Miler",
        "#ff6b6b",
        "Wysoka prędkość maksymalna, dynamika",
        "Szybki spadek tempa na dłuższych dystansach",
        "sprinter",
    )


def _compute_best_paces(df_plot: pd.DataFrame) -> tuple:
    """Return (best_1min, best_5min, best_10min, best_20min) or None per value."""
    windows = {"1min": 60, "5min": 300, "10min": 600, "20min": 1200}
    best = {}
    for label, w in windows.items():
        col = f"pace_{label}"
        df_plot[col] = df_plot["pace"].rolling(window=w, min_periods=w).mean()
        best[label] = df_plot[col].min() if not df_plot[col].isna().all() else None
    return best["1min"], best["5min"], best["10min"], best["20min"]


def _render_runner_profile(best_5min: Optional[float], best_10min: Optional[float]) -> tuple:
    """Display runner phenotype and return (phenotype, profile_color, pace_ratio)."""
    if not best_5min or not best_10min or best_5min <= 0:
        st.info("Trening zbyt krótki dla pełnej analizy profilu (min. 10 min).")
        return "unknown", "#888", None

    pace_ratio = best_10min / best_5min
    profile, profile_color, strength, weakness, phenotype = _classify_runner_phenotype(pace_ratio)

    st.markdown(
        f"""
    <div style="padding:15px; border-radius:8px; border:2px solid {profile_color}; background-color: #222; margin-top:15px;">
        <h4 style="margin:0; color:{profile_color};">{profile}</h4>
        <p style="margin:10px 0 0 0;"><b>💪 Mocna strona:</b> {strength}</p>
        <p style="margin:5px 0 0 0;"><b>⚠️ Do poprawy:</b> {weakness}</p>
        <p style="margin:5px 0 0 0; font-size:0.85em; color:#888;">Ratio 10min/5min: {pace_ratio:.3f}</p>
    </div>
    """,
        unsafe_allow_html=True,
    )
    return phenotype, profile_color, pace_ratio


def _render_pace_metrics(best_1min, best_5min, best_10min, best_20min) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Najlepsze 1 min", f"{best_1min / 60:.2f} min/km" if best_1min else "N/A")
    col2.metric("Najlepsze 5 min", f"{best_5min / 60:.2f} min/km" if best_5min else "N/A")
    col3.metric("Najlepsze 10 min", f"{best_10min / 60:.2f} min/km" if best_10min else "N/A")
    col4.metric("Najlepsze 20 min", f"{best_20min / 60:.2f} min/km" if best_20min else "N/A")


def _compute_limiter_scores(best_1min, best_5min, best_20min, avg_pace) -> tuple:
    """Return (speed_score, endurance_score, threshold_score)."""
    speed_drop = (best_1min / best_5min) if best_5min > 0 else 1
    speed_score = max(0, min(100, (1 - speed_drop) * 1000 + 50))

    endurance_drop = (best_20min / best_5min) if best_5min > 0 else 1.5
    endurance_score = max(0, min(100, (1.2 - endurance_drop) * 500))

    threshold_pace_est = best_20min * 1.01 if best_20min else best_5min * 1.1
    threshold_score = (
        max(0, min(100, (threshold_pace_est / avg_pace - 0.8) * 250)) if avg_pace else 50
    )

    return speed_score, endurance_score, threshold_score


def _render_limiter_radar(
    speed_score: float, endurance_score: float, threshold_score: float, weakest: str
) -> None:
    categories = ["Szybkość", "Wytrzymałość", "Próg"]
    values = [speed_score, endurance_score, threshold_score]
    values_closed = values + [values[0]]
    categories_closed = categories + [categories[0]]

    fig_radar = go.Figure()
    fig_radar.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            name="Profil Biegowy",
            line=dict(color="#00cc96"),
            fillcolor="rgba(0, 204, 150, 0.3)",
            hovertemplate="%{theta}: <b>%{r:.0f}</b><extra></extra>",
        )
    )

    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        template="plotly_dark",
        title="Radar Limitatorów Biegowych",
        height=400,
    )

    st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown(f"""
    ### 🔍 Diagnoza Limiterów

    | Limiter | Wynik | Status |
    |---------|-------|--------|
    | **Szybkość** | {speed_score:.0f} | {"🔴 Najsłabszy" if weakest == "Szybkość" else "🟢 OK"} |
    | **Wytrzymałość** | {endurance_score:.0f} | {"🔴 Najsłabszy" if weakest == "Wytrzymałość" else "🟢 OK"} |
    | **Próg** | {threshold_score:.0f} | {"🔴 Najsłabszy" if weakest == "Próg" else "🟢 OK"} |

    **Główny Limiter: {weakest}**
    """)


def _render_training_recommendations(weakest: str, phenotype: str) -> None:
    """Display limiter-specific and phenotype-specific training recommendations."""
    st.subheader("💡 Rekomendacje Treningowe")

    _render_limiter_recommendation(weakest)
    st.markdown("#### 🎯 Porady dla Twojego Fenotypu")
    _render_phenotype_advice(phenotype)


def _render_limiter_recommendation(weakest: str) -> None:
    if weakest == "Wytrzymałość":
        st.info("""
        **🏃 Ograniczenie: Wytrzymałość Aerobowa**

        Twoja szybkość na krótszych dystansach nie przekłada się na dłuższe wysiłki.

        **Sugerowane treningi:**
        - Dodaj więcej długich biegów Z2 (80% tygodniowego objętości)
        - Progressive long runs - zwiększaj dystans o 10% co tydzień
        - Biegi ciągłe 45-90 min w tempie konwersacyjnym
        - Cross-training na rowerze dla objętości bez obciążenia
        """)
    elif weakest == "Szybkość":
        st.info("""
        **⚡ Ograniczenie: Szybkość**

        Masz dobrą wytrzymałość, ale brakuje Ci wyższej prędkości maksymalnej.

        **Sugerowane treningi:**
        - Dodaj interwały 200-400m na torze, 2x/tydzień
        - Strides 4-6x 100m po łatwych biegach
        - Hill sprints 8-10x 10-15 sek na stromym podbiegu
        - Pływanie/siłownia dla dynamiki (plyometrics)
        """)
    else:
        st.info("""
        **📈 Ograniczenie: Wydolność Progowa**

        Twój próg mleczanowy jest zbyt nisko względem potencjału.

        **Sugerowane treningi:**
        - Tempo runs 20-40 min w strefie Z4, 1x/tydzień
        - Interwały progowe: 3-4x 10-15 min @ tempo 10K
        - Cruise intervals: 6-8x 5 min @ pół-maratońskie tempo
        - Podwójne sesje progowe w okresie specjalnym
        """)


def _render_phenotype_advice(phenotype: str) -> None:
    advice_map = {
        "marathoner": """
        **Maratończyk/Ultra** - Twoja wytrzymałość jest Twoją siłą!
        - Skup się na maratonach i ultra dystansach
        - Regularne biegi 2-3h budują economy
        - Trening na czczo dla adaptacji tłuszczowych
        """,
        "all_rounder": """
        **Wszechstronny** - Możesz startować na każdym dystansie!
        - Sezonowo specjalizuj się (wiosna 10K, jesień maraton)
        - Utrzymuj zróżnicowany trening
        - Testuj siebie na różnych dystansach
        """,
        "middle_distance": """
        **Średni dystans (5K-10K)** - Idealny balans szybkość/wytrzymałość!
        - Skup się na 5K i 10K - tu masz potencjał
        - VO2max intervals 4-6x 3-5 min @ 3K-5K pace
        - Tempo runs budują specyfikę wyścigową
        """,
        "sprinter": """
        **Sprinter/Miler** - Wykorzystaj swoją szybkość!
        - Mile (1609m) i 1500m to Twoje dystanse
        - Wiele treningu szybkościowego (150-400m)
        - Siłownia i plyometrics dla eksplozywności
        """,
    }
    text = advice_map.get(phenotype)
    if text:
        st.success(text)


def _render_running_mode(df_plot: pd.DataFrame) -> None:
    """Full running-mode limiter analysis."""
    st.header("Analiza Limiterów Biegowych")
    st.markdown(
        "Identyfikujemy Twój profil biegacza i ograniczenia wydolnościowe na podstawie tempa."
    )

    # --- SEKCJA 1: PROFIL BIEGACZA ---
    st.subheader("🏃 Profil Biegacza")

    best_1min, best_5min, best_10min, best_20min = _compute_best_paces(df_plot)
    _render_pace_metrics(best_1min, best_5min, best_10min, best_20min)

    phenotype, profile_color, pace_ratio = _render_runner_profile(best_5min, best_10min)

    st.divider()

    # --- SEKCJA 2: ANALIZA LIMITERÓW BIEGOWYCH ---
    st.subheader("📊 Analiza Limiterów Biegowych")

    if best_1min and best_5min and best_20min:
        speed_score, endurance_score, threshold_score = _compute_limiter_scores(
            best_1min, best_5min, best_20min, df_plot["pace"].mean()
        )

        limiters = {
            "Szybkość": speed_score,
            "Wytrzymałość": endurance_score,
            "Próg": threshold_score,
        }
        weakest = min(limiters, key=lambda k: limiters[k])

        _render_limiter_radar(speed_score, endurance_score, threshold_score, weakest)

        st.divider()

        # --- SEKCJA 3: REKOMENDACJE ---
        _render_training_recommendations(weakest, phenotype)
    else:
        st.warning("Za mało danych do pełnej analizy limiterów (wymagane min. 20 min danych).")

    st.divider()

    # --- SEKCJA 4: TEORIA PROFILÓW BIEGOWYCH ---
    _render_running_theory_expander()


def _render_running_theory_expander() -> None:
    with st.expander("📚 Teoria: Typy Biegaczy i Profilowanie", expanded=False):
        st.markdown("""
        ## Profilowanie Biegaczy

        Podobnie jak w kolarstwie (INSCYD), biegacze mają różne profile metaboliczne:

        ### 1. Sprinter / Miler
        * Wysoki VLaMax, duża moc anaerobowa
        * Szybki na 400m-1500m, duży spadek tempa na dłuższych dystansach
        * Przykłady: Noah Lyles, Jakob Ingebrigtsen (1500m)

        ### 2. Średni dystans (5K-10K)
        * Zbalansowany VO2max i wytrzymałość
        * Dobre tempo na 5K-10K
        * Przykłady: Joshua Cheptegei, Jakob Ingebrigtsen (5K)

        ### 3. Maratończyk
        * Niski VLaMax, wysoka ekonomia biegu
        * Utrzymuje równe tempo przez 2-3h
        * Przykłady: Eliud Kipchoge, Kelvin Kiptum

        ### 4. Ultra-biegacz
        * Ekstremalna wytrzymałość, odporność mięśniowa
        * Specjalizuje się w dystansach > maratonu
        * Przykłady: Kilian Jornet, Jim Walmsley

        ---

        ## Jak Zmienić Swój Profil?

        | Cel | Strategia | Przykładowe Treningi |
        |-----|-----------|---------------------|
        | ⬆️ **Szybkość** | Sprinty, interwały krótkie | 10x200m @ max, Hill sprints |
        | ⬆️ **VO2max** | Interwały 3-5 min | 5x4 min @ 5K pace |
        | ⬆️ **Próg** | Tempo runs | 3x15 min @ 10K pace |
        | ⬆️ **Wytrzymałość** | Długie biegi | 90-180 min Z2 |

        ---

        ## Wskaźnik FRI (Fatigue Resistance Index)

        FRI = tempo 10K / tempo 5K

        * FRI < 1.03: Wyjątkowa wytrzymałość (maratończyk/ultra)
        * FRI 1.03-1.06: Dobra wytrzymałość
        * FRI 1.06-1.10: Przeciętna
        * FRI > 1.10: Niska wytrzymałość (sprinter)

        *Analiza oparta na stosunku tempa 10min/5min.*
        """)


# ---------------------------------------------------------------------------
# CYCLING MODE helpers
# ---------------------------------------------------------------------------


def _classify_cycling_profile(anaerobic_ratio: float) -> tuple:
    """Return (profile, vlamax_est, profile_color, strength, weakness)."""
    if anaerobic_ratio > 1.08:
        return (
            "🏃 Sprinter / Puncheur",
            "Wysoki (>0.5 mmol/L/s)",
            "#ff6b6b",
            "Krótkie, dynamiczne ataki i sprinty",
            "Dłuższe wysiłki powyżej progu",
        )
    if anaerobic_ratio < 0.95:
        return (
            "🚴 Climber / TT Specialist",
            "Niski (<0.4 mmol/L/s)",
            "#4ecdc4",
            "Długie, równe tempo, wspinaczki",
            "Reaktywność na ataki, sprint finiszowy",
        )
    return (
        "⚖️ All-Rounder",
        "Średni (0.4-0.5 mmol/L/s)",
        "#ffd93d",
        "Wszechstronność",
        "Brak dominującej cechy",
    )


def _render_cycling_profile(df_plot: pd.DataFrame) -> Optional[float]:
    """Render metabolic profile section. Return anaerobic_ratio or None."""
    st.subheader("🧬 Profil Metaboliczny (Szacunkowy)")

    df_plot["mmp_1min"] = df_plot["watts"].rolling(window=60, min_periods=60).mean()
    df_plot["mmp_5min"] = df_plot["watts"].rolling(window=300, min_periods=300).mean()
    df_plot["mmp_20min"] = df_plot["watts"].rolling(window=1200, min_periods=1200).mean()

    mmp_1min = df_plot["mmp_1min"].max() if not df_plot["mmp_1min"].isna().all() else 0
    mmp_5min = df_plot["mmp_5min"].max() if not df_plot["mmp_5min"].isna().all() else 0
    mmp_20min = df_plot["mmp_20min"].max() if not df_plot["mmp_20min"].isna().all() else 0

    if mmp_20min <= 0:
        st.info("Trening zbyt krótki dla analizy profilu metabolicznego (min. 20 min).")
        return None

    anaerobic_ratio = mmp_5min / mmp_20min
    mmp_1min / mmp_5min if mmp_5min > 0 else 1.0

    profile, vlamax_est, profile_color, strength, weakness = _classify_cycling_profile(
        anaerobic_ratio
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Typ Zawodnika", profile)
    col2.metric("Est. VLaMax", vlamax_est)
    col3.metric("Ratio 5min/20min", f"{anaerobic_ratio:.2f}")

    st.markdown(
        f"""
    <div style="padding:15px; border-radius:8px; border:2px solid {profile_color}; background-color: #222;">
        <p style="margin:0;"><b>💪 Mocna strona:</b> {strength}</p>
        <p style="margin:5px 0 0 0;"><b>⚠️ Do poprawy:</b> {weakness}</p>
    </div>
    """,
        unsafe_allow_html=True,
    )
    return anaerobic_ratio


def _render_cycling_radar(
    df_plot: pd.DataFrame,
    cp_input: float,
    vt2_vent: float,
    has_hr: bool,
    has_ve: bool,
    has_smo2: bool,
) -> None:
    """Render the cycling-mode system-load radar chart."""
    if not (has_hr or has_ve or has_smo2):
        return

    st.subheader("📊 Radar Obciążenia Systemów")

    window_options = {
        "1 min (Anaerobic)": 60,
        "5 min (VO2max)": 300,
        "20 min (FTP)": 1200,
        "60 min (Endurance)": 3600,
    }
    selected_window_name = st.selectbox(
        "Wybierz okno analizy (MMP):", list(window_options.keys()), index=1
    )
    window_sec = window_options[selected_window_name]

    df_plot["rolling_watts"] = (
        df_plot["watts"].rolling(window=window_sec, min_periods=window_sec).mean()
    )

    if df_plot["rolling_watts"].isna().all():
        st.warning(f"Trening jest krótszy niż {window_sec / 60:.0f} min. Wybierz krótsze okno.")
        return

    peak_idx = df_plot["rolling_watts"].idxmax()
    if pd.isna(peak_idx):
        return

    start_idx = max(0, peak_idx - window_sec + 1)
    df_peak = df_plot.iloc[start_idx : peak_idx + 1]

    pct_hr, pct_ve, pct_smo2_util, pct_power, peak_w_avg = _compute_cycling_load_percentages(
        df_plot, df_peak, has_hr, has_ve, has_smo2, vt2_vent, cp_input
    )

    categories = [
        "Serce (% HRmax)",
        "Płuca (% VEmax)",
        "Mięśnie (% Desat)",
        "Moc (% CP)",
    ]
    values = [pct_hr, pct_ve, pct_smo2_util, pct_power]
    values += [values[0]]
    categories += [categories[0]]

    fig_radar = go.Figure()
    fig_radar.add_trace(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            name=selected_window_name,
            line=dict(color="#00cc96"),
            fillcolor="rgba(0, 204, 150, 0.3)",
            hovertemplate="%{theta}: <b>%{r:.1f}%</b><extra></extra>",
        )
    )

    max_val = max(values)
    range_max = 100 if max_val < 100 else (max_val + 10)

    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, range_max])),
        template="plotly_dark",
        title=f"Profil Obciążenia: {selected_window_name} ({peak_w_avg:.0f} W)",
        height=450,
    )

    st.plotly_chart(fig_radar, use_container_width=True)

    _render_cycling_diagnosis(selected_window_name, pct_hr, pct_ve, pct_smo2_util, pct_power)


def _compute_cycling_load_percentages(
    df_plot: pd.DataFrame,
    df_peak: pd.DataFrame,
    has_hr: bool,
    has_ve: bool,
    has_smo2: bool,
    vt2_vent: float,
    cp_input: float,
) -> tuple:
    """Return (pct_hr, pct_ve, pct_smo2_util, pct_power, peak_w_avg)."""
    peak_hr_avg = df_peak["hr"].mean() if has_hr else 0
    max_hr_user = df_plot["hr"].max() if has_hr else 1
    pct_hr = (peak_hr_avg / max_hr_user * 100) if max_hr_user > 0 else 0

    col_ve_nm = next(
        (c for c in ["tymeventilation", "ve", "ventilation"] if c in df_plot.columns),
        None,
    )
    peak_ve_avg = df_peak[col_ve_nm].mean() if col_ve_nm else 0
    max_ve_user = vt2_vent * 1.1 if vt2_vent > 0 else 1
    pct_ve = (peak_ve_avg / max_ve_user * 100) if max_ve_user > 0 else 0

    peak_smo2_avg = df_peak["smo2"].mean() if has_smo2 else 100
    pct_smo2_util = 100 - peak_smo2_avg

    peak_w_avg = df_peak["watts"].mean()
    pct_power = (peak_w_avg / cp_input * 100) if cp_input > 0 else 0

    return pct_hr, pct_ve, pct_smo2_util, pct_power, peak_w_avg


def _render_cycling_diagnosis(
    selected_window_name: str,
    pct_hr: float,
    pct_ve: float,
    pct_smo2_util: float,
    pct_power: float,
) -> None:
    limiting_factor = (
        "Serce"
        if pct_hr >= max(pct_ve, pct_smo2_util)
        else ("Płuca" if pct_ve >= pct_smo2_util else "Mięśnie")
    )

    st.markdown(f"""
    ### 🔍 Diagnoza: {selected_window_name}

    | System | Wartość | Interpretacja |
    |--------|---------|---------------|
    | **Serce** | {pct_hr:.1f}% HRmax | {"🔴 Limiter" if limiting_factor == "Serce" else "🟢 OK"} |
    | **Płuca** | {pct_ve:.1f}% VEmax | {"🔴 Limiter" if limiting_factor == "Płuca" else "🟢 OK"} |
    | **Mięśnie** | {pct_smo2_util:.1f}% Desat | {"🔴 Limiter" if limiting_factor == "Mięśnie" else "🟢 OK"} |
    | **Moc** | {pct_power:.0f}% CP | — |

    **Główny Limiter: {limiting_factor}**
    """)

    _render_cycling_limiter_recommendation(limiting_factor)


def _render_cycling_limiter_recommendation(limiting_factor: str) -> None:
    if limiting_factor == "Serce":
        st.warning("""
        **🫀 Ograniczenie Centralne (Serce)**

        Twoje serce pracuje na maksymalnych obrotach, ale mięśnie mogłyby więcej. Sugestie:
        - Więcej treningu Z2 (podniesienie SV - objętości wyrzutowej)
        - Interwały 4x8 min @ 88-94% HRmax
        - Rozważ pracę nad VO2max (Hill Repeats)
        """)
    elif limiting_factor == "Płuca":
        st.warning("""
        **🫁 Ograniczenie Oddechowe (Płuca)**

        Wentylacja jest na limicie. Sugestie:
        - Ćwiczenia oddechowe (pranayama, Wim Hof)
        - Trening na wysokości (lub maska hipoksyjna)
        - Sprawdź technikę oddychania podczas wysiłku
        """)
    else:
        st.warning("""
        **💪 Ograniczenie Peryferyjne (Mięśnie)**

        Mięśnie zużywają cały dostarczany tlen. Sugestie:
        - Więcej pracy siłowej (squat, deadlift)
        - Interwały "over-under" (93-97% FTP / 103-107% FTP)
        - Sprawdź pozycję na rowerze (okluzja mechaniczna?)
        """)


def _render_cycling_theory_expander() -> None:
    with st.expander("📚 Teoria: Model INSCYD i Typy Zawodników", expanded=False):
        st.markdown("""
        ## Model Metaboliczny INSCYD

        INSCYD (Power Performance Decoder) to zaawansowany system profilowania metabolicznego, który analizuje interakcję między:

        ### 1. VO2max (Zdolność Aerobowa)
        * Maksymalny pobór tlenu [ml/min/kg]
        * Im wyższy, tym więcej energii możesz wytworzyć tlenowo
        * Typowe wartości: Amator 40-50, Pro 70-85+ ml/min/kg

        ### 2. VLaMax (Zdolność Glikolityczna)
        * Maksymalna produkcja mleczanu [mmol/L/s]
        * Wysoki VLaMax = mocny sprint, ale szybsze zużycie glikogenu
        * Niski VLaMax = lepsza ekonomia tłuszczowa, wyższy próg

        ---

        ## Typy Zawodników (Profiling)

        | Typ | VO2max | VLaMax | Charakterystyka | Przykłady |
        |-----|--------|--------|-----------------|-----------|
        | **Sprinter** | Średni | Wysoki | Dynamika, punch, sprinty | Sagan, Cavendish, Philipsen |
        | **Climber** | Wysoki | Niski | Długie wspinaczki, tempo | Pogačar, Vingegaard, Yates |
        | **Puncheur** | Wysoki | Średni | Ataki, stromie, krótkie górki | Van Aert, Evenepoel |
        | **Time Trialist** | Wysoki | Niski | Równe tempo, aerodynamika | Ganna, Dennis, Küng |
        | **Rouleur** | Średni | Średni | Klasyki, bruk, wszechstronność | Van der Poel, Pidcock |

        ---

        ## Interakcja VO2max ↔ VLaMax

        ```
        Wysoki VO2max + Niski VLaMax = Wysoki FTP, dobre spalanie tłuszczu
        Wysoki VO2max + Wysoki VLaMax = Mocny sprint, ale niższy próg
        Niski VO2max + Niski VLaMax = Słaba wydolność ogólna
        ```

        ---

        ## Jak Zmienić Swój Profil?

        | Cel | Strategia | Przykładowe Treningi |
        |-----|-----------|---------------------|
        | ⬇️ **Obniżyć VLaMax** | Więcej Z2, mniej sprintów | 3-5h Z2 bez żadnych interwałów |
        | ⬆️ **Podnieść VO2max** | Interwały w Z5 | 5x5 min @ 105-110% FTP |
        | ⬆️ **Podnieść FatMax** | Train Low, Z2 na czczo | Poranki Z2 bez śniadania |
        | ⬆️ **Podnieść FTP** | Sweet Spot, Threshold | 2x20 min @ 88-94% FTP |

        ---

        ## Krzywa FatMax

        FatMax to intensywność, przy której spalasz najwięcej tłuszczu (zwykle 55-65% FTP).

        * Poniżej FatMax: Spalasz mniej energii ogółem
        * Powyżej FatMax: Spalanie tłuszczu spada, węgle dominują
        * Cel treningu Z2: Przesunąć FatMax w prawo (wyższa moc przy max spalaniu tłuszczu)

        *Ten kalkulator szacuje Twój profil na podstawie stosunku mocy 5min/20min.*
        """)


def _render_cycling_mode(
    df_plot: pd.DataFrame,
    cp_input: float,
    vt2_vent: float,
    has_hr: bool,
    has_ve: bool,
    has_smo2: bool,
) -> None:
    """Full cycling-mode limiter analysis."""
    _render_cycling_profile(df_plot)

    st.divider()

    # --- SEKCJA 2: RADAR LIMITERÓW ---
    _render_cycling_radar(df_plot, cp_input, vt2_vent, has_hr, has_ve, has_smo2)

    st.divider()

    # --- SEKCJA 3: TEORIA INSCYD ---
    _render_cycling_theory_expander()
