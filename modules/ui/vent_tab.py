"""Ventilation main tab — orchestrates all vent sub-sections."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from scipy import stats

from modules.calculations.quality import check_signal_quality
from modules.ui.vent_br_only import _render_br_only_section
from modules.ui.vent_charts import (
    _render_br_section,
    _render_tidal_volume_section,
    _render_ve_section,
)
from modules.ui.vent_legacy import _render_legacy_tools
from modules.ui.vent_utils import _format_time, _parse_time_to_seconds


def render_vent_tab(target_df, training_notes, uploaded_file_name):
    """Analiza wentylacji dla dowolnego treningu - struktura jak SmO2."""
    st.header("Analiza Wentylacji (VE & Breathing Rate)")
    st.markdown(
        "Analiza dynamiki oddechu dla dowolnego treningu. Szukaj anomalii w wentylacji i częstości oddechów."
    )

    # 1. Przygotowanie danych
    if target_df is None or target_df.empty:
        st.error("Brak danych. Najpierw wgraj plik w sidebar.")
        return

    if "time" not in target_df.columns:
        st.error("Brak kolumny 'time' w danych!")
        return

    has_ve = "tymeventilation" in target_df.columns
    has_br = "tymebreathrate" in target_df.columns

    if not has_ve and not has_br:
        st.info(
            """
        ℹ️ **Brak danych wentylacji (VE) i częstości oddechów (BR)**

        Aby uzyskać analizę wentylacyjną, potrzebujesz czujnika wentylacji
        (np. VO2 Master, Cosmed) lub zegarka z pomiarem BR (Garmin, COROS).

        **Twoje dane zawierają:**
        """
            + ", ".join(
                [
                    f"`{col}`"
                    for col in target_df.columns
                    if col in ["watts", "heartrate", "smo2", "cadence", "core_temperature"]
                ]
            )
            + """

        💡 **Analiza fizjologii mięśniowej jest dostępna w zakładce 🩸 SmO2**
        """
        )
        return

    if _render_br_only_section(target_df):
        return

    # Work on a copy to avoid mutating the caller's DataFrame
    target_df = target_df.copy()
    # FIX: Use 15s median (more robust to outliers than 5s mean)
    if "pace_smooth" not in target_df.columns and "pace" in target_df.columns:
        target_df["pace_smooth"] = target_df["pace"].rolling(window=15, center=True).median()
    if "ve_smooth" not in target_df.columns:
        target_df["ve_smooth"] = (
            target_df["tymeventilation"].rolling(window=15, center=True).median()
        )
    if "tymebreathrate" in target_df.columns and "rr_smooth" not in target_df.columns:
        target_df["rr_smooth"] = (
            target_df["tymebreathrate"].rolling(window=15, center=True).median()
        )
    # Tidal Volume = VE / BR (objętość oddechowa)
    if "tymebreathrate" in target_df.columns and "tymeventilation" in target_df.columns:
        # Avoid division by zero
        target_df["tidal_volume"] = target_df["tymeventilation"] / target_df[
            "tymebreathrate"
        ].replace(0, float("nan"))
        target_df["tv_smooth"] = target_df["tidal_volume"].rolling(window=10, center=True).mean()

    target_df["time_str"] = pd.to_datetime(target_df["time"], unit="s").dt.strftime("%H:%M:%S")

    # Check Quality
    qual_res = check_signal_quality(target_df["tymeventilation"], "VE", (0, 300))
    if not qual_res["is_valid"]:
        st.warning(f"⚠️ **Niska Jakość Sygnału VE (Score: {qual_res['score']})**")
        for issue in qual_res["issues"]:
            st.caption(f"❌ {issue}")

    # Inicjalizacja session_state
    if "vent_start_sec" not in st.session_state:
        st.session_state.vent_start_sec = 600
    if "vent_end_sec" not in st.session_state:
        st.session_state.vent_end_sec = 1200
    # BR chart range
    if "br_start_sec" not in st.session_state:
        st.session_state.br_start_sec = 600
    if "br_end_sec" not in st.session_state:
        st.session_state.br_end_sec = 1200
    # Tidal Volume chart range
    if "tv_start_sec" not in st.session_state:
        st.session_state.tv_start_sec = 600
    if "tv_end_sec" not in st.session_state:
        st.session_state.tv_end_sec = 1200

    # ===== NOTATKI VENTILATION =====
    with st.expander("📝 Dodaj Notatkę do tej Analizy", expanded=False):
        note_col1, note_col2 = st.columns([1, 2])
        with note_col1:
            note_time = st.number_input(
                "Czas (min)",
                min_value=0.0,
                max_value=float(len(target_df) / 60) if len(target_df) > 0 else 60.0,
                value=float(len(target_df) / 120) if len(target_df) > 0 else 15.0,
                step=0.5,
                key="vent_note_time",
            )
        with note_col2:
            note_text = st.text_input(
                "Notatka",
                key="vent_note_text",
                placeholder="Np. 'VE jump', 'Spłycenie oddechu', 'Hiperwentylacja'",
            )

        if st.button("➕ Dodaj Notatkę", key="vent_add_note"):
            if note_text:
                training_notes.add_note(uploaded_file_name, note_time, "ventilation", note_text)
                st.success(f"✅ Notatka: {note_text} @ {note_time:.1f} min")
            else:
                st.warning("Wpisz tekst notatki!")

    # Wyświetl istniejące notatki
    existing_notes = training_notes.get_notes_for_metric(uploaded_file_name, "ventilation")
    if existing_notes:
        st.subheader("📋 Notatki Wentylacji")
        for idx, note in enumerate(existing_notes):
            col_note, col_del = st.columns([4, 1])
            with col_note:
                st.info(f"⏱️ **{note['time_minute']:.1f} min** | {note['text']}")
            with col_del:
                if st.button("🗑️", key=f"del_vent_note_{idx}"):
                    training_notes.delete_note(uploaded_file_name, idx)
                    st.rerun()

    st.markdown("---")

    st.info(
        "💡 **ANALIZA MANUALNA:** Zaznacz obszar na wykresie poniżej (kliknij i przeciągnij), aby sprawdzić nachylenie lokalne."
    )

    with st.expander("🔧 Ręczne wprowadzenie zakresu czasowego (opcjonalne)", expanded=False):
        col_inp_1, col_inp_2 = st.columns(2)
        with col_inp_1:
            manual_start = st.text_input(
                "Start Interwału (hh:mm:ss)", value="00:10:00", key="vent_manual_start"
            )
        with col_inp_2:
            manual_end = st.text_input(
                "Koniec Interwału (hh:mm:ss)", value="00:20:00", key="vent_manual_end"
            )

        if st.button("Zastosuj ręczny zakres", key="btn_vent_manual"):
            manual_start_sec = _parse_time_to_seconds(manual_start)
            manual_end_sec = _parse_time_to_seconds(manual_end)
            if manual_start_sec is not None and manual_end_sec is not None:
                st.session_state.vent_start_sec = manual_start_sec
                st.session_state.vent_end_sec = manual_end_sec
                st.success(f"✅ Zaktualizowano zakres: {manual_start} - {manual_end}")

    startsec = st.session_state.vent_start_sec
    endsec = st.session_state.vent_end_sec

    # Wycinanie danych
    mask = (target_df["time"] >= startsec) & (target_df["time"] <= endsec)
    interval_data = target_df.loc[mask]

    if not interval_data.empty and endsec > startsec:
        duration_sec = int(endsec - startsec)

        # Obliczenia
        avg_pace = interval_data["pace"].mean() if "pace" in interval_data.columns else 0
        avg_pace_min = avg_pace / 60.0 if avg_pace > 0 else 0
        avg_ve = interval_data["tymeventilation"].mean()
        avg_rr = (
            interval_data["tymebreathrate"].mean()
            if "tymebreathrate" in interval_data.columns
            else 0
        )

        # Trend (Slope) dla VE
        if len(interval_data) > 1:
            slope_ve, intercept_ve, _, _, _ = stats.linregress(
                interval_data["time"], interval_data["tymeventilation"]
            )
            trend_desc = f"{slope_ve:.4f} (L/min)/s"
        else:
            slope_ve = 0
            intercept_ve = 0
            trend_desc = "N/A"

        st.subheader(
            f"METRYKI MANUALNE: {_format_time(startsec)} - {_format_time(endsec)} ({duration_sec}s)"
        )

        m1, m2, m3, m4 = st.columns(4)
        pace_str = (
            f"{int(avg_pace_min):02d}:{int((avg_pace_min % 1) * 60):02d}"
            if avg_pace > 0
            else "--:--"
        )
        m1.metric("Śr. Tempo", pace_str)
        m2.metric("Śr. VE", f"{avg_ve:.1f} L/min")
        m3.metric("Śr. BR", f"{avg_rr:.1f} /min")

        trend_color = "inverse" if slope_ve > 0.05 else "normal"
        m4.metric("Trend VE (Slope)", trend_desc, delta=trend_desc, delta_color=trend_color)

        _render_ve_section(target_df, startsec, endsec, interval_data, slope_ve, intercept_ve)

        st.markdown("---")
        _render_br_section(target_df)

        st.markdown("---")
        _render_tidal_volume_section(target_df)

        st.markdown("---")
        _render_legacy_tools(interval_data)

    else:
        st.warning("Brak danych w wybranym zakresie.")

    # ===== TEORIA =====
    with st.expander("🫁 TEORIA: Interpretacja Wentylacji", expanded=False):
        st.markdown("""
        ## Co oznacza Wentylacja (VE)?

        **VE (Minute Ventilation)** to objętość powietrza wdychanego/wydychanego na minutę.
        Mierzona przez sensory oddechowe np. **CORE, Tyme Wear, Garmin HRM-Pro (estymacja)**.

        | Parametr | Opis | Jednostka |
        |----------|------|-----------|
        | **VE** | Wentylacja minutowa | L/min |
        | **BR / RR** | Częstość oddechów | oddechy/min |
        | **VT** | Objętość oddechowa (VE/BR) | L |

        ---

        ## Strefy VE i ich znaczenie

        | VE (L/min) | Interpretacja | Typ wysiłku |
        |------------|---------------|-------------|
        | **20-40** | Spokojny oddech | Recovery, rozgrzewka |
        | **40-80** | Umiarkowany wysiłek | Tempo, Sweet Spot |
        | **80-120** | Intensywny wysiłek | Threshold, VO2max |
        | **> 120** | Maksymalny wysiłek | Sprint, test wyczerpania |

        ---

        ## Trend VE (Slope) - Co oznacza nachylenie?

        | Trend | Wartość | Interpretacja |
        |-------|---------|---------------|
        | 🟢 **Stabilny** | ~ 0 | Steady state, VE odpowiada obciążeniu |
        | 🟡 **Łagodny wzrost** | 0.01-0.05 | Normalna adaptacja do wysiłku |
        | 🔴 **Gwałtowny wzrost** | > 0.05 | Możliwy próg wentylacyjny (VT1/VT2) |

        ---

        ## BR (Breathing Rate) - Częstość oddechów

        **BR** odzwierciedla strategię oddechową:

        - **⬆️ Wzrost BR przy stałej VE**: Płytszy oddech, możliwe zmęczenie przepony
        - **⬇️ Spadek BR przy stałej VE**: Głębszy oddech, lepsza efektywność
        - **➡️ Stabilny BR**: Optymalna strategia oddechowa

        ### Praktyczny przykład:
        - **VE=100, BR=30**: Objętość oddechowa = 3.3L (głęboki oddech)
        - **VE=100, BR=50**: Objętość oddechowa = 2.0L (płytki oddech - nieefektywne!)

        ---

        ## Zastosowania Treningowe VE

        ### 1️⃣ Detekcja Progów (VT1, VT2)
        - **VT1 (Próg tlenowy)**: Pierwszy nieliniowy skok VE względem mocy
        - **VT2 (Próg beztlenowy)**: Drugi, gwałtowniejszy skok VE
        - 🔗 Użyj zakładki **"Ventilation - Progi"** do automatycznej detekcji

        ### 2️⃣ Kontrola Intensywności
        - Jeśli VE rośnie szybciej niż moc → zbliżasz się do progu
        - Stabilna VE przy stałej mocy → jesteś w strefie tlenowej

        ### 3️⃣ Efektywność Oddechowa
        - Optymalna częstość BR: 20-40 oddechów/min
        - Powyżej 50/min: możliwe zmęczenie, stres, lub panika

        ### 4️⃣ Detekcja Zmęczenia
        - **BR rośnie przy spadku VE**: Zmęczenie przepony
        - **VE fluktuuje chaotycznie**: Możliwe odwodnienie lub hipoglikemia

        ---

        ## Korelacja VE vs Moc

        Wykres scatter pokazuje zależność między mocą a wentylacją:

        - **Liniowa zależność**: Normalna odpowiedź fizjologiczna
        - **Punkt załamania**: Próg wentylacyjny (VT)
        - **Stroma krzywa**: Niska wydolność, szybkie zadyszenie

        ### Kolor punktów (czas):
        - **Wczesne punkty (ciemne)**: Początek treningu
        - **Późne punkty (jasne)**: Koniec treningu, kumulacja zmęczenia

        ---

        ## Limitacje Pomiaru VE

        ⚠️ **Czynniki wpływające na dokładność:**
        - Pozycja sensora na klatce piersiowej
        - Oddychanie ustami vs nosem
        - Warunki atmosferyczne (wysokość, wilgotność)
        - Intensywność mowy podczas jazdy

        💡 **Wskazówka**: Dla dokładnej detekcji progów wykonaj Test Stopniowany (Ramp Test)!
        """)
