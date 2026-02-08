"""
Signal Preprocessing Module

Provides standardized preprocessing functions for physiological signals:
- Smoothing (rolling, exponential)
- Detrending (linear, polynomial)
- Interpolation (gap filling)
- Quality flags

All physiological calculation functions should use this module.
NO STREAMLIT OR UI DEPENDENCIES ALLOWED.
"""

from dataclasses import dataclass, field
from typing import Literal, Dict, Any
import numpy as np
import pandas as pd


# ============================================================
# Quality Flags Dataclass
# ============================================================

@dataclass
class SignalQualityFlags:
    """Quality assessment flags for a signal."""
    valid_ratio: float          # Ratio of valid (non-NaN) samples (0.0-1.0)
    gap_count: int              # Number of gaps in signal
    max_gap_duration: int       # Longest gap in samples
    noise_level: float          # Estimated noise level (CV of diff)
    is_usable: bool             # Overall usability flag
    
    @classmethod
    def from_series(
        cls, 
        series: pd.Series,
        min_valid_ratio: float = 0.8,
        max_noise_level: float = 0.3
    ) -> 'SignalQualityFlags':
        """Compute quality flags from a pandas Series."""
        if series is None or len(series) == 0:
            return cls(
                valid_ratio=0.0, gap_count=0, max_gap_duration=0,
                noise_level=1.0, is_usable=False
            )
        
        # Valid ratio
        valid_mask = series.notna() & np.isfinite(series)
        valid_ratio = valid_mask.sum() / len(series)
        
        # Gap analysis
        gaps = (~valid_mask).astype(int)
        gap_starts = np.diff(gaps, prepend=0) == 1
        gap_count = gap_starts.sum()
        
        # Max gap duration
        if gap_count > 0:
            gap_lengths = []
            current_gap = 0
            for is_gap in gaps:
                if is_gap:
                    current_gap += 1
                else:
                    if current_gap > 0:
                        gap_lengths.append(current_gap)
                    current_gap = 0
            if current_gap > 0:
                gap_lengths.append(current_gap)
            max_gap_duration = max(gap_lengths) if gap_lengths else 0
        else:
            max_gap_duration = 0
        
        # Noise level (coefficient of variation of diffs)
        valid_data = series[valid_mask]
        if len(valid_data) > 10:
            diffs = np.abs(np.diff(valid_data.values))
            mean_val = np.mean(np.abs(valid_data.values))
            if mean_val > 0:
                noise_level = np.std(diffs) / mean_val
            else:
                noise_level = 0.0
        else:
            noise_level = 1.0
        
        is_usable = valid_ratio >= min_valid_ratio and noise_level <= max_noise_level
        
        return cls(
            valid_ratio=round(valid_ratio, 3),
            gap_count=int(gap_count),
            max_gap_duration=int(max_gap_duration),
            noise_level=round(noise_level, 3),
            is_usable=is_usable
        )


@dataclass
class SeriesResult:
    """Result of a preprocessing operation."""
    data: pd.Series
    quality: SignalQualityFlags
    method: str
    parameters: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Smoothing Functions
# ============================================================

def rolling_smooth(
    series: pd.Series,
    window: int = 30,
    method: Literal['mean', 'median'] = 'mean',
    min_periods: int = 1,
    center: bool = False
) -> SeriesResult:
    """
    Apply rolling window smoothing to a series.
    
    Args:
        series: Input pandas Series
        window: Window size in samples (default: 30)
        method: Aggregation method - 'mean' or 'median' (default: 'mean')
        min_periods: Minimum observations in window (default: 1)
        center: Center the window (default: False)
    
    Returns:
        SeriesResult with smoothed data, quality flags, and parameters
    """
    if series is None or len(series) == 0:
        return SeriesResult(
            data=pd.Series(dtype=float),
            quality=SignalQualityFlags.from_series(pd.Series(dtype=float)),
            method='rolling_smooth',
            parameters={'window': window, 'method': method}
        )
    
    rolling = series.rolling(window=window, min_periods=min_periods, center=center)
    
    if method == 'median':
        smoothed = rolling.median()
    else:
        smoothed = rolling.mean()
    
    # Fill any remaining NaNs at edges
    smoothed = smoothed.fillna(series)
    
    quality = SignalQualityFlags.from_series(smoothed)
    
    return SeriesResult(
        data=smoothed,
        quality=quality,
        method='rolling_smooth',
        parameters={
            'window': window,
            'method': method,
            'min_periods': min_periods,
            'center': center
        }
    )


def exponential_smooth(
    series: pd.Series,
    alpha: float = 0.3,
    adjust: bool = True
) -> SeriesResult:
    """
    Apply exponential weighted moving average (EWMA) smoothing.
    
    Args:
        series: Input pandas Series
        alpha: Smoothing factor (0 < alpha <= 1). Higher = less smoothing
        adjust: Whether to divide by decaying adjustment factor (default: True)
    
    Returns:
        SeriesResult with smoothed data, quality flags, and parameters
    """
    if series is None or len(series) == 0:
        return SeriesResult(
            data=pd.Series(dtype=float),
            quality=SignalQualityFlags.from_series(pd.Series(dtype=float)),
            method='exponential_smooth',
            parameters={'alpha': alpha}
        )
    
    smoothed = series.ewm(alpha=alpha, adjust=adjust).mean()
    quality = SignalQualityFlags.from_series(smoothed)
    
    return SeriesResult(
        data=smoothed,
        quality=quality,
        method='exponential_smooth',
        parameters={'alpha': alpha, 'adjust': adjust}
    )


# ============================================================
# Detrending Functions
# ============================================================

def detrend_linear(series: pd.Series) -> SeriesResult:
    """
    Remove linear trend from a series.
    
    Args:
        series: Input pandas Series
    
    Returns:
        SeriesResult with detrended data, quality flags, and parameters
    """
    if series is None or len(series) == 0:
        return SeriesResult(
            data=pd.Series(dtype=float),
            quality=SignalQualityFlags.from_series(pd.Series(dtype=float)),
            method='detrend_linear',
            parameters={}
        )
    
    valid_mask = series.notna() & np.isfinite(series)
    if valid_mask.sum() < 2:
        return SeriesResult(
            data=series.copy(),
            quality=SignalQualityFlags.from_series(series),
            method='detrend_linear',
            parameters={'slope': 0, 'intercept': 0}
        )
    
    x = np.arange(len(series))
    y = series.values.copy()
    
    # Fit linear regression only on valid points
    x_valid = x[valid_mask]
    y_valid = y[valid_mask]
    
    coeffs = np.polyfit(x_valid, y_valid, 1)
    slope, intercept = coeffs[0], coeffs[1]
    
    # Subtract trend
    trend = slope * x + intercept
    detrended = pd.Series(y - trend, index=series.index)
    
    quality = SignalQualityFlags.from_series(detrended)
    
    return SeriesResult(
        data=detrended,
        quality=quality,
        method='detrend_linear',
        parameters={'slope': round(slope, 6), 'intercept': round(intercept, 3)}
    )


def detrend_polynomial(
    series: pd.Series,
    degree: int = 2
) -> SeriesResult:
    """
    Remove polynomial trend from a series.
    
    Args:
        series: Input pandas Series
        degree: Polynomial degree (default: 2 = quadratic)
    
    Returns:
        SeriesResult with detrended data, quality flags, and parameters
    """
    if series is None or len(series) == 0:
        return SeriesResult(
            data=pd.Series(dtype=float),
            quality=SignalQualityFlags.from_series(pd.Series(dtype=float)),
            method='detrend_polynomial',
            parameters={'degree': degree}
        )
    
    valid_mask = series.notna() & np.isfinite(series)
    if valid_mask.sum() < degree + 1:
        return SeriesResult(
            data=series.copy(),
            quality=SignalQualityFlags.from_series(series),
            method='detrend_polynomial',
            parameters={'degree': degree, 'coefficients': []}
        )
    
    x = np.arange(len(series))
    y = series.values.copy()
    
    x_valid = x[valid_mask]
    y_valid = y[valid_mask]
    
    coeffs = np.polyfit(x_valid, y_valid, degree)
    trend = np.polyval(coeffs, x)
    detrended = pd.Series(y - trend, index=series.index)
    
    quality = SignalQualityFlags.from_series(detrended)
    
    return SeriesResult(
        data=detrended,
        quality=quality,
        method='detrend_polynomial',
        parameters={
            'degree': degree,
            'coefficients': [round(c, 6) for c in coeffs]
        }
    )


# ============================================================
# Interpolation Functions
# ============================================================

def interpolate_gaps(
    series: pd.Series,
    method: Literal['linear', 'spline', 'nearest', 'zero'] = 'linear',
    max_gap: int = 5,
    spline_order: int = 3
) -> SeriesResult:
    """
    Interpolate gaps (NaN values) in a series.
    
    Args:
        series: Input pandas Series
        method: Interpolation method (default: 'linear')
        max_gap: Maximum gap size to interpolate (larger gaps are left as NaN)
        spline_order: Order for spline interpolation (default: 3)
    
    Returns:
        SeriesResult with interpolated data, quality flags, and parameters
    """
    if series is None or len(series) == 0:
        return SeriesResult(
            data=pd.Series(dtype=float),
            quality=SignalQualityFlags.from_series(pd.Series(dtype=float)),
            method='interpolate_gaps',
            parameters={'method': method, 'max_gap': max_gap}
        )
    
    result = series.copy()
    
    # Identify gaps and their lengths
    is_nan = result.isna()
    gap_group = (~is_nan).cumsum()
    gap_sizes = is_nan.groupby(gap_group).transform('sum')
    
    # Mask for gaps that are too large
    large_gaps = is_nan & (gap_sizes > max_gap)
    
    # Interpolate
    if method == 'spline':
        result = result.interpolate(method='spline', order=spline_order, limit=max_gap)
    elif method == 'nearest':
        result = result.interpolate(method='nearest', limit=max_gap)
    elif method == 'zero':
        result = result.interpolate(method='zero', limit=max_gap)
    else:
        result = result.interpolate(method='linear', limit=max_gap)
    
    # Restore NaNs for large gaps
    result[large_gaps] = np.nan
    
    quality = SignalQualityFlags.from_series(result)
    gaps_filled = is_nan.sum() - result.isna().sum()
    
    return SeriesResult(
        data=result,
        quality=quality,
        method='interpolate_gaps',
        parameters={
            'method': method,
            'max_gap': max_gap,
            'gaps_filled': int(gaps_filled)
        }
    )


# ============================================================
# Combined Preprocessing Pipeline
# ============================================================

def preprocess_signal(
    series: pd.Series,
    interpolate: bool = True,
    smooth: bool = True,
    detrend: bool = False,
    smooth_window: int = 30,
    smooth_method: Literal['mean', 'median', 'ewma'] = 'mean',
    max_gap: int = 5
) -> SeriesResult:
    """
    Apply full preprocessing pipeline to a signal.
    
    Args:
        series: Input pandas Series
        interpolate: Fill gaps (default: True)
        smooth: Apply smoothing (default: True)
        detrend: Remove linear trend (default: False)
        smooth_window: Window for rolling smooth (default: 30)
        smooth_method: Smoothing method (default: 'mean')
        max_gap: Maximum gap to interpolate (default: 5)
    
    Returns:
        SeriesResult with processed data
    """
    result = series.copy()
    
    # Step 1: Interpolation
    if interpolate:
        interp_result = interpolate_gaps(result, method='linear', max_gap=max_gap)
        result = interp_result.data
    
    # Step 2: Detrending
    if detrend:
        detrend_result = detrend_linear(result)
        result = detrend_result.data
    
    # Step 3: Smoothing
    if smooth:
        if smooth_method == 'ewma':
            smooth_result = exponential_smooth(result, alpha=2/(smooth_window+1))
        elif smooth_method == 'median':
            smooth_result = rolling_smooth(result, window=smooth_window, method='median')
        else:
            smooth_result = rolling_smooth(result, window=smooth_window, method='mean')
        result = smooth_result.data
    
    quality = SignalQualityFlags.from_series(result)
    
    return SeriesResult(
        data=result,
        quality=quality,
        method='preprocess_signal',
        parameters={
            'interpolate': interpolate,
            'smooth': smooth,
            'detrend': detrend,
            'smooth_window': smooth_window,
            'smooth_method': smooth_method,
            'max_gap': max_gap
        }
    )


__all__ = [
    # Quality
    'SignalQualityFlags',
    'SeriesResult',
    # Smoothing
    'rolling_smooth',
    'exponential_smooth',
    # Detrending
    'detrend_linear',
    'detrend_polynomial',
    # Interpolation
    'interpolate_gaps',
    # Pipeline
    'preprocess_signal',
]
