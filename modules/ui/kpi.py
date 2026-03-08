import streamlit as st
import plotly.graph_objects as go
from modules.config import Config
from modules.calculations import calculate_vo2max, calculate_trend

def render_kpi_tab(df_plot, df_plot_resampled, metrics, rider_weight, decoupling_percent, drift_z2, vt1_vent, vt2_vent):
    st.header("Kluczowe Wskaźniki Wydajności (KPI)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Średnia Moc", f"{metrics.get('avg_watts', 0):.0f} W")
    c2.metric("Średnie Tętno", f"{metrics.get('avg_hr', 0):.0f} BPM")
    c3.metric("Średnie SmO2", f"{df_plot['smo2'].mean() if 'smo2' in df_plot.columns else 0:.1f} %")
    c4.metric("Kadencja", f"{metrics.get('avg_cadence', 0):.0f} SPM")  # FIX: SPM (steps/min) for running, not RPM
    
    vo2max_est = calculate_vo2max(df_plot['watts'].rolling(window=300).mean().max() if 'watts' in df_plot.columns else 0, rider_weight)
    c5.metric("Szac. VO2max", f"{vo2max_est:.1f}", help="Estymowane na podstawie mocy 5-minutowej (ACSM).")
                
    st.divider()
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Power/HR", f"{metrics.get('power_hr', 0):.2f}")
    c6.metric("Efficiency (EF)", f"{metrics.get('ef_factor', 0):.2f}")
    c7.metric("Praca > CP", f"{metrics.get('work_above_cp_kj', 0):.0f} kJ")
    c8.metric("Wentylacja (VE)", f"{metrics.get('avg_vent', 0):.1f} L/min")
    
    st.divider()
    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Dryf (Pa:Hr)", f"{decoupling_percent:.1f} %", delta_color="inverse" if decoupling_percent < 5 else "normal")
    c10.metric("Dryf Z2", f"{drift_z2:.1f} %", delta_color="inverse" if drift_z2 < 5 else "normal")
    
    max_hsi = df_plot['hsi'].max() if 'hsi' in df_plot.columns else 0
    c11.metric("Max HSI", f"{max_hsi:.1f}", delta_color="normal" if max_hsi > 5 else "inverse")
    c12.metric("Oddechy (RR)", f"{metrics.get('avg_rr', 0):.1f} /min")

    st.subheader("Wizualizacja Dryfu i Zmienności")
    if 'pace_smooth' in df_plot.columns:
        fig_dec = go.Figure()
        
        # Convert pace from sec/km to min/km for display
        pace_display = df_plot_resampled['pace_smooth'] / 60.0
        
        # Format pace for hover (mm:ss)
        pace_customdata = []
        for p in pace_display:
            minutes = int(p)
            seconds = int((p - minutes) * 60)
            pace_customdata.append(f"{minutes}:{seconds:02d}")
        
        fig_dec.add_trace(go.Scatter(
            x=df_plot_resampled['time_min'], 
            y=pace_display, 
            name='Tempo', 
            line=dict(color=Config.COLOR_POWER, width=1.5), 
            hovertemplate="Tempo: %{customdata} min/km<extra></extra>",
            customdata=[pace_customdata]
        ))
        
        if 'heartrate_smooth' in df_plot.columns:
            fig_dec.add_trace(go.Scatter(x=df_plot_resampled['time_min'], y=df_plot_resampled['heartrate_smooth'], name='HR', yaxis='y2', line=dict(color=Config.COLOR_HR, width=1.5), hovertemplate="HR: %{y:.0f} BPM<extra></extra>"))
        if 'smo2_smooth' in df_plot.columns:
            fig_dec.add_trace(go.Scatter(x=df_plot_resampled['time_min'], y=df_plot_resampled['smo2_smooth'], name='SmO2', yaxis='y3', line=dict(color=Config.COLOR_SMO2, dash='dot', width=1.5), hovertemplate="SmO2: %{y:.1f}%<extra></extra>"))
        
        # Convert time_min to hh:mm:ss format for x-axis
        time_vals = df_plot_resampled['time_min'].values if hasattr(df_plot_resampled['time_min'], 'values') else np.array(df_plot_resampled['time_min'])
        tick_step = 5  # every 5 minutes
        tick_vals = np.arange(0, time_vals.max() + tick_step, tick_step)
        tick_text = [f"{int(m//60):02d}:{int(m%60):02d}:00" for m in tick_vals]

        fig_dec.update_layout(template="plotly_dark", title="Dryf Tempa, Tętna i SmO2 w Czasie", hovermode="x unified",
            xaxis=dict(
                title="Czas [hh:mm:ss]",
                tickmode="array",
                tickvals=tick_vals,
                ticktext=tick_text,
            ),
            yaxis=dict(title="Tempo [min/km]", autorange="reversed"),
            yaxis2=dict(title="HR [bpm]", overlaying='y', side='right', showgrid=False),
            yaxis3=dict(title="SmO2 [%]", overlaying='y', side='right', showgrid=False, showticklabels=False, range=[0, 100]),
            legend=dict(orientation="h", y=1.1, x=0))
        st.plotly_chart(fig_dec, use_container_width=True)
        
        st.info("""
        **💡 Interpretacja: Fizjologia Zmęczenia (Triada: Tempo - HR - SmO2)**

        Ten wykres pokazuje "koszt fizjologiczny" utrzymania zadanego tempa w czasie.

        **1. Stan Idealny (Brak Dryfu):**
        * **Tempo (Zielony):** Linia płaska (stałe obciążenie).
        * **Tętno (Czerwony):** Linia płaska (równoległa do tempa).
        * **SmO2 (Fiolet):** Stabilne.
        * **Wniosek:** Jesteś w pełnej równowadze tlenowej. Możesz tak biec godzinami.

        **2. Dryf Sercowo-Naczyniowy (Cardiac Drift):**
        * **Tempo:** Stałe.
        * **Tętno:** Powoli rośnie (rozjeżdża się z linią tempa).
        * **SmO2:** Stabilne.
        * **Przyczyna:** Odwodnienie (spadek objętości osocza) lub przegrzanie (krew ucieka do skóry). Serce musi bić szybciej, by pompować tę samą ilość tlenu.

        **3. Zmęczenie Metaboliczne (Metabolic Fatigue):**
        * **Tempo:** Stałe.
        * **Tętno:** Stabilne lub lekko rośnie.
        * **SmO2:** **Zaczyna spadać.**
        * **Przyczyna:** Mięśnie tracą wydajność (rekrutacja włókien szybkokurczliwych II typu, które zużywają więcej tlenu). To pierwszy sygnał nadchodzącego "odcięcia".

        **4. "Zgon" (Bonking/Failure):**
        * **Tempo:** Zaczyna spadać (nie jesteś w stanie go utrzymać).
        * **Tętno:** Może paradoksalnie spadać (zmęczenie układu nerwowego) lub rosnąć (panika organizmu).
        * **SmO2:** Gwałtowny spadek lub chaotyczne skoki.
        """)

    st.divider()
    
    c1, c2 = st.columns(2)
    
    # LEWA KOLUMNA: SmO2 + TREND
    with c1:
        st.subheader("SmO2")
        col_smo2 = 'smo2_smooth_ultra' if 'smo2_smooth_ultra' in df_plot.columns else ('smo2_smooth' if 'smo2_smooth' in df_plot.columns else None)
        
        if col_smo2:
            fig_s = go.Figure()
            fig_s.add_trace(go.Scatter(x=df_plot_resampled['time_min'], y=df_plot_resampled[col_smo2], name='SmO2', line=dict(color='#ab63fa', width=2), hovertemplate="SmO2: %{y:.1f}%<extra></extra>"))
            
            trend_y = calculate_trend(df_plot_resampled['time_min'].values, df_plot_resampled[col_smo2].values)
            if trend_y is not None:
                fig_s.add_trace(go.Scatter(x=df_plot_resampled['time_min'], y=trend_y, name='Trend', line=dict(color='white', dash='dash', width=1.5), hovertemplate="Trend: %{y:.1f}%<extra></extra>"))
            
            # Convert time_min to hh:mm:ss format for x-axis
            time_vals_s = df_plot_resampled['time_min'].values if hasattr(df_plot_resampled['time_min'], 'values') else np.array(df_plot_resampled['time_min'])
            tick_vals_s = np.arange(0, time_vals_s.max() + tick_step, tick_step)
            tick_text_s = [f"{int(m//60):02d}:{int(m%60):02d}:00" for m in tick_vals_s]

            fig_s.update_layout(template="plotly_dark", title="Lokalna Oksydacja (SmO2)", hovermode="x unified", 
                xaxis=dict(
                    title="Czas [hh:mm:ss]",
                    tickmode="array",
                    tickvals=tick_vals_s,
                    ticktext=tick_text_s,
                ),
                yaxis=dict(title="SmO2 [%]", range=[0, 100]), 
                legend=dict(orientation="h", y=1.1, x=0), 
                margin=dict(l=10, r=10, t=40, b=10), 
                height=400)
            st.plotly_chart(fig_s, use_container_width=True)
            
            st.info("""
            **💡 Hemodynamika Mięśniowa (SmO2) - Lokalny Monitoring:**
            
            SmO2 to "wskaźnik paliwa" bezpośrednio w pracującym mięśniu (zazwyczaj czworogłowym uda).
            * **Równowaga (Linia Płaska):** Podaż tlenu = Zapotrzebowanie. To stan zrównoważony (Steady State).
            * **Desaturacja (Spadek):** Popyt > Podaż. Wchodzisz w dług tlenowy. Jeśli dzieje się to przy stałej mocy -> zmęczenie metaboliczne.
            * **Reoksygenacja (Wzrost):** Odpoczynek. Szybkość powrotu do normy to doskonały wskaźnik wytrenowania (regeneracji).
            """)
        else:
             st.info("Brak danych SmO2")

    # PRAWA KOLUMNA: TĘTNO (HR)
    with c2:
        st.subheader("Tętno")
        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(x=df_plot_resampled['time_min'], y=df_plot_resampled['heartrate_smooth'], name='HR', fill='tozeroy', line=dict(color='#ef553b', width=2), hovertemplate="HR: %{y:.0f} BPM<extra></extra>"))
        # Convert time_min to hh:mm:ss format for x-axis
        time_vals_h = df_plot_resampled['time_min'].values if hasattr(df_plot_resampled['time_min'], 'values') else np.array(df_plot_resampled['time_min'])
        tick_vals_h = np.arange(0, time_vals_h.max() + tick_step, tick_step)
        tick_text_h = [f"{int(m//60):02d}:{int(m%60):02d}:00" for m in tick_vals_h]

        fig_h.update_layout(template="plotly_dark", title="Odpowiedź Sercowa (HR)", hovermode="x unified", 
            xaxis=dict(
                title="Czas [hh:mm:ss]",
                tickmode="array",
                tickvals=tick_vals_h,
                ticktext=tick_text_h,
            ),
            yaxis=dict(title="HR [bpm]"), 
            margin=dict(l=10, r=10, t=40, b=10), 
            height=400)
        st.plotly_chart(fig_h, use_container_width=True)
        
        st.info("""
        **💡 Reakcja Sercowo-Naczyniowa (HR) - Globalny System:**
        
        Serce to pompa centralna. Jego reakcja jest **opóźniona** względem wysiłku.
        * **Lag (Opóźnienie):** W krótkich interwałach (np. 30s) tętno nie zdąży wzrosnąć, mimo że moc jest max. Nie steruj sprintami na tętno!
        * **Decoupling (Rozjazd):** Jeśli moc jest stała, a tętno rośnie (dryfuje) -> organizm walczy z przegrzaniem lub odwodnieniem.
        * **Recovery HR:** Jak szybko tętno spada po wysiłku? Szybki spadek = sprawne przywspółczulne układu nerwowego (dobra forma).
        """)

    st.divider()

    st.subheader("Wentylacja (VE) i Oddechy (RR)")
    
    fig_v = go.Figure()
    
    # 1. WENTYLACJA (Oś Lewa)
    if 'tymeventilation_smooth' in df_plot_resampled.columns:
        fig_v.add_trace(go.Scatter(
            x=df_plot_resampled['time_min'], 
            y=df_plot_resampled['tymeventilation_smooth'], 
            name="VE", 
            line=dict(color='#ffa15a', width=2), 
            hovertemplate="VE: %{y:.1f} L/min<extra></extra>"
        ))
        
        # Trend VE
        trend_ve = calculate_trend(df_plot_resampled['time_min'].values, df_plot_resampled['tymeventilation_smooth'].values)
        if trend_ve is not None:
             fig_v.add_trace(go.Scatter(
                 x=df_plot_resampled['time_min'], 
                 y=trend_ve, 
                 name="Trend VE", 
                 line=dict(color='#ffa15a', dash='dash', width=1.5), 
                 hovertemplate="Trend: %{y:.1f} L/min<extra></extra>"
             ))
    
    # 2. ODDECHY / RR (Oś Prawa)
    if 'tymebreathrate_smooth' in df_plot_resampled.columns:
        fig_v.add_trace(go.Scatter(
            x=df_plot_resampled['time_min'], 
            y=df_plot_resampled['tymebreathrate_smooth'], 
            name="RR", 
            yaxis="y2", # Druga oś
            line=dict(color='#19d3f3', dash='dot', width=2), 
            hovertemplate="RR: %{y:.1f} /min<extra></extra>"
        ))
    
    # Linie Progi Wentylacyjne 
    fig_v.add_hline(y=vt1_vent, line_dash="dot", line_color="green", annotation_text="VT1", annotation_position="bottom right")
    fig_v.add_hline(y=vt2_vent, line_dash="dot", line_color="red", annotation_text="VT2", annotation_position="bottom right")

    # Convert time_min to hh:mm:ss format for x-axis
    time_vals_v = df_plot_resampled['time_min'].values if hasattr(df_plot_resampled['time_min'], 'values') else np.array(df_plot_resampled['time_min'])
    tick_step_v = 5  # every 5 minutes
    tick_vals_v = np.arange(0, time_vals_v.max() + tick_step_v, tick_step_v)
    tick_text_v = [f"{int(m//60):02d}:{int(m%60):02d}:00" for m in tick_vals_v]

    # LAYOUT (Unified Hover)
    fig_v.update_layout(
        template="plotly_dark",
        title="Mechanika Oddechu (Wydajność vs Częstość)",
        hovermode="x unified",
        
        # X-axis with hh:mm:ss format
        xaxis=dict(
            title="Czas [hh:mm:ss]",
            tickmode="array",
            tickvals=tick_vals_v,
            ticktext=tick_text_v,
        ),
        
        # Oś Lewa
        yaxis=dict(title="Wentylacja [L/min]"),
        
        # Oś Prawa
        yaxis2=dict(
            title="Kadencja Oddechu [RR]", 
            overlaying="y", 
            side="right", 
            showgrid=False
        ),
        
        legend=dict(orientation="h", y=1.1, x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        height=450
    )
    st.plotly_chart(fig_v, use_container_width=True)
    
    st.info("""
    **💡 Interpretacja: Mechanika Oddychania**

    * **Wzorzec Prawidłowy (Efektywność):** Wentylacja (VE) rośnie liniowo wraz z mocą, a częstość (RR) jest stabilna. Oznacza to głęboki, spokojny oddech.
    * **Wzorzec Niekorzystny (Płytki Oddech):** Bardzo wysokie RR (>40-50) przy stosunkowo niskim VE. Oznacza to "dyszenie" - powietrze wchodzi tylko do "martwej strefy" płuc, nie biorąc udziału w wymianie gazowej.
    * **Dryf Wentylacyjny:** Jeśli przy stałej mocy VE ciągle rośnie (rosnący trend pomarańczowej linii), oznacza to narastającą kwasicę (organizm próbuje wydmuchać CO2) lub zmęczenie mięśni oddechowych.
    * **Próg VT2 (RCP):** Punkt załamania, gdzie VE wystrzeliwuje pionowo w górę. To Twoja "czerwona linia" metaboliczna.
    """)
