"""
Power-Duration Curve & Critical Power Model Module.

Provides functions for:
- Computing Mean Maximal Power (MMP) for various durations
- Fitting Critical Power (CP) model using non-linear regression
- Detecting Personal Records (PRs)
- Plotting log-log Power-Duration Curves with overlays
- Exporting results to JSON/CSV/PNG
"""
from typing import Dict, List, Optional
import json
import logging
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


# ============================================================
# Constants
# ============================================================

# Standard durations for PDC analysis (1s to 60min)
DEFAULT_DURATIONS = [
    1, 2, 3, 5, 10, 15, 20, 30, 45, 60,           # Short (1s-1min)
    90, 120, 180, 240, 300,                        # Medium (1.5-5min)
    360, 420, 480, 600, 720, 900,                  # Long (6-15min)
    1200, 1500, 1800, 2400, 3000, 3600             # Very long (20-60min)
]


@dataclass
class CPModelResult:
    """Result of Critical Power model fitting."""
    cp: float               # Critical Power [W]
    w_prime: float          # W' anaerobic capacity [J]
    rmse: float             # Root Mean Square Error
    r_squared: float        # R² goodness of fit
    durations_used: List[int]  # Durations used for fitting


@dataclass
class PersonalRecord:
    """Personal Record data structure."""
    duration: int           # Duration in seconds
    power: float            # Power in watts
    timestamp: Optional[str] = None  # When it was achieved


# ============================================================
# Core Functions
# ============================================================

def interpolate_to_1hz(
    power_series: pd.Series,
    time_series: Optional[pd.Series] = None
) -> pd.Series:
    """Interpolate power data to 1Hz if needed.
    
    Args:
        power_series: Raw power values
        time_series: Timestamps (optional, assumes 1Hz if not provided)
        
    Returns:
        Power series at 1Hz sampling rate
    """
    if time_series is None or len(time_series) == 0:
        return power_series.fillna(0)
    
    # Check if already 1Hz
    time_diff = np.diff(time_series.values)
    median_diff = np.median(time_diff) if len(time_diff) > 0 else 1.0
    
    if 0.9 <= median_diff <= 1.1:
        return power_series.fillna(0)
    
    # Create 1Hz time index
    start_time = time_series.iloc[0]
    end_time = time_series.iloc[-1]
    new_times = np.arange(start_time, end_time + 1, 1.0)
    
    # Interpolate
    interpolated = np.interp(new_times, time_series.values, power_series.fillna(0).values)
    
    return pd.Series(interpolated)


def compute_max_mean_power(
    power_series: pd.Series,
    windows_seconds: Optional[List[int]] = None
) -> Dict[int, float]:
    """Compute Maximum Mean Power for a list of durations.
    
    Uses rolling mean and max to find the best average power 
    achievable for each duration window.
    
    Args:
        power_series: Power values at 1Hz
        windows_seconds: List of durations in seconds (default: DEFAULT_DURATIONS)
        
    Returns:
        Dict mapping duration (seconds) to max mean power (watts)
    """
    if windows_seconds is None:
        windows_seconds = DEFAULT_DURATIONS
    
    power = power_series.fillna(0).values
    n = len(power)
    
    results = {}
    
    for window in windows_seconds:
        if n < window:
            results[window] = None
            continue
        
        # Compute rolling mean using pandas for efficiency
        rolling_mean = pd.Series(power).rolling(
            window=window, min_periods=window
        ).mean()
        
        max_power = rolling_mean.max()
        
        if pd.notna(max_power):
            results[window] = float(max_power)
        else:
            results[window] = None
    
    return results


def _cp_model(t: np.ndarray, w_prime: float, cp: float) -> np.ndarray:
    """Hyperbolic Critical Power model: P(t) = W'/t + CP.
    
    Args:
        t: Time/duration in seconds
        w_prime: Anaerobic work capacity (W') in Joules
        cp: Critical Power in Watts
        
    Returns:
        Predicted power at each duration
    """
    return w_prime / t + cp


def fit_critical_power(
    durations: List[int],
    max_mean_powers: List[float],
    min_duration: int = 120,
    max_duration: int = 1200
) -> CPModelResult:
    """Fit Critical Power model using non-linear regression.
    
    Uses scipy.optimize.curve_fit to fit the hyperbolic model:
    P(t) = W'/t + CP
    
    Only uses data points between min_duration and max_duration
    for more accurate fitting (avoids neuromuscular and slow-component effects).
    
    Args:
        durations: List of durations in seconds
        max_mean_powers: Corresponding MMP values in watts
        min_duration: Minimum duration for fitting (default 2min)
        max_duration: Maximum duration for fitting (default 20min)
        
    Returns:
        CPModelResult with CP, W', RMSE, and R²
        
    Raises:
        ValueError: If fitting fails or produces invalid parameters
    """
    # Filter data for fitting range
    valid_data = [
        (d, p) for d, p in zip(durations, max_mean_powers)
        if p is not None and min_duration <= d <= max_duration
    ]
    
    if len(valid_data) < 3:
        raise ValueError(f"Need at least 3 data points for fitting, got {len(valid_data)}")
    
    fit_durations = np.array([d for d, _ in valid_data], dtype=float)
    fit_powers = np.array([p for _, p in valid_data], dtype=float)
    
    # Initial guesses based on data
    # CP ~ power at longest duration
    # W' ~ (P_short - P_long) * duration_short
    cp_init = fit_powers[-1]  # Power at longest duration
    w_prime_init = (fit_powers[0] - fit_powers[-1]) * fit_durations[0]
    
    # Bounds: CP > 0, W' > 0
    bounds = ([0, 0], [100000, 1000])  # W' in Joules, CP in Watts
    
    try:
        popt, pcov = curve_fit(
            _cp_model,
            fit_durations,
            fit_powers,
            p0=[w_prime_init, cp_init],
            bounds=bounds,
            maxfev=5000
        )
        
        w_prime, cp = popt
        
        # Calculate RMSE
        predicted = _cp_model(fit_durations, w_prime, cp)
        residuals = fit_powers - predicted
        rmse = np.sqrt(np.mean(residuals**2))
        
        # Calculate R²
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((fit_powers - np.mean(fit_powers))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        # Validate results
        if cp <= 0 or w_prime <= 0:
            raise ValueError(f"Invalid model parameters: CP={cp}, W'={w_prime}")
        
        return CPModelResult(
            cp=float(cp),
            w_prime=float(w_prime),
            rmse=float(rmse),
            r_squared=float(r_squared),
            durations_used=list(map(int, fit_durations))
        )
        
    except Exception as e:
        logger.error(f"CP model fitting failed: {e}")
        raise ValueError(f"Failed to fit Critical Power model: {e}")


def detect_personal_records(
    current_pdc: Dict[int, float],
    history_pdc: Dict[int, float]
) -> List[PersonalRecord]:
    """Detect new Personal Records by comparing current session to history.
    
    Args:
        current_pdc: Current session's power-duration curve
        history_pdc: Historical best power-duration values
        
    Returns:
        List of PersonalRecord objects for new PRs
    """
    prs = []
    
    for duration, current_power in current_pdc.items():
        if current_power is None:
            continue
            
        historical_best = history_pdc.get(duration)
        
        # PR if no history or current beats history
        if historical_best is None or current_power > historical_best:
            prs.append(PersonalRecord(
                duration=duration,
                power=current_power,
                timestamp=pd.Timestamp.now().isoformat()
            ))
    
    return prs


def compute_historical_pdc(
    sessions: List[Dict[int, float]],
    method: str = "max"
) -> Dict[int, float]:
    """Compute historical PDC from multiple sessions.
    
    Args:
        sessions: List of PDC dicts from historical sessions
        method: Aggregation method ("max", "median", "mean")
        
    Returns:
        Aggregated PDC dict
    """
    if not sessions:
        return {}
    
    # Collect all durations
    all_durations = set()
    for session in sessions:
        all_durations.update(session.keys())
    
    result = {}
    for duration in all_durations:
        values = [s.get(duration) for s in sessions if s.get(duration) is not None]
        
        if not values:
            result[duration] = None
        elif method == "max":
            result[duration] = max(values)
        elif method == "median":
            result[duration] = float(np.median(values))
        elif method == "mean":
            result[duration] = float(np.mean(values))
        else:
            result[duration] = max(values)
    
    return result


def plot_power_duration(
    current_pdc: Dict[int, float],
    cp_model: Optional[CPModelResult] = None,
    history_30d: Optional[Dict[int, float]] = None,
    history_90d: Optional[Dict[int, float]] = None,
    personal_records: Optional[List[PersonalRecord]] = None,
    title: str = "Power-Duration Curve"
) -> go.Figure:
    """Create log-log Power-Duration Curve plot with overlays.
    
    Args:
        current_pdc: Current session PDC
        cp_model: Fitted CP model (optional)
        history_30d: 30-day historical best (optional)
        history_90d: 90-day historical best (optional)
        personal_records: List of new PRs to highlight (optional)
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    # Filter valid data points
    valid_current = {d: p for d, p in current_pdc.items() if p is not None}
    durations = sorted(valid_current.keys())
    powers = [valid_current[d] for d in durations]
    
    # Current session curve
    fig.add_trace(go.Scatter(
        x=durations,
        y=powers,
        mode='lines+markers',
        name='Dzisiaj',
        line=dict(color='#FF6B35', width=3),
        marker=dict(size=8, color='#FF6B35'),
        hovertemplate='P: <b>%{y:.0f} W</b><extra></extra>'
    ))
    
    # Historical overlays
    if history_30d:
        valid_30d = {d: p for d, p in history_30d.items() if p is not None}
        d30 = sorted(valid_30d.keys())
        p30 = [valid_30d[d] for d in d30]
        fig.add_trace(go.Scatter(
            x=d30,
            y=p30,
            mode='lines',
            name='Max 30 dni',
            line=dict(color='#4ECDC4', width=2, dash='dash'),
            opacity=0.7,
            hovertemplate='P: <b>%{y:.0f} W</b> (30d)<extra></extra>'
        ))
    
    if history_90d:
        valid_90d = {d: p for d, p in history_90d.items() if p is not None}
        d90 = sorted(valid_90d.keys())
        p90 = [valid_90d[d] for d in d90]
        fig.add_trace(go.Scatter(
            x=d90,
            y=p90,
            mode='lines',
            name='Max 90 dni',
            line=dict(color='#95E1D3', width=2, dash='dot'),
            opacity=0.6,
            hovertemplate='P: <b>%{y:.0f} W</b> (90d)<extra></extra>'
        ))
    
    # CP model fit curve
    if cp_model and cp_model.cp > 0:
        model_durations = np.logspace(np.log10(30), np.log10(3600), 100)
        model_powers = _cp_model(model_durations, cp_model.w_prime, cp_model.cp)
        
        fig.add_trace(go.Scatter(
            x=model_durations,
            y=model_powers,
            mode='lines',
            name=f'Model CP (CP={cp_model.cp:.0f}W, W\'={cp_model.w_prime/1000:.1f}kJ)',
            line=dict(color='#2D3436', width=2, dash='dashdot'),
            hovertemplate='Model: <b>%{y:.0f} W</b><extra></extra>'
        ))
        
        # Add CP horizontal line
        fig.add_hline(
            y=cp_model.cp,
            line_dash="solid",
            line_color="rgba(45, 52, 54, 0.5)",
            annotation_text=f"CP = {cp_model.cp:.0f}W",
            annotation_position="right",
            annotation_font=dict(size=10, color="rgba(45, 52, 54, 0.8)")
        )
    
    # PR markers
    if personal_records:
        pr_durations = [pr.duration for pr in personal_records]
        pr_powers = [pr.power for pr in personal_records]
        
        fig.add_trace(go.Scatter(
            x=pr_durations,
            y=pr_powers,
            mode='markers',
            name='🏆 Nowe Rekordy',
            marker=dict(
                size=15,
                color='gold',
                symbol='star',
                line=dict(color='#FF6B35', width=2)
            ),
            hovertemplate='🏆 PR: <b>%{y:.0f} W</b><extra></extra>'
        ))
    
    # Layout with log-log scale
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis=dict(
            title='Czas (sekundy)',
            type='log',
            tickvals=[1, 2, 5, 10, 30, 60, 120, 300, 600, 1200, 1800, 3600],
            ticktext=['1s', '2s', '5s', '10s', '30s', '1m', '2m', '5m', '10m', '20m', '30m', '1h'],
            tickangle=-45,
            hoverformat='.0f',
            gridcolor='rgba(0,0,0,0.1)'
        ),
        yaxis=dict(
            title='Moc (W)',
            type='log',
            tickformat='.0f',
            gridcolor='rgba(0,0,0,0.1)'
        ),
        template='plotly_white',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5
        ),
        hovermode='x unified'
    )
    
    return fig


# ============================================================
# Export Functions
# ============================================================

def export_model_json(
    cp_model: CPModelResult,
    output_path: str
) -> str:
    """Export CP model parameters to JSON file.
    
    Args:
        cp_model: CPModelResult from fitting
        output_path: Path for output JSON file
        
    Returns:
        Path to the created file
    """
    data = {
        "CP": round(cp_model.cp, 1),
        "W_prime": round(cp_model.w_prime, 0),
        "W_prime_kJ": round(cp_model.w_prime / 1000, 2),
        "RMSE": round(cp_model.rmse, 2),
        "R_squared": round(cp_model.r_squared, 4),
        "durations_used": cp_model.durations_used
    }
    
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Exported CP model to {path}")
    return str(path)


def export_pr_csv(
    personal_records: List[PersonalRecord],
    output_path: str
) -> str:
    """Export Personal Records to CSV file.
    
    Args:
        personal_records: List of PR objects
        output_path: Path for output CSV file
        
    Returns:
        Path to the created file
    """
    data = [
        {
            "duration_seconds": pr.duration,
            "duration_formatted": _format_duration(pr.duration),
            "power_watts": pr.power,
            "timestamp": pr.timestamp
        }
        for pr in personal_records
    ]
    
    df = pd.DataFrame(data)
    
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(path, index=False)
    
    logger.info(f"Exported {len(personal_records)} PRs to {path}")
    return str(path)


def export_chart_png(fig: go.Figure, output_path: str) -> str:
    """Export Plotly figure to PNG file.
    
    Args:
        fig: Plotly Figure object
        output_path: Path for output PNG file
        
    Returns:
        Path to the created file
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    fig.write_image(str(path), width=1200, height=700, scale=2)
    
    logger.info(f"Exported chart to {path}")
    return str(path)


def _format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}min{secs}s" if secs else f"{mins}min"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h{mins}min" if mins else f"{hours}h"
