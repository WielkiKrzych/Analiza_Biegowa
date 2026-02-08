import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import hashlib
from typing import Optional
from modules.calculations import calculate_thermal_decay


def _hash_dataframe(df) -> str:
    """Create a hash of DataFrame for cache key generation."""
    if df is None or df.empty:
        return "empty"
    sample = df.head(100).to_json() if hasattr(df, 'to_json') else str(df)
    shape_str = f"{df.shape}_{list(df.columns)}" if hasattr(df, 'shape') else str(df)
    return hashlib.md5(f"{shape_str}_{sample}".encode()).hexdigest()[:16]


@st.cache_data(ttl=3600, show_spinner=False)
def _build_thermal_chart(df_plot) -> Optional[go.Figure]:
    """Build thermal regulation chart (cached)."""
    fig = go.Figure()
    
    # 1. CORE TEMP (Oś Lewa)
    if 'core_temperature_smooth' in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=df_plot['time_min'], 
            y=df_plot['core_temperature_smooth'], 
            name='Core Temp', 
            line=dict(color='#ff7f0e', width=2), 
            hovertemplate="Temp: %{y:.2f}°C<extra></extra>"
        ))
    
    # 2. HSI - HEAT STRAIN INDEX (Oś Prawa)
    if 'hsi' in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=df_plot['time_min'], 
            y=df_plot['hsi'], 
            name='HSI', 
            yaxis="y2", 
            line=dict(color='#d62728', width=2, dash='dot'), 
            hovertemplate="HSI: %{y:.1f}<extra></extra>"
        ))
    
    fig.add_hline(y=38.5, line_dash="dash", line_color="red", opacity=0.5, annotation_text="Krytyczna (38.5°C)", annotation_position="top left")
    fig.add_hline(y=37.5, line_dash="dot", line_color="green", opacity=0.5, annotation_text="Optymalna (37.5°C)", annotation_position="bottom left")

    fig.update_layout(
        template="plotly_dark",
        title="Termoregulacja: Temperatura Głęboka vs Indeks Zmęczenia (HSI)",
        hovermode="x unified",
        xaxis=dict(
            title="Czas [min]",
            tickformat=".0f",
            hoverformat=".0f"
        ),
        yaxis=dict(title="Core Temp [°C]"),
        yaxis2=dict(title="HSI [0-10]", overlaying="y", side="right", showgrid=False, range=[0, 12]),
        legend=dict(orientation="h", y=1.1, x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        height=450
    )
    
    return fig


def render_thermal_tab(df_plot):
    st.header("Wydajność Chłodzenia i Koszt Termiczny")
    
    # --- NOWA SEKCJA: KPI KOSZTU TERMICZNEGO ---
    decay_res = calculate_thermal_decay(df_plot)
    
    col1, col2, col3 = st.columns(3)
    if decay_res['r_squared'] > 0:
        val_color = "inverse" if decay_res['decay_pct_per_c'] < -5 else "normal"
        col1.metric("Koszt Termiczny", f"{decay_res['decay_pct_per_c']}% / 1°C", 
                   delta=f"{decay_res['decay_pct_per_c']}%" if decay_res['decay_pct_per_c'] != 0 else None,
                   delta_color=val_color,
                   help="O ile procent spada Twoja wydajność (W/HR) na każdy 1°C wzrostu temperatury głębokiej.")
        col2.metric("Pewność Statystyczna (R²)", f"{decay_res['r_squared']:.2f}",
                   help="Jak dobrze linia trendu pasuje do danych. >0.5 oznacza wysoką wiarygodność.")
        
        status = "🔴 Wysoki" if decay_res['decay_pct_per_c'] < -6 else ("🟡 Średni" if decay_res['decay_pct_per_c'] < -3 else "🟢 Niski")
        col3.metric("Status Adaptacji", status)
    else:
        st.info("💡 " + decay_res['message'])

    st.divider()

    # Use cached chart building
    fig_t = _build_thermal_chart(df_plot)
    if fig_t is not None:
        st.plotly_chart(fig_t, use_container_width=True)
    
    with st.expander("🌡️ Teoria: Koszt Termiczny Wydajności (WKO5/INSCYD)", expanded=False):
        st.markdown("""
        ### Jak ciepło zabija Twoje Waty?
        
        Według założeń **WKO5** i **INSCYD**, temperatura nie jest tylko dyskomfortem – to realny "podatek metaboliczny", który płacisz za każdy wat mocy.

        #### 1. Mechanizm VLaMax (Wzrost Glikolizy)
        Wysoka temperatura ciała to stresor, który podnosi poziom katecholamin (adrenaliny). To z kolei stymuluje system glikolityczny.
        * **Efekt:** W upale Twój **VLaMax rośnie**. Oznacza to, że przy tej samej mocy spalasz więcej glikogenu i produkujesz więcej mleczanu niż w chłodzie.
        * **Konsekwencja:** Szybsze "odcięcie" i gorsza ekonomia na długim dystansie.

        #### 2. Cardiac Drift (Dryf Sercowy)
        Mózg musi zdecydować: krew do mięśni (napęd) czy krew do skóry (chłodzenie). 
        * **Blood Split:** W miarę wzrostu temp., coraz więcej krwi trafia do skóry. Serce musi bić szybciej, by utrzymać ciśnienie przy mniejszej objętości krwi (utrata osocza z potem).
        * **Efficiency Factor (EF):** Metryka spadku EF (W/HR) pokazuje, jak bardzo Twoja termoregulacja jest obciążona. Spadek powyżej 5% jest uznawany za znaczący.

        #### 3. Strefy i Adaptation Score
        * **37.5°C - 38.4°C:** Strefa Wydajności (Performance Zone). Mięśnie działają optymalnie.
        * **> 38.5°C:** Strefa Krytyczna (The Meltdown). Nagły spadek rekrutacji jednostek motorycznych – mózg broni się przed przegrzaniem.
        
        ---
        
        ### Strategia na Upalny Wyścig:
        1. **Pre-cooling:** Obniż core temp przed startem (kamizelki lodowe, ice slurry).
        2. **Per-cooling:** Polewaj nadgarstki i kark (duże naczynia krwionośne).
        3. **Nawadnianie:** Nie tylko woda – elektrolity (sód!) są kluczowe, by utrzymać objętość osocza i rzut serca.
        """)

    st.header("Cardiac Drift vs Temperatura")
    
    # Helper function to find column by aliases
    def find_column(df, aliases):
        for alias in aliases:
            if alias in df.columns:
                return alias
        return None
    
    temp_aliases = ['core_temperature_smooth', 'core_temperature', 'core_temp', 'temp', 'temperature', 'core temp']
    hr_aliases = ['heartrate', 'heartrate_smooth', 'heart_rate', 'hr', 'heart rate', 'bpm', 'pulse']
    pwr_aliases = ['watts', 'watts_smooth', 'power', 'pwr', 'moc']
    
    temp_col = find_column(df_plot, temp_aliases)
    hr_col = find_column(df_plot, hr_aliases)
    pwr_col = find_column(df_plot, pwr_aliases)
    
    if pwr_col and hr_col and temp_col:
        mask = (df_plot[pwr_col] > 10) & (df_plot[hr_col] > 60)
        df_clean = df_plot[mask].copy()
        df_clean['eff_raw'] = df_clean[pwr_col] / df_clean[hr_col]
        df_clean = df_clean[df_clean['eff_raw'] < 6.0]

        if not df_clean.empty:
            fig_te = px.scatter(
                df_clean, x=temp_col, y='eff_raw', 
                trendline="lowess", trendline_options=dict(frac=0.3), 
                trendline_color_override="#FF4B4B", template="plotly_dark", opacity=0.3,
                labels={temp_col: "Core Temperature", "eff_raw": "Efficiency Factor"},
                hover_data={temp_col: ":.2f", "eff_raw": ":.2f"}
            )
            fig_te.update_traces(selector=dict(mode='markers'), marker=dict(size=5, color='#1f77b4'))
            fig_te.update_layout(
                title="Spadek Efektywności (W/HR) vs Temperatura",
                xaxis=dict(title="Core Temperature [°C]", tickformat=".2f"),
                yaxis=dict(title="Efficiency Factor [W/bpm]", tickformat=".2f"),
                height=450, margin=dict(l=10, r=10, t=40, b=10),
                hovermode="x unified"
            )
            st.plotly_chart(fig_te, use_container_width=True)
            
            st.info("""
            ℹ️ **Interpretacja WKO5:**
            Ten wykres pokazuje, ile Watów generujesz z jednego uderzenia serca wraz ze wzrostem temperatury. Jeśli linia opada stromo, Twój koszt termiczny jest wysoki.
            """)
        else:
            st.warning("Zbyt mało danych do analizy dryfu.")
    else:
        st.error("Brak danych (Moc, HR lub Core Temp) do pełnej analizy.")

    # =========================================================================
    # PREDYKCJA STRAT MOCY W CIEPLE
    # =========================================================================
    st.divider()
    st.header("🌡️ Predykcja Strat Mocy w Cieple")
    
    _render_thermal_prediction_section(df_plot, decay_res)


def _render_thermal_prediction_section(df_plot, decay_result):
    """
    Renderuje sekcję predykcji strat mocy w cieple.
    
    Na podstawie dEF/dT, dHR/dT, HSI.
    """
    import numpy as np
    from modules.calculations.thermal import predict_thermal_performance
    
    st.markdown("""
    Model predykcji strat wydajnościowych na podstawie:
    - **dEF/dT** — spadek wydajności (W/bpm) na °C
    - **dHR/dT** — wzrost kosztu sercowego na °C
    - **HSI** — Heat Strain Index
    """)
    
    # === PARAMETRY WEJŚCIOWE ===
    st.subheader("📊 Parametry Symulacji")
    
    c1, c2, c3, c4 = st.columns(4)
    cp_input = c1.number_input("CP [W]", min_value=150, max_value=500, value=280, step=10)
    ftp_input = c2.number_input("FTP [W]", min_value=150, max_value=500, value=275, step=10)
    w_prime_input = c3.number_input("W' [kJ]", min_value=10.0, max_value=40.0, value=20.0, step=1.0)
    hr_threshold = c4.number_input("HR @ próg [bpm]", min_value=120, max_value=200, value=165, step=5)
    
    c5, c6 = st.columns(2)
    # Use detected decay if available, otherwise default
    default_decay = decay_result.get('decay_pct_per_c', -3.0) if decay_result.get('is_significant', False) else -3.0
    decay_pct = c5.slider("Spadek wydajności [%/°C]", min_value=-10.0, max_value=0.0, value=float(default_decay), step=0.5)
    hr_increase = c6.slider("Wzrost HR [bpm/°C]", min_value=1.0, max_value=10.0, value=3.0, step=0.5)
    
    # === TEMPERATURA DOCELOWA ===
    st.subheader("🎯 Temperatura Startu / Scenariusz")
    target_temp = st.slider("Temperatura rdzenia [°C]", min_value=37.0, max_value=41.0, value=39.0, step=0.1)
    
    # Oblicz predykcję
    prediction = predict_thermal_performance(
        cp=cp_input,
        ftp=ftp_input,
        w_prime=w_prime_input,
        baseline_hr=hr_threshold,
        target_temp=target_temp,
        decay_pct_per_c=decay_pct,
        hr_increase_per_c=hr_increase
    )
    
    # === WYNIKI ===
    st.subheader("📉 Prognoza Degradacji Wydajności")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div style="padding:15px; border-radius:8px; border:2px solid {prediction['risk_color']}; background-color: #222; text-align:center;">
            <p style="margin:0; color:#aaa; font-size:0.85em;">Critical Power</p>
            <h2 style="margin:5px 0;">{prediction['cp_degraded']:.0f} W</h2>
            <p style="margin:0; color:{prediction['risk_color']};">↓ {prediction['cp_loss_pct']:.1f}%</p>
            <p style="margin:0; color:#666; font-size:0.75em;">(baseline: {prediction['cp_baseline']} W)</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="padding:15px; border-radius:8px; border:2px solid {prediction['risk_color']}; background-color: #222; text-align:center;">
            <p style="margin:0; color:#aaa; font-size:0.85em;">FTP</p>
            <h2 style="margin:5px 0;">{prediction['ftp_degraded']:.0f} W</h2>
            <p style="margin:0; color:{prediction['risk_color']};">↓ {prediction['ftp_loss_pct']:.1f}%</p>
            <p style="margin:0; color:#666; font-size:0.75em;">(baseline: {prediction['ftp_baseline']} W)</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="padding:15px; border-radius:8px; border:2px solid {prediction['risk_color']}; background-color: #222; text-align:center;">
            <p style="margin:0; color:#aaa; font-size:0.85em;">W' (Anaerobic)</p>
            <h2 style="margin:5px 0;">{prediction['w_prime_degraded']:.1f} kJ</h2>
            <p style="margin:0; color:{prediction['risk_color']};">↓ {prediction['w_prime_loss_pct']:.1f}%</p>
            <p style="margin:0; color:#666; font-size:0.75em;">(baseline: {prediction['w_prime_baseline']} kJ)</p>
        </div>
        """, unsafe_allow_html=True)
    
    # HR Cost & TTE
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div style="padding:15px; border-radius:8px; border:2px solid #ff7f0e; background-color: #222; text-align:center;">
            <p style="margin:0; color:#aaa; font-size:0.85em;">Koszt HR (przy tej samej mocy)</p>
            <h2 style="margin:5px 0; color:#ff7f0e;">+{prediction['hr_cost_increase']:.0f} bpm</h2>
            <p style="margin:0; color:#888;">{prediction['hr_baseline']:.0f} → {prediction['hr_at_threshold']:.0f} bpm</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="padding:15px; border-radius:8px; border:2px solid #d62728; background-color: #222; text-align:center;">
            <p style="margin:0; color:#aaa; font-size:0.85em;">Skrócenie TTE @ FTP</p>
            <h2 style="margin:5px 0; color:#d62728;">-{prediction['tte_reduction_pct']:.0f}%</h2>
            <p style="margin:0; color:#888;">{prediction['tte_baseline_min']:.0f} → {prediction['tte_degraded_min']:.0f} min</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="padding:15px; border-radius:8px; border:2px solid {prediction['risk_color']}; background-color: #222; text-align:center;">
            <p style="margin:0; color:#aaa; font-size:0.85em;">Heat Strain Index (HSI)</p>
            <h2 style="margin:5px 0; color:{prediction['risk_color']};">{prediction['hsi_estimated']:.1f} / 10</h2>
            <p style="margin:0; color:{prediction['risk_color']};">Ryzyko: {prediction['risk_label']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # === WYKRES: CP vs TEMPERATURA ===
    st.markdown("### 📊 Krzywa Degradacji CP vs Temperatura")
    
    temps = np.arange(37.0, 41.1, 0.2)
    cp_values = []
    ftp_values = []
    
    for t in temps:
        pred = predict_thermal_performance(
            cp=cp_input,
            ftp=ftp_input,
            w_prime=w_prime_input,
            baseline_hr=hr_threshold,
            target_temp=t,
            decay_pct_per_c=decay_pct,
            hr_increase_per_c=hr_increase
        )
        cp_values.append(pred['cp_degraded'])
        ftp_values.append(pred['ftp_degraded'])
    
    fig_cp = go.Figure()
    
    fig_cp.add_trace(go.Scatter(
        x=temps,
        y=cp_values,
        mode='lines',
        name='CP [W]',
        line=dict(color='#1f77b4', width=3),
        hovertemplate="Temp: %{x:.1f}°C<br>CP: %{y:.0f} W<extra></extra>"
    ))
    
    fig_cp.add_trace(go.Scatter(
        x=temps,
        y=ftp_values,
        mode='lines',
        name='FTP [W]',
        line=dict(color='#ff7f0e', width=2, dash='dash'),
        hovertemplate="Temp: %{x:.1f}°C<br>FTP: %{y:.0f} W<extra></extra>"
    ))
    
    # Marker for target temp
    fig_cp.add_vline(x=target_temp, line_dash="dot", line_color="red", 
                     annotation_text=f"{target_temp}°C", annotation_position="top")
    
    fig_cp.update_layout(
        template="plotly_dark",
        title="Degradacja Mocy Krytycznej i FTP w Funkcji Temperatury",
        xaxis=dict(title="Temperatura Rdzenia [°C]"),
        yaxis=dict(title="Moc [W]"),
        height=400,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1, x=0)
    )
    
    st.plotly_chart(fig_cp, use_container_width=True)
    
    # Wnioski
    if prediction['temp_delta'] > 1.5:
        st.error(f"""
        🔴 **Wysoki koszt termiczny** przy {target_temp}°C:
        
        - CP spada o **{prediction['cp_loss_pct']:.0f}%** (z {prediction['cp_baseline']} do {prediction['cp_degraded']:.0f} W)
        - HR rośnie o **+{prediction['hr_cost_increase']:.0f} bpm** przy tej samej mocy
        - Czas do wyczerpania skraca się o **{prediction['tte_reduction_pct']:.0f}%**
        
        **Rekomendacja:** Pre-cooling, aktywne chłodzenie, redukcja tempa o {prediction['cp_loss_pct']:.0f}%
        """)
    elif prediction['temp_delta'] > 0.5:
        st.warning(f"""
        ⚠️ **Umiarkowany koszt termiczny** przy {target_temp}°C:
        
        - Spadek mocy: {prediction['cp_loss_pct']:.1f}%
        - Wzrost HR: +{prediction['hr_cost_increase']:.0f} bpm
        
        **Rekomendacja:** Nawadnianie, chłodzenie nadgarstków, monitorowanie HSI
        """)
    else:
        st.success(f"""
        ✅ **Niski koszt termiczny** przy {target_temp}°C — wydajność zbliżona do optymalnej.
        """)
    
    # Teoria
    with st.expander("📖 Model i Metodologia", expanded=False):
        st.markdown(f"""
        ### Wzory Modelu
        
        **Degradacja CP/FTP:**
        ```
        CP_degraded = CP × (1 + dEF/dT × ΔT)
        
        gdzie:
        - dEF/dT = {decay_pct:.1f}% / °C (wykryty: {decay_result.get('decay_pct_per_c', 'N/A')})
        - ΔT = {prediction['temp_delta']:.1f}°C
        ```
        
        **Degradacja W':**
        ```
        W'_degraded = W' × (1 + dEF/dT × 1.5 × ΔT)
        ```
        W' degraduje szybciej, ponieważ ciepło zwiększa koszt glikolityczny.
        
        **Wzrost HR:**
        ```
        HR_at_threshold = HR_baseline + {hr_increase:.1f} × ΔT
        ```
        
        **Redukcja TTE:**
        ```
        TTE_reduction = 5% × ΔT
        ```
        
        ---
        
        ### Źródła
        - WKO5 Thermal Decay Model
        - INSCYD VLaMax × Temperature interaction
        - Periard et al. (2015) — Heat stress and performance
        """)
