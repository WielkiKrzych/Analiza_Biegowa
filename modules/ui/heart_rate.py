import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def render_hr_tab(df):
    st.markdown("### ❤️ Analiza Tętna")
    
    if df is None or df.empty:
        st.error("Brak danych.")
        return

    # 1. Normalizacja danych
    df_chart = df.copy()
    # Ensure columns are lowercased and stripped (though load_data usually does this)
    df_chart.columns = df_chart.columns.str.lower().str.strip()
    
    # Aliasy dla HR
    if 'hr' not in df_chart.columns:
        for alias in ['heart_rate', 'heart rate', 'bpm', 'tętno', 'heartrate', 'heart_rate_bpm']:
            if alias in df_chart.columns:
                df_chart.rename(columns={alias: 'hr'}, inplace=True)
                break
                
    if 'hr' not in df_chart.columns:
        st.warning("⚠️ Brak danych tętna (HR) w wczytanym pliku.")
        with st.expander("Pokaż dostępne kolumny"):
            st.write(list(df_chart.columns))
        return

    # Upewnij się że time istnieje
    if 'time' not in df_chart.columns:
        # Spróbuj wygenerować czas z indexu jeśli brak
        df_chart['time'] = np.arange(len(df_chart))
    
    # 2. Selektor zakresu
    # Konwersja czasu na ładny format HH:MM:SS do wyświetlania w sliderze byłaby super, 
    # ale slider na sekundach jest bardziej precyzyjny/prostszy w kodzie.
    # Dodamy formatowanie czasu w opisie.
    
    # Konwersja czasu
    def parse_time(t_str):
        try:
            parts = list(map(int, t_str.split(':')))
            if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
            if len(parts) == 2: return parts[0]*60 + parts[1]
            if len(parts) == 1: return parts[0]
        except:
            return None
        return None
    
    def format_time(seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    min_time = df_chart['time'].min()
    max_time = df_chart['time'].max()
    
    st.markdown("#### Wybierz zakres analizy")
    
    c1, c2 = st.columns(2)
    # Domyślne wartości to cały zakres
    start_str = c1.text_input("Start (hh:mm:ss/mm:ss)", value=format_time(min_time))
    end_str = c2.text_input("Koniec (hh:mm:ss/mm:ss)", value=format_time(max_time))
    
    start_s = parse_time(start_str)
    end_s = parse_time(end_str)
    
    if start_s is None or end_s is None:
        st.error("Nieprawidłowy format czasu. Użyj formatu HH:MM:SS lub MM:SS")
        return # Stop execution until fixed

    if start_s >= end_s:
        st.error("Czas końcowy musi być większy niż startowy.")
        return
    
    # Filtrowanie
    mask = (df_chart['time'] >= start_s) & (df_chart['time'] <= end_s)
    df_segment = df_chart.loc[mask]
    
    if df_segment.empty:
        st.info("Brak danych w wybranym zakresie.")
        return

    # Obliczenie czasu trwania
    duration = end_s - start_s
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    st.caption(f"Analizowany fragment: {minutes} min {seconds} s")

    # 3. Metryki
    avg_hr = df_segment['hr'].mean()
    min_hr = df_segment['hr'].min()
    max_hr = df_segment['hr'].max()
    
    # Wyświetlenie metryk
    # Stylizacja metryk w kontenerze
    with st.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Średnie HR", f"{avg_hr:.0f} bpm")
        c2.metric("Min HR", f"{min_hr:.0f} bpm")
        c3.metric("Max HR", f"{max_hr:.0f} bpm")
    
    st.markdown("---")

    # 4. Wykres z wygładzaniem (10s średnia krocząca)
    # Wyliczamy window (zakładamy 1Hz, można by sprawdzić częstotliwość, ale 10 wierszy to bezpieczny default)
    # Jeśli dane są rzadsze, rolling(window=10) i tak zadziała.
    df_segment['hr_smooth'] = df_segment['hr'].rolling(window=10, center=True, min_periods=1).mean()
    
    fig = go.Figure()
    
    # Linia HR (wygładzona)
    # Dodajemy sformatowany czas do tooltipa
    df_segment['time_str'] = pd.to_datetime(df_segment['time'], unit='s').dt.strftime('%H:%M:%S')

    fig.add_trace(go.Scatter(
        x=df_segment['time'], 
        y=df_segment['hr_smooth'],
        mode='lines',
        name='HR (10s avg)',
        line=dict(color='#d62728', width=2),
        customdata=df_segment['time_str'],
        hovertemplate="<b>Czas:</b> %{customdata} (%{x}s)<br><b>HR (10s):</b> %{y:.1f} bpm<extra></extra>"
    ))
    
    # Linia średniej wizualnie
    fig.add_hline(y=avg_hr, line_dash="dash", line_color="white", opacity=0.5, annotation_text="Avg", annotation_position="bottom right")

    fig.update_layout(
        title="Wykres Tętna (HR) - Średnia Krocząca 10s",
        xaxis_title="Czas (s)",
        yaxis_title="Tętno (bpm)",
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
