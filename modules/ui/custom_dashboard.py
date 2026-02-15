"""
Custom Dashboard - User-configurable dashboard with drag-and-drop widgets.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta


def render_custom_dashboard():
    """Render customizable dashboard."""
    st.header("📊 Własny Dashboard")
    
    # Check for saved dashboard config
    if "dashboard_config" not in st.session_state:
        st.session_state["dashboard_config"] = {
            "widgets": ["ctl", "tsb", "rss", "distance", "pace", "hr"]
        }
    
    config = st.session_state["dashboard_config"]
    
    # Dashboard layout selector
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("**Konfiguracja widżetów:**")
    with col2:
        if st.button("🔄 Resetuj"):
            config["widgets"] = ["ctl", "tsb", "rss", "distance", "pace", "hr"]
            st.rerun()
    
    # Available widgets
    available_widgets = {
        "ctl": ("CTL (Forma)", "modules.training_load", "get_ctl"),
        "tsb": ("TSB (Balance)", "modules.training_load", "get_tsb"),
        "rss": ("RSS (Stress)", "modules.ui.running", "get_rss"),
        "distance": ("Dystans", "modules.ui.running", "get_distance"),
        "pace": ("Tempo", "modules.ui.running", "get_pace"),
        "hr": ("Tętno", "modules.ui.heart_rate", "get_hr"),
        "cadence": ("Kadencja", "modules.ui.biomech", "get_cadence"),
        "vo": ("Vertical Oscillation", "modules.ui.biomech", "get_vo"),
    }
    
    # Widget selection
    selected = st.multiselect(
        "Wybierz widżety do wyświetlenia",
        options=list(available_widgets.keys()),
        default=config["widgets"],
        format_func=lambda x: available_widgets[x][0]
    )
    
    config["widgets"] = selected
    
    # Render selected widgets in grid
    if selected:
        cols = st.columns(min(len(selected), 3))
        
        for i, widget in enumerate(selected):
            with cols[i % 3]:
                if widget == "ctl":
                    from modules.training_load import TrainingLoadManager
                    manager = TrainingLoadManager()
                    current = manager.get_current_form()
                    if current:
                        st.metric("CTL (Forma)", f"{current.ctl:.0f}", help="Chronic Training Load - Twoja baza fitness")
                elif widget == "tsb":
                    from modules.training_load import TrainingLoadManager
                    manager = TrainingLoadManager()
                    current = manager.get_current_form()
                    if current:
                        st.metric("TSB (Balance)", f"{current.tsb:.0f}", delta=current.form_status, delta_color="off")
                elif widget == "rss":
                    st.metric("RSS", "—", help="Running Stress Score z ostatniego treningu")
                elif widget == "distance":
                    st.metric("Dystans", "—", help="Dystans z ostatniego treningu")
                elif widget == "pace":
                    st.metric("Tempo", "—", help="Średnie tempo z ostatniego treningu")
                elif widget == "hr":
                    st.metric("Tętno", "—", help="Średnie tętno z ostatniego treningu")
                elif widget == "cadence":
                    st.metric("Kadencja", "—", help="Średnia kadencja z ostatniego treningu")
                elif widget == "vo":
                    st.metric("VO", "—", help="Vertical Oscillation z ostatniego treningu")
    else:
        st.info("Wybierz widżety aby wyświetlić swój dashboard")
    
    # Quick stats section
    st.divider()
    st.subheader("📈 Statystyki tygodnia")
    
    from modules.training_load import TrainingLoadManager
    manager = TrainingLoadManager()
    
    sessions = manager.store.get_sessions(days=7)
    if sessions:
        week_df = pd.DataFrame([
            {
                "Data": s.date,
                "Dystans": f"{s.distance_km:.1f} km" if s.distance_km else "—",
                "Czas": f"{s.duration_sec//60} min",
            }
            for s in sessions
        ])
        st.dataframe(week_df, use_container_width=True, hide_index=True)
    else:
        st.info("Brak treningów w tym tygodniu")


def render_training_zones_chart():
    """Render training zones visualization."""
    st.header("🎯 Strefy Treningowe")
    
    # Get threshold pace from session state
    threshold_pace = st.session_state.get("threshold_pace", 300)  # 5:00/km default
    
    # Calculate zone boundaries (based on percentage of threshold pace)
    zones = [
        ("Z1 - Recovery", 1.15, 1.25, "#4CAF50", "Nadmiernie lekki"),
        ("Z2 - Aerobic", 1.05, 1.15, "#8BC34A", "Lekki - budowa bazy"),
        ("Z3 - Tempo", 0.95, 1.05, "#FFEB3B", "Umiarkowany - threshold"),
        ("Z4 - Threshold", 0.88, 0.95, "#FF9800", "Ciężki - powyżej progu"),
        ("Z5 - VO2max", 0.75, 0.88, "#F44336", "Bardzo ciężki - interwały"),
        ("Z6 - Repetition", 0.60, 0.75, "#9C27B0", "Maksymalny - sprinty"),
    ]
    
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    # Create zone bars
    for zone_name, lower_pct, upper_pct, color, desc in zones:
        lower = threshold_pace * lower_pct
        upper = threshold_pace * upper_pct
        
        # Format pace
        def fmt(s):
            mins = int(s // 60)
            secs = int(s % 60)
            return f"{mins}:{secs:02d}"
        
        fig.add_trace(go.Bar(
            x=[zone_name],
            y=[upper - lower],
            base=[lower],
            name=zone_name,
            marker_color=color,
            hovertemplate=f"{zone_name}<br>{fmt(lower)} - {fmt(upper)} /km<br>{desc}<extra></extra>"
        ))
    
    fig.update_layout(
        title="Strefy tempa (jako % tempa progowego)",
        yaxis_title="Tempo [s/km]",
        yaxis=dict(autorange="reversed"),
        template="plotly_dark",
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Zone table
    st.subheader("📋 Szczegóły stref")
    
    zone_data = []
    for zone_name, lower_pct, upper_pct, color, desc in zones:
        lower = threshold_pace * lower_pct
        upper = threshold_pace * upper_pct
        
        mins_l = int(lower // 60)
        secs_l = int(lower % 60)
        mins_u = int(upper // 60)
        secs_u = int(upper % 60)
        
        zone_data.append({
            "Strefa": zone_name,
            "Zakres": f"{mins_l}:{secs_l:02d} - {mins_u}:{secs_u:02d}",
            "Opis": desc
        })
    
    st.dataframe(pd.DataFrame(zone_data), use_container_width=True, hide_index=True)


def render_weekly_report():
    """Render weekly report."""
    st.header("📅 Raport Tygodniowy")
    
    from modules.training_load import TrainingLoadManager
    from modules.db import SessionStore
    
    manager = TrainingLoadManager()
    store = SessionStore()
    
    # Week selector
    today = datetime.now().date()
    week_offset = st.selectbox("Tydzień", range(-4, 1), format_func=lambda x: f"{x} tydzień")
    
    # Calculate week range
    week_start = today - timedelta(days=today.weekday() + 7 * abs(week_offset))
    week_end = week_start + timedelta(days=6)
    
    st.write(f"**{week_start} - {week_end}**")
    
    # Get sessions for the week
    sessions = store.get_sessions(days=7)
    
    if not sessions:
        st.info("Brak treningów w tym okresie")
        return
    
    # Calculate weekly stats
    total_distance = sum(s.distance_km for s in sessions)
    total_time = sum(s.duration_sec for s in sessions) / 3600
    total_rss = sum(s.rss for s in sessions)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Treningi", len(sessions))
    m2.metric("Dystans", f"{total_distance:.1f} km")
    m3.metric("Czas", f"{total_time:.1f} h")
    m4.metric("RSS", f"{total_rss:.0f}")
    
    # Training distribution
    st.subheader("📊 Rozkład treningów")
    
    import plotly.express as px
    
    training_types = {}
    for s in sessions:
        t = s.filename.split('.')[0] if s.filename else "Inny"
        training_types[t] = training_types.get(t, 0) + 1
    
    if training_types:
        fig = px.pie(
            values=list(training_types.values()),
            names=list(training_types.keys()),
            title="Rodzaje treningów"
        )
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    
    # Form trend
    st.subheader("📈 Trend formy")
    
    history = manager.calculate_load(days=14)
    if history:
        df = pd.DataFrame([
            {"Data": h.date, "CTL": h.ctl, "ATL": h.atl, "TSB": h.tsb}
            for h in history
        ])
        
        fig = px.line(df, x="Data", y=["CTL", "ATL"], title="CTL vs ATL")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    
    # Recommendations
    st.subheader("💡 Rekomendacje")
    
    current = manager.get_current_form()
    if current:
        if current.tsb < -20:
            st.warning("⚠️ Zmęczenie wysokie. Rozważ odpoczynek lub lekki trening.")
        elif current.tsb > 20:
            st.success("✅ Forma dobra. Możesz zwiększyć intensywność!")
        else:
            st.info("📊 Forma stabilna. Kontynuuj plan treningowy.")
        
        ramp = manager.calculate_ramp_rate()
        if ramp > 10:
            st.warning(f"⚠️ Ramp rate wysoki ({ramp:.1f}%/tydzień). Zwiększaj obciążenie wolniej.")
    
    # Export
    if st.button("📥 Eksportuj raport"):
        st.info("Funkcja eksportu PDF - wkrótce!")


def render_training_recommendations():
    """Render AI training recommendations."""
    st.header("🤖 Rekomendacje Treningowe")
    
    from modules.training_load import TrainingLoadManager
    
    manager = TrainingLoadManager()
    current = manager.get_current_form()
    
    if not current:
        st.info("Brak danych do generowania rekomendacji. Wgraj treningi.")
        return
    
    # Analyze current state
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Forma (CTL)", f"{current.ctl:.0f}")
    with col2:
        st.metric("TSB", f"{current.tsb:.0f}", delta=current.form_status, delta_color="off")
    
    # Generate recommendations
    st.subheader("🎯 Rekomendacje na dziś:")
    
    recommendations = []
    
    # Based on TSB
    if current.tsb > 25:
        recommendations.append({
            "type": "high_intensity",
            "title": "✅ Możesz trenować intensywnie",
            "description": "Twoja forma jest bardzo dobra (TSB > 25). Idealny dzień na interwały lub trening threshold.",
            "suggested": "2x15min @ Z4-Z5 z 5min przerwami"
        })
    elif current.tsb > 5:
        recommendations.append({
            "type": "moderate",
            "title": "📊 Dobra forma na trening",
            "description": "TSB dodatnie oznacza, że możesz trenować produktywnie.",
            "suggested": "1h @ Z2 z 4x8min @ Z3"
        })
    elif current.tsb > -10:
        recommendations.append({
            "type": "recovery",
            "title": "🟡 Umiarkowane obciążenie",
            "description": "TSB w optymalnym zakresie. Możesz trenować ale nie przesadzaj.",
            "suggested": "45min @ Z1-Z2"
        })
    else:
        recommendations.append({
            "type": "rest",
            "title": "🔴 Rozważ odpoczynek",
            "description": "TSB bardzo niski. Ryzyko przetrenowania.",
            "suggested": "Dzień odpoczynku lub lekka aktywność"
        })
    
    # Based on ramp rate
    ramp = manager.calculate_ramp_rate()
    if ramp > 10:
        recommendations.append({
            "type": "warning",
            "title": "⚠️ Uważaj na ramp rate",
            "description": "Twoje obciążenie rośnie zbyt szybko.",
            "suggested": "Zmniejsz TSS o 10-20% w tym tygodniu"
        })
    
    # Display recommendations
    for rec in recommendations:
        with st.expander(f"{rec['title']}"):
            st.write(rec['description'])
            st.write(f"**Sugestia:** {rec['suggested']}")
    
    # Long term prediction
    st.divider()
    st.subheader("🔮 Prognoza")
    
    min_tss, max_tss = manager.get_recommended_tss()
    st.info(f"**Zalecany TSS na dziś:** {min_tss:.0f} - {max_tss:.0f}")
    
    st.caption("Rekomendacje oparte na modelu Training Load (PMC)")


def render_smart_intervals():
    """Render smart interval detection."""
    st.header("🔍 Inteligentna Detekcja Interwałów")
    
    st.info("""
    Ta funkcja automatycznie wykrywa interwały w Twoim treningu na podstawie danych z pliku.
    Wgraj plik treningowy aby przeprowadzić analizę.
    """)
    
    # This would be integrated with the actual training data
    # For now, showing the UI structure
    
    # Detection settings
    with st.expander("⚙️ Ustawienia detekcji"):
        col1, col2 = st.columns(2)
        with col1:
            min_duration = st.slider("Min. czas interwału [min]", 1, 10, 3)
        with col2:
            intensity_threshold = st.slider("Próg intensywności [%]", 50, 100, 80)
    
    st.write(f"Wykrywanie interwałów: min. {min_duration} min, próg {intensity_threshold}%")
    
    # Placeholder for detected intervals
    st.warning("Wgraj plik treningowy aby wykryć interwały")
    
    # Would show:
    # - Interval segments
    # - Recovery periods
    # - Intensity distribution
    # - Suggested interval structure
