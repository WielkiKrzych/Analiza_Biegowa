import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy import stats

def render_model_tab(df_plot, cp_input, w_prime_input):
    st.header("Matematyczny Model CP (Critical Power Estimation)")
    st.markdown("Estymacja Twojego CP i W' na podstawie krzywej mocy (MMP) z tego treningu. Używamy modelu liniowego: `Praca = CP * t + W'`.")

    if 'watts' in df_plot.columns and len(df_plot) > 1200: # Minimum 20 minut danych
        
        # 1. Wybieramy punkty czasowe do modelu (standardowe dla modelu 2-parametrowego)
        # Unikamy bardzo krótkich czasów (< 2-3 min), bo tam dominuje Pmax/AC
        durations = [180, 300, 600, 900, 1200] # 3min, 5min, 10min, 15min, 20min
        
        # Filtrujemy czasy dłuższe niż długość treningu
        valid_durations = [d for d in durations if d < len(df_plot)]
        
        if len(valid_durations) >= 3: # Potrzebujemy min. 3 punktów do sensownej regresji
            
            mmp_values = []
            work_values = []
            
            # Liczymy MMP i Pracę dla każdego punktu
            for d in valid_durations:
                # Rolling mean max
                p = df_plot['watts'].rolling(window=d).mean().max()
                if not pd.isna(p):
                    mmp_values.append(p)
                    # Praca [J] = Moc [W] * Czas [s]
                    work_values.append(p * d)
            
            # 2. Regresja Liniowa (Work vs Time)
            # Y = Work, X = Time
            # Slope = CP, Intercept = W'
            slope, intercept, r_value, p_value, std_err = stats.linregress(valid_durations, work_values)
            
            modeled_cp = slope
            modeled_w_prime = intercept
            r_squared = r_value**2

            # 3. Wyświetlenie Wyników
            c_res1, c_res2, c_res3 = st.columns(3)
            
            c_res1.metric("Estymowane CP (z pliku)", f"{modeled_cp:.0f} W", 
                          delta=f"{modeled_cp - cp_input:.0f} W vs Ustawienia",
                          help="Moc Krytyczna wyliczona z Twoich najmocniejszych odcinków w tym pliku.")
            
            c_res2.metric("Estymowane W'", f"{modeled_w_prime:.0f} J",
                          delta=f"{modeled_w_prime - w_prime_input:.0f} J vs Ustawienia",
                          help="Pojemność beztlenowa wyliczona z modelu.")
            
            c_res3.metric("Jakość Dopasowania (R²)", f"{r_squared:.4f}", 
                          delta_color="normal" if r_squared > 0.98 else "inverse",
                          help="Jak bardzo Twoje wyniki pasują do teoretycznej krzywej. >0.98 = Bardzo wiarygodne.")

            st.markdown("---")

            # 4. Wizualizacja: Krzywa MMP vs Krzywa Modelowa
            # Generujemy punkty teoretyczne dla zakresu 1 min - 30 min
            x_theory = np.arange(60, 1800, 60) # co minutę
            y_theory = [modeled_cp + (modeled_w_prime / t) for t in x_theory]
            
            # Rzeczywiste MMP z pliku dla tych samych czasów
            y_actual = []
            x_actual = []
            for t in x_theory:
                if t < len(df_plot):
                    val = df_plot['watts'].rolling(t).mean().max()
                    y_actual.append(val)
                    x_actual.append(t)

            fig_model = go.Figure()
            
            # Rzeczywiste MMP
            fig_model.add_trace(go.Scatter(
                x=np.array(x_actual)/60, y=y_actual,
                mode='markers', name='MMP (Plik)',
                marker=dict(color='#00cc96', size=8),
                hovertemplate='%{y:.0f} W'
            ))
            
            # Model Teoretyczny
            fig_model.add_trace(go.Scatter(
                x=x_theory/60, y=y_theory,
                mode='lines', name=f'Model: {modeled_cp:.0f}W',
                line=dict(color='#ef553b', dash='dash'),
                hovertemplate='%{y:.0f} W'
            ))

            fig_model.update_layout(
                template="plotly_dark",
                title="Power Duration Curve: Rzeczywistość vs Model",
                xaxis_title="Czas trwania [min]",
                yaxis_title="Moc [W]",
                yaxis=dict(tickformat=".0f"),
                hovermode="x unified",
                height=500
            )
            st.plotly_chart(fig_model, use_container_width=True)
            
            # 5. Interpretacja
            st.info(f"""
            **📊 Interpretacja Modelu:**
            
            Ten algorytm próbuje dopasować Twoje wysiłki do fizjologicznego prawa mocy krytycznej.
            
            * **Jeśli Estymowane CP > Ustawione CP:** Brawo! W tym treningu pokazałeś, że jesteś mocniejszy niż myślisz. Rozważ aktualizację ustawień w sidebarze.
            * **Jeśli Estymowane CP < Ustawione CP:** To normalne, jeśli nie jechałeś "do odciny" (All-Out) na odcinkach 3-20 min. Model pokazuje tylko to, co *zademonstrowałeś*, a nie Twój absolutny potencjał.
            * **R² (R-kwadrat):** Jeśli jest niskie (< 0.95), oznacza to, że Twoja jazda była nieregularna i model nie może znaleźć jednej linii, która pasuje do Twoich wyników.
            """)

        else:
            st.warning("Trening jest zbyt krótki lub brakuje mocnych odcinków, by zbudować wiarygodny model CP (wymagane wysiłki > 3 min i > 10 min).")
    else:
        st.warning("Za mało danych (wymagane min. 20 minut jazdy z pomiarem mocy).")
