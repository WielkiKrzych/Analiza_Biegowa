import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy import stats
from modules.calculations.quality import check_signal_quality


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

    if "tymeventilation" not in target_df.columns:
        st.info("""
        ℹ️ **Brak danych wentylacji (VE)**
        
        Aby uzyskać analizę wentylacyjną, potrzebujesz czujnika wentylacji 
        (np. VO2 Master, Cosmed, lub inny metabolimeter).
        
        **Brakujące kolumny:**
        - `tymeventilation` (VE - wentylacja w L/min)
        - `tymebreathrate` (BR - częstość oddechów w oddechach/min)
        
        **Twoje dane zawierają:**
        """ + ", ".join([f"`{col}`" for col in target_df.columns if col in 
            ["watts", "heartrate", "smo2", "cadence", "core_temperature"]]) + """
        
        💡 **Analiza fizjologii mięśniowej jest dostępna w zakładce 🩸 SmO2**
        """)
        return

    # Wygładzanie
    if "pace_smooth" not in target_df.columns and "pace" in target_df.columns:
        target_df["pace_smooth"] = target_df["pace"].rolling(window=5, center=True).mean()
    if "ve_smooth" not in target_df.columns:
        target_df["ve_smooth"] = target_df["tymeventilation"].rolling(window=10, center=True).mean()
    if "tymebreathrate" in target_df.columns and "rr_smooth" not in target_df.columns:
        target_df["rr_smooth"] = target_df["tymebreathrate"].rolling(window=10, center=True).mean()
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

    # ===== ANALIZA MANUALNA =====
    st.info(
        "💡 **ANALIZA MANUALNA:** Zaznacz obszar na wykresie poniżej (kliknij i przeciągnij), aby sprawdzić nachylenie lokalne."
    )

    def parse_time_to_seconds(t_str):
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
            manual_start_sec = parse_time_to_seconds(manual_start)
            manual_end_sec = parse_time_to_seconds(manual_end)
            if manual_start_sec is not None and manual_end_sec is not None:
                st.session_state.vent_start_sec = manual_start_sec
                st.session_state.vent_end_sec = manual_end_sec
                st.success(f"✅ Zaktualizowano zakres: {manual_start} - {manual_end}")

    # Użyj wartości z session_state
    startsec = st.session_state.vent_start_sec
    endsec = st.session_state.vent_end_sec

    def format_time(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"

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
            trend_desc = f"{slope_ve:.4f} L/s"
        else:
            slope_ve = 0
            intercept_ve = 0
            trend_desc = "N/A"

        # Metryki Manualne
        st.subheader(
            f"METRYKI MANUALNE: {format_time(startsec)} - {format_time(endsec)} ({duration_sec}s)"
        )

        m1, m2, m3, m4 = st.columns(4)
        pace_str = f"{int(avg_pace_min):02d}:{int((avg_pace_min % 1) * 60):02d}" if avg_pace > 0 else "--:--"
        m1.metric("Śr. Tempo", pace_str)
        m2.metric("Śr. VE", f"{avg_ve:.1f} L/min")
        m3.metric("Śr. BR", f"{avg_rr:.1f} /min")

        # Kolorowanie trendu (pozytywny = wzrost VE = potencjalnie próg)
        trend_color = "inverse" if slope_ve > 0.05 else "normal"
        m4.metric("Trend VE (Slope)", trend_desc, delta=trend_desc, delta_color=trend_color)

        # ===== WYKRES GŁÓWNY (VE + Power) =====
        fig_vent = go.Figure()

        # VE (Primary)
        fig_vent.add_trace(
            go.Scatter(
                x=target_df["time"],
                y=target_df["ve_smooth"],
                customdata=target_df["time_str"],
                mode="lines",
                name="VE (L/min)",
                line=dict(color="#ffa15a", width=2),
                hovertemplate="<b>Czas:</b> %{customdata}<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
            )
        )

        # Pace (Secondary)
        if "pace_smooth" in target_df.columns:
            # Convert pace to min/km for display
            pace_min_display = target_df["pace_smooth"] / 60.0
            # Create formatted pace string as mm:ss
            pace_formatted = pace_min_display.apply(lambda x: f"{int(x):d}:{int((x % 1) * 60):02d}" if x > 0 else "--:--")
            fig_vent.add_trace(
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

        # Zaznaczenie manualne
        fig_vent.add_vrect(
            x0=startsec,
            x1=endsec,
            fillcolor="orange",
            opacity=0.1,
            layer="below",
            line_width=0,
            annotation_text="MANUAL",
            annotation_position="top left",
        )

        # Linia trendu VE (dla manualnego)
        if len(interval_data) > 1:
            trend_line = intercept_ve + slope_ve * interval_data["time"]
            fig_vent.add_trace(
                go.Scatter(
                    x=interval_data["time"],
                    y=trend_line,
                    mode="lines",
                    name="Trend VE (Man)",
                    line=dict(color="white", width=2, dash="dash"),
                    hovertemplate="<b>Trend:</b> %{y:.2f} L/min<extra></extra>",
                )
            )

        fig_vent.update_layout(
            title="Dynamika Wentylacji vs Tempo",
            xaxis_title="Czas",
            yaxis=dict(title=dict(text="Wentylacja (L/min)", font=dict(color="#ffa15a"))),
            yaxis2=dict(
                title=dict(text="Tempo (min/km)", font=dict(color="#00BCD4")),
                overlaying="y",
                side="right",
                showgrid=False,
                autorange="reversed",  # Invert pace axis (lower = faster)
            ),
            legend=dict(x=0.01, y=0.99),
            height=500,
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode="x unified",
        )

        # Wykres z interaktywnym zaznaczaniem
        selected = st.plotly_chart(
            fig_vent,
            use_container_width=True,
            key="vent_chart",
            on_select="rerun",
            selection_mode="box",
        )

        # Obsługa zaznaczenia
        if selected and "selection" in selected and "box" in selected["selection"]:
            box_data = selected["selection"]["box"]
            if box_data and len(box_data) > 0:
                x_range = box_data[0].get("x", [])
                if len(x_range) == 2:
                    new_start = min(x_range)
                    new_end = max(x_range)
                    if (
                        new_start != st.session_state.vent_start_sec
                        or new_end != st.session_state.vent_end_sec
                    ):
                        st.session_state.vent_start_sec = new_start
                        st.session_state.vent_end_sec = new_end
                        st.rerun()

        # ===== BREATH RATE (BR) INTERACTIVE CHART =====
        st.markdown("---")
        st.subheader("🫁 Częstość Oddechów (Breath Rate)")

        if "tymebreathrate" in target_df.columns:
            st.info(
                "💡 **ANALIZA BR:** Zaznacz obszar na wykresie (kliknij i przeciągnij), aby sprawdzić statystyki i trend."
            )

            with st.expander("🔧 Ręczne wprowadzenie zakresu czasowego BR", expanded=False):
                col_br_1, col_br_2 = st.columns(2)
                with col_br_1:
                    manual_br_start = st.text_input(
                        "Start Interwału (hh:mm:ss)", value="00:10:00", key="br_manual_start"
                    )
                with col_br_2:
                    manual_br_end = st.text_input(
                        "Koniec Interwału (hh:mm:ss)", value="00:20:00", key="br_manual_end"
                    )

                if st.button("Zastosuj ręczny zakres", key="btn_br_manual"):
                    br_start = parse_time_to_seconds(manual_br_start)
                    br_end = parse_time_to_seconds(manual_br_end)
                    if br_start is not None and br_end is not None:
                        st.session_state.br_start_sec = br_start
                        st.session_state.br_end_sec = br_end
                        st.success(
                            f"✅ Zaktualizowano zakres BR: {manual_br_start} - {manual_br_end}"
                        )

            # BR chart range
            br_startsec = st.session_state.br_start_sec
            br_endsec = st.session_state.br_end_sec
            br_mask = (target_df["time"] >= br_startsec) & (target_df["time"] <= br_endsec)
            br_interval_data = target_df.loc[br_mask]

            if not br_interval_data.empty and br_endsec > br_startsec:
                br_duration_sec = int(br_endsec - br_startsec)

                # BR Statistics
                avg_br = br_interval_data["tymebreathrate"].mean()
                min_br = br_interval_data["tymebreathrate"].min()
                max_br = br_interval_data["tymebreathrate"].max()
                avg_pace_br = (
                    br_interval_data["pace"].mean() if "pace" in br_interval_data.columns else 0
                )
                avg_pace_br_min = avg_pace_br / 60.0 if avg_pace_br > 0 else 0

                # Trend (Slope) for BR
                if len(br_interval_data) > 1:
                    slope_br, intercept_br, _, _, _ = stats.linregress(
                        br_interval_data["time"], br_interval_data["tymebreathrate"]
                    )
                    trend_br_desc = f"{slope_br:.4f} /s"
                else:
                    slope_br = 0
                    intercept_br = 0
                    trend_br_desc = "N/A"

                # BR Metrics
                st.markdown(
                    f"##### METRYKI BR: {format_time(br_startsec)} - {format_time(br_endsec)} ({br_duration_sec}s)"
                )
                br_m1, br_m2, br_m3, br_m4, br_m5 = st.columns(5)
                br_m1.metric("Śr. BR", f"{avg_br:.1f} /min")
                br_m2.metric("Min BR", f"{min_br:.1f} /min")
                br_m3.metric("Max BR", f"{max_br:.1f} /min")
                br_m4.metric("Śr. Tempo", f"{avg_pace_br_min:.2f} min/km")
                trend_color_br = "inverse" if slope_br > 0.01 else "normal"
                br_m5.metric(
                    "Trend BR (Slope)",
                    trend_br_desc,
                    delta=trend_br_desc,
                    delta_color=trend_color_br,
                )

                # BR Chart
                fig_br = go.Figure()

                # BR (Primary)
                fig_br.add_trace(
                    go.Scatter(
                        x=target_df["time"],
                        y=target_df["rr_smooth"],
                        customdata=target_df["time_str"],
                        mode="lines",
                        name="BR (/min)",
                        line=dict(color="#00cc96", width=2),
                        hovertemplate="<b>Czas:</b> %{customdata}<br><b>BR:</b> %{y:.1f} /min<extra></extra>",
                    )
                )

                # Pace (Secondary)
                if "pace_smooth" in target_df.columns:
                    # Convert pace to min/km for display
                    pace_min_br = target_df["pace_smooth"] / 60.0
                    # Create formatted pace string as mm:ss
                    pace_br_formatted = pace_min_br.apply(lambda x: f"{int(x):d}:{int((x % 1) * 60):02d}" if x > 0 else "--:--")
                    fig_br.add_trace(
                        go.Scatter(
                            x=target_df["time"],
                            y=pace_min_br,
                            customdata=np.stack([target_df["time_str"], pace_br_formatted], axis=-1),
                            mode="lines",
                            name="Tempo",
                            line=dict(color="#00BCD4", width=1),
                            yaxis="y2",
                            opacity=0.3,
                            hovertemplate="<b>Czas:</b> %{customdata[0]}<br><b>Tempo:</b> %{customdata[1]} min/km<extra></extra>",
                        )
                    )

                # Selection area
                fig_br.add_vrect(
                    x0=br_startsec,
                    x1=br_endsec,
                    fillcolor="green",
                    opacity=0.1,
                    layer="below",
                    line_width=0,
                    annotation_text="BR",
                    annotation_position="top left",
                )

                # Trend line
                if len(br_interval_data) > 1:
                    trend_line_br = intercept_br + slope_br * br_interval_data["time"]
                    fig_br.add_trace(
                        go.Scatter(
                            x=br_interval_data["time"],
                            y=trend_line_br,
                            mode="lines",
                            name="Trend BR",
                            line=dict(color="white", width=2, dash="dash"),
                            hovertemplate="<b>Trend:</b> %{y:.2f} /min<extra></extra>",
                        )
                    )

                fig_br.update_layout(
                    title="Dynamika Częstości Oddechów vs Tempo",
                    xaxis_title="Czas",
                    yaxis=dict(title=dict(text="BR (/min)", font=dict(color="#00cc96"))),
                    yaxis2=dict(
                        title=dict(text="Tempo (min/km)", font=dict(color="#00BCD4")),
                        overlaying="y",
                        side="right",
                        showgrid=False,
                        autorange="reversed",
                    ),
                    legend=dict(x=0.01, y=0.99),
                    height=450,
                    margin=dict(l=20, r=20, t=40, b=20),
                    hovermode="x unified",
                )

                # Interactive chart
                selected_br = st.plotly_chart(
                    fig_br,
                    use_container_width=True,
                    key="br_chart",
                    on_select="rerun",
                    selection_mode="box",
                )

                # Handle selection
                if selected_br and "selection" in selected_br and "box" in selected_br["selection"]:
                    box_data_br = selected_br["selection"]["box"]
                    if box_data_br and len(box_data_br) > 0:
                        x_range_br = box_data_br[0].get("x", [])
                        if len(x_range_br) == 2:
                            new_br_start = min(x_range_br)
                            new_br_end = max(x_range_br)
                            if (
                                new_br_start != st.session_state.br_start_sec
                                or new_br_end != st.session_state.br_end_sec
                            ):
                                st.session_state.br_start_sec = new_br_start
                                st.session_state.br_end_sec = new_br_end
                                st.rerun()
        else:
            st.warning("Brak danych Breath Rate (tymebreathrate) w pliku.")

        # ===== TIDAL VOLUME (VT) INTERACTIVE CHART =====
        st.markdown("---")
        st.subheader("💨 Objętość Oddechowa (Tidal Volume)")

        if "tidal_volume" in target_df.columns:
            st.info(
                "💡 **ANALIZA VT:** Zaznacz obszar na wykresie (kliknij i przeciągnij), aby sprawdzić statystyki i trend. VT = VE / BR."
            )

            with st.expander("🔧 Ręczne wprowadzenie zakresu czasowego VT", expanded=False):
                col_tv_1, col_tv_2 = st.columns(2)
                with col_tv_1:
                    manual_tv_start = st.text_input(
                        "Start Interwału (hh:mm:ss)", value="00:10:00", key="tv_manual_start"
                    )
                with col_tv_2:
                    manual_tv_end = st.text_input(
                        "Koniec Interwału (hh:mm:ss)", value="00:20:00", key="tv_manual_end"
                    )

                if st.button("Zastosuj ręczny zakres", key="btn_tv_manual"):
                    tv_start = parse_time_to_seconds(manual_tv_start)
                    tv_end = parse_time_to_seconds(manual_tv_end)
                    if tv_start is not None and tv_end is not None:
                        st.session_state.tv_start_sec = tv_start
                        st.session_state.tv_end_sec = tv_end
                        st.success(
                            f"✅ Zaktualizowano zakres VT: {manual_tv_start} - {manual_tv_end}"
                        )

            # VT chart range
            tv_startsec = st.session_state.tv_start_sec
            tv_endsec = st.session_state.tv_end_sec
            tv_mask = (target_df["time"] >= tv_startsec) & (target_df["time"] <= tv_endsec)
            tv_interval_data = target_df.loc[tv_mask]

            if not tv_interval_data.empty and tv_endsec > tv_startsec:
                tv_duration_sec = int(tv_endsec - tv_startsec)

                # VT Statistics (filter out NaN/inf)
                tv_clean = (
                    tv_interval_data["tidal_volume"]
                    .replace([float("inf"), float("-inf")], float("nan"))
                    .dropna()
                )
                if len(tv_clean) > 0:
                    avg_tv = tv_clean.mean()
                    min_tv = tv_clean.min()
                    max_tv = tv_clean.max()
                else:
                    avg_tv = min_tv = max_tv = 0
                avg_pace_tv = (
                    tv_interval_data["pace"].mean() if "pace" in tv_interval_data.columns else 0
                )
                avg_pace_tv_min = avg_pace_tv / 60.0 if avg_pace_tv > 0 else 0

                # Trend (Slope) for VT
                tv_valid = tv_interval_data[["time", "tidal_volume"]].dropna()
                tv_valid = tv_valid[~tv_valid["tidal_volume"].isin([float("inf"), float("-inf")])]
                if len(tv_valid) > 1:
                    slope_tv, intercept_tv, _, _, _ = stats.linregress(
                        tv_valid["time"], tv_valid["tidal_volume"]
                    )
                    trend_tv_desc = f"{slope_tv:.5f} L/s"
                else:
                    slope_tv = 0
                    intercept_tv = 0
                    trend_tv_desc = "N/A"

                # VT Metrics
                st.markdown(
                    f"##### METRYKI VT: {format_time(tv_startsec)} - {format_time(tv_endsec)} ({tv_duration_sec}s)"
                )
                tv_m1, tv_m2, tv_m3, tv_m4, tv_m5 = st.columns(5)
                tv_m1.metric("Śr. VT", f"{avg_tv:.2f} L")
                tv_m2.metric("Min VT", f"{min_tv:.2f} L")
                tv_m3.metric("Max VT", f"{max_tv:.2f} L")
                tv_m4.metric("Śr. Tempo", f"{avg_pace_tv_min:.2f} min/km")
                trend_color_tv = "inverse" if slope_tv < -0.0001 else "normal"
                tv_m5.metric(
                    "Trend VT (Slope)",
                    trend_tv_desc,
                    delta=trend_tv_desc,
                    delta_color=trend_color_tv,
                )

                # VT Chart
                fig_tv = go.Figure()

                # VT (Primary)
                fig_tv.add_trace(
                    go.Scatter(
                        x=target_df["time"],
                        y=target_df["tv_smooth"],
                        customdata=target_df["time_str"],
                        mode="lines",
                        name="VT (L)",
                        line=dict(color="#ab63fa", width=2),
                        hovertemplate="<b>Czas:</b> %{customdata}<br><b>VT:</b> %{y:.2f} L<extra></extra>",
                    )
                )

                # Pace (Secondary)
                if "pace_smooth" in target_df.columns:
                    # Convert pace to min/km for display
                    pace_min_tv = target_df["pace_smooth"] / 60.0
                    # Create formatted pace string as mm:ss
                    pace_tv_formatted = pace_min_tv.apply(lambda x: f"{int(x):d}:{int((x % 1) * 60):02d}" if x > 0 else "--:--")
                    fig_tv.add_trace(
                        go.Scatter(
                            x=target_df["time"],
                            y=pace_min_tv,
                            customdata=np.stack([target_df["time_str"], pace_tv_formatted], axis=-1),
                            mode="lines",
                            name="Tempo",
                            line=dict(color="#00BCD4", width=1),
                            yaxis="y2",
                            opacity=0.3,
                            hovertemplate="<b>Czas:</b> %{customdata[0]}<br><b>Tempo:</b> %{customdata[1]} min/km<extra></extra>",
                        )
                    )

                # Selection area
                fig_tv.add_vrect(
                    x0=tv_startsec,
                    x1=tv_endsec,
                    fillcolor="purple",
                    opacity=0.1,
                    layer="below",
                    line_width=0,
                    annotation_text="VT",
                    annotation_position="top left",
                )

                # Trend line
                if len(tv_valid) > 1:
                    trend_line_tv = intercept_tv + slope_tv * tv_valid["time"]
                    fig_tv.add_trace(
                        go.Scatter(
                            x=tv_valid["time"],
                            y=trend_line_tv,
                            mode="lines",
                            name="Trend VT",
                            line=dict(color="white", width=2, dash="dash"),
                            hovertemplate="<b>Trend:</b> %{y:.3f} L<extra></extra>",
                        )
                    )

                fig_tv.update_layout(
                    title="Dynamika Objętości Oddechowej vs Tempo",
                    xaxis_title="Czas",
                    yaxis=dict(title=dict(text="VT (L)", font=dict(color="#ab63fa"))),
                    yaxis2=dict(
                        title=dict(text="Tempo (min/km)", font=dict(color="#00BCD4")),
                        overlaying="y",
                        side="right",
                        showgrid=False,
                        autorange="reversed",
                    ),
                    legend=dict(x=0.01, y=0.99),
                    height=450,
                    margin=dict(l=20, r=20, t=40, b=20),
                    hovermode="x unified",
                )

                # Interactive chart
                selected_tv = st.plotly_chart(
                    fig_tv,
                    use_container_width=True,
                    key="tv_chart",
                    on_select="rerun",
                    selection_mode="box",
                )

                # Handle selection
                if selected_tv and "selection" in selected_tv and "box" in selected_tv["selection"]:
                    box_data_tv = selected_tv["selection"]["box"]
                    if box_data_tv and len(box_data_tv) > 0:
                        x_range_tv = box_data_tv[0].get("x", [])
                        if len(x_range_tv) == 2:
                            new_tv_start = min(x_range_tv)
                            new_tv_end = max(x_range_tv)
                            if (
                                new_tv_start != st.session_state.tv_start_sec
                                or new_tv_end != st.session_state.tv_end_sec
                            ):
                                st.session_state.tv_start_sec = new_tv_start
                                st.session_state.tv_end_sec = new_tv_end
                                st.rerun()
        else:
            st.warning(
                "Brak danych do obliczenia Tidal Volume (wymagane: tymeventilation i tymebreathrate)."
            )

        # ===== LEGACY TOOLS (Surowe Dane) =====
        st.markdown("---")
        with st.expander("🔧 Szczegółowa Analiza (Surowe Dane)", expanded=False):
            st.markdown("### Surowe Dane i Korelacje")

            # Scatter Plot: VE vs Watts
            if "watts" in interval_data.columns:
                interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                    "%H:%M:%S"
                )

                fig_scatter = go.Figure()
                fig_scatter.add_trace(
                    go.Scatter(
                        x=interval_data["watts"],
                        y=interval_data["tymeventilation"],
                        customdata=interval_time_str,
                        mode="markers",
                        marker=dict(
                            size=6,
                            color=interval_data["time"],
                            colorscale="Viridis",
                            showscale=True,
                            colorbar=dict(title="Czas (s)"),
                        ),
                        name="VE vs Power",
                        hovertemplate="<b>Czas:</b> %{customdata}<br><b>Tempo:</b> %{x:.2f} min/km<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
                    )
                )
                fig_scatter.update_layout(
                    title="Korelacja: VE vs Tempo",
                    xaxis_title="Tempo [min/km]",
                    yaxis_title="VE (L/min)",
                    height=400,
                    hovermode="closest",
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

            # Breathing Rate Visualization
            if "tymebreathrate" in interval_data.columns:
                st.subheader("Częstość Oddechów (Breathing Rate)")

                interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                    "%H:%M:%S"
                )

                fig_br = go.Figure()
                fig_br.add_trace(
                    go.Scatter(
                        x=interval_data["time"],
                        y=interval_data["tymebreathrate"],
                        customdata=interval_time_str,
                        mode="lines",
                        name="BR",
                        line=dict(color="#00cc96", width=2),
                        hovertemplate="<b>Czas:</b> %{customdata}<br><b>BR:</b> %{y:.1f} /min<extra></extra>",
                    )
                )
                fig_br.update_layout(
                    title="Breathing Rate",
                    xaxis_title="Czas",
                    yaxis_title="BR (/min)",
                    height=300,
                    hovermode="x unified",
                )
                st.plotly_chart(fig_br, use_container_width=True)

            # Minute Ventilation Chart
            st.subheader("Wentylacja Minutowa (VE)")

            interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                "%H:%M:%S"
            )

            fig_ve = go.Figure()
            fig_ve.add_trace(
                go.Scatter(
                    x=interval_data["time"],
                    y=interval_data["tymeventilation"],
                    customdata=interval_time_str,
                    mode="lines",
                    name="VE",
                    line=dict(color="#ffa15a", width=2),
                    hovertemplate="<b>Czas:</b> %{customdata}<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
                )
            )
            fig_ve.update_layout(
                title="Minute Ventilation (VE)",
                xaxis_title="Czas",
                yaxis_title="VE (L/min)",
                height=300,
                hovermode="x unified",
            )
            st.plotly_chart(fig_ve, use_container_width=True)

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
