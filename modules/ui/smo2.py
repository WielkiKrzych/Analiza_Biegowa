import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from modules.calculations.quality import check_signal_quality
from modules.calculations.smo2_phases import (
    calculate_smo2_recovery_halftime,
    classify_smo2_slope,
    detect_smo2_phases,
)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _parse_time_to_seconds(t_str: str) -> int | None:
    """Convert ``hh:mm:ss`` / ``mm:ss`` / ``ss`` string to total seconds."""
    try:
        parts = list(map(int, t_str.split(":")))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 1:
            return parts[0]
    except (ValueError, AttributeError):
        return None
    return None


def _format_time(s: float) -> str:
    """Format seconds into ``hh:mm:ss`` or ``mm:ss`` string."""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


# ---------------------------------------------------------------------------
# Input validation & preparation
# ---------------------------------------------------------------------------


def _validate_input(target_df: pd.DataFrame | None) -> bool:
    """Return *True* when data is present and usable, *False* otherwise."""
    if target_df is None or target_df.empty:
        st.error("Brak danych. Najpierw wgraj plik w sidebar.")
        return False
    if "time" not in target_df.columns:
        st.error("Brak kolumny 'time' w danych!")
        return False
    if "smo2" not in target_df.columns:
        st.info("ℹ️ Brak danych SmO2 w tym pliku.")
        return False
    return True


def _prepare_dataframe(target_df: pd.DataFrame) -> pd.DataFrame:
    """Add smoothed columns and ``time_str``.  Returns a *copy*."""
    df = target_df.copy()
    if "pace_smooth" not in df.columns and "pace" in df.columns:
        df["pace_smooth"] = df["pace"].rolling(window=15, center=True).median()
    if "smo2_smooth" not in df.columns:
        df["smo2_smooth"] = df["smo2"].rolling(window=15, center=True).median()
    df["time_str"] = pd.to_datetime(df["time"], unit="s").dt.strftime("%H:%M:%S")
    return df


# ---------------------------------------------------------------------------
# UI sections — notes
# ---------------------------------------------------------------------------


def _render_notes_section(
    training_notes: object,
    uploaded_file_name: str,
    max_time_min: float,
    mid_time_min: float,
) -> None:
    """Render the SmO2 notes expander and existing notes list."""
    with st.expander("📝 Dodaj Notatkę do tej Analizy", expanded=False):
        note_col1, note_col2 = st.columns([1, 2])
        with note_col1:
            note_time = st.number_input(
                "Czas (min)",
                min_value=0.0,
                max_value=max_time_min,
                value=mid_time_min,
                step=0.5,
                key="smo2_note_time",
            )
        with note_col2:
            note_text = st.text_input(
                "Notatka",
                key="smo2_note_text",
                placeholder="Np. 'Atak 500W', 'Próg beztlenowy', 'Błąd sensoryka'",
            )

        if st.button("➕ Dodaj Notatkę", key="smo2_add_note"):
            if note_text:
                training_notes.add_note(uploaded_file_name, note_time, "smo2", note_text)
                st.success(f"✅ Notatka: {note_text} @ {note_time:.1f} min")
            else:
                st.warning("Wpisz tekst notatki!")

    existing_notes_smo2 = training_notes.get_notes_for_metric(uploaded_file_name, "smo2")
    if existing_notes_smo2:
        st.subheader("📋 Notatki SmO2")
        for idx, note in enumerate(existing_notes_smo2):
            col_note, col_del = st.columns([4, 1])
            with col_note:
                st.info(f"⏱️ **{note['time_minute']:.1f} min** | {note['text']}")
            with col_del:
                if st.button("🗑️", key=f"del_smo2_note_{idx}"):
                    training_notes.delete_note(uploaded_file_name, idx)
                    st.rerun()


# ---------------------------------------------------------------------------
# UI sections — manual time-range input
# ---------------------------------------------------------------------------


def _render_manual_range_input() -> None:
    """Render the manual time-range expander and update session_state."""
    with st.expander("🔧 Ręczne wprowadzenie zakresu czasowego (opcjonalne)", expanded=False):
        col_inp_1, col_inp_2 = st.columns(2)
        with col_inp_1:
            manual_start = st.text_input(
                "Start Interwału (hh:mm:ss)", value="00:10:00", key="smo2_manual_start"
            )
        with col_inp_2:
            manual_end = st.text_input(
                "Koniec Interwału (hh:mm:ss)", value="00:20:00", key="smo2_manual_end"
            )

        if st.button("Zastosuj ręczny zakres", key="btn_smo2_manual"):
            manual_start_sec = _parse_time_to_seconds(manual_start)
            manual_end_sec = _parse_time_to_seconds(manual_end)
            if manual_start_sec is not None and manual_end_sec is not None:
                st.session_state.smo2_start_sec = manual_start_sec
                st.session_state.smo2_end_sec = manual_end_sec
                st.success(f"✅ Zaktualizowano zakres: {manual_start} - {manual_end}")


# ---------------------------------------------------------------------------
# UI sections — manual metrics cards
# ---------------------------------------------------------------------------


def _render_manual_metrics(
    interval_data: pd.DataFrame,
    startsec: float,
    endsec: float,
    slope_smo2: float,
    trend_desc: str,
) -> None:
    """Render the manual-metrics sub-header and 4-column metric cards."""
    duration_sec = int(endsec - startsec)
    avg_pace = interval_data["pace"].mean() if "pace" in interval_data.columns else 0
    avg_pace_min = avg_pace / 60.0 if avg_pace > 0 else 0
    avg_smo2 = interval_data["smo2"].mean()
    avg_thb = interval_data["thb"].mean() if "thb" in interval_data.columns else None

    st.subheader(
        f"METRYKI MANUALNE: {_format_time(startsec)} - {_format_time(endsec)} ({duration_sec}s)"
    )

    _m1, m2, m3, m4 = st.columns(4)

    pace_str = (
        f"{int(avg_pace_min):02d}:{int((avg_pace_min % 1) * 60):02d}" if avg_pace > 0 else "--:--"
    )
    _m1.metric("Śr. Tempo", pace_str)
    m2.metric("Śr. SmO2", f"{avg_smo2:.1f} %")

    if avg_thb is not None:
        m3.metric("Śr. THb", f"{avg_thb:.2f} g/dL")
    else:
        cadence = interval_data["cadence"].mean() if "cadence" in interval_data.columns else 0
        sport_type = st.session_state.get("sport_type", "unknown")
        cad_unit = "SPM" if sport_type == "running" or "pace" in interval_data.columns else "rpm"
        m3.metric("Śr. Kadencja", f"{cadence:.0f} {cad_unit}")

    trend_color = "inverse" if slope_smo2 < -0.01 else "normal"
    m4.metric("Trend SmO2 (Slope)", trend_desc, delta=trend_desc, delta_color=trend_color)


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------


def _build_smo2_chart(
    target_df: pd.DataFrame,
    interval_data: pd.DataFrame,
    startsec: float,
    endsec: float,
    slope_smo2: float,
    intercept_smo2: float,
) -> go.Figure:
    """Build the main SmO2 + Pace chart with manual-range highlight."""
    fig = go.Figure()

    # SmO2 trace
    fig.add_trace(
        go.Scatter(
            x=target_df["time"],
            y=target_df["smo2_smooth"],
            customdata=target_df["time_str"],
            mode="lines",
            name="SmO2 (%)",
            line=dict(color="#FF4B4B", width=2),
            hovertemplate="<b>Czas:</b> %{customdata}<br><b>SmO2:</b> %{y:.1f}%<extra></extra>",
        )
    )

    # Pace trace
    if "pace_smooth" in target_df.columns:
        pace_min_display = target_df["pace_smooth"] / 60.0
        pace_formatted = pace_min_display.apply(
            lambda x: f"{int(x):d}:{int((x % 1) * 60):02d}" if x > 0 else "--:--"
        )
        fig.add_trace(
            go.Scatter(
                x=target_df["time"],
                y=pace_min_display,
                customdata=np.stack([target_df["time_str"], pace_formatted], axis=-1),
                mode="lines",
                name="Tempo",
                line=dict(color="#00BCD4", width=1),
                yaxis="y2",
                opacity=0.3,
                hovertemplate="<b>Czas:</b> %{customdata[0]}<br><b>Tempo:</b> %{customdata[1]} min/km<extra></extra>",
            )
        )

    # Manual-range highlight
    fig.add_vrect(
        x0=startsec,
        x1=endsec,
        fillcolor="orange",
        opacity=0.1,
        layer="below",
        line_width=0,
        annotation_text="MANUAL",
        annotation_position="top left",
    )

    # Trend line for manual range
    if len(interval_data) > 1:
        trend_line = intercept_smo2 + slope_smo2 * interval_data["time"]
        fig.add_trace(
            go.Scatter(
                x=interval_data["time"],
                y=trend_line,
                mode="lines",
                name="Trend SmO2 (Man)",
                line=dict(color="white", width=2, dash="dash"),
                hovertemplate="<b>Trend:</b> %{y:.2f}%<extra></extra>",
            )
        )

    fig.update_layout(
        title="Dynamika SmO2 vs Tempo (Surowe Wartości)",
        xaxis_title="Czas",
        yaxis=dict(title=dict(text="SmO2 (%)", font=dict(color="#FF4B4B"))),
        yaxis2=dict(
            title=dict(text="Tempo (min/km)", font=dict(color="#00BCD4")),
            overlaying="y",
            side="right",
            showgrid=False,
            autorange="reversed",
        ),
        legend=dict(x=0.01, y=0.99),
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
    )
    return fig


def _render_thb_chart(
    target_df: pd.DataFrame,
    interval_data: pd.DataFrame,
    startsec: float,
    endsec: float,
    avg_pace_min: float,
    avg_thb: float | None,
) -> None:
    """Render the THb metrics row and chart (only when THb column exists)."""
    if "thb" not in target_df.columns:
        return

    st.markdown("---")

    target_df["thb_smooth"] = target_df["thb"].rolling(window=30, center=True).median()

    # THb trend
    if len(interval_data) > 1 and "thb" in interval_data.columns:
        slope_thb, intercept_thb, _, _, _ = stats.linregress(
            interval_data["time"], interval_data["thb"]
        )
        trend_thb_desc = f"{slope_thb:.4f} g/dL/s"
    else:
        slope_thb = 0
        intercept_thb = 0
        trend_thb_desc = "N/A"

    # THb metrics
    thb_cols = st.columns(4)
    thb_cols[0].metric("Śr. Tempo", f"{avg_pace_min:.2f} min/km")
    thb_cols[1].metric("Śr. THb", f"{avg_thb:.2f} g/dL")
    thb_cols[2].metric("Trend THb (Slope)", trend_thb_desc)

    # THb chart
    fig_thb = go.Figure()
    fig_thb.add_trace(
        go.Scatter(
            x=target_df["time"],
            y=target_df["thb_smooth"],
            customdata=target_df["time_str"],
            mode="lines",
            name="THb (g/dL)",
            line=dict(color="#9467bd", width=2),
            hovertemplate="<b>Czas:</b> %{customdata}<br><b>THb:</b> %{y:.2f} g/dL<extra></extra>",
        )
    )

    # Pace overlay
    if "pace_smooth" in target_df.columns:
        pace_min_thb = target_df["pace_smooth"] / 60.0
        pace_thb_formatted = pace_min_thb.apply(
            lambda x: f"{int(x):d}:{int((x % 1) * 60):02d}" if x > 0 else "--:--"
        )
        fig_thb.add_trace(
            go.Scatter(
                x=target_df["time"],
                y=pace_min_thb,
                customdata=np.stack([target_df["time_str"], pace_thb_formatted], axis=-1),
                mode="lines",
                name="Tempo",
                line=dict(color="#00BCD4", width=1),
                yaxis="y2",
                opacity=0.3,
                hovertemplate="<b>Czas:</b> %{customdata[0]}<br><b>Tempo:</b> %{customdata[1]} min/km<extra></extra>",
            )
        )

    # Manual highlight
    fig_thb.add_vrect(
        x0=startsec,
        x1=endsec,
        fillcolor="orange",
        opacity=0.1,
        layer="below",
        line_width=0,
        annotation_text="MANUAL",
        annotation_position="top left",
    )

    # Trend line
    if len(interval_data) > 1 and "thb" in interval_data.columns:
        trend_thb_line = intercept_thb + slope_thb * interval_data["time"]
        fig_thb.add_trace(
            go.Scatter(
                x=interval_data["time"],
                y=trend_thb_line,
                mode="lines",
                name="Trend THb (Man)",
                line=dict(color="white", width=2, dash="dash"),
                hovertemplate="<b>Trend:</b> %{y:.2f} g/dL<extra></extra>",
            )
        )

    fig_thb.update_layout(
        title="Dynamika THb vs Tempo (Surowe Wartości)",
        xaxis_title="Czas",
        yaxis=dict(title=dict(text="THb (g/dL)", font=dict(color="#9467bd"))),
        yaxis2=dict(
            title=dict(text="Tempo (min/km)", font=dict(color="#00BCD4")),
            overlaying="y",
            side="right",
            showgrid=False,
            autorange="reversed",
        ),
        legend=dict(x=0.01, y=0.99),
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
    )

    st.plotly_chart(fig_thb, use_container_width=True, key="thb_chart")


# ---------------------------------------------------------------------------
# Chart selection handler
# ---------------------------------------------------------------------------


def _handle_chart_selection(selected: dict | None) -> None:
    """Update ``session_state`` range when the user box-selects on the chart."""
    if not selected or "selection" not in selected or "box" not in selected["selection"]:
        return
    box_data = selected["selection"]["box"]
    if not box_data or len(box_data) == 0:
        return
    x_range = box_data[0].get("x", [])
    if len(x_range) != 2:
        return
    new_start = min(x_range)
    new_end = max(x_range)
    if new_start != st.session_state.smo2_start_sec or new_end != st.session_state.smo2_end_sec:
        st.session_state.smo2_start_sec = new_start
        st.session_state.smo2_end_sec = new_end
        st.rerun()


# ---------------------------------------------------------------------------
# 4-phase model & slope classification
# ---------------------------------------------------------------------------


def _render_phase_model(target_df: pd.DataFrame) -> None:
    """Render the 4-phase SmO2 model and slope classification sections."""
    st.markdown("---")
    st.subheader("🔬 Model 4-fazowy SmO2 (Contreras-Briceno 2023)")

    smo2_valid = target_df["smo2"].dropna()
    if len(smo2_valid) < 120:
        st.info("Za mało danych SmO2 do analizy 4-fazowej (min. 120 próbek).")
        return

    time_s = target_df["time"].iloc[: len(smo2_valid)] if "time" in target_df.columns else None
    phase_result = detect_smo2_phases(smo2_valid, time_s)

    if phase_result.is_valid:
        col_ph1, col_ph2, col_ph3 = st.columns(3)
        col_ph1.metric(
            "Desaturacja",
            f"{phase_result.desaturation_magnitude:.1f}%",
            help="Różnica między max a min SmO2",
        )
        col_ph2.metric(
            "Recovery Rate",
            f"{phase_result.recovery_rate_pct_per_min:.2f} %/min",
            help="Szybkość reoxygenacji w Fazie 4",
        )
        col_ph3.metric("Fazy wykryte", f"{len(phase_result.phases)}/4")

        _render_phase_table(phase_result)
        _render_recovery_halftime(smo2_valid)
    else:
        st.info("Niewystarczające dane do wykrycia 4 faz SmO2. " + "; ".join(phase_result.notes))

    _render_slope_classification(smo2_valid)


def _render_phase_table(phase_result: object) -> None:
    """Render the phase data table."""
    phase_rows = []
    for p in phase_result.phases:
        dur_min = p["duration_sec"] / 60
        phase_rows.append(
            {
                "Faza": p["name"],
                "Start": f"{p['start_sec'] // 60}:{p['start_sec'] % 60:02d}",
                "Koniec": f"{p['end_sec'] // 60}:{p['end_sec'] % 60:02d}",
                "Czas": f"{dur_min:.1f} min",
                "Śr. SmO2": f"{p['mean_smo2']:.1f}%",
                "Slope": f"{p['slope_pct_per_sec']:.4f} %/s",
                "R²": f"{p['r_squared']:.2f}",
            }
        )
    st.dataframe(pd.DataFrame(phase_rows), use_container_width=True, hide_index=True)


def _render_recovery_halftime(smo2_valid: pd.Series) -> None:
    """Render recovery halftime info."""
    halftime = calculate_smo2_recovery_halftime(smo2_valid)
    if halftime.get("is_valid"):
        st.info(
            f"**Recovery Half-time:** {halftime['halftime_sec']}s — "
            f"**{halftime['classification']}** "
            f"(nadir {halftime['nadir_pct']:.1f}% → baseline {halftime['baseline_pct']:.1f}%)"
        )


def _render_slope_classification(smo2_valid: pd.Series) -> None:
    """Render the SmO2 slope classification section."""
    st.markdown("#### Klasyfikacja nachylenia SmO2 (Rodriguez 2023)")
    slope_class = classify_smo2_slope(smo2_valid)
    counts = slope_class.value_counts()
    total = len(slope_class)
    if total == 0:
        return

    col_s1, col_s2, col_s3 = st.columns(3)
    sus_pct = counts.get("sustainable", 0) / total * 100
    thr_pct = counts.get("threshold", 0) / total * 100
    unsus_pct = counts.get("unsustainable", 0) / total * 100
    col_s1.metric(
        "Sustainable",
        f"{sus_pct:.0f}%",
        help="Slope > 0: dostawa > zużycie (poniżej CS/CP)",
    )
    col_s2.metric("Threshold", f"{thr_pct:.0f}%", help="Slope ≈ 0: na progu")
    col_s3.metric(
        "Unsustainable",
        f"{unsus_pct:.0f}%",
        help="Slope < 0: zużycie > dostawa (powyżej CS/CP)",
    )


# ---------------------------------------------------------------------------
# Legacy tools
# ---------------------------------------------------------------------------


def _render_legacy_tools(interval_data: pd.DataFrame) -> None:
    """Render the legacy scatter-plot and interval-THb sections."""
    with st.expander("🔧 Szczegółowa Analiza (Legacy Tools)", expanded=False):
        st.markdown("### Surowe Dane i Korelacje")
        _render_scatter_watts(interval_data)
        _render_interval_thb(interval_data)


def _render_scatter_watts(interval_data: pd.DataFrame) -> None:
    """SmO2 vs Watts scatter plot (legacy)."""
    if "watts" not in interval_data.columns:
        return

    interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime("%H:%M:%S")
    fig_scatter = go.Figure()
    fig_scatter.add_trace(
        go.Scatter(
            x=interval_data["watts"],
            y=interval_data["smo2"],
            customdata=interval_time_str,
            mode="markers",
            marker=dict(
                size=6,
                color=interval_data["time"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="Czas (s)"),
            ),
            name="SmO2 vs Power",
            hovertemplate="<b>Czas:</b> %{customdata}<br><b>Moc:</b> %{x:.0f} W<br><b>SmO2:</b> %{y:.1f}%<extra></extra>",
        )
    )
    fig_scatter.update_layout(
        title="Korelacja: SmO2 vs Moc",
        xaxis_title="Moc [W]",
        yaxis_title="SmO2 (%)",
        height=400,
        hovermode="closest",
    )
    st.plotly_chart(fig_scatter, use_container_width=True)


def _render_interval_thb(interval_data: pd.DataFrame) -> None:
    """THb time-series for the selected interval (legacy)."""
    if "thb" not in interval_data.columns:
        return

    st.subheader("Hemoglobina Całkowita (THb)")
    interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime("%H:%M:%S")

    fig_thb = go.Figure()
    fig_thb.add_trace(
        go.Scatter(
            x=interval_data["time"],
            y=interval_data["thb"],
            customdata=interval_time_str,
            mode="lines",
            name="THb",
            line=dict(color="purple", width=2),
            hovertemplate="<b>Czas:</b> %{customdata}<br><b>THb:</b> %{y:.2f} g/dL<extra></extra>",
        )
    )
    fig_thb.update_layout(
        title="Total Hemoglobin (tHb)",
        xaxis_title="Czas",
        yaxis_title="THb (g/dL)",
        height=300,
        hovermode="x unified",
    )
    st.plotly_chart(fig_thb, use_container_width=True)


# ---------------------------------------------------------------------------
# Theory section
# ---------------------------------------------------------------------------


_THEORY_MARKDOWN = """
## Co oznacza SmO2?

**SmO2 (Muscle Oxygen Saturation)** to procent hemoglobiny związanej z tlenem w tkance mięśniowej.
Mierzona przez sensory NIRS (Near-Infrared Spectroscopy), np. **Moxy, TrainRed, Humon Hex**.

| Parametr | Opis |
|----------|------|
| **SmO2** | Saturacja tlenu w mięśniu (%) |
| **THb** | Całkowita hemoglobina - wskaźnik przepływu krwi |
| **Zakres typowy** | 30% - 80% (zależnie od sensora i umiejscowienia) |

---

## Strefy SmO2 i ich znaczenie

| Strefa SmO2 | Interpretacja | Typ wysiłku |
|-------------|---------------|-------------|
| **70-80%** | Pełna saturacja, regeneracja | Recovery, rozgrzewka |
| **50-70%** | Równowaga zużycie/dostawa | Tempo, Sweet Spot |
| **30-50%** | Desaturacja, próg beztlenowy | Threshold, VO2max |
| **< 30%** | Głęboka hipoksja, okluzja | Sprint, maksymalny wysiłek |

---

## Trend SmO2 (Slope) - Co oznacza nachylenie?

| Trend | Wartość | Interpretacja |
|-------|---------|---------------|
| 🟢 **Pozytywny** | > 0 | Reoxygenacja - recovery, spadek obciążenia |
| 🟡 **Zerowy** | ~ 0 | Równowaga - steady state, zużycie = dostawa |
| 🔴 **Negatywny** | < 0 | Desaturacja - mięsień zużywa więcej tlenu niż dostaje |

---

## THb (Total Hemoglobin) - Przepływ krwi

**THb** odzwierciedla ilość krwi w obszarze pomiaru:

- **⬆️ Wzrost THb**: Większy przepływ krwi (rozszerzenie naczyń, niższa kadencja)
- **⬇️ Spadek THb**: Okluzja naczyń (wysokie napięcie mięśniowe, niska kadencja + duża siła)
- **➡️ Stabilny THb**: Prawidłowy przepływ przy stałym obciążeniu

### Praktyczny przykład:
- **Podjazd na niskiej kadencji (50 rpm)**: THb spada → napięcie mięśni blokuje przepływ
- **Płaski teren, wysoka kadencja (95 rpm)**: THb rośnie → "pompa mięśniowa" wspomaga krążenie

---

## Zastosowania Treningowe SmO2

### 1️⃣ Wyznaczanie Progów (VT1, VT2)
- **VT1 (Próg tlenowy)**: Moment, gdy SmO2 zaczyna stabilnie spadać
- **VT2 (Próg beztlenowy)**: Gwałtowny spadek SmO2, przejście do metabolizmu beztlenowego

### 2️⃣ Kontrola Intensywności Interwałów
- **Start interwału**: SmO2 powinno być wysokie (> 60%)
- **Koniec interwału**: Obserwuj głębokość desaturacji
- **Przerwa**: Czekaj na reoxygenację (SmO2 > 70%) przed kolejnym powtórzeniem

### 3️⃣ Optymalizacja Kadencji
- Jeśli SmO2 spada szybko przy niskiej kadencji → **zwiększ kadencję**
- Optymalna kadencja = maksymalna moc przy stabilnym SmO2

### 4️⃣ Detekcja Zmęczenia
- **Zmęczenie lokalne**: SmO2 baseline spada w czasie treningu
- **Zmęczenie centralne**: SmO2 przestaje odpowiadać na zmiany mocy

---

## Korelacja SmO2 vs Moc

Wykres scatter pokazuje zależność między mocą a saturacją:

- **Negatywna korelacja** (typowa): Wyższa moc → niższe SmO2
- **Płaska krzywa**: Dobra wydolność tlenowa, mięśnie dobrze ukrwione
- **Stroma krzywa**: Szybka desaturacja, limitacja przepływu lub mitochondriów

### Kolor punktów (czas):
- **Wczesne punkty (ciemne)**: Początek treningu, świeże mięśnie
- **Późne punkty (jasne)**: Koniec treningu, kumulacja zmęczenia

Jeśli późne punkty są niżej niż wczesne przy tej samej mocy → **zmęczenie lokalne mięśni**

---

## Limitacje Pomiaru SmO2

⚠️ **Czynniki wpływające na dokładność:**
- Grubość tkanki tłuszczowej (> 10mm zaburza pomiar)
- Pozycja sensora (różne mięśnie = różne wartości)
- Ruch sensora podczas jazdy
- Światło zewnętrzne (bezpośrednie słońce)
- Temperatura skóry

💡 **Wskazówka**: Porównuj tylko pomiary z tej samej pozycji sensora!
"""


def _render_theory_section() -> None:
    """Render the SmO2 theory expander."""
    with st.expander("🫁 TEORIA: Interpretacja SmO2", expanded=False):
        st.markdown(_THEORY_MARKDOWN)


# ---------------------------------------------------------------------------
# Interval computation helpers
# ---------------------------------------------------------------------------


def _compute_interval_stats(
    interval_data: pd.DataFrame,
) -> tuple[float, float, float, float | None, float, float, str]:
    """Return ``(avg_pace_min, avg_smo2, avg_thb_or_none, slope, intercept, trend_desc)``."""
    avg_pace = interval_data["pace"].mean() if "pace" in interval_data.columns else 0
    avg_pace_min = avg_pace / 60.0 if avg_pace > 0 else 0
    avg_smo2 = float(interval_data["smo2"].mean())
    avg_thb: float | None = (
        float(interval_data["thb"].mean()) if "thb" in interval_data.columns else None
    )

    if len(interval_data) > 1:
        slope_smo2, intercept_smo2, _, _, _ = stats.linregress(
            interval_data["time"], interval_data["smo2"]
        )
        trend_desc = f"{slope_smo2:.4f} %/s"
    else:
        slope_smo2 = 0.0
        intercept_smo2 = 0.0
        trend_desc = "N/A"

    return avg_pace_min, avg_smo2, avg_thb, slope_smo2, intercept_smo2, trend_desc


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_smo2_tab(
    target_df: pd.DataFrame | None,
    training_notes: object,
    uploaded_file_name: str,
) -> None:
    """Main SmO2 analysis tab renderer."""
    st.header("Analiza SmO2 (Oksygenacja Mięśniowa)")
    st.markdown("Analiza surowych danych SmO2, trendów i kontekstu obciążenia.")

    if not _validate_input(target_df):
        return

    target_df = _prepare_dataframe(target_df)

    # Signal quality
    qual_res = check_signal_quality(target_df["smo2"], "SmO2", (0, 100))
    if not qual_res["is_valid"]:
        st.warning(f"⚠️ **Niska Jakość Sygnału SmO2 (Score: {qual_res['score']})**")
        for issue in qual_res["issues"]:
            st.caption(f"❌ {issue}")

    # Initialise session_state defaults
    if "smo2_start_sec" not in st.session_state:
        st.session_state.smo2_start_sec = 600
    if "smo2_end_sec" not in st.session_state:
        st.session_state.smo2_end_sec = 1200

    # Notes
    n_rows = len(target_df)
    _render_notes_section(
        training_notes,
        uploaded_file_name,
        max_time_min=float(n_rows / 60) if n_rows > 0 else 60.0,
        mid_time_min=float(n_rows / 120) if n_rows > 0 else 15.0,
    )

    st.markdown("---")

    # Manual analysis intro
    st.info(
        "💡 **ANALIZA MANUALNA:** Zaznacz obszar na wykresie poniżej (kliknij i przeciągnij), aby sprawdzić nachylenie lokalne."
    )

    _render_manual_range_input()

    startsec = st.session_state.smo2_start_sec
    endsec = st.session_state.smo2_end_sec

    # Slice data for the selected range
    mask = (target_df["time"] >= startsec) & (target_df["time"] <= endsec)
    interval_data = target_df.loc[mask]

    if interval_data.empty or endsec <= startsec:
        st.warning("Brak danych w wybranym zakresie.")
        _render_theory_section()
        return

    # Compute stats & render metrics
    avg_pace_min, avg_smo2, avg_thb, slope_smo2, intercept_smo2, trend_desc = (
        _compute_interval_stats(interval_data)
    )
    _render_manual_metrics(interval_data, startsec, endsec, slope_smo2, trend_desc)

    # Main SmO2 chart
    fig_smo2 = _build_smo2_chart(
        target_df, interval_data, startsec, endsec, slope_smo2, intercept_smo2
    )
    selected = st.plotly_chart(
        fig_smo2,
        use_container_width=True,
        key="smo2_chart",
        on_select="rerun",
        selection_mode="box",
    )

    # THb chart
    _render_thb_chart(target_df, interval_data, startsec, endsec, avg_pace_min, avg_thb)

    # Handle box selection
    _handle_chart_selection(selected)

    # 4-phase model
    _render_phase_model(target_df)

    st.markdown("---")

    # Legacy tools
    _render_legacy_tools(interval_data)

    # Theory
    _render_theory_section()
