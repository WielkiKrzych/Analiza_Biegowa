import streamlit as st
import plotly.graph_objects as go
import pandas as pd

def render_limiters_tab(df_plot, cp_input, vt2_vent):
    st.header("Analiza Limiterów Fizjologicznych (INSCYD-style)")
    st.markdown("Identyfikujemy Twoje ograniczenia metaboliczne i typ zawodniczy na podstawie danych treningowych.")

    # Normalize columns
    df_plot.columns = df_plot.columns.str.lower().str.strip()
    
    # Handle HR aliases
    if 'hr' not in df_plot.columns:
        for alias in ['heartrate', 'heart_rate', 'bpm']:
            if alias in df_plot.columns:
                df_plot.rename(columns={alias: 'hr'}, inplace=True)
                break
    
    has_hr = 'hr' in df_plot.columns
    has_ve = any(c in df_plot.columns for c in ['tymeventilation', 've', 'ventilation'])
    has_smo2 = 'smo2' in df_plot.columns
    has_watts = 'watts' in df_plot.columns
    
    # Sport detection: running uses pace, cycling uses watts
    is_running = "pace" in df_plot.columns and "watts" not in df_plot.columns

    # =========================================================================
    # RUNNING MODE - Pace-based athlete profiling
    # =========================================================================
    if is_running:
        st.header("Analiza Limiterów Biegowych")
        st.markdown("Identyfikujemy Twój profil biegacza i ograniczenia wydolnościowe na podstawie tempa.")
        
        # --- SEKCJA 1: PROFIL BIEGACZA ---
        st.subheader("🏃 Profil Biegacza")
        
        # Calculate best pace for different windows (lower = faster)
        df_plot['pace_1min'] = df_plot['pace'].rolling(window=60, min_periods=60).mean()
        df_plot['pace_5min'] = df_plot['pace'].rolling(window=300, min_periods=300).mean()
        df_plot['pace_10min'] = df_plot['pace'].rolling(window=600, min_periods=600).mean()
        df_plot['pace_20min'] = df_plot['pace'].rolling(window=1200, min_periods=1200).mean()
        
        # Best (minimum) pace values
        best_1min = df_plot['pace_1min'].min() if not df_plot['pace_1min'].isna().all() else None
        best_5min = df_plot['pace_5min'].min() if not df_plot['pace_5min'].isna().all() else None
        best_10min = df_plot['pace_10min'].min() if not df_plot['pace_10min'].isna().all() else None
        best_20min = df_plot['pace_20min'].min() if not df_plot['pace_20min'].isna().all() else None
        
        # Display pace metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Najlepsze 1 min", f"{best_1min/60:.2f} min/km" if best_1min else "N/A")
        col2.metric("Najlepsze 5 min", f"{best_5min/60:.2f} min/km" if best_5min else "N/A")
        col3.metric("Najlepsze 10 min", f"{best_10min/60:.2f} min/km" if best_10min else "N/A")
        col4.metric("Najlepsze 20 min", f"{best_20min/60:.2f} min/km" if best_20min else "N/A")
        
        # Classify runner phenotype based on pace ratio
        if best_5min and best_10min and best_5min > 0:
            pace_ratio = best_10min / best_5min  # Lower ratio = better endurance
            
            if pace_ratio < 1.03:
                profile = "🏃 Maratończyk / Ultra"
                profile_color = "#4ecdc4"
                strength = "Doskonała wytrzymałość, utrzymuje tempo na długich dystansach"
                weakness = "Może brakować dynamiki na krótkich odcinkach"
                phenotype = "marathoner"
            elif pace_ratio < 1.06:
                profile = "⚖️ Wszechstronny biegacz"
                profile_color = "#ffd93d"
                strength = "Zbalansowany profil, dobry na różnych dystansach"
                weakness = "Brak dominującej specjalizacji"
                phenotype = "all_rounder"
            elif pace_ratio < 1.10:
                profile = "🏃‍♂️ Średniak (5K-10K)"
                profile_color = "#45b7d1"
                strength = "Dobre połączenie szybkości i wytrzymałości"
                weakness = "Może słabnąć na dystansach powyżej 10K"
                phenotype = "middle_distance"
            else:
                profile = "⚡ Sprinter / Miler"
                profile_color = "#ff6b6b"
                strength = "Wysoka prędkość maksymalna, dynamika"
                weakness = "Szybki spadek tempa na dłuższych dystansach"
                phenotype = "sprinter"
            
            # Display profile
            st.markdown(f"""
            <div style="padding:15px; border-radius:8px; border:2px solid {profile_color}; background-color: #222; margin-top:15px;">
                <h4 style="margin:0; color:{profile_color};">{profile}</h4>
                <p style="margin:10px 0 0 0;"><b>💪 Mocna strona:</b> {strength}</p>
                <p style="margin:5px 0 0 0;"><b>⚠️ Do poprawy:</b> {weakness}</p>
                <p style="margin:5px 0 0 0; font-size:0.85em; color:#888;">Ratio 10min/5min: {pace_ratio:.3f}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            profile = "❓ Nieznany"
            profile_color = "#888"
            phenotype = "unknown"
            pace_ratio = None
            st.info("Trening zbyt krótki dla pełnej analizy profilu (min. 10 min).")
        
        st.divider()
        
        # --- SEKCJA 2: ANALIZA LIMITERÓW BIEGOWYCH ---
        st.subheader("📊 Analiza Limiterów Biegowych")
        
        if best_1min and best_5min and best_20min:
            # Calculate limiter scores (0-100)
            # 1. Speed - based on how fast 1min pace is relative to 5min
            speed_drop = (best_1min / best_5min) if best_5min > 0 else 1
            speed_score = max(0, min(100, (1 - speed_drop) * 1000 + 50))  # Higher = more speed reserve
            
            # 2. Aerobic endurance - based on pace degradation 5min → 20min
            endurance_drop = (best_20min / best_5min) if best_5min > 0 else 1.5
            endurance_score = max(0, min(100, (1.2 - endurance_drop) * 500))  # Higher = better endurance
            
            # 3. Threshold capacity - based on ratio to estimated threshold pace
            threshold_pace_est = best_20min * 1.01 if best_20min else best_5min * 1.1
            avg_pace = df_plot['pace'].mean()
            threshold_score = max(0, min(100, (threshold_pace_est / avg_pace - 0.8) * 250)) if avg_pace else 50
            
            # Normalize to 0-100 range with better scaling
            speed_score = min(100, max(0, speed_score))
            endurance_score = min(100, max(0, endurance_score))
            threshold_score = min(100, max(0, threshold_score))
            
            # Radar chart
            categories = ['Szybkość', 'Wytrzymałość', 'Próg']
            values = [speed_score, endurance_score, threshold_score]
            values_closed = values + [values[0]]
            categories_closed = categories + [categories[0]]
            
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=values_closed,
                theta=categories_closed,
                fill='toself',
                name='Profil Biegowy',
                line=dict(color='#00cc96'),
                fillcolor='rgba(0, 204, 150, 0.3)',
                hovertemplate="%{theta}: <b>%{r:.0f}</b><extra></extra>"
            ))
            
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                template="plotly_dark",
                title="Radar Limitatorów Biegowych",
                height=400
            )
            
            st.plotly_chart(fig_radar, use_container_width=True)
            
            # Identify weakest limiter
            limiters = {
                "Szybkość": speed_score,
                "Wytrzymałość": endurance_score,
                "Próg": threshold_score
            }
            weakest = min(limiters, key=lambda k: limiters[k])
            
            # Display limiter table
            st.markdown(f"""
            ### 🔍 Diagnoza Limiterów
            
            | Limiter | Wynik | Status |
            |---------|-------|--------|
            | **Szybkość** | {speed_score:.0f} | {"🔴 Najsłabszy" if weakest == "Szybkość" else "🟢 OK"} |
            | **Wytrzymałość** | {endurance_score:.0f} | {"🔴 Najsłabszy" if weakest == "Wytrzymałość" else "🟢 OK"} |
            | **Próg** | {threshold_score:.0f} | {"🔴 Najsłabszy" if weakest == "Próg" else "🟢 OK"} |
            
            **Główny Limiter: {weakest}**
            """)
            
            st.divider()
            
            # --- SEKCJA 3: REKOMENDACJE TRENINGOWE ---
            st.subheader("💡 Rekomendacje Treningowe")
            
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
            else:  # Threshold
                st.info("""
                **📈 Ograniczenie: Wydolność Progowa**
                
                Twój próg mleczanowy jest zbyt nisko względem potencjału.
                
                **Sugerowane treningi:**
                - Tempo runs 20-40 min w strefie Z4, 1x/tydzień
                - Interwały progowe: 3-4x 10-15 min @ tempo 10K
                - Cruise intervals: 6-8x 5 min @ pół-maratońskie tempo
                - Podwójne sesje progowe w okresie specjalnym
                """)
            
            # Additional phenotype-specific advice
            st.markdown("#### 🎯 Porady dla Twojego Fenotypu")
            if phenotype == "marathoner":
                st.success("""
                **Maratończyk/Ultra** - Twoja wytrzymałość jest Twoją siłą!
                - Skup się na maratonach i ultra dystansach
                - Regularne biegi 2-3h budują economy
                - Trening na czczo dla adaptacji tłuszczowych
                """)
            elif phenotype == "all_rounder":
                st.success("""
                **Wszechstronny** - Możesz startować na każdym dystansie!
                - Sezonowo specjalizuj się (wiosna 10K, jesień maraton)
                - Utrzymuj zróżnicowany trening
                - Testuj siebie na różnych dystansach
                """)
            elif phenotype == "middle_distance":
                st.success("""
                **Średni dystans (5K-10K)** - Idealny balans szybkość/wytrzymałość!
                - Skup się na 5K i 10K - tu masz potencjał
                - VO2max intervals 4-6x 3-5 min @ 3K-5K pace
                - Tempo runs budują specyfikę wyścigową
                """)
            elif phenotype == "sprinter":
                st.success("""
                **Sprinter/Miler** - Wykorzystaj swoją szybkość!
                - Mile (1609m) i 1500m to Twoje dystanse
                - Wiele treningu szybkościowego (150-400m)
                - Siłownia i plyometrics dla eksplozywności
                """)
        else:
            st.warning("Za mało danych do pełnej analizy limiterów (wymagane min. 20 min danych).")
        
        st.divider()
        
        # --- SEKCJA 4: TEORIA PROFILÓW BIEGOWYCH ---
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
    
    # =========================================================================
    # CYCLING MODE - Power-based athlete profiling (EXISTING CODE)
    # =========================================================================
    elif has_watts:
        # --- SEKCJA 1: PROFIL METABOLICZNY (INSCYD-style) ---
        st.subheader("🧬 Profil Metaboliczny (Szacunkowy)")
        
        # Oblicz MMP dla różnych okien
        df_plot['mmp_1min'] = df_plot['watts'].rolling(window=60, min_periods=60).mean()
        df_plot['mmp_5min'] = df_plot['watts'].rolling(window=300, min_periods=300).mean()
        df_plot['mmp_20min'] = df_plot['watts'].rolling(window=1200, min_periods=1200).mean()
        
        mmp_1min = df_plot['mmp_1min'].max() if not df_plot['mmp_1min'].isna().all() else 0
        mmp_5min = df_plot['mmp_5min'].max() if not df_plot['mmp_5min'].isna().all() else 0
        mmp_20min = df_plot['mmp_20min'].max() if not df_plot['mmp_20min'].isna().all() else 0
        
        # Klasyfikacja typu zawodnika
        if mmp_20min > 0:
            anaerobic_ratio = mmp_5min / mmp_20min
            sprint_ratio = mmp_1min / mmp_5min if mmp_5min > 0 else 1.0
            
            if anaerobic_ratio > 1.08:
                profile = "🏃 Sprinter / Puncheur"
                vlamax_est = "Wysoki (>0.5 mmol/L/s)"
                profile_color = "#ff6b6b"
                strength = "Krótkie, dynamiczne ataki i sprinty"
                weakness = "Dłuższe wysiłki powyżej progu"
            elif anaerobic_ratio < 0.95:
                profile = "🚴 Climber / TT Specialist"
                vlamax_est = "Niski (<0.4 mmol/L/s)"
                profile_color = "#4ecdc4"
                strength = "Długie, równe tempo, wspinaczki"
                weakness = "Reaktywność na ataki, sprint finiszowy"
            else:
                profile = "⚖️ All-Rounder"
                vlamax_est = "Średni (0.4-0.5 mmol/L/s)"
                profile_color = "#ffd93d"
                strength = "Wszechstronność"
                weakness = "Brak dominującej cechy"
            
            # Wyświetl profil
            col1, col2, col3 = st.columns(3)
            col1.metric("Typ Zawodnika", profile)
            col2.metric("Est. VLaMax", vlamax_est)
            col3.metric("Ratio 5min/20min", f"{anaerobic_ratio:.2f}")
            
            st.markdown(f"""
            <div style="padding:15px; border-radius:8px; border:2px solid {profile_color}; background-color: #222;">
                <p style="margin:0;"><b>💪 Mocna strona:</b> {strength}</p>
                <p style="margin:5px 0 0 0;"><b>⚠️ Do poprawy:</b> {weakness}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Trening zbyt krótki dla analizy profilu metabolicznego (min. 20 min).")
            anaerobic_ratio = None
        
        st.divider()

        # --- SEKCJA 2: RADAR LIMITERÓW ---
        if has_hr or has_ve or has_smo2:
            st.subheader("📊 Radar Obciążenia Systemów")
            
            window_options = {
                "1 min (Anaerobic)": 60, 
                "5 min (VO2max)": 300, 
                "20 min (FTP)": 1200,
                "60 min (Endurance)": 3600
            }
            selected_window_name = st.selectbox("Wybierz okno analizy (MMP):", list(window_options.keys()), index=1)
            window_sec = window_options[selected_window_name]

            df_plot['rolling_watts'] = df_plot['watts'].rolling(window=window_sec, min_periods=window_sec).mean()

            if df_plot['rolling_watts'].isna().all():
                st.warning(f"Trening jest krótszy niż {window_sec/60:.0f} min. Wybierz krótsze okno.")
            else:
                peak_idx = df_plot['rolling_watts'].idxmax()

                if not pd.isna(peak_idx):
                    start_idx = max(0, peak_idx - window_sec + 1)
                    df_peak = df_plot.iloc[start_idx:peak_idx+1]
                    
                    # Obliczenia %
                    peak_hr_avg = df_peak['hr'].mean() if has_hr else 0
                    max_hr_user = df_plot['hr'].max() if has_hr else 1
                    pct_hr = (peak_hr_avg / max_hr_user * 100) if max_hr_user > 0 else 0
                    
                    col_ve_nm = next((c for c in ['tymeventilation', 've', 'ventilation'] if c in df_plot.columns), None)
                    peak_ve_avg = df_peak[col_ve_nm].mean() if col_ve_nm else 0
                    max_ve_user = vt2_vent * 1.1 if vt2_vent > 0 else 1
                    pct_ve = (peak_ve_avg / max_ve_user * 100) if max_ve_user > 0 else 0
                    
                    peak_smo2_avg = df_peak['smo2'].mean() if has_smo2 else 100
                    pct_smo2_util = 100 - peak_smo2_avg
                    
                    peak_w_avg = df_peak['watts'].mean()
                    pct_power = (peak_w_avg / cp_input * 100) if cp_input > 0 else 0

                    # Radar
                    categories = ['Serce (% HRmax)', 'Płuca (% VEmax)', 'Mięśnie (% Desat)', 'Moc (% CP)']
                    values = [pct_hr, pct_ve, pct_smo2_util, pct_power]
                    values += [values[0]]
                    categories += [categories[0]]

                    fig_radar = go.Figure()
                    fig_radar.add_trace(go.Scatterpolar(
                        r=values,
                        theta=categories,
                        fill='toself',
                        name=selected_window_name,
                        line=dict(color='#00cc96'),
                        fillcolor='rgba(0, 204, 150, 0.3)',
                        hovertemplate="%{theta}: <b>%{r:.1f}%</b><extra></extra>"
                    ))

                    max_val = max(values)
                    range_max = 100 if max_val < 100 else (max_val + 10)

                    fig_radar.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, range_max])),
                        template="plotly_dark",
                        title=f"Profil Obciążenia: {selected_window_name} ({peak_w_avg:.0f} W)",
                        height=450
                    )
                    
                    st.plotly_chart(fig_radar, use_container_width=True)
                    
                    # Diagnoza
                    limiting_factor = "Serce" if pct_hr >= max(pct_ve, pct_smo2_util) else ("Płuca" if pct_ve >= pct_smo2_util else "Mięśnie")
                    
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
                    
                    # Rekomendacje
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
        
        st.divider()
        
        # --- SEKCJA 3: TEORIA INSCYD ---
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
    else:
        st.error("Brakuje danych mocy (Watts) do analizy limiterów.")
