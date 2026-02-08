"""
SOLID: Open/Closed Principle - System eksportu wykresów.

Wzorzec Registry pozwala na dodawanie nowych wykresów bez modyfikacji
istniejącego kodu. Każdy wykres to osobna klasa implementująca ChartExporter.

Użycie:
    from modules.chart_exporters import CHART_REGISTRY, ChartContext
    
    ctx = ChartContext(df_plot, df_resampled, rider_weight, ...)
    for exporter in CHART_REGISTRY:
        if exporter.can_export(ctx):
            fig = exporter.create_figure(ctx)
            # save to zip...
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from .plots import add_stats_to_legend


# ============================================================
# SOLID: Kontener danych - zamiast wielu parametrów (ISP)
# ============================================================

@dataclass
class ChartContext:
    """Kontekst danych potrzebnych do generowania wykresów.
    
    Jedna struktura zamiast wielu parametrów funkcji.
    """
    df_plot: pd.DataFrame
    df_plot_resampled: pd.DataFrame
    rider_weight: float
    cp_input: float
    vt1_watts: float
    vt2_watts: float
    metrics: dict
    smo2_start_sec: Optional[float] = None
    smo2_end_sec: Optional[float] = None
    vent_start_sec: Optional[float] = None
    vent_end_sec: Optional[float] = None
    
    # Wspólny layout dla wszystkich wykresów
    layout_args: dict = None
    
    def __post_init__(self):
        if self.layout_args is None:
            self.layout_args = {
                'template': 'plotly_dark',
                'height': 600,
                'width': 1200,
                'font': {'family': "Inter", 'size': 14},
                'margin': {'l': 50, 'r': 50, 't': 80, 'b': 50},
                'legend': {'font': {'size': 12}}
            }


# ============================================================
# SOLID: Abstrakcja eksportera (OCP)
# ============================================================

class ChartExporter(ABC):
    """Abstrakcyjna klasa bazowa dla eksporterów wykresów.
    
    Nowe wykresy można dodawać tworząc nowe klasy bez modyfikacji
    istniejącego kodu.
    """
    
    @property
    @abstractmethod
    def filename(self) -> str:
        """Nazwa pliku PNG (np. '01_Power.png')."""
        pass
    
    @property
    @abstractmethod
    def title(self) -> str:
        """Tytuł wykresu."""
        pass
    
    @abstractmethod
    def can_export(self, ctx: ChartContext) -> bool:
        """Sprawdza czy dane pozwalają na wygenerowanie wykresu."""
        pass
    
    @abstractmethod
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        """Tworzy wykres Plotly."""
        pass
    
    def export(self, ctx: ChartContext) -> bytes:
        """Eksportuje wykres do PNG."""
        fig = self.create_figure(ctx)
        return fig.to_image(format='png', width=1200, height=600)


# ============================================================
# Registry - automatyczna rejestracja eksporterów
# ============================================================

CHART_REGISTRY: List[ChartExporter] = []


def register_chart(cls):
    """Dekorator do automatycznej rejestracji eksporterów."""
    CHART_REGISTRY.append(cls())
    return cls


# ============================================================
# SOLID: Konkretne implementacje (OCP - rozszerzenia)
# ============================================================

@register_chart
class PowerChartExporter(ChartExporter):
    """Eksporter wykresu mocy."""
    
    @property
    def filename(self) -> str:
        return '01_Power.png'
    
    @property
    def title(self) -> str:
        return '1. Power Profile (W)'
    
    def can_export(self, ctx: ChartContext) -> bool:
        return 'watts_smooth' in ctx.df_plot_resampled.columns
    
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        df = ctx.df_plot_resampled
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['time_min'], 
            y=df['watts_smooth'],
            name='Power', 
            fill='tozeroy', 
            line=dict(color='#00cc96', width=1.5)
        ))
        
        avg_p = df['watts_smooth'].mean()
        max_p = df['watts_smooth'].max()
        norm_p = np.power(np.mean(np.power(df['watts_smooth'], 4)), 0.25)
        
        legend_stats = [
            f"⚡ Avg: {avg_p:.0f} W",
            f"🔥 Max: {max_p:.0f} W",
            f"📈 NP (est): {norm_p:.0f} W",
            f"⚖️ W/kg: {avg_p/ctx.rider_weight:.2f}"
        ]
        add_stats_to_legend(fig, legend_stats)
        
        fig.update_layout(
            title=self.title, 
            xaxis_title='Time (min)', 
            yaxis_title='Power (W)', 
            **ctx.layout_args
        )
        return fig


@register_chart
class HeartRateChartExporter(ChartExporter):
    """Eksporter wykresu tętna."""
    
    @property
    def filename(self) -> str:
        return '02_HeartRate.png'
    
    @property
    def title(self) -> str:
        return '2. Heart Rate (bpm)'
    
    def can_export(self, ctx: ChartContext) -> bool:
        return 'heartrate_smooth' in ctx.df_plot_resampled.columns
    
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        df = ctx.df_plot_resampled
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['time_min'], 
            y=df['heartrate_smooth'],
            name='HR', 
            fill='tozeroy', 
            line=dict(color='#ef553b', width=1.5)
        ))
        
        avg_hr = df['heartrate_smooth'].mean()
        max_hr = df['heartrate_smooth'].max()
        min_hr = df[df['heartrate_smooth'] > 40]['heartrate_smooth'].min()
        
        legend_stats = [
            f"❤️ Avg: {avg_hr:.0f} bpm",
            f"🔥 Max: {max_hr:.0f} bpm",
            f"💤 Min: {min_hr:.0f} bpm"
        ]
        add_stats_to_legend(fig, legend_stats)
        
        fig.update_layout(
            title=self.title, 
            xaxis_title='Time (min)', 
            yaxis_title='HR (bpm)', 
            **ctx.layout_args
        )
        return fig


@register_chart
class SmO2ChartExporter(ChartExporter):
    """Eksporter wykresu SmO2."""
    
    @property
    def filename(self) -> str:
        return '03_SmO2.png'
    
    @property
    def title(self) -> str:
        return '3. Muscle Oxygenation (SmO2)'
    
    def can_export(self, ctx: ChartContext) -> bool:
        return 'smo2_smooth' in ctx.df_plot_resampled.columns
    
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        df = ctx.df_plot_resampled
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['time_min'], 
            y=df['smo2_smooth'],
            name='SmO2', 
            line=dict(color='#ab63fa', width=2)
        ))
        
        avg_smo2 = df['smo2_smooth'].mean()
        min_smo2 = df['smo2_smooth'].min()
        max_smo2 = df['smo2_smooth'].max()
        
        legend_stats = [
            f"📊 Avg: {avg_smo2:.1f}%",
            f"🔻 Min: {min_smo2:.1f}%",
            f"🔺 Max: {max_smo2:.1f}%"
        ]
        add_stats_to_legend(fig, legend_stats)
        
        fig.update_layout(
            title=self.title, 
            xaxis_title='Time (min)', 
            yaxis_title='SmO2 (%)', 
            yaxis=dict(range=[0, 100]),
            **ctx.layout_args
        )
        return fig


@register_chart
class VentilationChartExporter(ChartExporter):
    """Eksporter wykresu wentylacji."""
    
    @property
    def filename(self) -> str:
        return '04_Ventilation_RR.png'
    
    @property
    def title(self) -> str:
        return '4. Ventilation (VE) & Respiratory Rate (RR)'
    
    def can_export(self, ctx: ChartContext) -> bool:
        return 'tymeventilation_smooth' in ctx.df_plot_resampled.columns
    
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        df = ctx.df_plot_resampled
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['time_min'], 
            y=df['tymeventilation_smooth'],
            name='VE', 
            line=dict(color='#ffa15a', width=2)
        ))
        
        legend_stats = []
        avg_ve = df['tymeventilation_smooth'].mean()
        max_ve = df['tymeventilation_smooth'].max()
        legend_stats.append(f"🫁 Avg VE: {avg_ve:.1f} L/min")
        legend_stats.append(f"🔥 Max VE: {max_ve:.1f} L/min")
        
        if 'tymebreathrate_smooth' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time_min'], 
                y=df['tymebreathrate_smooth'],
                name='RR', 
                line=dict(color='#19d3f3', width=2, dash='dot'), 
                yaxis='y2'
            ))
            avg_rr = df['tymebreathrate_smooth'].mean()
            legend_stats.append(f"💨 Avg RR: {avg_rr:.1f} /min")
        
        add_stats_to_legend(fig, legend_stats)
        
        fig.update_layout(
            title=self.title, 
            xaxis_title='Time (min)', 
            yaxis=dict(title='VE (L/min)'),
            yaxis2=dict(title='RR (bpm)', overlaying='y', side='right'),
            **ctx.layout_args
        )
        return fig


@register_chart
class PulsePowerChartExporter(ChartExporter):
    """Eksporter wykresu Pulse Power."""
    
    @property
    def filename(self) -> str:
        return '05_PulsePower.png'
    
    @property
    def title(self) -> str:
        return '5. Pulse Power (Watts / Heart Beat)'
    
    def can_export(self, ctx: ChartContext) -> bool:
        df = ctx.df_plot_resampled
        if 'watts_smooth' not in df.columns or 'heartrate_smooth' not in df.columns:
            return False
        mask = (df['watts_smooth'] > 50) & (df['heartrate_smooth'] > 90)
        return mask.sum() > 10
    
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        df = ctx.df_plot_resampled
        mask = (df['watts_smooth'] > 50) & (df['heartrate_smooth'] > 90)
        df_pp = df[mask].copy()
        
        df_pp['pp'] = df_pp['watts_smooth'] / df_pp['heartrate_smooth']
        df_pp['pp_smooth'] = df_pp['pp'].rolling(window=30, center=True).mean()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_pp['time_min'], 
            y=df_pp['pp_smooth'],
            name='Pulse Power', 
            line=dict(color='#FFD700', width=2)
        ))
        
        slope, intercept, _, _, _ = stats.linregress(df_pp['time_min'], df_pp['pp'])
        trend = intercept + slope * df_pp['time_min']
        fig.add_trace(go.Scatter(
            x=df_pp['time_min'], 
            y=trend, 
            name='Trend', 
            line=dict(color='white', dash='dash')
        ))
        
        avg_eff = df_pp['pp'].mean()
        total_drift = slope * (df_pp['time_min'].iloc[-1] - df_pp['time_min'].iloc[0])
        drift_pct = (total_drift / intercept) * 100 if intercept != 0 else 0
        
        legend_stats = [
            f"🔋 Avg EF: {avg_eff:.2f} W/bpm",
            f"📉 Drift: {drift_pct:.1f}%"
        ]
        add_stats_to_legend(fig, legend_stats)
        
        fig.update_layout(
            title=self.title, 
            xaxis_title='Time (min)', 
            yaxis_title='Efficiency (W/bpm)', 
            **ctx.layout_args
        )
        return fig


@register_chart
class TorqueSmO2ChartExporter(ChartExporter):
    """Eksporter wykresu Torque vs SmO2."""
    
    @property
    def filename(self) -> str:
        return '08_Torque_SmO2.png'
    
    @property
    def title(self) -> str:
        return '8. Mechanical Impact: Torque vs SmO2'
    
    def can_export(self, ctx: ChartContext) -> bool:
        df = ctx.df_plot
        if 'torque' not in df.columns or 'smo2' not in df.columns:
            return False
        df_bins = df.copy()
        df_bins['Torque_Bin'] = (df_bins['torque'] // 2 * 2).astype(int)
        bin_stats = df_bins.groupby('Torque_Bin')['smo2'].agg(['count']).reset_index()
        return (bin_stats['count'] > 10).any()
    
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        df = ctx.df_plot.copy()
        df['Torque_Bin'] = (df['torque'] // 2 * 2).astype(int)
        bin_stats = df.groupby('Torque_Bin')['smo2'].agg(['mean', 'std', 'count']).reset_index()
        bin_stats = bin_stats[bin_stats['count'] > 10]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=bin_stats['Torque_Bin'], 
            y=bin_stats['mean']+bin_stats['std'],
            mode='lines', 
            line=dict(width=0), 
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=bin_stats['Torque_Bin'], 
            y=bin_stats['mean']-bin_stats['std'],
            mode='lines', 
            line=dict(width=0), 
            fill='tonexty', 
            fillcolor='rgba(255,75,75,0.2)', 
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=bin_stats['Torque_Bin'], 
            y=bin_stats['mean'],
            mode='lines+markers', 
            name='Mean SmO2', 
            line=dict(color='#FF4B4B', width=3)
        ))
        
        max_t_idx = bin_stats['Torque_Bin'].idxmax()
        max_t = bin_stats.loc[max_t_idx, 'Torque_Bin']
        smo2_at_max = bin_stats.loc[max_t_idx, 'mean']
        
        legend_stats = [
            f"💪 Max Torque: {max_t:.0f} Nm",
            f"🩸 SmO2 @ Max: {smo2_at_max:.1f}%"
        ]
        add_stats_to_legend(fig, legend_stats)
        
        fig.update_layout(
            title=self.title, 
            xaxis_title='Torque (Nm)', 
            yaxis_title='SmO2 (%)', 
            **ctx.layout_args
        )
        return fig


@register_chart
class SmO2AnalysisChartExporter(ChartExporter):
    """Eksporter wykresu analizy SmO2."""
    
    @property
    def filename(self) -> str:
        return '09_SmO2_Analysis.png'
    
    @property
    def title(self) -> str:
        return '9. SmO2 Kinetics Analysis'
    
    def can_export(self, ctx: ChartContext) -> bool:
        return 'smo2_smooth' in ctx.df_plot_resampled.columns
    
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        df = ctx.df_plot_resampled
        df_full = ctx.df_plot
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['time_min'], 
            y=df['smo2_smooth'],
            name='SmO2 (Full)', 
            line=dict(color='#FF4B4B', width=1.5)
        ))
        
        if 'watts' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time_min'], 
                y=df['watts_smooth'],
                name='Power', 
                line=dict(color='#1f77b4', width=1), 
                opacity=0.3, 
                yaxis='y2'
            ))
        
        s_sec = ctx.smo2_start_sec
        e_sec = ctx.smo2_end_sec
        
        if s_sec is not None and e_sec is not None:
            s_min = s_sec / 60.0
            e_min = e_sec / 60.0
            fig.add_vrect(
                x0=s_min, x1=e_min, 
                fillcolor="green", 
                opacity=0.15, 
                layer="below", 
                line_width=0, 
                annotation_text="ANALYSIS"
            )
            
            mask = (df_full['time'] >= s_sec) & (df_full['time'] <= e_sec)
            df_sel = df_full.loc[mask]
            
            if not df_sel.empty and 'smo2_smooth' in df_sel.columns:
                duration = e_sec - s_sec
                avg_w_sel = df_sel['watts_smooth'].mean() if 'watts_smooth' in df_sel else 0
                avg_s_sel = df_sel['smo2_smooth'].mean()
                min_s_sel = df_sel['smo2_smooth'].min()
                max_s_sel = df_sel['smo2_smooth'].max()
                
                slope, intercept, _, _, _ = stats.linregress(df_sel['time'], df_sel['smo2_smooth'])
                
                x_trend_min = df_sel['time'] / 60.0
                y_trend = intercept + slope * df_sel['time']
                fig.add_trace(go.Scatter(
                    x=x_trend_min, 
                    y=y_trend, 
                    name='Trend', 
                    line=dict(color='yellow', dash='solid', width=3)
                ))
                
                m_dur, s_dur = divmod(int(duration), 60)
                legend_stats = [
                    f"⏱️ Time: {m_dur:02d}:{s_dur:02d}",
                    f"⚡ Avg W: {avg_w_sel:.0f} W",
                    f"📉 Slope: {slope:.4f} %/s",
                    f"📊 Avg SmO2: {avg_s_sel:.1f}%",
                    f"🔻 Min: {min_s_sel:.1f}%",
                    f"🔺 Max: {max_s_sel:.1f}%"
                ]
                add_stats_to_legend(fig, legend_stats)
        
        fig.update_layout(
            title=self.title, 
            xaxis_title='Time (min)', 
            yaxis=dict(title='SmO2 (%)'),
            yaxis2=dict(title='Power (W)', overlaying='y', side='right', showgrid=False),
            **ctx.layout_args
        )
        return fig


@register_chart
class VentAnalysisChartExporter(ChartExporter):
    """Eksporter wykresu analizy wentylacji."""
    
    @property
    def filename(self) -> str:
        return '10_Vent_Analysis.png'
    
    @property
    def title(self) -> str:
        return '10. Ventilation Threshold Analysis'
    
    def can_export(self, ctx: ChartContext) -> bool:
        return 'tymeventilation_smooth' in ctx.df_plot_resampled.columns
    
    def create_figure(self, ctx: ChartContext) -> go.Figure:
        df = ctx.df_plot_resampled
        df_full = ctx.df_plot
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['time_min'], 
            y=df['tymeventilation_smooth'],
            name='VE (Full)', 
            line=dict(color='#ffa15a', width=1.5)
        ))
        
        if 'watts' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time_min'], 
                y=df['watts_smooth'],
                name='Power', 
                line=dict(color='#1f77b4', width=1), 
                opacity=0.3, 
                yaxis='y2'
            ))
        
        s_v_sec = ctx.vent_start_sec
        e_v_sec = ctx.vent_end_sec
        
        if s_v_sec is not None and e_v_sec is not None:
            s_v_min = s_v_sec / 60.0
            e_v_min = e_v_sec / 60.0
            fig.add_vrect(
                x0=s_v_min, x1=e_v_min, 
                fillcolor="orange", 
                opacity=0.15, 
                layer="below", 
                line_width=0, 
                annotation_text="ANALYSIS"
            )
            
            mask_v = (df_full['time'] >= s_v_sec) & (df_full['time'] <= e_v_sec)
            df_v = df_full.loc[mask_v]
            
            if not df_v.empty and 'tymeventilation_smooth' in df_v.columns:
                duration_v = e_v_sec - s_v_sec
                avg_w_v = df_v['watts_smooth'].mean() if 'watts_smooth' in df_v else 0
                avg_ve = df_v['tymeventilation_smooth'].mean()
                min_ve = df_v['tymeventilation_smooth'].min()
                max_ve = df_v['tymeventilation_smooth'].max()
                
                slope_v, intercept_v, _, _, _ = stats.linregress(df_v['time'], df_v['tymeventilation_smooth'])
                
                x_trend_v_min = df_v['time'] / 60.0
                y_trend_v = intercept_v + slope_v * df_v['time']
                fig.add_trace(go.Scatter(
                    x=x_trend_v_min, 
                    y=y_trend_v, 
                    name='Trend', 
                    line=dict(color='white', dash='solid', width=3)
                ))
                
                m_dur_v, s_dur_v = divmod(int(duration_v), 60)
                legend_stats = [
                    f"⏱️ Time: {m_dur_v:02d}:{s_dur_v:02d}",
                    f"⚡ Avg W: {avg_w_v:.0f} W",
                    f"📈 Slope: {slope_v:.4f} L/s",
                    f"🫁 Avg VE: {avg_ve:.1f} L/min",
                    f"🔻 Min: {min_ve:.1f}",
                    f"🔺 Max: {max_ve:.1f}"
                ]
                add_stats_to_legend(fig, legend_stats)
        
        fig.update_layout(
            title=self.title, 
            xaxis_title='Time (min)', 
            yaxis=dict(title='VE (L/min)'),
            yaxis2=dict(title='Power (W)', overlaying='y', side='right', showgrid=False),
            **ctx.layout_args
        )
        return fig
