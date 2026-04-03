"""
Community Comparison UI.

Displays anonymized comparisons with other athletes:
- FTP/kg percentiles
- VO2max rankings
- Category placement
"""
import plotly.graph_objects as go
import streamlit as st

from modules.social.comparison import ComparisonService


def render_community_tab(
    ftp: float,
    weight: float,
    vo2max: float,
    age: int,
    gender: str
):
    """Render community comparison tab.
    
    Args:
        ftp: FTP in watts
        weight: Weight in kg
        vo2max: VO2max estimate
        age: Athlete age
        gender: 'M' or 'F'
    """
    st.header("👥 Community Comparison")

    if weight <= 0 or ftp <= 0:
        st.warning("Uzupełnij wagę i FTP w panelu bocznym aby zobaczyć porównanie.")
        return

    service = ComparisonService()

    # Get rankings
    rankings = service.get_summary_rankings(ftp, weight, vo2max, age, gender)

    if not rankings:
        st.info("Brak danych do porównania.")
        return

    # Display rankings
    col1, col2 = st.columns(2)

    for i, ranking in enumerate(rankings):
        with col1 if i == 0 else col2:
            # Percentile gauge
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=ranking.percentile,
                title={'text': ranking.metric},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': _get_percentile_color(ranking.percentile)},
                    'steps': [
                        {'range': [0, 25], 'color': 'rgba(255, 0, 0, 0.2)'},
                        {'range': [25, 50], 'color': 'rgba(255, 165, 0, 0.2)'},
                        {'range': [50, 75], 'color': 'rgba(255, 255, 0, 0.2)'},
                        {'range': [75, 100], 'color': 'rgba(0, 255, 0, 0.2)'},
                    ],
                    'threshold': {
                        'line': {'color': 'white', 'width': 2},
                        'thickness': 0.75,
                        'value': ranking.percentile
                    }
                }
            ))

            fig.update_layout(
                template="plotly_dark",
                height=200,
                margin=dict(t=50, b=0)
            )

            st.plotly_chart(fig, use_container_width=True)

            st.markdown(f"""
            **{ranking.metric}:** {ranking.value:.2f}
            
            🏆 **Kategoria:** {ranking.category}
            
            📊 Lepszy od **{ranking.percentile:.0f}%** zawodników
            """)

    # Category explanation
    st.divider()
    st.subheader("🏅 Kategorie Kolarskie")

    categories_data = [
        ("World Tour Pro", 7.0, "🌍"),
        ("Cat 1 / Elite", 5.8, "🥇"),
        ("Cat 2", 5.0, "🥈"),
        ("Cat 3", 4.2, "🥉"),
        ("Cat 4", 3.5, "⭐"),
        ("Cat 5", 3.0, ""),
        ("Recreational", 2.5, ""),
    ]

    ftp_wkg = ftp / weight

    for cat_name, threshold, emoji in categories_data:
        if ftp_wkg >= threshold:
            st.success(f"{emoji} **{cat_name}** (≥{threshold} W/kg) ← Tu jesteś!")
        else:
            st.markdown(f"- {cat_name} (≥{threshold} W/kg)")

    # Privacy notice
    st.divider()
    st.caption("""
    ℹ️ **Prywatność:** Wszystkie porównania są wykonywane lokalnie. 
    Twoje dane nie są wysyłane na zewnętrzne serwery. 
    Percentyle oparte są na opublikowanych badaniach naukowych.
    """)


def _get_percentile_color(percentile: float) -> str:
    """Get color based on percentile."""
    if percentile >= 90:
        return "#00cc96"  # Green
    elif percentile >= 75:
        return "#00d4ff"  # Cyan
    elif percentile >= 50:
        return "#ffd700"  # Yellow
    elif percentile >= 25:
        return "#ff8c00"  # Orange
    else:
        return "#ff4444"  # Red
