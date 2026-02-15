import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy import stats

from modules.calculations.running_dynamics import (
    calculate_cadence_stats,
    calculate_gct_stats,
    calculate_stride_metrics,
    analyze_cadence_drift
)
from modules.calculations.pace_utils import pace_to_speed, pace_array_to_speed_array


def render_biomech_tab(df_plot, df_plot_resampled):
    st.header("Biomechaniczny Stres")
    
    # =========================================================================
    # DETEKCJA TYPU SPORTU
    # =========================================================================
    sport_type = st.session_state.get("sport_type", "unknown")
    is_running = sport_type == "running" or 'pace' in df_plot.columns
    is_cycling = sport_type == "cycling" or 'torque_smooth' in df_plot_resampled.columns
    
    # =========================================================================
    # SEKCJE BIEGOWE (tylko dla running)
    # =========================================================================
    if is_running:
        runner_weight = st.session_state.get('rider_weight', 70.0)
        runner_height = st.session_state.get('runner_height', 175)
        
        # ---------------------------------------------------------------------
        # KADENCJA BIEGOWA (SPM)
        # ---------------------------------------------------------------------
        st.subheader("🏃 Kadencja Biegowa (SPM)")
        
        cad_col = None
        for col in ['cadence_smooth', 'cadence', 'spm']:
            if col in df_plot.columns:
                cad_col = col
                break
        
        if cad_col:
            cad_data = df_plot[cad_col].dropna().values
            cad_stats = calculate_cadence_stats(cad_data)
            
            if cad_stats.get('mean_spm', 0) > 0:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Średnia Kadencja", f"{cad_stats['mean_spm']:.0f} SPM")
                c2.metric("Min Kadencja", f"{cad_stats.get('min_spm', '-')}")
                c3.metric("Max Kadencja", f"{cad_stats.get('max_spm', '-')}")
                c4.metric("CV", f"{cad_stats.get('cv_pct', 0):.1f}%")
                
                # Wykres kadencji w czasie
                time_col = 'time_min' if 'time_min' in df_plot.columns else 'time'
                if time_col in df_plot.columns:
                    fig_cad = go.Figure()
                    
                    cad_smooth = df_plot[cad_col].rolling(10, center=True).mean()
                    fig_cad.add_trace(go.Scatter(
                        x=df_plot[time_col],
                        y=cad_smooth,
                        name='Kadencja',
                        line=dict(color='#00D4FF', width=2),
                        hovertemplate="Kadencja: %{y:.0f} SPM<extra></extra>"
                    ))
                    
                    # Linia trendu
                    valid_mask = ~np.isnan(df_plot[cad_col])
                    if valid_mask.sum() > 100:
                        try:
                            slope, intercept, _, _, _ = stats.linregress(
                                df_plot.loc[valid_mask, time_col],
                                df_plot.loc[valid_mask, cad_col]
                            )
                            trend = intercept + slope * df_plot[time_col]
                            fig_cad.add_trace(go.Scatter(
                                x=df_plot[time_col],
                                y=trend,
                                name='Trend',
                                line=dict(color='white', dash='dash'),
                                hoverinfo='skip'
                            ))
                        except:
                            pass
                    
                    # Strefy kadencji (hlines)
                    fig_cad.add_hline(y=170, line_dash="dot", line_color="green", 
                                      annotation_text="Opt min", annotation_position="right")
                    fig_cad.add_hline(y=185, line_dash="dot", line_color="green",
                                      annotation_text="Opt max", annotation_position="right")
                    
                    fig_cad.update_layout(
                        template="plotly_dark",
                        title="Kadencja w czasie",
                        xaxis_title="Czas [min]",
                        yaxis_title="Kadencja [SPM]",
                        height=400,
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", y=1.1, x=0)
                    )
                    st.plotly_chart(fig_cad, use_container_width=True)
                
                st.info("""
                **💡 Interpretacja Kadencji:**
                
                * **Optymalna: 170-185 SPM** - większość biegaczy osiąga najlepszą efektywność
                * **< 160 SPM:** Zbyt wolna - zwiększa obciążenie stawów i ryzyko kontuzji
                * **160-170 SPM:** Niska-moderowana - możliwa poprawa
                * **185-190 SPM:** Wysoka - często u elite
                * **> 190 SPM:** Bardzo wysoka - może wskazywać na krótki krok
                
                **Wskazówka:** Zwiększenie kadencji o 5-10% może zmniejszyć obciążenie stawów bez utraty prędkości.
                """)
        
        st.divider()
        
        # ---------------------------------------------------------------------
        # GROUND CONTACT TIME (GCT)
        # ---------------------------------------------------------------------
        st.subheader("⏱️ Ground Contact Time (GCT)")
        
        gct_col = None
        for col in ['ground_contact', 'gct', 'GroundContactTime']:
            if col in df_plot.columns:
                gct_col = col
                break
        
        if gct_col:
            gct_data = df_plot[gct_col].dropna().values
            gct_stats = calculate_gct_stats(gct_data)
            
            if gct_stats.get('mean_ms', 0) > 0:
                g1, g2, g3 = st.columns(3)
                g1.metric("Średnie GCT", f"{gct_stats['mean_ms']:.0f} ms")
                g2.metric("Min GCT", f"{gct_stats.get('min_ms', '-')}")
                g3.metric("Max GCT", f"{gct_stats.get('max_ms', '-')}")
                
                classification = gct_stats.get('classification', 'unknown')
                class_labels = {
                    'excellent': '🟢 Excellent (<200ms)',
                    'good': '🟢 Dobry (200-220ms)',
                    'average': '🟡 Średni (220-240ms)',
                    'needs-improvement': '🔴 Wymaga poprawy (>240ms)'
                }
                st.metric("Klasyfikacja", class_labels.get(classification, classification))
                
                # Wykres GCT w czasie
                time_col = 'time_min' if 'time_min' in df_plot.columns else 'time'
                if time_col in df_plot.columns:
                    fig_gct = go.Figure()
                    
                    gct_smooth = df_plot[gct_col].rolling(10, center=True).mean()
                    fig_gct.add_trace(go.Scatter(
                        x=df_plot[time_col],
                        y=gct_smooth,
                        name='GCT',
                        line=dict(color='#FF6B6B', width=2),
                        hovertemplate="GCT: %{y:.0f} ms<extra></extra>"
                    ))
                    
                    # Strefy GCT
                    fig_gct.add_hrect(y0=0, y1=200, fillcolor="green", opacity=0.1, line_width=0)
                    fig_gct.add_hrect(y0=200, y1=250, fillcolor="yellow", opacity=0.1, line_width=0)
                    fig_gct.add_hrect(y0=250, y1=400, fillcolor="red", opacity=0.1, line_width=0)
                    
                    fig_gct.update_layout(
                        template="plotly_dark",
                        title="Ground Contact Time w czasie",
                        xaxis_title="Czas [min]",
                        yaxis_title="GCT [ms]",
                        height=400,
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", y=1.1, x=0)
                    )
                    st.plotly_chart(fig_gct, use_container_width=True)
                
                st.info("""
                **💡 Interpretacja GCT:**
                
                * **< 200 ms:** Excellent - typowe dla elite, bardzo efektywny kontakt z podłożem
                * **200-250 ms:** Dobry - solidny poziom amatorski
                * **250-300 ms:** Średni - miejsce na poprawę
                * **> 300 ms:** Wymaga poprawy - długi kontakt = utrata energii
                
                **Krótsze GCT = lepsza sprężystość i ekonomia biegu**
                """)
                if gct_col == 'gct':
                    st.caption("⚠️ GCT estymowane z kadencji (duty cycle ~65%). Dla dokładnych pomiarów użyj Garmin HRM-Run lub Stryd.")
        else:
            st.info("ℹ️ Brak danych GCT - wymagany czujnik biegowy (np. Garmin HRM-Run, Stryd)")
        
        st.divider()
        
        # ---------------------------------------------------------------------
        # STRIDE LENGTH (Długość kroku)
        # ---------------------------------------------------------------------
        st.subheader("📏 Długość Kroku (Stride Length)")
        
        if 'cadence' in df_plot.columns and 'pace' in df_plot.columns:
            stride_metrics = calculate_stride_metrics(df_plot, runner_height)
            
            if stride_metrics:
                s1, s2, s3 = st.columns(3)
                s1.metric("Średnia długość kroku", f"{stride_metrics['stride_length_m']:.2f} m")
                s2.metric("Ratio do wzrostu", f"{stride_metrics['height_ratio']:.2f}")
                s3.metric("Próbki", stride_metrics['samples'])
                
                # Oblicz stride length dla każdego punktu
                valid_mask = (df_plot['cadence'] > 50) & (df_plot['cadence'] < 300) & (df_plot['pace'] > 0)
                df_stride = df_plot[valid_mask].copy()
                
                if not df_stride.empty:
                    speed_m_s = pace_array_to_speed_array(df_stride['pace'].values)
                    cadence_spm = df_stride['cadence'].values
                    # stride_length = speed * 2 * 60 / cadence (pełny krok)
                    df_stride['stride_length'] = speed_m_s * 2 * 60 / cadence_spm
                    
                    time_col = 'time_min' if 'time_min' in df_stride.columns else 'time'
                    
                    fig_stride = go.Figure()
                    stride_smooth = df_stride['stride_length'].rolling(10, center=True).mean()
                    
                    fig_stride.add_trace(go.Scatter(
                        x=df_stride[time_col],
                        y=stride_smooth,
                        name='Długość kroku',
                        line=dict(color='#9B59B6', width=2),
                        hovertemplate="Krok: %{y:.2f} m<extra></extra>"
                    ))
                    
                    fig_stride.update_layout(
                        template="plotly_dark",
                        title="Długość kroku w czasie",
                        xaxis_title="Czas [min]",
                        yaxis_title="Długość kroku [m]",
                        height=350,
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", y=1.1, x=0)
                    )
                    st.plotly_chart(fig_stride, use_container_width=True)
                
                st.info("""
                **💡 Interpretacja długości kroku:**
                
                * **Ratio do wzrostu 0.9-1.1:** Typowy zakres
                * **Większy krok ≠ szybszy bieg** - zależy od kadencji
                * **Optymalna kombinacja:** Wyższa kadencja + umiarkowany krok
                
                **Wzór:** Stride Length = Speed (m/s) × 2 × 60 / Cadence (SPM)
                """)
        else:
            st.info("ℹ️ Do obliczenia długości kroku wymagane dane kadencji i tempa")
        
        st.divider()
        
        # ---------------------------------------------------------------------
        # RUNNING EFFECTIVENESS (RE)
        # ---------------------------------------------------------------------
        st.subheader("⚡ Running Effectiveness (RE)")
        
        if 'watts' in df_plot.columns and 'pace' in df_plot.columns:
            # Oblicz RE dla każdego punktu: RE = speed (m/s) / power (W/kg) * weight
            valid_mask = (df_plot['watts'] > 50) & (df_plot['pace'] > 0)
            df_re = df_plot[valid_mask].copy()
            
            if not df_re.empty:
                speed_m_s = pace_array_to_speed_array(df_re['pace'].values)
                power_w = df_re['watts'].values
                power_per_kg = power_w / runner_weight
                
                # RE = speed / power_per_kg
                df_re['re'] = np.where(power_per_kg > 0, speed_m_s / power_per_kg, np.nan)
                
                avg_re = df_re['re'].mean()
                
                re1, re2, re3 = st.columns(3)
                re1.metric("Średnie RE", f"{avg_re:.3f} m/s/W/kg", 
                          help="RE = prędkość (m/s) / moc (W/kg)")
                
                # Trend RE
                time_col = 'time_min' if 'time_min' in df_re.columns else 'time'
                if time_col in df_re.columns:
                    valid_re = df_re.dropna(subset=['re'])
                    if len(valid_re) > 100:
                        slope, intercept, _, _, _ = stats.linregress(
                            valid_re[time_col], valid_re['re']
                        )
                        total_drift = slope * (valid_re[time_col].iloc[-1] - valid_re[time_col].iloc[0])
                        re2.metric("Trend RE", f"{total_drift:+.3f}", 
                                  delta_color="inverse" if total_drift < 0 else "normal")
                
                # Klasyfikacja
                if avg_re > 1.0:
                    re3.metric("Klasyfikacja", "🟢 Bardzo dobra")
                elif avg_re > 0.85:
                    re3.metric("Klasyfikacja", "🟡 Dobra")
                else:
                    re3.metric("Klasyfikacja", "🔴 Wymaga poprawy")
                
                # Wykres RE w czasie
                fig_re = go.Figure()
                
                re_smooth = df_re['re'].rolling(15, center=True).mean()
                fig_re.add_trace(go.Scatter(
                    x=df_re[time_col],
                    y=re_smooth,
                    name='RE',
                    line=dict(color='#F39C12', width=2),
                    hovertemplate="RE: %{y:.3f}<extra></extra>"
                ))
                
                # Linia odniesienia 1.0
                fig_re.add_hline(y=1.0, line_dash="dash", line_color="green",
                                annotation_text="RE = 1.0 (dobre)")
                
                fig_re.update_layout(
                    template="plotly_dark",
                    title="Running Effectiveness w czasie",
                    xaxis_title="Czas [min]",
                    yaxis_title="RE [m/s/W/kg]",
                    height=350,
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", y=1.1, x=0)
                )
                st.plotly_chart(fig_re, use_container_width=True)
                
                st.info("""
                **💡 Interpretacja Running Effectiveness:**
                
                * **RE > 1.0:** Bardzo dobra efektywność - prędkość dobrze przekłada się na moc
                * **RE 0.85-1.0:** Dobra efektywność
                * **RE < 0.85:** Możliwość poprawy techniki biegu
                
                **Wzór:** RE = Prędkość (m/s) / Moc (W/kg)
                """)
        else:
            st.info("ℹ️ Do obliczenia RE wymagane dane mocy (watts) i tempa (pace)")
        
        st.divider()
    
    # =========================================================================
    # SEKCJE KOLARSKIE (tylko dla cycling)
    # =========================================================================
    if 'torque_smooth' in df_plot_resampled.columns or (is_cycling and not is_running):
        fig_b = go.Figure()
        
        # 1. MOMENT OBROTOWY (Oś Lewa)
        # Kolor różowy/magenta - symbolizuje napięcie/siłę
        fig_b.add_trace(go.Scatter(
            x=df_plot_resampled['time_min'], 
            y=df_plot_resampled['torque_smooth'], 
            name='Moment (Torque)', 
            line=dict(color='#e377c2', width=1.5), 
            hovertemplate="Moment: %{y:.1f} Nm<extra></extra>"
        ))
        
        # 2. KADENCJA (Oś Prawa)
        # Kolor cyan/turkus - symbolizuje szybkość/obroty
        if 'cadence_smooth' in df_plot_resampled.columns:
            fig_b.add_trace(go.Scatter(
                x=df_plot_resampled['time_min'], 
                y=df_plot_resampled['cadence_smooth'], 
                name='Kadencja', 
                yaxis="y2", # Druga oś
                line=dict(color='#19d3f3', width=1.5), 
                hovertemplate="Kadencja: %{y:.0f} RPM<extra></extra>"
            ))
        
        # LAYOUT (Unified Hover)
        fig_b.update_layout(
            template="plotly_dark",
            title="Analiza Generowania Mocy (Siła vs Szybkość)",
            hovermode="x unified",
            
            # Oś X - Czas
            xaxis=dict(
                title="Czas [min]",
                tickformat=".0f",
                hoverformat=".0f"
            ),
            
            # Oś Lewa
            yaxis=dict(title="Moment [Nm]"),
            
            # Oś Prawa
            yaxis2=dict(
                title="Kadencja [RPM]", 
                overlaying="y", 
                side="right", 
                showgrid=False
            ),
            
            legend=dict(orientation="h", y=1.1, x=0),
            margin=dict(l=10, r=10, t=40, b=10),
            height=450
        )
        
        st.plotly_chart(fig_b, use_container_width=True)
        
        st.info("""
        **💡 Kompendium: Moment Obrotowy (Siła) vs Kadencja (Szybkość)**

        Wykres pokazuje, w jaki sposób generujesz moc.
        Pamiętaj: `Moc = Moment x Kadencja`. Tę samą moc (np. 200W) możesz uzyskać "siłowo" (50 RPM) lub "szybkościowo" (100 RPM).

        **1. Interpretacja Stylu Jazdy:**
        * **Grinding (Niska Kadencja < 70, Wysoki Moment):**
            * **Fizjologia:** Dominacja włókien szybkokurczliwych (beztlenowych). Szybkie zużycie glikogenu.
            * **Skutek:** "Betonowe nogi" na biegu.
            * **Ryzyko:** Przeciążenie stawu rzepkowo-udowego (ból kolan) i odcinka lędźwiowego.
        * **Spinning (Wysoka Kadencja > 90, Niski Moment):**
            * **Fizjologia:** Przeniesienie obciążenia na układ krążenia (serce i płuca). Lepsze ukrwienie mięśni (pompa mięśniowa).
            * **Skutek:** Świeższe nogi do biegu (T2).
            * **Wyzwanie:** Wymaga dobrej koordynacji nerwowo-mięśniowej (żeby nie podskakiwać na siodełku).

        **2. Praktyczne Przykłady (Kiedy co stosować?):**
        * **Podjazd:** Naturalna tendencja do spadku kadencji. **Błąd:** "Przepychanie" na twardym biegu. **Korekta:** Zredukuj bieg, utrzymaj 80+ RPM, nawet jeśli prędkość spadnie. Oszczędzisz mięśnie.
        * **Płaski odcinek (TT):** Utrzymuj "Sweet Spot" kadencji (zazwyczaj 85-95 RPM). To balans między zmęczeniem mięśniowym a sercowym.
        * **Finisz / Atak:** Chwilowe wejście w wysoki moment I wysoką kadencję. Kosztowne energetycznie, ale daje max prędkość.

        **3. Możliwe Komplikacje i Sygnały Ostrzegawcze:**
        * **Ból przodu kolana:** Zbyt duży moment obrotowy (za twarde przełożenia). -> Zwiększ kadencję.
        * **Ból bioder / "skakanie":** Zbyt wysoka kadencja przy słabej stabilizacji (core). -> Wzmocnij brzuch lub nieco zwolnij obroty.
        * **Drętwienie stóp:** Często wynik ciągłego nacisku przy niskiej kadencji. Wyższa kadencja poprawia krążenie (faza luzu w obrocie).
        """)
        
        st.divider()
        st.subheader("Wpływ Momentu na Oksydację (Torque vs SmO2)")
        
        if 'torque' in df_plot.columns and 'smo2' in df_plot.columns:
            df_bins = df_plot.copy()
            df_bins['Torque_Bin'] = (df_bins['torque'] // 2 * 2).astype(int)
            
            bin_stats = df_bins.groupby('Torque_Bin')['smo2'].agg(['mean', 'std', 'count']).reset_index()
            bin_stats = bin_stats[bin_stats['count'] > 10]
            
            fig_ts = go.Figure()
            
            fig_ts.add_trace(go.Scatter(
                x=bin_stats['Torque_Bin'], 
                y=bin_stats['mean'] + bin_stats['std'], 
                mode='lines', 
                line=dict(width=0), 
                showlegend=False, 
                name='Górny zakres (+1SD)',
                hovertemplate="Max (zakres): %{y:.1f}%<extra></extra>"
            ))
            
            fig_ts.add_trace(go.Scatter(
                x=bin_stats['Torque_Bin'], 
                y=bin_stats['mean'] - bin_stats['std'], 
                mode='lines', 
                line=dict(width=0), 
                fill='tonexty',
                fillcolor='rgba(255, 75, 75, 0.15)',
                showlegend=False, 
                name='Dolny zakres (-1SD)',
                hovertemplate="Min (zakres): %{y:.1f}%<extra></extra>"
            ))
            
            fig_ts.add_trace(go.Scatter(
                x=bin_stats['Torque_Bin'], 
                y=bin_stats['mean'], 
                mode='lines+markers', 
                name='Średnie SmO2', 
                line=dict(color='#FF4B4B', width=3), 
                marker=dict(size=6, color='#FF4B4B', line=dict(width=1, color='white')),
                hovertemplate="<b>Śr. SmO2:</b> %{y:.1f}%<extra></extra>"
            ))
            
            fig_ts.update_layout(
                template="plotly_dark",
                title="Agregacja: Jak Siła (Moment) wpływa na Tlen (SmO2)?",
                hovermode="x unified",
                xaxis=dict(title="Moment Obrotowy [Nm]"),
                yaxis=dict(title="SmO2 [%]"),
                legend=dict(orientation="h", y=1.1, x=0),
                margin=dict(l=10, r=10, t=40, b=10),
                height=450
            )
            
            st.plotly_chart(fig_ts, use_container_width=True)
            
            st.info("""
            **💡 Fizjologia Okluzji (Analiza Koszykowa):**
            
            **Mechanizm Okluzji:** Kiedy mocno napinasz mięsień (wysoki moment), ciśnienie wewnątrzmięśniowe przewyższa ciśnienie w naczyniach włosowatych. Krew przestaje płynąć, tlen nie dociera, a metabolity (kwas mlekowy) nie są usuwane. To "duszenie" mięśnia od środka.
            
            **Punkt Krytyczny:** Szukaj momentu (na osi X), gdzie czerwona linia gwałtownie opada w dół. To Twój limit siłowy. Powyżej tej wartości generujesz waty 'na kredyt' beztlenowy.
            
            **Praktyczny Wniosek (Scenario):** * Masz do wygenerowania 300W. Możesz to zrobić siłowo (70 RPM, wysoki moment) lub kadencyjnie (90 RPM, niższy moment).
            * Spójrz na wykres: Jeśli przy momencie odpowiadającym 70 RPM Twoje SmO2 spada do 30%, a przy momencie dla 90 RPM wynosi 50% -> **Wybierz wyższą kadencję!** Oszczędzasz nogi (glikogen) kosztem nieco wyższego tętna.
            """)
        
        st.divider()
        st.subheader("🫀 Pulse Power (Moc na Uderzenie Serca)")
        
        if 'watts_smooth' in df_plot_resampled.columns and 'heartrate_smooth' in df_plot_resampled.columns:
            mask_pp = (df_plot_resampled['watts_smooth'] > 50) & (df_plot_resampled['heartrate_smooth'] > 90)
            df_pp = df_plot_resampled[mask_pp].copy()
            
            if not df_pp.empty:
                df_pp['pulse_power'] = df_pp['watts_smooth'] / df_pp['heartrate_smooth']
                
                df_pp['pp_smooth'] = df_pp['pulse_power'].rolling(window=12, center=True).mean() 
                x_pp = df_pp['time_min']
                y_pp = df_pp['pulse_power']
                valid_idx = np.isfinite(x_pp) & np.isfinite(y_pp)
                
                if valid_idx.sum() > 100:
                    slope_pp, intercept_pp, _, _, _ = stats.linregress(x_pp[valid_idx], y_pp[valid_idx])
                    trend_line_pp = intercept_pp + slope_pp * x_pp
                    total_drop = (trend_line_pp.iloc[-1] - trend_line_pp.iloc[0]) / trend_line_pp.iloc[0] * 100
                else:
                    slope_pp = 0; total_drop = 0; trend_line_pp = None

                avg_pp = df_pp['pulse_power'].mean()
                
                c_pp1, c_pp2, c_pp3 = st.columns(3)
                c_pp1.metric("Średnie Pulse Power", f"{avg_pp:.2f} W/bpm", help="Ile watów generuje jedno uderzenie serca.")
                
                drift_color = "normal"
                if total_drop < -5: drift_color = "inverse"
                
                c_pp2.metric("Zmiana Efektywności (Trend)", f"{total_drop:.1f}%", delta_color=drift_color)
                c_pp3.metric("Interpretacja", "Stabilna Wydolność" if total_drop > -5 else "Dryf / Zmęczenie")

                fig_pp = go.Figure()
                
                fig_pp.add_trace(go.Scatter(
                    x=df_pp['time_min'], 
                    y=df_pp['pp_smooth'], 
                    customdata=df_pp['watts_smooth'],
                    name='Pulse Power (W/bpm)', 
                    mode='lines',
                    line=dict(color='#FFD700', width=2),
                    hovertemplate="Pulse Power: %{y:.2f} W/bpm<br>Moc: %{customdata:.0f} W<extra></extra>"
                ))
                
                if trend_line_pp is not None:
                    fig_pp.add_trace(go.Scatter(
                        x=x_pp, y=trend_line_pp,
                        name='Trend',
                        mode='lines',
                        line=dict(color='white', width=1.5, dash='dash'),
                        hoverinfo='skip'
                    ))
                
                fig_pp.add_trace(go.Scatter(
                    x=df_pp['time_min'], y=df_pp['watts_smooth'],
                    name='Moc (tło)',
                    yaxis='y2',
                    line=dict(width=0),
                    fill='tozeroy',
                    fillcolor='rgba(255,255,255,0.05)',
                    hoverinfo='skip'
                ))

                fig_pp.update_layout(
                    template="plotly_dark",
                    title="Pulse Power: Koszt Energetyczny Serca",
                    hovermode="x unified",
                    xaxis=dict(
                        title="Czas [min]",
                        tickformat=".0f",
                        hoverformat=".0f"
                    ),
                    yaxis=dict(title="Pulse Power [W / bpm]"),
                    yaxis2=dict(overlaying='y', side='right', showgrid=False, visible=False),
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", y=1.05, x=0),
                    height=450
                )
                
                st.plotly_chart(fig_pp, use_container_width=True)
                
                st.info("""
                **💡 Jak to czytać?**
                
                * **Pulse Power (W/bpm)** mówi nam o objętości wyrzutowej serca i ekstrakcji tlenu. Im wyżej, tym lepiej.
                * **Trend Płaski:** Idealnie. Twoje serce pracuje tak samo wydajnie w 1. minucie jak w 60. minucie. Jesteś dobrze nawodniony i chłodzony.
                * **Trend Spadkowy (Dryf):** Serce musi bić coraz szybciej, żeby utrzymać te same waty.
                    * **Spadek < 5%:** Norma fizjologiczna.
                    * **Spadek > 10%:** Odwodnienie, przegrzanie lub wyczerpanie zapasów glikogenu w mięśniach. Czas zjeść i pić!
                """)
            else:
                st.warning("Zbyt mało danych (jazda poniżej 50W lub HR poniżej 90bpm), aby obliczyć wiarygodne Pulse Power.")
        else:
            st.error("Brak danych mocy lub tętna.")
        
        st.divider()
        st.subheader("⚙️ Gross Efficiency (GE%) - Estymacja")
        st.caption("Stosunek mocy generowanej (Waty) do spalanej energii (Metabolizm). Typowo: 18-23%.")

        rider_weight = st.session_state.get('rider_weight', 75.0)
        rider_age = st.session_state.get('rider_age', 30)
        is_male = st.session_state.get('is_male', True)

        if 'watts_smooth' in df_plot_resampled.columns and 'heartrate_smooth' in df_plot_resampled.columns:
            gender_factor = -55.0969 if is_male else -20.4022
            
            ee_kj_min = gender_factor + \
                        (0.6309 * df_plot_resampled['heartrate_smooth']) + \
                        (0.1988 * rider_weight) + \
                        (0.2017 * rider_age)
            
            p_metabolic = (ee_kj_min * 1000) / 60
            p_metabolic = p_metabolic.replace(0, np.nan)
            
            ge_series = (df_plot_resampled['watts_smooth'] / p_metabolic) * 100
            
            mask_ge = (df_plot_resampled['watts_smooth'] > 100) & \
                    (ge_series > 5) & (ge_series < 30) & \
                    (df_plot_resampled['heartrate_smooth'] > 110) 
            
            df_ge = pd.DataFrame({
                'time_min': df_plot_resampled['time_min'],
                'ge': ge_series,
                'watts': df_plot_resampled['watts_smooth']
            })
            df_ge.loc[~mask_ge, 'ge'] = np.nan

            if not df_ge['ge'].isna().all():
                avg_ge = df_ge['ge'].mean()
                
                cg1, cg2, cg3 = st.columns(3)
                cg1.metric("Średnie GE", f"{avg_ge:.1f}%", help="Pro: 23%+, Amator: 18-21%")
                
                valid_ge = df_ge.dropna(subset=['ge'])
                if len(valid_ge) > 100:
                    slope_ge, _, _, _, _ = stats.linregress(valid_ge['time_min'], valid_ge['ge'])
                    total_drift_ge = slope_ge * (valid_ge['time_min'].iloc[-1] - valid_ge['time_min'].iloc[0])
                    cg2.metric("Zmiana GE (Trend)", f"{total_drift_ge:.1f}%", delta_color="inverse" if total_drift_ge < 0 else "normal")
                else:
                    cg2.metric("Zmiana GE", "-")

                cg3.info("Wartości powyżej 25% mogą wynikać z opóźnienia tętna względem mocy (np. krótkie interwały). Analizuj trendy na długich odcinkach.")

                fig_ge = go.Figure()
                
                fig_ge.add_trace(go.Scatter(
                    x=df_ge['time_min'], 
                    y=df_ge['ge'],
                    customdata=df_ge['watts'],
                    mode='lines',
                    name='Gross Efficiency (%)',
                    line=dict(color='#00cc96', width=1.5),
                    connectgaps=False,
                    hovertemplate="GE: %{y:.1f}%<br>Moc: %{customdata:.0f} W<extra></extra>"
                ))
                
                fig_ge.add_trace(go.Scatter(
                    x=df_ge['time_min'], 
                    y=df_ge['watts'],
                    mode='lines',
                    name='Moc (Tło)',
                    yaxis='y2',
                    line=dict(color='rgba(255,255,255,0.1)', width=1),
                    fill='tozeroy',
                    fillcolor='rgba(255,255,255,0.05)',
                    hoverinfo='skip'
                ))
                
                if len(valid_ge) > 100:
                    trend_line = np.poly1d(np.polyfit(valid_ge['time_min'], valid_ge['ge'], 1))(valid_ge['time_min'])
                    fig_ge.add_trace(go.Scatter(
                        x=valid_ge['time_min'],
                        y=trend_line,
                        mode='lines',
                        name='Trend GE',
                        line=dict(color='white', width=2, dash='dash')
                    ))

                fig_ge.update_layout(
                    template="plotly_dark",
                    title="Efektywność Brutto (GE%) w Czasie",
                    hovermode="x unified",
                    xaxis=dict(
                        title="Czas [min]",
                        tickformat=".0f",
                        hoverformat=".0f"
                    ),
                    yaxis=dict(title="GE [%]", range=[10, 30]),
                    yaxis2=dict(title="Moc [W]", overlaying='y', side='right', showgrid=False),
                    height=400,
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", y=1.1, x=0)
                )
                
                st.plotly_chart(fig_ge, use_container_width=True)
                
                with st.expander("🧠 Jak interpretować GE?", expanded=False):
                    st.markdown("""
                    **Fizjologia GE:**
                    * **< 18%:** Niska wydajność. Dużo energii tracisz na ciepło i nieskoordynowane ruchy (kołysanie biodrami). Częste u początkujących.
                    * **19-21%:** Standard amatorski. Dobrze wytrenowany kolarz klubowy.
                    * **22-24%:** Poziom ELITE / PRO. Twoje mięśnie to maszyny.
                    * **> 25%:** Podejrzane (chyba że jesteś zwycięzcą Tour de France). Często wynika z błędów pomiaru (np. miernik mocy zawyża, tętno zaniżone, jazda w dół).

                    **Dlaczego GE spada w czasie?**
                    Gdy się męczysz, rekrutujesz włókna mięśniowe typu II (szybkokurczliwe), które są mniej wydajne tlenowo. Dodatkowo rośnie temperatura ciała (Core Temp), co kosztuje energię. Spadek GE pod koniec długiego treningu to doskonały wskaźnik zmęczenia metabolicznego.
                """)
            else:
                st.warning("Brak wystarczających danych do obliczenia GE (zbyt krótkie odcinki stabilnej jazdy).")
        else:
            st.error("Do obliczenia GE potrzebujesz danych Mocy (Watts) oraz Tętna (HR).")

    _render_vertical_oscillation_section(df_plot, df_plot_resampled)


def _render_vertical_oscillation_section(df_plot, df_plot_resampled):
    """Render Vertical Oscillation analysis section."""
    st.divider()
    st.subheader("📊 Vertical Oscillation (Oscylacja Pionowa)")
    
    # Sprawdź czy mamy dane VO
    vo_col = None
    for col in ["verticaloscillation", "VerticalOscillation", "vo", "oscillation"]:
        if col in df_plot.columns:
            vo_col = col
            break
    
    if vo_col is None:
        st.info("""
        ℹ️ **Brak danych Vertical Oscillation**
        
        Aby uzyskać analizę oscylacji pionowej, potrzebujesz czujnika biegowego 
        (np. Garmin HRM-Run, Stryd, lub inny czujnik z pomiarem VO).
        
        **Brakująca kolumna:** `VerticalOscillation` (oscylacja pionowa w cm)
        """)
        return
    
    # Oblicz statystyki
    from modules.calculations.running_dynamics import (
        calculate_vo_stats, 
        analyze_vo_efficiency,
        calculate_running_effectiveness_from_vo
    )
    
    vo_data = df_plot[vo_col].values
    vo_stats = calculate_vo_stats(vo_data)
    
    if not vo_stats:
        st.warning("Brak wystarczających danych VO do analizy.")
        return
    
    # Wyświetl metryki
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Średnie VO", f"{vo_stats.get('mean_vo', 0):.1f} cm")
    col2.metric("Min VO", f"{vo_stats.get('min_vo', 0):.1f} cm")
    col3.metric("Max VO", f"{vo_stats.get('max_vo', 0):.1f} cm")
    col4.metric("CV", f"{vo_stats.get('cv_vo', 0):.1f}%")
    
    # Wykres VO w czasie
    fig_vo = go.Figure()
    
    time_col = 'time_min' if 'time_min' in df_plot.columns else 'time'
    if time_col in df_plot.columns:
        vo_smooth = df_plot[vo_col].rolling(5, center=True).mean()
        fig_vo.add_trace(go.Scatter(
            x=df_plot[time_col],
            y=vo_smooth,
            name='VO',
            line=dict(color='#ff6b6b', width=2),
            hovertemplate="VO: %{y:.1f} cm<extra></extra>"
        ))
        
        # Dodaj linię trendu
        valid_mask = ~np.isnan(df_plot[vo_col])
        if valid_mask.sum() > 100:
            from scipy import stats
            try:
                slope, intercept, _, _, _ = stats.linregress(
                    df_plot.loc[valid_mask, time_col], 
                    df_plot.loc[valid_mask, vo_col]
                )
                trend = intercept + slope * df_plot[time_col]
                fig_vo.add_trace(go.Scatter(
                    x=df_plot[time_col],
                    y=trend,
                    name='Trend',
                    line=dict(color='white', dash='dash'),
                    hoverinfo='skip'
                ))
            except:
                pass
    
    fig_vo.update_layout(
        template="plotly_dark",
        title="Vertical Oscillation w czasie",
        yaxis_title="VO [cm]",
        xaxis_title="Czas [min]",
        height=400,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1, x=0)
    )
    st.plotly_chart(fig_vo, use_container_width=True)
    
    # Analiza efektywności z kadencją
    cad_col = None
    for col in ['cadence_smooth', 'cadence', 'spm']:
        if col in df_plot.columns:
            cad_col = col
            break
    
    if cad_col:
        efficiency = analyze_vo_efficiency(vo_data, df_plot[cad_col].values)
        
        if efficiency.get('optimal_cadence'):
            st.success(f"🎯 **Optymalna kadencja:** {efficiency['optimal_cadence']} SPM "
                      f"(najniższa oscylacja)")
        
        # Wykres VO vs Cadence
        fig_scatter = go.Figure()
        fig_scatter.add_trace(go.Scatter(
            x=df_plot[cad_col],
            y=df_plot[vo_col],
            mode='markers',
            marker=dict(size=4, opacity=0.5, color='#ff6b6b'),
            name='VO vs Cadence',
            hovertemplate="Cadence: %{x:.0f} SPM<br>VO: %{y:.1f} cm<extra></extra>"
        ))
        fig_scatter.update_layout(
            template="plotly_dark",
            title="VO vs Kadencja",
            xaxis_title="Cadence [SPM/RPM]",
            yaxis_title="VO [cm]",
            height=400,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    # Analiza efektywności biegowej (jeśli mamy pace i wzrost)
    if 'pace' in df_plot.columns and 'pace' in df_plot.columns:
        st.subheader("🏃 Efektywność Biegu z VO")
        
        runner_height = st.session_state.get('runner_height', 180)
        avg_pace = df_plot['pace'].mean()
        avg_vo = vo_stats['mean_vo']
        
        effectiveness = calculate_running_effectiveness_from_vo(
            avg_pace, avg_vo, runner_height
        )
        
        if effectiveness:
            col1, col2, col3 = st.columns(3)
            col1.metric("VO % wzrostu", f"{effectiveness['vo_percent_height']:.1f}%")
            col2.metric("Efektywność", f"{effectiveness['effectiveness_score']:.0f}/100")
            col3.metric("Klasyfikacja", effectiveness['classification'])
    
    # Interpretacja
    st.info("""
    **💡 Interpretacja Vertical Oscillation:**
    
    **Co to jest?**
    VO to odległość o jaką centrum masy podnosi się i opuszcza podczas biegu.
    
    **Normy (dla biegaczy):**
    - **< 6 cm:** Bardzo efektywny bieg (elite)
    - **6-8 cm:** Dobra efektywność
    - **8-10 cm:** Średnia efektywność
    - **> 10 cm:** Wysoka oscylacja - "bouncing"
    
    **Dla rowerzystów:**
    VO jest naturalnie niższa (siedzenie). Wartości > 3 cm przy pedałowaniu 
    mogą wskazywać na "podskakiwanie" na siodełku.
    
    **Korelacja z kadencją:**
    Wyższa kadencja zazwyczaj = niższa VO (mniej "bouncing").
    Szukaj optymalnego punktu gdzie VO jest minimalna przy komfortowej kadencji.
    """)
