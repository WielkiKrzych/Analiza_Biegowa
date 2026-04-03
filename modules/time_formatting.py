"""
Utilities for formatting time values in charts.
"""
import pandas as pd


def format_time_hhmmss(seconds: float) -> str:
    """
    Format seconds as hh:mm:ss string.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted string like "01:30:45"
    """
    if pd.isna(seconds) or seconds < 0:
        return "00:00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_time_axis(df: pd.DataFrame, time_col: str = 'time_min') -> pd.Series:
    """
    Convert time column from minutes to formatted hh:mm:ss strings.
    
    Args:
        df: DataFrame with time column
        time_col: Name of time column (in minutes)
        
    Returns:
        Series with formatted time strings
    """
    if time_col not in df.columns:
        return pd.Series(index=df.index, dtype=str)

    # Convert minutes to seconds, then format
    seconds = df[time_col] * 60
    return seconds.apply(format_time_hhmmss)


def get_time_axis_config(time_values: pd.Series, is_minutes: bool = True) -> dict:
    """
    Get Plotly axis configuration for time formatting.
    
    Args:
        time_values: Time values (in minutes if is_minutes=True)
        is_minutes: Whether time_values are in minutes
        
    Returns:
        Dict with axis configuration
    """
    if is_minutes:
        time_values = time_values * 60

    max_time = time_values.max() if len(time_values) > 0 else 3600

    # Determine tick format based on duration
    if max_time > 3600:  # More than 1 hour
        tickformat = "%H:%M:%S"
        title = "Czas [hh:mm:ss]"
    else:
        tickformat = "%M:%S"
        title = "Czas [mm:ss]"

    return {
        'tickformat': tickformat,
        'title': title,
        'type': 'linear',
        'tickmode': 'auto',
        'nticks': 10
    }


def pace_to_seconds(pace: float) -> str:
    """
    Convert pace in seconds per km to mm:ss format.
    
    Args:
        pace: Pace in seconds per km
        
    Returns:
        Formatted string like "4:30"
    """
    if pd.isna(pace) or pace <= 0:
        return "--:--"

    minutes = int(pace // 60)
    seconds = int(pace % 60)

    return f"{minutes}:{seconds:02d}"


def seconds_to_pace(seconds_per_km: float) -> str:
    """
    Alias for pace_to_seconds - converts seconds to pace format.
    """
    return pace_to_seconds(seconds_per_km)
