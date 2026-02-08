"""
Historical Trends UI.

Visualizes training progress over time:
- NP/TSS trends
- MMP evolution
- HRV trends
- Zone distribution changes
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from modules.db import SessionStore


def render_trends_history_tab():
    """Render historical trends analysis tab."""
    st.header("📈 Historical Trends")
    
    store = SessionStore()
    session_count = store.get_session_count()
    
    if session_count < 3:
        st.info(f"""
        **Potrzebujesz więcej danych.**
        
        Masz {session_count} zapisanych sesji. Wgraj więcej plików treningowych 
        aby zobaczyć trendy. Minimalna wymagana ilość: 3 sesje.
        """)
        return
    
    # Time range selector
    col1, col2 = st.columns([1, 3])
    with col1:
        days = st.selectbox(
            "Zakres",
            options=[30, 60, 90, 180, 365],
            index=2,
            format_func=lambda x: f"{x} dni"
        )
    
    sessions = store.get_sessions(days=days)
    
    if not sessions:
        st.warning("Brak sesji w wybranym okresie.")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame([
        {
            'date': s.date,
            'duration': s.duration_sec / 60,
            'tss': s.tss,
            'np': s.np,
            'avg_watts': s.avg_watts,
            'avg_hr': s.avg_hr,
            'work_kj': s.work_kj,
            'mmp_5m': s.mmp_5m,
            'mmp_20m': s.mmp_20m,
            'avg_rmssd': s.avg_rmssd,
        }
        for s in sessions
    ])
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    st.subheader("📊 Power Progression")
    
    # NP/TSS trend
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Weekly aggregation for smoother trend
    df_weekly = df.set_index('date').resample('W').agg({
        'tss': 'sum',
        'np': 'mean',
        'avg_watts': 'mean',
        'duration': 'sum'
    }).reset_index()
    
    fig.add_trace(
        go.Bar(
            x=df_weekly['date'],
            y=df_weekly['tss'],
            name='Weekly TSS',
            marker_color='rgba(100, 100, 100, 0.5)'
        ),
        secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(
            x=df_weekly['date'],
            y=df_weekly['np'],
            name='Avg NP',
            line=dict(color='#00cc96', width=3),
            mode='lines+markers'
        ),
        secondary_y=True
    )
    
    # Add trendline
    if len(df_weekly) > 2:
        z = np.polyfit(range(len(df_weekly)), df_weekly['np'].fillna(0), 1)
        p = np.poly1d(z)
        trend_direction = "📈" if z[0] > 0 else "📉"
        
        fig.add_trace(
            go.Scatter(
                x=df_weekly['date'],
                y=p(range(len(df_weekly))),
                name=f'Trend {trend_direction}',
                line=dict(color='white', dash='dash', width=2)
            ),
            secondary_y=True
        )
    
    fig.update_layout(
        template="plotly_dark",
        height=400,
        hovermode="x unified",
        yaxis_title="Weekly TSS",
        yaxis2_title="Avg NP (W)"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # MMP Evolution
    st.subheader("🏆 MMP Evolution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 5-min power trend
        if df['mmp_5m'].notna().sum() > 2:
            fig_5m = go.Figure()
            fig_5m.add_trace(go.Scatter(
                x=df['date'],
                y=df['mmp_5m'],
                name='5min Power',
                mode='lines+markers',
                line=dict(color='#ef553b', width=2)
            ))
            fig_5m.update_layout(
                template="plotly_dark",
                height=250,
                title="5-min MMP",
                yaxis_title="Watts"
            )
            st.plotly_chart(fig_5m, use_container_width=True)
        else:
            st.info("Za mało danych dla 5min MMP")
    
    with col2:
        # 20-min power trend
        if df['mmp_20m'].notna().sum() > 2:
            fig_20m = go.Figure()
            fig_20m.add_trace(go.Scatter(
                x=df['date'],
                y=df['mmp_20m'],
                name='20min Power',
                mode='lines+markers',
                line=dict(color='#636efa', width=2)
            ))
            fig_20m.update_layout(
                template="plotly_dark",
                height=250,
                title="20-min MMP (≈FTP)",
                yaxis_title="Watts"
            )
            st.plotly_chart(fig_20m, use_container_width=True)
        else:
            st.info("Za mało danych dla 20min MMP")
    
    # HRV Trend
    if df['avg_rmssd'].notna().sum() > 2:
        st.subheader("💓 HRV Trend")
        
        fig_hrv = go.Figure()
        fig_hrv.add_trace(go.Scatter(
            x=df['date'],
            y=df['avg_rmssd'],
            name='RMSSD',
            mode='lines+markers',
            line=dict(color='#00cc96', width=2)
        ))
        
        # 7-day rolling average
        df['rmssd_7d'] = df['avg_rmssd'].rolling(7, min_periods=1).mean()
        fig_hrv.add_trace(go.Scatter(
            x=df['date'],
            y=df['rmssd_7d'],
            name='7-day Avg',
            line=dict(color='white', dash='dash')
        ))
        
        fig_hrv.update_layout(
            template="plotly_dark",
            height=300,
            yaxis_title="RMSSD (ms)"
        )
        st.plotly_chart(fig_hrv, use_container_width=True)
    
    # Summary stats
    st.divider()
    st.subheader("📋 Summary")
    
    c1, c2, c3, c4 = st.columns(4)
    
    c1.metric("Total Sessions", len(sessions))
    c2.metric("Total TSS", f"{df['tss'].sum():.0f}")
    c3.metric("Total Hours", f"{df['duration'].sum() / 60:.1f}")
    c4.metric("Avg Weekly TSS", f"{df['tss'].sum() / max(1, days/7):.0f}")
