"""
Physio Drift Maps Module.

Provides scatter plots and drift analysis for Pace-HR-SmO2 relationships:
- Pace vs HR scatter with time coloring and trendline
- Pace vs SmO2 scatter
- Constant-pace segment detection
- HR and SmO2 drift analysis at constant pace
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

logger = logging.getLogger(__name__)


def _sec_to_min(pace_sec: float) -> float:
    """Convert pace from sec/km to min/km for display."""
    return pace_sec / 60.0 if pace_sec and pace_sec > 0 else 0


@dataclass
class DriftMetrics:
    """Result of drift analysis at constant pace."""

    hr_drift_slope: Optional[float]  # HR slope per minute
    hr_drift_pvalue: Optional[float]  # p-value for HR slope
    smo2_slope: Optional[float]  # SmO2 slope per minute
    smo2_pvalue: Optional[float]  # p-value for SmO2 slope
    correlation_pace_hr: Optional[float]
    correlation_pace_smo2: Optional[float]
    segment_duration_min: float
    avg_pace: float

    def to_dict(self) -> Dict:
        avg_pace_min = _sec_to_min(self.avg_pace)
        return {
            "hr_drift_slope_per_min": round(self.hr_drift_slope, 3)
            if self.hr_drift_slope
            else None,
            "hr_drift_pvalue": round(self.hr_drift_pvalue, 4) if self.hr_drift_pvalue else None,
            "smo2_slope_per_min": round(self.smo2_slope, 3) if self.smo2_slope else None,
            "smo2_pvalue": round(self.smo2_pvalue, 4) if self.smo2_pvalue else None,
            "correlation_pace_hr": round(self.correlation_pace_hr, 3)
            if self.correlation_pace_hr
            else None,
            "correlation_pace_smo2": round(self.correlation_pace_smo2, 3)
            if self.correlation_pace_smo2
            else None,
            "segment_duration_min": round(self.segment_duration_min, 1),
            "avg_pace_min_per_km": round(avg_pace_min, 2),
        }


# ============================================================
# Scatter Plot Functions
# ============================================================


def scatter_pace_hr(df: pd.DataFrame, title: str = "Pace vs Heart Rate") -> Optional[go.Figure]:
    """Create Pace vs HR scatter with time coloring and trendline.

    Args:
        df: DataFrame with 'pace' and 'heartrate' (or 'hr') columns
        title: Chart title

    Returns:
        Plotly Figure or None if data missing
    """
    # Detect HR column
    hr_col = None
    for col in ["heartrate", "hr", "heart_rate", "HeartRate"]:
        if col in df.columns:
            hr_col = col
            break

    # Detect pace column
    pace_col = None
    for col in ["pace", "pace_sec_per_km", "tempo"]:
        if col in df.columns:
            pace_col = col
            break

    if pace_col is None or hr_col is None:
        logger.warning(
            f"Missing pace or HR columns for scatter_pace_hr. Found: {df.columns.tolist()}"
        )
        return None

    # Prepare data
    plot_df = df[[pace_col, hr_col]].dropna()
    if len(plot_df) < 10:
        return None

    # Filter valid pace data and convert to min/km
    plot_df = plot_df[(plot_df[pace_col] > 0) & (plot_df[pace_col] < 1200)].copy()
    plot_df["pace_min"] = plot_df[pace_col] / 60.0

    # Add time index for coloring
    plot_df["time_min"] = np.arange(len(plot_df)) / 60

    # Calculate correlation
    corr = plot_df["pace_min"].corr(plot_df[hr_col])

    # Create scatter
    fig = px.scatter(
        plot_df,
        x="pace_min",
        y=hr_col,
        color="time_min",
        color_continuous_scale="Viridis",
        labels={"pace_min": "Tempo [min/km]", hr_col: "HR [bpm]", "time_min": "Czas [hh:mm:ss]"},
        hover_data={"pace_min": ":.2f", hr_col: ":.0f", "time_min": ":.0f"},
        title=f"{title} (r = {corr:.2f})",
    )

    # Add trendline
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        plot_df["pace_min"], plot_df[hr_col]
    )
    x_line = np.array([plot_df["pace_min"].min(), plot_df["pace_min"].max()])
    y_line = slope * x_line + intercept

    fig.add_trace(
        go.Scatter(
            x=x_line,
            y=y_line,
            mode="lines",
            name=f"Trend (slope={slope:.2f})",
            line=dict(color="red", width=2, dash="dash"),
        )
    )

    # Invert x-axis (lower pace = faster = better)
    fig.update_xaxes(autorange="reversed")

    fig.update_layout(
        template="plotly_dark",
        height=450,
        margin=dict(l=20, r=20, t=50, b=20),
        coloraxis_colorbar=dict(title="Czas [hh:mm:ss]", tickformat=".0f"),
    )

    return fig


def scatter_pace_smo2(df: pd.DataFrame, title: str = "Pace vs SmO₂") -> Optional[go.Figure]:
    """Create Pace vs SmO2 scatter with time coloring.

    Args:
        df: DataFrame with 'pace' and 'smo2' columns
        title: Chart title

    Returns:
        Plotly Figure or None if SmO2 data missing (graceful degradation)
    """
    # Detect pace column
    pace_col = None
    for col in ["pace", "pace_sec_per_km", "tempo"]:
        if col in df.columns:
            pace_col = col
            break

    if pace_col is None:
        return None

    # Check for SmO2 column variants
    smo2_col = None
    for col in ["smo2", "SmO2", "muscle_oxygen"]:
        if col in df.columns:
            smo2_col = col
            break

    if smo2_col is None:
        logger.info("SmO2 data not available - graceful degradation")
        return None

    # Prepare data
    plot_df = df[[pace_col, smo2_col]].dropna()
    if len(plot_df) < 10:
        return None

    # Filter valid pace data and convert to min/km
    plot_df = plot_df[(plot_df[pace_col] > 0) & (plot_df[pace_col] < 1200)].copy()
    plot_df["pace_min"] = plot_df[pace_col] / 60.0

    # Add time index for coloring
    plot_df["time_min"] = np.arange(len(plot_df)) / 60

    # Calculate correlation
    corr = plot_df["pace_min"].corr(plot_df[smo2_col])

    # Create scatter
    fig = px.scatter(
        plot_df,
        x="pace_min",
        y=smo2_col,
        color="time_min",
        color_continuous_scale="Plasma",
        labels={"pace_min": "Tempo [min/km]", smo2_col: "SmO₂ [%]", "time_min": "Czas [hh:mm:ss]"},
        hover_data={"pace_min": ":.2f", smo2_col: ":.1f", "time_min": ":.0f"},
        title=f"{title} (r = {corr:.2f})",
    )

    # Add trendline
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        plot_df["pace_min"], plot_df[smo2_col]
    )
    x_line = np.array([plot_df["pace_min"].min(), plot_df["pace_min"].max()])
    y_line = slope * x_line + intercept

    fig.add_trace(
        go.Scatter(
            x=x_line,
            y=y_line,
            mode="lines",
            name=f"Trend (slope={slope:.3f})",
            line=dict(color="cyan", width=2, dash="dash"),
        )
    )

    # Invert x-axis (lower pace = faster = better)
    fig.update_xaxes(autorange="reversed")

    fig.update_layout(
        template="plotly_dark",
        height=450,
        margin=dict(l=20, r=20, t=50, b=20),
        coloraxis_colorbar=dict(title="Czas [hh:mm:ss]", tickformat=".0f"),
    )

    return fig


# ============================================================
# Legacy Power-based Functions (kept for backwards compatibility)
# ============================================================


def scatter_power_hr(df: pd.DataFrame, title: str = "Power vs Heart Rate") -> Optional[go.Figure]:
    """Legacy function - redirects to pace-based analysis."""
    return scatter_pace_hr(df, title)


def scatter_power_smo2(df: pd.DataFrame, title: str = "Power vs SmO₂") -> Optional[go.Figure]:
    """Legacy function - redirects to pace-based analysis."""
    return scatter_pace_smo2(df, title)


# ============================================================
# Constant Pace Segment Detection
# ============================================================


def detect_constant_pace_segments(
    df: pd.DataFrame, tolerance_pct: float = 5.0, min_duration_sec: int = 120
) -> List[Tuple[int, int, float]]:
    """Find segments where pace is stable within tolerance.

    Args:
        df: DataFrame with 'pace' column (sec/km)
        tolerance_pct: Percentage tolerance around median pace
        min_duration_sec: Minimum segment duration in seconds

    Returns:
        List of (start_idx, end_idx, avg_pace_sec) tuples
    """
    pace_col = None
    for col in ["pace", "pace_sec_per_km", "tempo"]:
        if col in df.columns:
            pace_col = col
            break

    if pace_col is None:
        return []

    pace = df[pace_col].ffill().values
    n = len(pace)

    if n < min_duration_sec:
        return []

    segments = []

    # Sliding window approach
    window_size = min_duration_sec

    i = 0
    while i < n - window_size:
        window = pace[i : i + window_size]
        median_pace = np.median(window)

        if median_pace <= 0 or median_pace > 1200:  # Skip invalid pace
            i += window_size // 2
            continue

        # Check if window is within tolerance
        lower = median_pace * (1 - tolerance_pct / 100)
        upper = median_pace * (1 + tolerance_pct / 100)

        if np.all((window >= lower) & (window <= upper)):
            # Extend segment as far as possible
            end_idx = i + window_size
            while end_idx < n:
                if lower <= pace[end_idx] <= upper:
                    end_idx += 1
                else:
                    break

            avg_pace = np.mean(pace[i:end_idx])
            segments.append((i, end_idx, avg_pace))
            i = end_idx
        else:
            i += 1

    return segments


# Legacy function name
detect_constant_power_segments = detect_constant_pace_segments


def _resolve_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Return the first matching column name from candidates, or None."""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _analyze_smo2_drift(
    segment: pd.DataFrame,
    smo2_col: str,
    pace_col: str,
    df_full: pd.DataFrame,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Run SmO2 linear regression and pace-SmO2 correlation.

    Returns:
        (smo2_slope, smo2_intercept, smo2_pvalue, corr_pace_smo2)
    """
    if segment[smo2_col].notna().sum() <= 10:
        return None, None, None, None
    smo2_clean = segment.dropna(subset=[smo2_col])
    smo2_slope, smo2_int, _, smo2_p, _ = stats.linregress(
        smo2_clean["time_min"], smo2_clean[smo2_col]
    )
    corr_pace_smo2 = (
        df_full[pace_col].corr(df_full[smo2_col]) if smo2_col in df_full.columns else None
    )
    return smo2_slope, smo2_int, smo2_p, corr_pace_smo2


def _build_drift_figure(
    segment: pd.DataFrame,
    hr_col: str,
    hr_slope: float,
    hr_intercept: float,
    smo2_col: Optional[str],
    smo2_slope: Optional[float],
    smo2_int: Optional[float],
    pace_target_sec: float,
    tolerance_pct: float,
) -> go.Figure:
    """Build the Plotly figure for HR and SmO2 drift at constant pace."""
    fig = go.Figure()

    segment[f"{hr_col}_smooth"] = segment[hr_col].rolling(window=30, min_periods=1).mean()
    fig.add_trace(
        go.Scatter(
            x=segment["time_min"],
            y=segment[f"{hr_col}_smooth"],
            mode="lines",
            name="HR [bpm]",
            line=dict(color="#FF4B4B", width=2),
            yaxis="y",
        )
    )

    hr_trend = hr_intercept + hr_slope * segment["time_min"]
    fig.add_trace(
        go.Scatter(
            x=segment["time_min"],
            y=hr_trend,
            mode="lines",
            name=f"HR Trend (slope={hr_slope:.2f}/min)",
            line=dict(color="#FF4B4B", width=1, dash="dash"),
            yaxis="y",
        )
    )

    if smo2_col:
        segment[f"{smo2_col}_smooth"] = segment[smo2_col].rolling(window=30, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=segment["time_min"],
                y=segment[f"{smo2_col}_smooth"],
                mode="lines",
                name="SmO₂ [%]",
                line=dict(color="#00CC96", width=2),
                yaxis="y2",
            )
        )
        if smo2_slope is not None and smo2_int is not None:
            smo2_trend = smo2_int + smo2_slope * segment["time_min"]
            fig.add_trace(
                go.Scatter(
                    x=segment["time_min"],
                    y=smo2_trend,
                    mode="lines",
                    name=f"SmO₂ Trend (slope={smo2_slope:.3f}/min)",
                    line=dict(color="#00CC96", width=1, dash="dash"),
                    yaxis="y2",
                )
            )

    pace_min_str = _sec_to_min(pace_target_sec)
    fig.update_layout(
        title=f"Fizjologia przy Tempo {pace_min_str:.2f} min/km (±{tolerance_pct}%)",
        xaxis_title="Czas w segmencie [hh:mm:ss]",
        yaxis=dict(
            title="HR [bpm]", title_font=dict(color="#FF4B4B"), tickfont=dict(color="#FF4B4B")
        ),
        yaxis2=dict(
            title="SmO₂ [%]",
            title_font=dict(color="#00CC96"),
            tickfont=dict(color="#00CC96"),
            overlaying="y",
            side="right",
            range=[0, 100] if smo2_col else None,
        ),
        template="plotly_dark",
        height=400,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(x=0.01, y=0.99),
    )
    return fig


def trend_at_constant_pace(
    df: pd.DataFrame,
    pace_target_sec: float,
    tolerance_pct: float = 5.0,
    min_duration_sec: int = 120,
) -> Tuple[Optional[go.Figure], Optional[DriftMetrics]]:
    """Extract segment at target pace and compute HR/SmO2 drift."""
    hr_col = _resolve_column(df, ["heartrate", "hr", "heart_rate"])
    pace_col = _resolve_column(df, ["pace", "pace_sec_per_km", "tempo"])

    if pace_col is None or hr_col is None:
        return None, None

    lower = pace_target_sec * (1 - tolerance_pct / 100)
    upper = pace_target_sec * (1 + tolerance_pct / 100)
    mask = (df[pace_col] >= lower) & (df[pace_col] <= upper)
    segment = df[mask].copy()

    if len(segment) < min_duration_sec:
        return None, None

    segment = segment.reset_index(drop=True)
    segment["time_min"] = segment.index / 60

    hr_slope, hr_intercept, hr_r, hr_p, hr_se = stats.linregress(
        segment["time_min"], segment[hr_col]
    )

    smo2_col = _resolve_column(segment, ["smo2", "SmO2", "muscle_oxygen"])
    smo2_slope, smo2_int, smo2_p, corr_pace_smo2 = (
        _analyze_smo2_drift(segment, smo2_col, pace_col, df)
        if smo2_col
        else (None, None, None, None)
    )

    fig = _build_drift_figure(
        segment,
        hr_col,
        hr_slope,
        hr_intercept,
        smo2_col,
        smo2_slope,
        smo2_int,
        pace_target_sec,
        tolerance_pct,
    )

    duration_min = len(segment) / 60
    drift_metrics = DriftMetrics(
        hr_drift_slope=hr_slope,
        hr_drift_pvalue=hr_p,
        smo2_slope=smo2_slope,
        smo2_pvalue=smo2_p,
        correlation_pace_hr=df[pace_col].corr(df[hr_col]),
        correlation_pace_smo2=corr_pace_smo2,
        segment_duration_min=duration_min,
        avg_pace=pace_target_sec,
    )

    return fig, drift_metrics


# Legacy function name
trend_at_constant_power = trend_at_constant_pace


# ============================================================
# Drift Analysis Functions
# ============================================================


def analyze_drift_pace_hr(df: pd.DataFrame, min_segment_duration_min: float = 3.0) -> Dict:
    """Analyze HR drift at constant pace across all detected segments.

    Args:
        df: DataFrame with pace and HR data
        min_segment_duration_min: Minimum segment duration in minutes

    Returns:
        Dictionary with drift analysis results
    """
    segments = detect_constant_pace_segments(
        df, tolerance_pct=5.0, min_duration_sec=int(min_segment_duration_min * 60)
    )

    if not segments:
        return {"error": "No constant-pace segments found"}

    results = []
    for start_idx, end_idx, avg_pace in segments:
        fig, metrics = trend_at_constant_pace(
            df.iloc[start_idx:end_idx],
            pace_target_sec=avg_pace,
            tolerance_pct=10.0,  # Already filtered, use loose tolerance
            min_duration_sec=int(min_segment_duration_min * 60),
        )
        if metrics:
            results.append(
                {
                    "pace_sec_per_km": round(avg_pace, 1),
                    "pace_min_per_km": round(_sec_to_min(avg_pace), 2),
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    **metrics.to_dict(),
                }
            )

    if not results:
        return {"error": "No valid drift segments analyzed"}

    # Summary statistics
    df_results = pd.DataFrame(results)
    return {
        "segments": results,
        "summary": {
            "total_segments": len(results),
            "avg_hr_drift_per_min": round(df_results["hr_drift_slope_per_min"].mean(), 3),
            "max_hr_drift_per_min": round(df_results["hr_drift_slope_per_min"].max(), 3),
            "avg_pace_min_per_km": round(df_results["pace_min_per_km"].mean(), 2),
        },
    }


# Legacy function name
analyze_drift_power_hr = analyze_drift_pace_hr
