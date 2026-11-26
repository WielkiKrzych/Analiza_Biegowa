"""Convert inputs shared by calculations to pandas DataFrames."""

from typing import Any

import pandas as pd


def ensure_pandas(df: Any) -> pd.DataFrame:
    """
    Convert any DataFrame-like object to pandas DataFrame.
    Minimizes unnecessary copying when already a pandas DataFrame.

    Args:
        df: Input data (pandas DataFrame, Polars DataFrame, or dict)

    Returns:
        pandas DataFrame
    """
    if isinstance(df, pd.DataFrame):
        return df
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    if isinstance(df, dict):
        return pd.DataFrame(df)
    return pd.DataFrame(df)
