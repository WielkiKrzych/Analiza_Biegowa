"""
Physio Drift Maps Module.

Provides scatter plots and drift analysis for Power-HR-SmO2 relationships:
- Power vs HR scatter with time coloring and trendline
- Power vs SmO2 scatter
- Constant-power segment detection
- HR and SmO2 drift analysis at constant power
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

import numpy as np
import pandas as pd
from scipy import stats
import plotly.graph_objects as go
import plotly.express as px

logger = logging.getLogger(__name__)


@dataclass
class DriftMetrics:
    """Result of drift analysis at constant power."""
    hr_drift_slope: Optional[float]      # HR slope per minute
    hr_drift_pvalue: Optional[float]     # p-value for HR slope
    smo2_slope: Optional[float]          # SmO2 slope per minute
    smo2_pvalue: Optional[float]         # p-value for SmO2 slope
    correlation_power_hr: Optional[float]
    correlation_power_smo2: Optional[float]
    segment_duration_min: float
    avg_power: float
    
    def to_dict(self) -> Dict:
        return {
            "hr_drift_slope_per_min": round(self.hr_drift_slope, 3) if self.hr_drift_slope else None,
            "hr_drift_pvalue": round(self.hr_drift_pvalue, 4) if self.hr_drift_pvalue else None,
            "smo2_slope_per_min": round(self.smo2_slope, 3) if self.smo2_slope else None,
            "smo2_pvalue": round(self.smo2_pvalue, 4) if self.smo2_pvalue else None,
            "correlation_power_hr": round(self.correlation_power_hr, 3) if self.correlation_power_hr else None,
            "correlation_power_smo2": round(self.correlation_power_smo2, 3) if self.correlation_power_smo2 else None,
            "segment_duration_min": round(self.segment_duration_min, 1),
            "avg_power_watts": round(self.avg_power, 0)
        }


# ============================================================
# Scatter Plot Functions
# ============================================================

def scatter_power_hr(
    df: pd.DataFrame,
    title: str = "Power vs Heart Rate"
) -> Optional[go.Figure]:
    """Create Power vs HR scatter with time coloring and trendline.
    
    Args:
        df: DataFrame with 'watts' and 'heartrate' (or 'hr') columns
        title: Chart title
        
    Returns:
        Plotly Figure or None if data missing
    """
    # Detect HR column
    hr_col = None
    for col in ['heartrate', 'hr', 'heart_rate', 'HeartRate']:
        if col in df.columns:
            hr_col = col
            break
            
    if 'watts' not in df.columns or hr_col is None:
        logger.warning(f"Missing watts or HR columns for scatter_power_hr. Found: {df.columns.tolist()}")
        return None
    
    # Prepare data
    plot_df = df[['watts', hr_col]].dropna()
    if len(plot_df) < 10:
        return None
    
    # Add time index for coloring
    plot_df = plot_df.copy()
    plot_df['time_min'] = np.arange(len(plot_df)) / 60
    
    # Calculate correlation
    corr = plot_df['watts'].corr(plot_df[hr_col])
    
    # Create scatter
    fig = px.scatter(
        plot_df,
        x='watts',
        y=hr_col,
        color='time_min',
        color_continuous_scale='Viridis',
        labels={'watts': 'Moc [W]', hr_col: 'HR [bpm]', 'time_min': 'Czas [min]'},
        hover_data={
            'watts': ':.0f',
            hr_col: ':.0f',
            'time_min': ':.0f'
        },
        title=f"{title} (r = {corr:.2f})"
    )
    
    # Add trendline
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        plot_df['watts'], plot_df[hr_col]
    )
    x_line = np.array([plot_df['watts'].min(), plot_df['watts'].max()])
    y_line = slope * x_line + intercept
    
    fig.add_trace(go.Scatter(
        x=x_line,
        y=y_line,
        mode='lines',
        name=f'Trend (slope={slope:.2f})',
        line=dict(color='red', width=2, dash='dash')
    ))
    
    fig.update_layout(
        template='plotly_dark',
        height=450,
        margin=dict(l=20, r=20, t=50, b=20),
        coloraxis_colorbar=dict(
            title="Czas [min]",
            tickformat=".0f"
        )
    )
    
    return fig


def scatter_power_smo2(
    df: pd.DataFrame,
    title: str = "Power vs SmO₂"
) -> Optional[go.Figure]:
    """Create Power vs SmO2 scatter with time coloring.
    
    Args:
        df: DataFrame with 'watts' and 'smo2' columns
        title: Chart title
        
    Returns:
        Plotly Figure or None if SmO2 data missing (graceful degradation)
    """
    if 'watts' not in df.columns:
        return None
    
    # Check for SmO2 column variants
    smo2_col = None
    for col in ['smo2', 'SmO2', 'muscle_oxygen']:
        if col in df.columns:
            smo2_col = col
            break
    
    if smo2_col is None:
        logger.info("SmO2 data not available - graceful degradation")
        return None
    
    # Prepare data
    plot_df = df[['watts', smo2_col]].dropna()
    if len(plot_df) < 10:
        return None
    
    plot_df = plot_df.copy()
    plot_df['time_min'] = np.arange(len(plot_df)) / 60
    
    # Calculate correlation
    corr = plot_df['watts'].corr(plot_df[smo2_col])
    
    # Create scatter
    fig = px.scatter(
        plot_df,
        x='watts',
        y=smo2_col,
        color='time_min',
        color_continuous_scale='Plasma',
        labels={'watts': 'Moc [W]', smo2_col: 'SmO₂ [%]', 'time_min': 'Czas [min]'},
        hover_data={
            'watts': ':.0f',
            smo2_col: ':.1f',
            'time_min': ':.0f'
        },
        title=f"{title} (r = {corr:.2f})"
    )
    
    # Add trendline
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        plot_df['watts'], plot_df[smo2_col]
    )
    x_line = np.array([plot_df['watts'].min(), plot_df['watts'].max()])
    y_line = slope * x_line + intercept
    
    fig.add_trace(go.Scatter(
        x=x_line,
        y=y_line,
        mode='lines',
        name=f'Trend (slope={slope:.3f})',
        line=dict(color='cyan', width=2, dash='dash')
    ))
    
    fig.update_layout(
        template='plotly_dark',
        height=450,
        margin=dict(l=20, r=20, t=50, b=20),
        coloraxis_colorbar=dict(
            title="Czas [min]",
            tickformat=".0f"
        )
    )
    
    return fig


# ============================================================
# Constant Power Segment Detection
# ============================================================

def detect_constant_power_segments(
    df: pd.DataFrame,
    tolerance_pct: float = 5.0,
    min_duration_sec: int = 120
) -> List[Tuple[int, int, float]]:
    """Find segments where power is stable within tolerance.
    
    Args:
        df: DataFrame with 'watts' column
        tolerance_pct: Percentage tolerance around median power
        min_duration_sec: Minimum segment duration in seconds
        
    Returns:
        List of (start_idx, end_idx, avg_power) tuples
    """
    if 'watts' not in df.columns:
        return []
    
    watts = df['watts'].fillna(0).values
    n = len(watts)
    
    if n < min_duration_sec:
        return []
    
    segments = []
    
    # Sliding window approach
    window_size = min_duration_sec
    
    i = 0
    while i < n - window_size:
        window = watts[i:i + window_size]
        median_power = np.median(window)
        
        if median_power < 50:  # Skip very low power
            i += window_size // 2
            continue
        
        # Check if window is within tolerance
        lower = median_power * (1 - tolerance_pct / 100)
        upper = median_power * (1 + tolerance_pct / 100)
        
        if np.all((window >= lower) & (window <= upper)):
            # Extend segment as far as possible
            end_idx = i + window_size
            while end_idx < n:
                if lower <= watts[end_idx] <= upper:
                    end_idx += 1
                else:
                    break
            
            avg_power = np.mean(watts[i:end_idx])
            segments.append((i, end_idx, avg_power))
            i = end_idx
        else:
            i += 1
    
    return segments


def trend_at_constant_power(
    df: pd.DataFrame,
    power_target: float,
    tolerance_pct: float = 5.0,
    min_duration_sec: int = 120
) -> Tuple[Optional[go.Figure], Optional[DriftMetrics]]:
    """Extract segment at target power and compute HR/SmO2 drift.
    
    Args:
        df: DataFrame with watts, hr, and optionally smo2
        power_target: Target power level in watts
        tolerance_pct: Tolerance around target power
        min_duration_sec: Minimum segment duration
        
    Returns:
        Tuple of (Plotly Figure, DriftMetrics)
    """
    # Detect HR column
    hr_col = None
    for col in ['heartrate', 'hr', 'heart_rate']:
        if col in df.columns:
            hr_col = col
            break

    if 'watts' not in df.columns or hr_col is None:
        return None, None
    
    # Find matching segment
    lower = power_target * (1 - tolerance_pct / 100)
    upper = power_target * (1 + tolerance_pct / 100)
    
    mask = (df['watts'] >= lower) & (df['watts'] <= upper)
    segment = df[mask].copy()
    
    if len(segment) < min_duration_sec:
        return None, None
    
    # Create time axis in minutes
    segment = segment.reset_index(drop=True)
    segment['time_min'] = segment.index / 60
    
    # Calculate HR drift
    hr_slope, hr_intercept, hr_r, hr_p, hr_se = stats.linregress(
        segment['time_min'], segment[hr_col]
    )
    
    # Calculate SmO2 drift (if available)
    smo2_col = None
    for col in ['smo2', 'SmO2', 'muscle_oxygen']:
        if col in segment.columns:
            smo2_col = col
            break
    
    smo2_slope = None
    smo2_p = None
    corr_power_smo2 = None
    
    if smo2_col and segment[smo2_col].notna().sum() > 10:
        smo2_clean = segment.dropna(subset=[smo2_col])
        smo2_slope, smo2_int, smo2_r, smo2_p, smo2_se = stats.linregress(
            smo2_clean['time_min'], smo2_clean[smo2_col]
        )
        corr_power_smo2 = df['watts'].corr(df[smo2_col]) if smo2_col in df.columns else None
    
    # Create figure
    fig = go.Figure()
    
    # HR trace (smoothed)
    segment[f'{hr_col}_smooth'] = segment[hr_col].rolling(window=30, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=segment['time_min'],
        y=segment[f'{hr_col}_smooth'],
        mode='lines',
        name='HR (30s avg)',
        line=dict(color='#FF6B6B', width=2),
        hovertemplate='%{y:.1f} bpm'
    ))
    
    # HR trendline
    hr_trend = hr_slope * segment['time_min'] + hr_intercept
    fig.add_trace(go.Scatter(
        x=segment['time_min'],
        y=hr_trend,
        mode='lines',
        name=f'Trend HR: {hr_slope:.2f}',
        line=dict(color='#FF6B6B', width=2, dash='dash'),
        hovertemplate='%{y:.1f} bpm'
    ))
    
    # SmO2 trace (smoothed)
    if smo2_col and smo2_slope is not None:
        segment[f'{smo2_col}_smooth'] = segment[smo2_col].rolling(window=30, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=segment['time_min'],
            y=segment[f'{smo2_col}_smooth'],
            mode='lines',
            name='SmO₂ (30s avg)',
            line=dict(color='#4ECDC4', width=2),
            yaxis='y2',
            hovertemplate='%{y:.1f} %'
        ))
        
        # SmO2 trendline
        smo2_trend = smo2_slope * segment['time_min'] + smo2_int
        fig.add_trace(go.Scatter(
            x=segment['time_min'],
            y=smo2_trend,
            mode='lines',
            name=f'Trend SmO₂: {smo2_slope:.2f}',
            line=dict(color='#4ECDC4', width=2, dash='dash'),
            yaxis='y2',
            hovertemplate='Trend: %{y:.1f} %'
        ))
    
    fig.update_layout(
        template='plotly_dark',
        title=f'Drift Analysis @ {power_target:.0f}W (±{tolerance_pct}%)',
        xaxis=dict(
            title='Czas [min]',
            tickformat='.0f',
            hoverformat='.0f'
        ),
        yaxis=dict(title='HR [bpm]', color='#FF6B6B'),
        yaxis2=dict(
            title='SmO₂ [%]',
            color='#4ECDC4',
            overlaying='y',
            side='right'
        ) if smo2_col else None,
        hovermode="x unified",
        height=400,
        margin=dict(l=20, r=60, t=50, b=20),
        legend=dict(orientation='h', yanchor='bottom', y=1.02)
    )
    
    # Precise axes formatting
    fig.update_yaxes(title_text="HR [bpm]", tickformat=".0f", color='#FF6B6B', side='left')
    if smo2_col:
        fig.update_layout(yaxis2=dict(
            title='SmO₂ [%]',
            tickformat=".1f",
            color='#4ECDC4',
            overlaying='y',
            side='right',
            anchor='x'
        ))
    
    # Calculate correlations
    # Detect HR column again for safety
    hr_col = next((c for c in ['heartrate', 'hr', 'heart_rate'] if c in df.columns), 'hr')
    corr_power_hr = df['watts'].corr(df[hr_col]) if hr_col in df.columns else None
    
    metrics = DriftMetrics(
        hr_drift_slope=hr_slope,
        hr_drift_pvalue=hr_p,
        smo2_slope=smo2_slope,
        smo2_pvalue=smo2_p,
        correlation_power_hr=corr_power_hr,
        correlation_power_smo2=corr_power_smo2,
        segment_duration_min=len(segment) / 60,
        avg_power=segment['watts'].mean()
    )
    
    return fig, metrics


def calculate_drift_metrics(df: pd.DataFrame) -> Dict:
    """Calculate overall drift metrics for the session.
    
    Args:
        df: DataFrame with watts, hr, and optionally smo2
        
    Returns:
        Dict with drift metrics
    """
    result = {
        "hr_drift_slope": None,
        "smo2_slope": None,
        "correlation_power_hr": None,
        "correlation_power_smo2": None
    }
    
    # Detect HR column
    hr_col = None
    for col in ['heartrate', 'hr', 'heart_rate', 'HeartRate']:
        if col in df.columns:
            hr_col = col
            break

    if 'watts' not in df.columns or hr_col is None:
        return result
    
    # Overall correlations
    result["correlation_power_hr"] = round(df['watts'].corr(df[hr_col]), 3)
    
    # SmO2 correlation if available
    for col in ['smo2', 'SmO2', 'muscle_oxygen']:
        if col in df.columns:
            result["correlation_power_smo2"] = round(df['watts'].corr(df[col]), 3)
            break
    
    # Find longest constant-power segment for drift analysis
    segments = detect_constant_power_segments(df, tolerance_pct=10, min_duration_sec=300)
    
    if segments:
        # Use longest segment
        longest = max(segments, key=lambda x: x[1] - x[0])
        start, end, avg_power = longest
        
        segment = df.iloc[start:end].copy()
        segment = segment.reset_index(drop=True)
        segment['time_min'] = segment.index / 60
        
        # HR drift
        if len(segment) > 30:
            slope, _, _, _, _ = stats.linregress(segment['time_min'], segment[hr_col])
            result["hr_drift_slope"] = round(slope, 3)
        
        # SmO2 drift
        for col in ['smo2', 'SmO2', 'muscle_oxygen']:
            if col in segment.columns and segment[col].notna().sum() > 30:
                slope, _, _, _, _ = stats.linregress(
                    segment.dropna(subset=[col])['time_min'],
                    segment.dropna(subset=[col])[col]
                )
                result["smo2_slope"] = round(slope, 3)
                break
    
    return result
