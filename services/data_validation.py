"""
Data Validation Service

Handles DataFrame validation logic for uploaded training files.
"""

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from modules.config import Config
from modules.utils import derive_pace

logger = logging.getLogger(__name__)


def _ensure_numeric(df: pd.DataFrame, col: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Ensure column is numeric; coerce if needed.

    Mutates df in place.

    Coercion happens IN PLACE on *df*. The caller keeps processing the very
    frame it passed in, so a coerced copy would be thrown away and the
    object-dtype column would reach `process_data`, where
    `resample_with_pace` keeps only `select_dtypes(include=[np.number])`
    and would silently drop the column from the output.

    Returns (df_or_None, error_message_or_None).
    On success returns (df, None); on failure returns (None, error_msg).
    """
    if col not in df.columns:
        return df, None
    if pd.api.types.is_numeric_dtype(df[col]):
        return df, None
    try:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if df[col].isna().all():
            return None, f"Kolumna '{col}' zawiera nieprawidłowe dane (nie-liczbowe)."
        return df, None
    except (ValueError, TypeError):
        return None, f"Kolumna '{col}' zawiera nieprawidłowe dane (nie-liczbowe)."


def _validate_column_range(
    df: pd.DataFrame, col: str, max_val: float, label: str, unit: str
) -> Optional[str]:
    """Check if column 99th percentile exceeds limit; returns failure message or None.

    Uses 99th percentile (not max) so isolated sensor spikes do not block
    an otherwise valid import.
    """
    if col not in df.columns:
        return None
    series = df[col].dropna()
    if series.empty:
        return None
    col_p99 = float(series.quantile(0.99))
    if col_p99 > max_val:
        return f"{label} ({col_p99:.0f} {unit}) przekracza limit ({max_val} {unit}). Sprawdź jednostki."
    return None


def _validate_numeric_columns(df: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """Validate and coerce numeric columns; returns (df, failure_messages)."""
    failures: List[str | None] = []

    # These three block the import when they cannot be coerced (unchanged).
    for col in ("heartrate", "cadence"):
        df, err = _ensure_numeric(df, col)
        if err is not None:
            return None, [err]

    # The remaining declared data columns were never coerced, so a numeric-looking
    # object column (stray whitespace, one bad row) survived validation and was then
    # dropped by `resample_with_pace`'s select_dtypes(include=[np.number]) -- the
    # dashboard lost e.g. `pace` without a word. Coercion here keeps them. A column
    # that is genuinely non-numeric (pace as "4:30") only gets logged: rejecting the
    # whole file would block imports that work today.
    for col in ("watts", "pace", "speed", "speed_m_s", "velocity_smooth", "smo2", "hr"):
        if col not in df.columns:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        coerced = pd.to_numeric(df[col], errors="coerce")
        if coerced.isna().all():
            logger.warning("Kolumna '%s' nie jest liczbowa i zostanie pominieta w analizie.", col)
            continue
        df[col] = coerced

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
    time = df["time"]
    if time.isna().all():
        return "Kolumna 'time' zawiera same wartości puste (NaN)."
    if not np.isfinite(time).all() or not time.is_monotonic_increasing:
        return "Kolumna 'time' musi zawierać uporządkowane, skończone sekundy."
    elapsed = time.iloc[-1] - time.iloc[0]
    if not 0 < elapsed <= 7 * 24 * 3600:
        return "Sprawdź jednostkę czasu [s] i odstęp między pierwszą i ostatnią próbką."
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
    if "time" not in cols:
        return False, "Brak wymaganej kolumny: 'time'"

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

    derive_pace(df)
    if "pace" not in df or not df["pace"].gt(0).any():
        return False, "Brak użytecznych danych tempa [s/km] lub prędkości [m/s]."

    return True, ""
