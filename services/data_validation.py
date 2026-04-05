"""
Data Validation Service

Handles DataFrame validation logic for uploaded training files.
"""

from typing import List, Optional, Tuple

import pandas as pd

from modules.config import Config


def _ensure_numeric(df: pd.DataFrame, col: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Ensure column is numeric; coerce if needed.

    Returns (df_or_None, error_message_or_None).
    On success returns (df, None); on failure returns (None, error_msg).
    """
    if col not in df.columns:
        return df, None
    if pd.api.types.is_numeric_dtype(df[col]):
        return df, None
    try:
        df = df.copy()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if df[col].isna().all():
            return None, f"Kolumna '{col}' zawiera nieprawidłowe dane (nie-liczbowe)."
        return df, None
    except (ValueError, TypeError):
        return None, f"Kolumna '{col}' zawiera nieprawidłowe dane (nie-liczbowe)."


def _validate_column_range(
    df: pd.DataFrame, col: str, max_val: float, label: str, unit: str
) -> Optional[str]:
    """Check if column max exceeds limit; returns failure message or None."""
    if col not in df.columns:
        return None
    col_max = df[col].max()
    if col_max > max_val:
        return f"{label} ({col_max:.0f} {unit}) przekracza limit ({max_val} {unit}). Sprawdź jednostki."
    return None


def _validate_numeric_columns(df: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """Validate and coerce numeric columns; returns (df, failure_messages)."""
    failures: List[str] = []

    for col in ("watts", "heartrate", "cadence"):
        df, err = _ensure_numeric(df, col)
        if err is not None:
            return None, [err]

    failures.append(
        _validate_column_range(df, "watts", Config.VALIDATION_MAX_WATTS, "Moc maksymalna", "W")
    )
    failures.append(
        _validate_column_range(df, "heartrate", Config.VALIDATION_MAX_HR, "Tętno maksymalne", "bpm")
    )
    failures.append(
        _validate_column_range(df, "cadence", Config.VALIDATION_MAX_CADENCE, "Kadencja", "rpm")
    )

    return df, [f for f in failures if f is not None]


def _validate_time_column(df: pd.DataFrame) -> Optional[str]:
    """Validate time column type and content. Returns error message or None."""
    if "time" not in df.columns:
        return None
    if not pd.api.types.is_numeric_dtype(df["time"]):
        return "Kolumna 'time' musi być liczbowa."
    if df["time"].isnull().all():
        return "Kolumna 'time' zawiera same wartości puste (NaN)."
    return None


def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
    """Validate that DataFrame has minimum required structure and valid data.

    Checks for:
    - Non-empty DataFrame
    - Required columns (e.g., 'time')
    - At least one data column (watts, heartrate, etc.)
    - Minimum number of records
    - Data integrity (timestamps monotonic, reasonable ranges)

    Args:
        df: DataFrame to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # 1. Basic Structure
    if df is None or df.empty:
        return False, "Plik jest pusty lub nie udało się go wczytać."

    cols = df.columns

    # 2. Required Columns
    for req in Config.VALIDATION_REQUIRED_COLS:
        if req not in cols:
            return False, f"Brak wymaganej kolumny: '{req}'"

    # 3. Data Presence
    if not any(col in cols for col in Config.VALIDATION_DATA_COLS):
        return (
            False,
            f"Brak wymaganych kolumn danych. Oczekiwane przynajmniej jedna z: {Config.VALIDATION_DATA_COLS}",
        )

    # 4. Length Check
    if len(df) < Config.MIN_DF_LENGTH:
        return False, f"Za mało danych ({len(df)} rekordów). Minimum: {Config.MIN_DF_LENGTH}."

    # 5. Time column validation
    time_err = _validate_time_column(df)
    if time_err:
        return False, time_err

    # 6. Numeric column validation + range checks
    df, validation_failures = _validate_numeric_columns(df)
    if df is None:
        return False, validation_failures[0]

    if validation_failures:
        return False, "Błędy walidacji danych:\n" + "\n".join(validation_failures)

    return True, ""
