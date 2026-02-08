"""
Genetics UI.

Display genetic profile analysis and personalized recommendations.
"""
import streamlit as st
import plotly.graph_objects as go

from modules.genetics import GeneticAnalyzer, GeneticProfile


def render_genetics_tab():
    """Render genetics analysis tab."""
    st.header("🧬 Genetic Fitness Profile")
    
    st.info("""
    **Analiza genetyczna** pozwala zrozumieć Twoje predyspozycje do różnych typów wysiłku.
    
    Możesz wgrać plik z 23andMe lub Ancestry DNA, lub ręcznie wprowadzić znane warianty.
    """)
    
    analyzer = GeneticAnalyzer()
    profile = None
    
    # Manual input or file upload
    tab_manual, tab_upload = st.tabs(["📝 Wprowadź ręcznie", "📤 Wgraj plik"])
    
    with tab_manual:
        st.subheader("Wprowadź swoje warianty genetyczne")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            actn3 = st.selectbox(
                "ACTN3 (rs1815739)",
                options=["Nieznany", "RR", "RX", "XX"],
                help="RR = włókna szybkie, XX = włókna wolne"
            )
        
        with col2:
            ace = st.selectbox(
                "ACE (rs1799752)",
                options=["Nieznany", "II", "ID", "DD"],
                help="II = wytrzymałość, DD = siła"
            )
        
        with col3:
            ppargc1a = st.selectbox(
                "PPARGC1A (rs8192678)",
                options=["Nieznany", "GG", "GA", "AA"],
                help="AA = lepsza biogeneza mitochondriów"
            )
        
        if st.button("🔬 Analizuj profil"):
            profile = GeneticProfile(
                actn3=actn3 if actn3 != "Nieznany" else None,
                ace=ace if ace != "Nieznany" else None,
                ppargc1a=ppargc1a if ppargc1a != "Nieznany" else None
            )
    
    with tab_upload:
        uploaded = st.file_uploader(
            "Wgraj plik raw data z 23andMe/Ancestry",
            type=['txt', 'csv']
        )
        
        if uploaded:
            try:
                raw_data = uploaded.read().decode('utf-8')
                profile = analyzer.parse_23andme(raw_data)
                st.success("✅ Plik przeanalizowany!")
            except Exception as e:
                st.error(f"Błąd parsowania: {e}")
    
    # Display results
    if profile:
        st.divider()
        _display_profile(profile, analyzer)


def _display_profile(profile: GeneticProfile, analyzer: GeneticAnalyzer):
    """Display genetic profile analysis."""
    st.subheader(f"📊 Twój typ: {profile.athlete_type}")
    
    # Score gauges
    col1, col2, col3 = st.columns(3)
    
    with col1:
        _create_score_gauge("Wytrzymałość", profile.endurance_score, "#00cc96")
    
    with col2:
        _create_score_gauge("Moc", profile.power_score, "#ef553b")
    
    with col3:
        _create_score_gauge("Regeneracja", profile.recovery_score, "#636efa")
    
    # Detected variants
    st.divider()
    st.subheader("🔬 Wykryte warianty")
    
    variants = []
    if profile.actn3:
        desc = {"RR": "Włókna szybkie (sprint)", "RX": "Mieszany", "XX": "Włókna wolne (wytrzymałość)"}
        variants.append(f"**ACTN3:** {profile.actn3} - {desc.get(profile.actn3, '')}")
    
    if profile.ace:
        desc = {"II": "Wytrzymałość", "ID": "Mieszany", "DD": "Siła/Moc"}
        variants.append(f"**ACE:** {profile.ace} - {desc.get(profile.ace, '')}")
    
    if profile.ppargc1a:
        desc = {"GG": "Standardowy", "GA": "Ulepszona biogeneza", "AA": "Wysoka efektywność"}
        variants.append(f"**PPARGC1A:** {profile.ppargc1a} - {desc.get(profile.ppargc1a, '')}")
    
    if variants:
        for v in variants:
            st.markdown(f"- {v}")
    else:
        st.info("Nie wykryto wariantów. Wprowadź dane ręcznie lub wgraj plik.")
    
    # Recommendations
    st.divider()
    st.subheader("💡 Rekomendacje treningowe")
    
    recommendations = analyzer.get_recommendations(profile)
    
    for rec in recommendations:
        with st.expander(f"{rec['title']}", expanded=True):
            st.markdown(rec['description'])


def _create_score_gauge(label: str, value: float, color: str):
    """Create a score gauge chart."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': label, 'font': {'size': 14}},
        number={'suffix': '/100', 'font': {'size': 20}},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': color},
            'bgcolor': 'rgba(0,0,0,0)',
            'steps': [
                {'range': [0, 33], 'color': 'rgba(255,255,255,0.1)'},
                {'range': [33, 66], 'color': 'rgba(255,255,255,0.15)'},
                {'range': [66, 100], 'color': 'rgba(255,255,255,0.2)'},
            ]
        }
    ))
    
    fig.update_layout(
        template="plotly_dark",
        height=180,
        margin=dict(t=40, b=0, l=20, r=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)
