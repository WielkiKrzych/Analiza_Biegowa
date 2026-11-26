"""Prepare elapsed time for one-second resampling."""

import pandas as pd


def prepare_time_index(df: pd.DataFrame) -> pd.DataFrame:
    time = pd.to_numeric(df["time"], errors="coerce")
    df = df.loc[time.notna()].copy()
    time = time.loc[time.notna()]
    df.index = pd.to_timedelta(time - time.min(), unit="s")
    return df.sort_index()
