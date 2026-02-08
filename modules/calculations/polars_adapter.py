"""
Polars Adapter Module.

Provides seamless interoperability between Pandas and Polars.
Allows gradual migration without breaking existing code.
"""
import logging
from typing import Union, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Try to import Polars
try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

import pandas as pd


# Type alias for DataFrame compatibility
DataFrame = Union[pd.DataFrame, 'pl.DataFrame'] if POLARS_AVAILABLE else pd.DataFrame


def is_polars_available() -> bool:
    """Check if Polars is installed."""
    return POLARS_AVAILABLE


def is_polars_df(df: Any) -> bool:
    """Check if object is a Polars DataFrame."""
    if not POLARS_AVAILABLE:
        return False
    return isinstance(df, pl.DataFrame)


def is_pandas_df(df: Any) -> bool:
    """Check if object is a Pandas DataFrame."""
    return isinstance(df, pd.DataFrame)


def to_polars(df: Any) -> 'pl.DataFrame':
    """Convert any DataFrame-like object to Polars.
    
    Args:
        df: Pandas DataFrame, Polars DataFrame, dict, or similar
        
    Returns:
        Polars DataFrame
        
    Raises:
        ImportError: If Polars is not installed
        TypeError: If conversion not possible
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars is not installed. Run: pip install polars")
    
    if is_polars_df(df):
        return df
    
    if is_pandas_df(df):
        return pl.from_pandas(df)
    
    if isinstance(df, dict):
        return pl.DataFrame(df)
    
    if hasattr(df, 'to_pandas'):
        # Some libraries have to_pandas method
        return pl.from_pandas(df.to_pandas())
    
    raise TypeError(f"Cannot convert {type(df)} to Polars DataFrame")


def to_pandas(df: Any) -> pd.DataFrame:
    """Convert any DataFrame-like object to Pandas.
    
    Args:
        df: Polars DataFrame, Pandas DataFrame, dict, or similar
        
    Returns:
        Pandas DataFrame
    """
    if is_pandas_df(df):
        return df
    
    if POLARS_AVAILABLE and is_polars_df(df):
        return df.to_pandas()
    
    if isinstance(df, dict):
        return pd.DataFrame(df)
    
    if hasattr(df, 'to_pandas'):
        return df.to_pandas()
    
    raise TypeError(f"Cannot convert {type(df)} to Pandas DataFrame")


def ensure_polars(df: Any) -> Optional['pl.DataFrame']:
    """Safely convert to Polars, returning None if not possible.
    
    Use this when Polars is preferred but not required.
    """
    if not POLARS_AVAILABLE:
        return None
    
    try:
        return to_polars(df)
    except (TypeError, Exception) as e:
        logger.debug(f"Could not convert to Polars: {e}")
        return None


def ensure_pandas(df: Any) -> pd.DataFrame:
    """Safely convert to Pandas DataFrame.
    
    This is the main compatibility function - use when you need
    to ensure Pandas format for Streamlit/Plotly.
    """
    try:
        return to_pandas(df)
    except (TypeError, Exception) as e:
        logger.warning(f"Could not convert to Pandas: {e}")
        return pd.DataFrame()


# ============================================================
# High-Performance Operations (Polars-first, Pandas fallback)
# ============================================================

def fast_rolling_mean(
    df: DataFrame,
    column: str,
    window: int,
    min_periods: int = 1
) -> np.ndarray:
    """Fast rolling mean using Polars if available.
    
    Falls back to Pandas if Polars not installed.
    
    Returns numpy array for maximum compatibility.
    """
    if POLARS_AVAILABLE:
        try:
            pl_df = to_polars(df)
            result = pl_df.select(
                pl.col(column).rolling_mean(window_size=window, min_periods=min_periods)
            ).to_numpy().flatten()
            return result
        except Exception:
            pass
    
    # Pandas fallback
    pd_df = to_pandas(df)
    return pd_df[column].rolling(window=window, min_periods=min_periods).mean().values


def fast_groupby_agg(
    df: DataFrame,
    group_col: str,
    agg_col: str,
    agg_func: str = 'mean'
) -> pd.DataFrame:
    """Fast groupby aggregation using Polars if available.
    
    Args:
        df: Input DataFrame
        group_col: Column to group by
        agg_col: Column to aggregate
        agg_func: Aggregation function ('mean', 'sum', 'max', 'min', 'count')
        
    Returns:
        Pandas DataFrame with results (for Streamlit compatibility)
    """
    if POLARS_AVAILABLE:
        try:
            pl_df = to_polars(df)
            
            agg_expr = {
                'mean': pl.col(agg_col).mean(),
                'sum': pl.col(agg_col).sum(),
                'max': pl.col(agg_col).max(),
                'min': pl.col(agg_col).min(),
                'count': pl.col(agg_col).count(),
            }.get(agg_func, pl.col(agg_col).mean())
            
            result = pl_df.group_by(group_col).agg(agg_expr)
            return result.to_pandas()
        except Exception:
            pass
    
    # Pandas fallback
    pd_df = to_pandas(df)
    return pd_df.groupby(group_col)[agg_col].agg(agg_func).reset_index()


def fast_filter(
    df: DataFrame,
    column: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> pd.DataFrame:
    """Fast filtering using Polars if available.
    
    Returns Pandas DataFrame for compatibility.
    """
    if POLARS_AVAILABLE:
        try:
            pl_df = to_polars(df)
            
            expr = pl.lit(True)
            if min_val is not None:
                expr = expr & (pl.col(column) >= min_val)
            if max_val is not None:
                expr = expr & (pl.col(column) <= max_val)
            
            result = pl_df.filter(expr)
            return result.to_pandas()
        except Exception:
            pass
    
    # Pandas fallback
    pd_df = to_pandas(df)
    mask = pd.Series([True] * len(pd_df))
    if min_val is not None:
        mask &= pd_df[column] >= min_val
    if max_val is not None:
        mask &= pd_df[column] <= max_val
    return pd_df[mask]


def fast_read_csv(
    path: str,
    separator: str = ',',
    **kwargs
) -> pd.DataFrame:
    """Fast CSV reading using Polars if available.
    
    Returns Pandas DataFrame for compatibility.
    """
    if POLARS_AVAILABLE:
        try:
            pl_df = pl.read_csv(path, separator=separator, **kwargs)
            return pl_df.to_pandas()
        except Exception as e:
            logger.debug(f"Polars CSV read failed, using Pandas: {e}")
    
    return pd.read_csv(path, sep=separator, **kwargs)


# ============================================================
# Power Calculation Optimizations
# ============================================================

def fast_normalized_power(
    df: DataFrame,
    power_column: str = 'watts',
    window: int = 30
) -> float:
    """Calculate Normalized Power using fastest available method.
    
    NP = 4th root of (mean of 4th power of 30s rolling average)
    """
    if POLARS_AVAILABLE:
        try:
            pl_df = to_polars(df)
            
            # Rolling 30s average
            rolling = pl_df.select(
                pl.col(power_column).rolling_mean(window_size=window, min_periods=1)
            ).to_numpy().flatten()
            
            # 4th power
            pow4 = np.power(rolling, 4)
            
            # 4th root of mean
            return float(np.power(np.nanmean(pow4), 0.25))
        except Exception:
            pass
    
    # Pandas fallback
    pd_df = to_pandas(df)
    rolling = pd_df[power_column].rolling(window=window, min_periods=1).mean()
    pow4 = np.power(rolling, 4)
    return float(np.power(np.nanmean(pow4), 0.25))


def fast_power_duration_curve(
    df: DataFrame,
    durations: list[int],
    power_column: str = 'watts'
) -> dict[int, Optional[float]]:
    """Calculate PDC using fastest available method.
    
    Returns dict mapping duration (seconds) to max mean power.
    """
    results = {}
    
    if POLARS_AVAILABLE:
        try:
            pl_df = to_polars(df)
            watts = pl_df.select(pl.col(power_column)).to_numpy().flatten()
            
            for duration in durations:
                if len(watts) < duration:
                    results[duration] = None
                    continue
                
                # Use Polars rolling max for efficiency
                rolling = pl_df.select(
                    pl.col(power_column).rolling_mean(window_size=duration, min_periods=duration)
                ).to_numpy().flatten()
                
                max_power = np.nanmax(rolling)
                results[duration] = float(max_power) if not np.isnan(max_power) else None
            
            return results
        except Exception:
            pass
    
    # Pandas fallback
    pd_df = to_pandas(df)
    watts = pd_df[power_column]
    
    for duration in durations:
        if len(watts) < duration:
            results[duration] = None
            continue
        
        rolling = watts.rolling(window=duration, min_periods=duration).mean()
        max_power = rolling.max()
        results[duration] = float(max_power) if pd.notna(max_power) else None
    
    return results
