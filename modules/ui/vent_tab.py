"""Ventilation main tab — orchestrates all vent sub-sections."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from scipy import stats

from modules.calculations.quality import check_signal_quality
from modules.notes import TrainingNotes
from modules.ui.vent_br_only import _render_br_only_section
from modules.ui.vent_charts import (
    _render_br_section,
    _render_tidal_volume_section,
    _render_ve_section,
)
from modules.ui.vent_legacy import _render_legacy_tools
from modules.ui.vent_utils import _format_time, _parse_time_to_seconds

_VENT_THEORY_MD = """
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
"""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _prepare_vent_data(target_df: pd.DataFrame) -> pd.DataFrame:
    """Create smoothed columns and derived metrics on a copy of *target_df*."""
    df = target_df.copy()

    if "pace_smooth" not in df.columns and "pace" in df.columns:
        df["pace_smooth"] = df["pace"].rolling(window=15, center=True).median()
    if "ve_smooth" not in df.columns:
        df["ve_smooth"] = df["tymeventilation"].rolling(window=15, center=True).median()
    if "tymebreathrate" in df.columns and "rr_smooth" not in df.columns:
        df["rr_smooth"] = df["tymebreathrate"].rolling(window=15, center=True).median()

    # Tidal Volume = VE / BR
    if "tymebreathrate" in df.columns and "tymeventilation" in df.columns:
        df["tidal_volume"] = df["tymeventilation"] / df["tymebreathrate"].replace(0, float("nan"))
        df["tv_smooth"] = df["tidal_volume"].rolling(window=10, center=True).mean()

    df["time_str"] = pd.to_datetime(df["time"], unit="s").dt.strftime("%H:%M:%S")
    return df


def _check_ve_quality(ve_series: pd.Series) -> None:
    """Display a Streamlit warning when VE signal quality is low."""
    qual_res = check_signal_quality(ve_series, "VE", (0, 300))
    if not qual_res["is_valid"]:
        st.warning(f"⚠️ **Niska Jakość Sygnału VE (Score: {qual_res['score']})**")
        for issue in qual_res["issues"]:
            st.caption(f"❌ {issue}")


def _init_vent_session_state() -> None:
    """Set default session_state values for vent / BR / TV chart ranges."""
    defaults: dict[str, int] = {
        "vent_start_sec": 600,
        "vent_end_sec": 1200,
        "br_start_sec": 600,
        "br_end_sec": 1200,
        "tv_start_sec": 600,
        "tv_end_sec": 1200,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_vent_notes(
    target_df: pd.DataFrame,
    training_notes: TrainingNotes,
    uploaded_file_name: str,
) -> None:
    """Render the notes input form and list of existing ventilation notes."""
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


def _render_manual_range() -> None:
    """Render the manual time-range input expander."""
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


def _render_interval_analysis(
    target_df: pd.DataFrame,
    startsec: int,
    endsec: int,
) -> None:
    """Compute and display interval metrics, charts, and legacy tools."""
    mask = (target_df["time"] >= startsec) & (target_df["time"] <= endsec)
    interval_data = target_df.loc[mask]

    if interval_data.empty or endsec <= startsec:
        st.warning("Brak danych w wybranym zakresie.")
        return

    duration_sec = int(endsec - startsec)

    avg_pace = interval_data["pace"].mean() if "pace" in interval_data.columns else 0
    avg_pace_min = avg_pace / 60.0 if avg_pace > 0 else 0
    avg_ve: float = interval_data["tymeventilation"].mean()
    avg_rr: float = (
        interval_data["tymebreathrate"].mean() if "tymebreathrate" in interval_data.columns else 0
    )

    # Trend (Slope) dla VE
    slope_ve, intercept_ve, trend_desc = _compute_ve_slope(interval_data)

    st.subheader(
        f"METRYKI MANUALNE: {_format_time(startsec)} - {_format_time(endsec)} ({duration_sec}s)"
    )

    m1, m2, m3, m4 = st.columns(4)
    pace_str = (
        f"{int(avg_pace_min):02d}:{int((avg_pace_min % 1) * 60):02d}" if avg_pace > 0 else "--:--"
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


def _compute_ve_slope(
    interval_data: pd.DataFrame,
) -> tuple[float, float, str]:
    """Return ``(slope, intercept, human_readable_desc)`` for VE trend."""
    if len(interval_data) > 1:
        slope, intercept, _, _, _ = stats.linregress(
            interval_data["time"], interval_data["tymeventilation"]
        )
        return slope, intercept, f"{slope:.4f} (L/min)/s"
    return 0.0, 0.0, "N/A"


def _render_vent_theory() -> None:
    """Render the collapsible theory section (pure static content)."""
    with st.expander("🫁 TEORIA: Interpretacja Wentylacji", expanded=False):
        st.markdown(_VENT_THEORY_MD)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_vent_tab(target_df, training_notes, uploaded_file_name):
    """Analiza wentylacji dla dowolnego treningu - struktura jak SmO2."""
    st.header("Analiza Wentylacji (VE & Breathing Rate)")
    st.markdown(
        "Analiza dynamiki oddechu dla dowolnego treningu. Szukaj anomalii w wentylacji i częstości oddechów."
    )

    # 1. Guard clauses
    if target_df is None or target_df.empty:
        st.error("Brak danych. Najpierw wgraj plik w sidebar.")
        return

    if "time" not in target_df.columns:
        st.error("Brak kolumny 'time' w danych!")
        return

    has_ve = "tymeventilation" in target_df.columns
    has_br = "tymebreathrate" in target_df.columns

    if not has_ve and not has_br:
        _show_missing_vent_info(target_df)
        return

    if _render_br_only_section(target_df):
        return

    # 2. Prepare data
    target_df = _prepare_vent_data(target_df)
    _check_ve_quality(target_df["tymeventilation"])
    _init_vent_session_state()

    # 3. Notes
    _render_vent_notes(target_df, training_notes, uploaded_file_name)
    st.markdown("---")

    # 4. Manual analysis
    st.info(
        "💡 **ANALIZA MANUALNA:** Zaznacz obszar na wykresie poniżej (kliknij i przeciągnij), aby sprawdzić nachylenie lokalne."
    )
    _render_manual_range()

    startsec = st.session_state.vent_start_sec
    endsec = st.session_state.vent_end_sec

    # 5. Interval analysis
    _render_interval_analysis(target_df, startsec, endsec)

    # 6. Theory
    _render_vent_theory()


def _show_missing_vent_info(target_df: pd.DataFrame) -> None:
    """Display an info box listing available columns when VE/BR are absent."""
    available = [
        f"`{col}`"
        for col in target_df.columns
        if col in ["watts", "heartrate", "smo2", "cadence", "core_temperature"]
    ]
    st.info(
        """
    ℹ️ **Brak danych wentylacji (VE) i częstości oddechów (BR)**

    Aby uzyskać analizę wentylacyjną, potrzebujesz czujnika wentylacji
    (np. VO2 Master, Cosmed) lub zegarka z pomiarem BR (Garmin, COROS).

    **Twoje dane zawierają:**
    """
        + ", ".join(available)
        + """

    💡 **Analiza fizjologii mięśniowej jest dostępna w zakładce 🩸 SmO2**
    """
    )
