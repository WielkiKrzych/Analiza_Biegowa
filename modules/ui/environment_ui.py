"""
Environment UI.

Display weather conditions and TSS corrections.
"""
import streamlit as st
from datetime import datetime

from modules.environment import EnvironmentService, WeatherData


def render_environment_tab(tss: float):
    """Render environment/weather tab.
    
    Args:
        tss: Base TSS value for correction calculation
    """
    st.header("🌡️ Environmental Factors")
    
    service = EnvironmentService()
    
    # Location input
    st.subheader("📍 Lokalizacja treningu")
    
    col1, col2 = st.columns(2)
    
    with col1:
        lat = st.number_input("Szerokość geogr.", value=52.23, format="%.4f")
    
    with col2:
        lon = st.number_input("Długość geogr.", value=21.01, format="%.4f")
    
    # Manual altitude input
    altitude = st.number_input("Wysokość (m n.p.m.)", value=0, min_value=0, max_value=5000)
    
    # Fetch weather
    if st.button("🌤️ Pobierz pogodę"):
        weather = service.get_conditions(datetime.now(), lat, lon)
        
        if weather:
            weather.altitude = altitude
            st.session_state['current_weather'] = weather
    
    # Display weather if available
    weather = st.session_state.get('current_weather')
    
    if weather:
        st.divider()
        _display_weather(weather, tss, service)
    else:
        st.info("""
        Kliknij "Pobierz pogodę" lub ustaw zmienną środowiskową `OPENWEATHER_API_KEY` 
        dla automatycznego pobierania danych pogodowych.
        """)
    
    # Manual conditions input
    st.divider()
    st.subheader("📝 Ręczne wprowadzanie warunków")
    
    with st.expander("Wprowadź warunki ręcznie"):
        temp = st.slider("Temperatura (°C)", -10, 45, 20)
        humidity = st.slider("Wilgotność (%)", 0, 100, 60)
        wind = st.slider("Wiatr (km/h)", 0, 50, 10)
        
        if st.button("Oblicz korekty"):
            manual_weather = WeatherData(
                temperature=temp,
                humidity=humidity,
                wind_speed=wind,
                feels_like=temp,
                description="Ręcznie wprowadzone",
                location="Manual",
                timestamp=datetime.now(),
                altitude=altitude
            )
            st.session_state['current_weather'] = manual_weather
            st.rerun()


def _display_weather(weather: WeatherData, tss: float, service: EnvironmentService):
    """Display weather conditions and corrections."""
    st.subheader("🌤️ Aktualne warunki")
    
    # Weather display
    c1, c2, c3, c4 = st.columns(4)
    
    c1.metric("Temperatura", f"{weather.temperature:.1f}°C", 
              delta="↑" if weather.is_hot else None,
              delta_color="inverse" if weather.is_hot else "off")
    
    c2.metric("Wilgotność", f"{weather.humidity:.0f}%",
              delta="↑" if weather.is_humid else None,
              delta_color="inverse" if weather.is_humid else "off")
    
    c3.metric("Wiatr", f"{weather.wind_speed:.0f} km/h",
              delta="↑" if weather.is_windy else None)
    
    c4.metric("Wysokość", f"{weather.altitude:.0f} m",
              delta="↑" if weather.is_high_altitude else None)
    
    # TSS correction
    st.divider()
    st.subheader("📊 Korekta TSS")
    
    correction, explanation = service.calculate_tss_correction(weather)
    adjusted_tss, _ = service.adjust_tss(tss, weather)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Bazowy TSS", f"{tss:.0f}")
    
    with col2:
        delta = adjusted_tss - tss
        st.metric("Skorygowany TSS", f"{adjusted_tss:.0f}", 
                  delta=f"+{delta:.0f}" if delta > 0 else None)
    
    if correction > 0:
        st.info(f"**Korekty:** {explanation}")
    else:
        st.success("Warunki optymalne - brak korekt TSS")
    
    # Heat acclimation status
    st.divider()
    if weather.is_hot:
        st.subheader("🔥 Aklimatyzacja cieplna")
        
        recent_hot = st.number_input(
            "Ile sesji w gorących warunkach (>30°C) w ostatnich 14 dniach?",
            min_value=0, max_value=20, value=0
        )
        
        status = service.get_heat_acclimation_status(recent_hot)
        st.markdown(status)
        
        if recent_hot < 5:
            st.warning("""
            **Wskazówki do aklimatyzacji:**
            - Zaplanuj 10-14 dni treningu w gorących warunkach
            - Rozpocznij od krótszych, lżejszych sesji
            - Zwiększ nawodnienie o 50-100%
            - Monitoruj temperaturę ciała
            """)
