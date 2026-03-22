import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import hashlib
from typing import Optional
from modules.calculations import calculate_thermal_decay
from modules.calculations.thermal import (
    classify_core_temp_zone,
    calculate_core_temp_zones_time,
    calculate_thermal_drift_rate,
)


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

    # Convert time_min to hh:mm:ss format for x-axis
    import numpy as np
    time_vals = df_plot['time_min'].values if hasattr(df_plot['time_min'], 'values') else np.array(df_plot['time_min'])
    tick_step = 5  # every 5 minutes
    tick_vals = np.arange(0, time_vals.max() + tick_step, tick_step)
    tick_text = [f"{int(m//60):02d}:{int(m%60):02d}:00" for m in tick_vals]

    fig.update_layout(
        template="plotly_dark",
        title="Termoregulacja: Temperatura Głęboka vs Indeks Zmęczenia (HSI)",
        hovermode="x unified",
        xaxis=dict(
            title="Czas [hh:mm:ss]",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
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

    # ===== CORE TEMP ZONES & DRIFT RATE =====
    temp_col_name = None
    for alias in ['core_temperature_smooth', 'core_temperature', 'core_temp']:
        if alias in df_plot.columns:
            temp_col_name = alias
            break

    if temp_col_name:
        import pandas as pd_thermal
        st.subheader("🌡️ Strefy Temperatury Głębokiej")

        temp_series = df_plot[temp_col_name].dropna()
        if len(temp_series) > 60:
            zones_time = calculate_core_temp_zones_time(temp_series)
            total_sec = sum(zones_time.values())

            if total_sec > 0:
                zone_colors = {
                    "Optimal (<38.0°C)": "#2ecc71",
                    "Elevated (38.0-38.5°C)": "#f1c40f",
                    "High (38.5-39.0°C)": "#e67e22",
                    "Critical (39.0-39.5°C)": "#e74c3c",
                    "Dangerous (>39.5°C)": "#9b59b6",
                }
                zone_names = list(zones_time.keys())
                zone_pcts = [zones_time[z] / total_sec * 100 for z in zone_names]
                zone_cols = [zone_colors.get(z, "#808080") for z in zone_names]

                fig_tz = go.Figure(data=[go.Bar(
                    x=zone_pcts, y=zone_names, orientation="h",
                    marker_color=zone_cols,
                    text=[f"{p:.0f}%" for p in zone_pcts],
                    textposition="auto",
                )])
                fig_tz.update_layout(
                    template="plotly_dark",
                    title="Czas w strefach temperatury głębokiej",
                    xaxis_title="% czasu", height=250,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig_tz, use_container_width=True)

            # Thermal drift rate
            drift = calculate_thermal_drift_rate(temp_series)
            if drift.get("is_valid"):
                col_dr1, col_dr2, col_dr3 = st.columns(3)
                col_dr1.metric(
                    "Drift Rate",
                    f"{drift['drift_c_per_hour']:.2f} °C/h",
                    help="Szybkość wzrostu temperatury — marker hydratacji i sprawności termoregulacyjnej",
                )
                col_dr2.metric("R²", f"{drift['r_squared']:.2f}")
                col_dr3.metric("Klasyfikacja", drift["classification"])

        st.divider()

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
