"""
SRP: Moduł odpowiedzialny za przetwarzanie surowych danych treningowych.
"""
from typing import Union, Any
import numpy as np
import pandas as pd

from .common import ensure_pandas, WINDOW_LONG, WINDOW_SHORT


def process_data(df: Union[pd.DataFrame, Any]) -> pd.DataFrame:
    """Process raw data: resample, smooth, and add time columns.
    
    This function:
    1. Ensures time column exists and is numeric
    2. Resamples to 1 second intervals
    3. Interpolates missing values
    4. Creates smoothed versions of key metrics
    
    Args:
        df: Raw DataFrame from CSV/file
    
    Returns:
        Processed DataFrame ready for analysis
    """
    df_pd = ensure_pandas(df)

    if 'time' not in df_pd.columns:
        df_pd['time'] = np.arange(len(df_pd)).astype(float)
    df_pd['time'] = pd.to_numeric(df_pd['time'], errors='coerce')
    
    # Remove rows with NaN time before creating index
    df_pd = df_pd.dropna(subset=['time'])
    
    # Fill missing time values sequentially if there are duplicates or gaps
    if df_pd['time'].isna().any() or len(df_pd) == 0:
        df_pd['time'] = np.arange(len(df_pd)).astype(float)

    df_pd = df_pd.sort_values('time').reset_index(drop=True)
    df_pd['time_dt'] = pd.to_timedelta(df_pd['time'], unit='s')
    
    # Ensure index has no NaN
    df_pd = df_pd[df_pd['time_dt'].notna()]
    df_pd = df_pd.set_index('time_dt')

    num_cols = df_pd.select_dtypes(include=['float64', 'int64']).columns.tolist()
    if num_cols:
        df_pd[num_cols] = df_pd[num_cols].interpolate(method='linear').ffill().bfill()

    try:
        df_numeric = df_pd.select_dtypes(include=[np.number])
        df_resampled = df_numeric.resample('1s').mean()
        df_resampled = df_resampled.interpolate(method='linear').ffill().bfill()
    except Exception:
        df_resampled = df_pd
    
    df_resampled['time'] = df_resampled.index.total_seconds()
    df_resampled['time_min'] = df_resampled['time'] / 60.0

    # Create smoothed versions of key columns
    smooth_cols = [
        'watts', 'heartrate', 'cadence', 'smo2', 'torque', 'core_temperature',
        'skin_temperature', 'velocity_smooth', 'tymebreathrate', 'tymeventilation', 'thb'
    ]
    
    for col in smooth_cols:
        if col in df_resampled.columns:
            df_resampled[f'{col}_smooth'] = df_resampled[col].rolling(
                window=WINDOW_LONG, min_periods=1
            ).mean()
            df_resampled[f'{col}_smooth_5s'] = df_resampled[col].rolling(
                window=WINDOW_SHORT, min_periods=1
            ).mean()

    df_resampled = df_resampled.reset_index(drop=True)

    return df_resampled
