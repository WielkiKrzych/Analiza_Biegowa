import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from scipy import stats
from modules.calculations.kinetics import generate_state_timeline
from modules.calculations.quality import check_signal_quality


def render_smo2_tab(target_df, training_notes, uploaded_file_name):
    st.header("Analiza SmO2 (Oksygenacja Mięśniowa)")
    st.markdown("Analiza surowych danych SmO2, trendów i kontekstu obciążenia.")

    if target_df is None or target_df.empty:
        st.error("Brak danych. Najpierw wgraj plik w sidebar.")
        return

    if "time" not in target_df.columns:
        st.error("Brak kolumny 'time' w danych!")
        return

    if "smo2" not in target_df.columns:
        st.info("ℹ️ Brak danych SmO2 w tym pliku.")
        return

    # Ensure smoothed columns exist
    if "watts_smooth_5s" not in target_df.columns and "watts" in target_df.columns:
        target_df["watts_smooth_5s"] = target_df["watts"].rolling(window=5, center=True).mean()
    if "smo2_smooth" not in target_df.columns:
        target_df["smo2_smooth"] = target_df["smo2"].rolling(window=5, center=True).mean()

    target_df["time_str"] = pd.to_datetime(target_df["time"], unit="s").dt.strftime("%H:%M:%S")

    # Check Quality
    qual_res = check_signal_quality(target_df["smo2"], "SmO2", (0, 100))
    if not qual_res["is_valid"]:
        st.warning(f"⚠️ **Niska Jakość Sygnału SmO2 (Score: {qual_res['score']})**")
        for issue in qual_res["issues"]:
            st.caption(f"❌ {issue}")

    # Inicjalizacja session_state
    if "smo2_start_sec" not in st.session_state:
        st.session_state.smo2_start_sec = 600
    if "smo2_end_sec" not in st.session_state:
        st.session_state.smo2_end_sec = 1200

    # ===== NOTATKI SmO2 =====
    with st.expander("📝 Dodaj Notatkę do tej Analizy", expanded=False):
        note_col1, note_col2 = st.columns([1, 2])
        with note_col1:
            note_time = st.number_input(
                "Czas (min)",
                min_value=0.0,
                max_value=float(len(target_df) / 60) if len(target_df) > 0 else 60.0,
                value=float(len(target_df) / 120) if len(target_df) > 0 else 15.0,
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

    # Wyświetl istniejące notatki SmO2
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

    st.markdown("---")

    # ===== ANALIZA MANUALNA (jak w Wentylacji) =====
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
                "Start Interwału (hh:mm:ss)", value="00:10:00", key="smo2_manual_start"
            )
        with col_inp_2:
            manual_end = st.text_input(
                "Koniec Interwału (hh:mm:ss)", value="00:20:00", key="smo2_manual_end"
            )

        if st.button("Zastosuj ręczny zakres", key="btn_smo2_manual"):
            manual_start_sec = parse_time_to_seconds(manual_start)
            manual_end_sec = parse_time_to_seconds(manual_end)
            if manual_start_sec is not None and manual_end_sec is not None:
                st.session_state.smo2_start_sec = manual_start_sec
                st.session_state.smo2_end_sec = manual_end_sec
                st.success(f"✅ Zaktualizowano zakres: {manual_start} - {manual_end}")

    # Użyj wartości z session_state
    startsec = st.session_state.smo2_start_sec
    endsec = st.session_state.smo2_end_sec

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
        avg_watts = interval_data["watts"].mean() if "watts" in interval_data.columns else 0
        avg_smo2 = interval_data["smo2"].mean()
        avg_thb = interval_data["thb"].mean() if "thb" in interval_data.columns else None

        # Trend (Slope) dla SmO2
        if len(interval_data) > 1:
            slope_smo2, intercept_smo2, _, _, _ = stats.linregress(
                interval_data["time"], interval_data["smo2"]
            )
            trend_desc = f"{slope_smo2:.4f} %/s"
        else:
            slope_smo2 = 0
            intercept_smo2 = 0
            trend_desc = "N/A"

        # Metryki Manualne
        st.subheader(
            f"METRYKI MANUALNE: {format_time(startsec)} - {format_time(endsec)} ({duration_sec}s)"
        )

        if avg_thb is not None:
            m1, m2, m3, m4 = st.columns(4)
        else:
            m1, m2, m3, m4 = st.columns(4)

        m1.metric("Śr. Moc", f"{avg_watts:.0f} W")
        m2.metric("Śr. SmO2", f"{avg_smo2:.1f} %")

        if avg_thb is not None:
            m3.metric("Śr. THb", f"{avg_thb:.2f} g/dL")
        else:
            cadence = interval_data["cadence"].mean() if "cadence" in interval_data.columns else 0
            m3.metric("Śr. Kadencja", f"{cadence:.0f} rpm")

        # Kolorowanie trendu
        trend_color = "inverse" if slope_smo2 < -0.01 else "normal"
        m4.metric("Trend SmO2 (Slope)", trend_desc, delta=trend_desc, delta_color=trend_color)

        # ===== WYKRES GŁÓWNY (SUROWE SmO2) =====
        fig_smo2 = go.Figure()

        # SmO2 (Primary - RAW values)
        fig_smo2.add_trace(
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

        # Power (Secondary)
        if "watts_smooth_5s" in target_df.columns:
            fig_smo2.add_trace(
                go.Scatter(
                    x=target_df["time"],
                    y=target_df["watts_smooth_5s"],
                    customdata=target_df["time_str"],
                    mode="lines",
                    name="Power",
                    line=dict(color="#1f77b4", width=1),
                    yaxis="y2",
                    opacity=0.3,
                    hovertemplate="<b>Czas:</b> %{customdata}<br><b>Moc:</b> %{y:.0f} W<extra></extra>",
                )
            )

        # Zaznaczenie manualne
        fig_smo2.add_vrect(
            x0=startsec,
            x1=endsec,
            fillcolor="orange",
            opacity=0.1,
            layer="below",
            line_width=0,
            annotation_text="MANUAL",
            annotation_position="top left",
        )

        # Linia trendu SmO2 (dla manualnego)
        if len(interval_data) > 1:
            trend_line = intercept_smo2 + slope_smo2 * interval_data["time"]
            fig_smo2.add_trace(
                go.Scatter(
                    x=interval_data["time"],
                    y=trend_line,
                    mode="lines",
                    name="Trend SmO2 (Man)",
                    line=dict(color="white", width=2, dash="dash"),
                    hovertemplate="<b>Trend:</b> %{y:.2f}%<extra></extra>",
                )
            )

        fig_smo2.update_layout(
            title="Dynamika SmO2 vs Moc (Surowe Wartości)",
            xaxis_title="Czas",
            yaxis=dict(title=dict(text="SmO2 (%)", font=dict(color="#FF4B4B"))),
            yaxis2=dict(
                title=dict(text="Moc (W)", font=dict(color="#1f77b4")),
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            legend=dict(x=0.01, y=0.99),
            height=500,
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode="x unified",
        )

        # Wykres z interaktywnym zaznaczaniem
        selected = st.plotly_chart(
            fig_smo2,
            use_container_width=True,
            key="smo2_chart",
            on_select="rerun",
            selection_mode="box",
        )

        # ===== WYKRES THb (taki sam jak SmO2) =====
        if "thb" in target_df.columns:
            st.markdown("---")

            # Przygotowanie danych THb
            target_df["thb_smooth"] = target_df["thb"].rolling(window=30, center=True).median()

            # Trend (Slope) dla THb
            if len(interval_data) > 1 and "thb" in interval_data.columns:
                slope_thb, intercept_thb, _, _, _ = stats.linregress(
                    interval_data["time"], interval_data["thb"]
                )
                trend_thb_desc = f"{slope_thb:.4f} g/dL/s"
            else:
                slope_thb = 0
                intercept_thb = 0
                trend_thb_desc = "N/A"

            # Metryki THb
            thb_cols = st.columns(4)
            thb_cols[0].metric("Śr. Moc", f"{avg_watts:.0f} W")
            thb_cols[1].metric("Śr. THb", f"{avg_thb:.2f} g/dL")
            thb_cols[2].metric("Trend THb (Slope)", trend_thb_desc)

            # Wykres THb
            fig_thb = go.Figure()

            # THb (Primary)
            fig_thb.add_trace(
                go.Scatter(
                    x=target_df["time"],
                    y=target_df["thb_smooth"],
                    customdata=target_df["time_str"],
                    mode="lines",
                    name="THb (g/dL)",
                    line=dict(color="#9467bd", width=2),  # Purple color
                    hovertemplate="<b>Czas:</b> %{customdata}<br><b>THb:</b> %{y:.2f} g/dL<extra></extra>",
                )
            )

            # Power (Secondary)
            if "watts_smooth_5s" in target_df.columns:
                fig_thb.add_trace(
                    go.Scatter(
                        x=target_df["time"],
                        y=target_df["watts_smooth_5s"],
                        customdata=target_df["time_str"],
                        mode="lines",
                        name="Power",
                        line=dict(color="#1f77b4", width=1),
                        yaxis="y2",
                        opacity=0.3,
                        hovertemplate="<b>Czas:</b> %{customdata}<br><b>Moc:</b> %{y:.0f} W<extra></extra>",
                    )
                )

            # Zaznaczenie manualne
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

            # Linia trendu THb
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
                title="Dynamika THb vs Moc (Surowe Wartości)",
                xaxis_title="Czas",
                yaxis=dict(title=dict(text="THb (g/dL)", font=dict(color="#9467bd"))),
                yaxis2=dict(
                    title=dict(text="Moc (W)", font=dict(color="#1f77b4")),
                    overlaying="y",
                    side="right",
                    showgrid=False,
                ),
                legend=dict(x=0.01, y=0.99),
                height=500,
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode="x unified",
            )

            st.plotly_chart(fig_thb, use_container_width=True, key="thb_chart")

        # Obsługa zaznaczenia
        if selected and "selection" in selected and "box" in selected["selection"]:
            box_data = selected["selection"]["box"]
            if box_data and len(box_data) > 0:
                x_range = box_data[0].get("x", [])
                if len(x_range) == 2:
                    new_start = min(x_range)
                    new_end = max(x_range)
                    if (
                        new_start != st.session_state.smo2_start_sec
                        or new_end != st.session_state.smo2_end_sec
                    ):
                        st.session_state.smo2_start_sec = new_start
                        st.session_state.smo2_end_sec = new_end
                        st.rerun()

        # ===== LEGACY TOOLS =====
        with st.expander("🔧 Szczegółowa Analiza (Legacy Tools)", expanded=False):
            st.markdown("### Surowe Dane i Korelacje")

            # Scatter Plot: SmO2 vs Watts
            if "watts" in interval_data.columns:
                # Prepare time formatting
                interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                    "%H:%M:%S"
                )

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
                    xaxis_title="Power (W)",
                    yaxis_title="SmO2 (%)",
                    height=400,
                    hovermode="closest",
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

            # THb Visualization
            if "thb" in interval_data.columns:
                st.subheader("Hemoglobina Całkowita (THb)")

                # Prepare time_str for interval data
                interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                    "%H:%M:%S"
                )

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

    else:
        st.warning("Brak danych w wybranym zakresie.")

    # ===== TEORIA =====
    with st.expander("🫁 TEORIA: Interpretacja SmO2", expanded=False):
        st.markdown("""
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
        """)
