import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def render_nutrition_tab(df_plot, cp_input, vt1_watts, vt2_watts):
    st.header("⚡ Kalkulator Spalania Glikogenu (The Bonk Prediction)")
    
    # Interaktywne suwaki
    c1, c2, c3 = st.columns(3)
    carb_intake = c1.number_input("Spożycie Węglowodanów [g/h]", min_value=0, max_value=200, value=60, step=10)
    initial_glycogen = c2.number_input("Początkowy Zapas Glikogenu [g]", min_value=200, max_value=800, value=450, step=50, help="Standardowo: 400-500g dla wytrenowanego sportowca.")
    efficiency_input = c3.number_input("Sprawność Mechaniczna [%]", min_value=18.0, max_value=26.0, value=22.0, step=0.5, help="Amator: 18-21%, Pro: 23%+")
    
    # --- MENU KOLARSKIE (ROZBUDOWANE) ---
    with st.expander("🍬 Menu Kolarskie (Ile to węglowodanów?)", expanded=False):
        st.markdown("""
        ### Produkty Energetyczne na Rower
        
        | Produkt | CHO [g] | Szybkość wchłaniania | Uwagi |
        |---------|---------|---------------------|-------|
        | **Żel energetyczny** (1 szt.) | 25-30 | ⚡ Bardzo szybka | Glukoza/maltodekstryna, łatwy do spożycia |
        | **Baton energetyczny** | 40-50 | 🔵 Średnia | Orzech/płatki, dłuższe żucie |
        | **Banan** | 25-30 | 🟢 Średnia | Naturalny cukier + potas |
        | **Izotonik (500ml)** | 30-40 | ⚡ Szybka | Płynne, łatwe do spożycia w ruchu |
        | **Żelki (100g)** | ~75 | ⚡ Szybka | Glukoza/fruktoza mix, idealne na interwały |
        | **Rodzynki (50g)** | 35 | 🔵 Średnia | Naturalne, ale wolniejsze wchłanianie |
        | **Miód (1 łyżka)** | 20 | ⚡ Szybka | Może podrażnić żołądek |
        | **Cola (330ml)** | 35 | ⚡ Szybka | Kofeina + cukier, "emergency boost" |
        | **Daktyle (3 szt.)** | 45 | 🟢 Średnia | Naturalne, wysokie w błonnik |
        | **Ryż kleisty (100g)** | 80 | 🔵 Średnia-wolna | "Rice cakes", popularne w peletonie |
        | **Syrop klonowy (50ml)** | 50 | ⚡ Szybka | Alternatywa dla żeli |
        
        ---
        
        **💡 Pro Tip: Glukoza + Fruktoza (2:1)**
        
        Jelita mają oddzielne transportery dla glukozy (SGLT1) i fruktozy (GLUT5). 
        Łącząc oba cukry w proporcji 2:1, możesz wchłonąć nawet **90-120g/h** zamiast standardowych 60g/h samej glukozy.
        
        *Pamiętaj: Trening jelita jest równie ważny jak trening nóg! Nie testuj 90g/h pierwszy raz na zawodach.*
        """)
    
    if 'watts' in df_plot.columns:
        # --- CORRECTED MODEL: Physics-based CHO consumption ---
        # Based on XERT/INSCYD research and intervals.icu forum discussions
        
        # Step 1: Mechanical work to total energy expenditure
        # 1 kJ mechanical work ≈ 1 kcal total energy burned
        # (The ~24% efficiency factor roughly cancels the 4.184 kJ/kcal conversion)
        # Power [W] = J/s. For 1 hour: W * 3600 / 1000 = kJ/h ≈ kcal/h
        energy_kcal_per_hour = df_plot['watts'] * 3.6  # kJ/h ≈ kcal/h
        
        # Step 2: CHO fraction based on %FTP (INSCYD/XERT model)
        # Research shows:
        # - FatMax occurs around 55-65% FTP
        # - Above threshold, almost all energy from CHO
        intensity = df_plot['watts'] / cp_input if cp_input > 0 else df_plot['watts'] / 280
        
        # Piecewise linear CHO fraction model
        # Z1 (<55% FTP): ~30% CHO (fat dominant - recovery)
        # Z2 (55-75% FTP): 30-60% CHO (endurance - mixed)
        # Z3-Z4 (75-100% FTP): 60-90% CHO (tempo/threshold)
        # Z5+ (>100% FTP): 90-100% CHO (VO2max - almost all CHO)
        cho_fraction = np.where(intensity < 0.55, 0.30,
                      np.where(intensity < 0.75, 0.30 + (intensity - 0.55) * 1.5,   # 30→60%
                      np.where(intensity < 1.00, 0.60 + (intensity - 0.75) * 1.2,   # 60→90%
                      np.clip(0.90 + (intensity - 1.0) * 0.5, 0.90, 1.0))))         # 90-100%
        
        # Step 3: Calculate CHO burn rate
        # 1g CHO = 4 kcal
        cho_kcal_per_hour = energy_kcal_per_hour * cho_fraction
        carb_rate_per_sec = cho_kcal_per_hour / 4.0 / 3600.0  # Convert to g/s
        
        cumulative_burn = carb_rate_per_sec.cumsum()
        
        intake_per_sec = carb_intake / 3600.0
        cumulative_intake = np.cumsum(np.full(len(df_plot), intake_per_sec))
        
        glycogen_balance = initial_glycogen - cumulative_burn + cumulative_intake
        
        df_nutri = pd.DataFrame({
            'Czas [min]': df_plot['time_min'],
            'Bilans Glikogenu [g]': glycogen_balance,
            'Spalone [g]': cumulative_burn,
            'Spożyte [g]': cumulative_intake,
            'Burn Rate [g/h]': carb_rate_per_sec * 3600
        })

        
        # --- WYKRES 1: BILANS GLIKOGENU ---
        fig_nutri = go.Figure()
        
        # Linia Balansu
        line_color = '#00cc96' if df_nutri['Bilans Glikogenu [g]'].min() > 0 else '#ef553b'
        
        fig_nutri.add_trace(go.Scatter(
            x=df_nutri['Czas [min]'], 
            y=df_nutri['Bilans Glikogenu [g]'], 
            name='Zapas Glikogenu', 
            fill='tozeroy', 
            line=dict(color=line_color, width=2), 
            hovertemplate="<b>Czas: %{x:.0f} min</b><br>Zapas: %{y:.0f} g<extra></extra>"
        ))
        
        # Linia "Ściana" (Bonk)
        fig_nutri.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Ściana (Bonk)", annotation_position="bottom right")
        
        fig_nutri.update_layout(
            template="plotly_dark",
            title=f"Symulacja Baku Paliwa (Start: {initial_glycogen}g, Intake: {carb_intake}g/h)",
            hovermode="x unified",
            yaxis=dict(title="Glikogen [g]"),
            xaxis=dict(title="Czas [min]", tickformat=".0f"),
            margin=dict(l=10, r=10, t=40, b=10),
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_nutri, use_container_width=True)
        
        # --- WYKRES 2: TEMPO SPALANIA (BURN RATE) ---
        st.subheader("🔥 Tempo Spalania (Burn Rate)")
        fig_burn = go.Figure()
        
        burn_rate_smooth = df_nutri['Burn Rate [g/h]'].rolling(window=60, center=True, min_periods=1).mean()
        
        fig_burn.add_trace(go.Scatter(
            x=df_nutri['Czas [min]'], 
            y=burn_rate_smooth, 
            name='Spalanie', 
            line=dict(color='#ff7f0e', width=2), 
            fill='tozeroy', 
            hovertemplate="<b>Czas: %{x:.0f} min</b><br>Spalanie: %{y:.0f} g/h<extra></extra>"
        ))
        
        # Linia Spożycia (Intake)
        fig_burn.add_hline(y=carb_intake, line_dash="dot", line_color="#00cc96", annotation_text=f"Intake: {carb_intake}g/h", annotation_position="top right")
        
        # Linia limitu jelitowego
        fig_burn.add_hline(y=90, line_dash="dash", line_color="yellow", opacity=0.5, annotation_text="Limit jelitowy ~90g/h", annotation_position="bottom left")
        
        fig_burn.update_layout(
            template="plotly_dark",
            title="Zapotrzebowanie na Węglowodany",
            hovermode="x unified",
            yaxis=dict(title="Burn Rate [g/h]"),
            xaxis=dict(title="Czas [min]", tickformat=".0f"),
            margin=dict(l=10, r=10, t=40, b=10),
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_burn, use_container_width=True)

        # PODSUMOWANIE LICZBOWE
        total_burn = cumulative_burn.iloc[-1]
        total_intake = cumulative_intake[-1]
        final_balance = glycogen_balance.iloc[-1]
        avg_burn_rate = df_nutri['Burn Rate [g/h]'].mean()
        
        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Spalone Węgle", f"{total_burn:.0f} g", help="Suma węglowodanów zużytych na wysiłek")
        n2.metric("Spożyte Węgle", f"{total_intake:.0f} g", help="Suma węglowodanów dostarczonych z jedzenia/napojów")
        n3.metric("Wynik Końcowy", f"{final_balance:.0f} g", delta=f"{final_balance - initial_glycogen:.0f} g", delta_color="inverse" if final_balance < 0 else "normal")
        n4.metric("Śr. Spalanie", f"{avg_burn_rate:.0f} g/h", help="Średnie tempo spalania węgli podczas treningu")
        
        if final_balance < 0:
            bonk_time = df_nutri[df_nutri['Bilans Glikogenu [g]'] < 0]['Czas [min]'].iloc[0]
            st.error(f"⚠️ **UWAGA:** Według symulacji, Twoje zapasy glikogenu wyczerpały się w okolicach {bonk_time:.0f} minuty! To oznacza ryzyko 'odcięcia' (bonk).")
        else:
            st.success(f"✅ **OK:** Zakończyłeś trening z zapasem {final_balance:.0f}g glikogenu. Strategia żywieniowa wystarczająca dla tej intensywności.")
        
        # --- TEORIA FIZJOLOGII SPALANIA (ROZBUDOWANA) ---
        with st.expander("🔬 Fizjologia Spalania Węglowodanów (Model INSCYD)", expanded=False):
            st.markdown("""
            ## Model Metaboliczny: VO2max, VLaMax, i Spalanie Węglowodanów
            
            INSCYD i WKO5 używają zaawansowanych modeli metabolicznych, które uwzględniają dwa kluczowe parametry:
            
            ### 1. VO2max (Maksymalny Pobór Tlenu)
            * Określa Twoją maksymalną zdolność aerobową (tlenową)
            * Im wyższy VO2max, tym więcej energii możesz wytworzyć z tłuszczu i węglowodanów przy udziale tlenu
            
            ### 2. VLaMax (Maksymalna Produkcja Mleczanu)
            * Określa Twoją zdolność glikolityczną (beztlenową)
            * **Wysoki VLaMax** (>0.6 mmol/L/s): Sprintery, szybkie spalanie węgli, słabsza wytrzymałość
            * **Niski VLaMax** (<0.4 mmol/L/s): Climbers, oszczędne spalanie, lepsza ekonomia tłuszczowa
            
            ---
            
            ## Strefy Spalania Paliwa (dla FTP ~280W)
            
            | Intensywność | %FTP | Moc [W] | Udział CHO | Spalanie CHO [g/h] |
            |--------------|------|---------|------------|-------------------|
            | Z1 (Recovery) | <55% | <155 | ~30% | 30-50 |
            | Z2 (Endurance) | 55-75% | 155-210 | 30-60% | 50-100 |
            | Z3 (Tempo) | 76-90% | 210-250 | 60-80% | 100-180 |
            | Z4 (Threshold) | 91-105% | 250-295 | 80-95% | 180-250 |
            | Z5/Z6 (VO2max) | >105% | >295 | 95-100% | 250-350+ |
            
            ---
            
            ## Kluczowe Koncepcje
            
            ### FatMax (Maksymalne Spalanie Tłuszczu)
            * Intensywność, przy której spalasz najwięcej tłuszczu (zwykle 55-65% FTP)
            * Powyżej tego punktu, spalanie tłuszczu spada, a węgla rośnie
            
            ### CarbMax (Maksymalne Spalanie Węgli)
            * Maksymalne tempo, w jakim Twój organizm może spalać węglowodany
            * Limitowane przez VLaMax i enzymy glikolityczne
            * Typowo: 150-250 g/h dla elitarnych sportowców
            
            ### Limity Jelitowe
            * **Sama glukoza**: max ~60 g/h absorpcji
            * **Glukoza + Fruktoza (2:1)**: max ~90-120 g/h
            * Dlatego przy intensywnych wysiłkach (>Z4) zawsze "pożyczasz" z rezerw glikogenu
            
            ---
            
            ## Strategie Żywieniowe
            
            | Strategia | Kiedy stosować | Cel |
            |-----------|----------------|-----|
            | **Train Low** | Treningi Z2, długie bazy | Poprawa adaptacji tłuszczowej |
            | **Train High** | Interwały, tempo, wyścigi | Maksymalna wydajność |
            | **Periodyzacja** | Cykl tygodniowy | Łączenie obu strategii |
            | **Sleep Low** | Po treningu wieczorem | Wzmocnienie odpowiedzi adaptacyjnej |
            
            *Ten kalkulator używa modelu opartego na fizyce i badaniach XERT/INSCYD: praca mechaniczna (kJ) → energia całkowita (kcal) × udział węglowodanów (zależny od %FTP) / 4 kcal/g.*
            """)
    else:
        st.warning("Brak danych mocy (Watts) do obliczenia wydatku energetycznego.")


