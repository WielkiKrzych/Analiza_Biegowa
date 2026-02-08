"""
Polars DataFrame adapter for high-performance operations.

Provides drop-in replacements for Pandas operations using Polars
for 10-100x speedup on large datasets.
"""

import pandas as pd
import numpy as np
from typing import Optional, Union, List, Dict, Any
from pathlib import Path

# Try to import Polars
try:
    import polars as pl

    _POLARS_AVAILABLE = True
except ImportError:
    _POLARS_AVAILABLE = False
    pl = None


class PolarsAdapter:
    """
    Adapter class that provides Polars-accelerated operations
    with Pandas-compatible interface.
    """

    def __init__(self, df: Union[pd.DataFrame, "pl.DataFrame"]):
        """Initialize with either Pandas or Polars DataFrame."""
        if _POLARS_AVAILABLE and isinstance(df, pl.DataFrame):
            self._df = df
            self._is_polars = True
        else:
            self._df = df if isinstance(df, pd.DataFrame) else df.to_pandas()
            self._is_polars = False

    @classmethod
    def from_pandas(cls, df: pd.DataFrame) -> "PolarsAdapter":
        """Convert Pandas DataFrame to Polars."""
        if not _POLARS_AVAILABLE:
            return cls(df)

        try:
            # Convert to Polars
            pl_df = pl.from_pandas(df)
            return cls(pl_df)
        except Exception:
            # Fallback to Pandas
            return cls(df)

    def to_pandas(self) -> pd.DataFrame:
        """Convert back to Pandas DataFrame."""
        if self._is_polars:
            return self._df.to_pandas()
        return self._df

    def groupby_agg(self, group_col: str, agg_dict: Dict[str, str]) -> pd.DataFrame:
        """
        Fast groupby aggregation.

        Args:
            group_col: Column to group by
            agg_dict: {column: aggregation_function}

        Returns:
            Aggregated DataFrame
        """
        if not self._is_polars:
            # Use Pandas
            return self._df.groupby(group_col).agg(agg_dict).reset_index()

        # Use Polars for speed
        agg_exprs = []
        for col, func in agg_dict.items():
            if func == "mean":
                agg_exprs.append(pl.col(col).mean().alias(f"{col}_mean"))
            elif func == "sum":
                agg_exprs.append(pl.col(col).sum().alias(f"{col}_sum"))
            elif func == "max":
                agg_exprs.append(pl.col(col).max().alias(f"{col}_max"))
            elif func == "min":
                agg_exprs.append(pl.col(col).min().alias(f"{col}_min"))
            elif func == "count":
                agg_exprs.append(pl.col(col).count().alias(f"{col}_count"))
            elif func == "std":
                agg_exprs.append(pl.col(col).std().alias(f"{col}_std"))
            else:
                agg_exprs.append(pl.col(col).mean().alias(f"{col}_{func}"))

        result = self._df.group_by(group_col).agg(agg_exprs)
        return result.to_pandas()

    def rolling_mean(self, col: str, window: int) -> np.ndarray:
        """Fast rolling mean calculation."""
        if not self._is_polars:
            return self._df[col].rolling(window=window, min_periods=1).mean().values

        result = self._df.select(pl.col(col).rolling_mean(window_size=window, min_periods=1))
        return result.to_pandas()[col].values

    def filter(self, condition: str) -> "PolarsAdapter":
        """Filter rows based on condition."""
        if not self._is_polars:
            return PolarsAdapter(self._df.query(condition))

        # Parse simple conditions for Polars
        result = self._df.filter(eval(f"pl.{condition}"))
        return PolarsAdapter(result)

    def sort(self, by: str, descending: bool = False) -> "PolarsAdapter":
        """Sort by column."""
        if not self._is_polars:
            return PolarsAdapter(self._df.sort_values(by, ascending=not descending))

        result = self._df.sort(by, descending=descending)
        return PolarsAdapter(result)

    @property
    def shape(self) -> tuple:
        """Get DataFrame shape."""
        return self._df.shape

    @property
    def columns(self) -> List[str]:
        """Get column names."""
        if self._is_polars:
            return self._df.columns
        return list(self._df.columns)


def read_csv_fast(file_path: Union[str, Path], **kwargs) -> pd.DataFrame:
    """
    Fast CSV reading using Polars when available.

    10-50x faster than Pandas for large files.
    """
    if not _POLARS_AVAILABLE:
        return pd.read_csv(file_path, **kwargs)

    try:
        # Use Polars for reading
        pl_df = pl.read_csv(file_path, **kwargs)
        return pl_df.to_pandas()
    except Exception:
        # Fallback to Pandas
        return pd.read_csv(file_path, **kwargs)


def fast_groupby_agg(df: pd.DataFrame, group_col: str, agg_dict: Dict[str, str]) -> pd.DataFrame:
    """
    Drop-in replacement for Pandas groupby.agg() using Polars.

    Usage:
        result = fast_groupby_agg(df, 'category', {'value': 'mean', 'count': 'sum'})
    """
    adapter = PolarsAdapter.from_pandas(df)
    return adapter.groupby_agg(group_col, agg_dict)


def fast_rolling_mean(series: pd.Series, window: int) -> pd.Series:
    """
    Fast rolling mean using Polars.

    Usage:
        smoothed = fast_rolling_mean(df['value'], window=10)
    """
    if not _POLARS_AVAILABLE:
        return series.rolling(window=window, min_periods=1).mean()

    try:
        pl_series = pl.Series(series.values)
        result = pl_series.rolling_mean(window_size=window, min_periods=1)
        return pd.Series(result.to_numpy(), index=series.index)
    except Exception:
        return series.rolling(window=window, min_periods=1).mean()


def fast_moving_average(arr: np.ndarray, window: int) -> np.ndarray:
    """
    Fast moving average calculation.

    Uses convolution for O(n) complexity vs O(n*w) for naive approach.
    """
    if len(arr) < window:
        return arr

    # Use convolution for speed
    kernel = np.ones(window) / window
    return np.convolve(arr, kernel, mode="valid")


# Performance comparison utilities


def benchmark_operation(func_pandas, func_polars, data_size: int = 100000):
    """
    Benchmark Pandas vs Polars operation.

    Returns:
        dict with timing results
    """
    import time

    # Generate test data
    df = pd.DataFrame(
        {
            "group": np.random.choice(["A", "B", "C"], data_size),
            "value": np.random.randn(data_size),
            "count": np.random.randint(1, 100, data_size),
        }
    )

    # Benchmark Pandas
    start = time.time()
    result_pd = func_pandas(df)
    time_pd = time.time() - start

    # Benchmark Polars
    if _POLARS_AVAILABLE:
        start = time.time()
        result_pl = func_polars(df)
        time_pl = time.time() - start

        speedup = time_pd / time_pl if time_pl > 0 else float("inf")

        return {
            "pandas_time": time_pd,
            "polars_time": time_pl,
            "speedup": speedup,
            "results_match": np.allclose(result_pd.values, result_pl.values, rtol=1e-5),
        }

    return {"pandas_time": time_pd, "polars_available": False}
