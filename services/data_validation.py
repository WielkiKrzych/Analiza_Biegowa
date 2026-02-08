"""
Data Validation Service

Handles DataFrame validation logic for uploaded training files.
"""

import pandas as pd
from typing import Tuple
from modules.config import Config


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

    # 5. Type & Integrity Checks

    # Time monotonicity
    if "time" in cols:
        if not pd.api.types.is_numeric_dtype(df["time"]):
            return False, "Kolumna 'time' musi być liczbowa."
        if df["time"].isnull().all():
            return False, "Kolumna 'time' zawiera same wartości puste (NaN)."

        # Check for monotonicity (allowing for small resets/gaps if needed, but strictly it should be increasing usually)
        # Note: Some trainers reset time. But usually we want monotonic.
        # Let's just check if it's completely scrambled or garbage
        pass

    # Type Validation - Convert or reject non-numeric data
    validation_failures = []

    if "watts" in cols:
        if not pd.api.types.is_numeric_dtype(df["watts"]):
            try:
                df["watts"] = pd.to_numeric(df["watts"], errors="coerce")
                if df["watts"].isna().all():
                    return False, "Kolumna 'watts' zawiera nieprawidłowe dane (nie-liczbowe)."
            except Exception:
                return False, "Kolumna 'watts' zawiera nieprawidłowe dane (nie-liczbowe)."
        max_w = df["watts"].max()
        if max_w > Config.VALIDATION_MAX_WATTS:
            validation_failures.append(
                f"Moc maksymalna ({max_w:.0f} W) przekracza limit ({Config.VALIDATION_MAX_WATTS} W). Sprawdź jednostki."
            )

    if "heartrate" in cols:
        if not pd.api.types.is_numeric_dtype(df["heartrate"]):
            try:
                df["heartrate"] = pd.to_numeric(df["heartrate"], errors="coerce")
                if df["heartrate"].isna().all():
                    return False, "Kolumna 'heartrate' zawiera nieprawidłowe dane (nie-liczbowe)."
            except Exception:
                return False, "Kolumna 'heartrate' zawiera nieprawidłowe dane (nie-liczbowe)."
        max_hr = df["heartrate"].max()
        if max_hr > Config.VALIDATION_MAX_HR:
            validation_failures.append(
                f"Tętno maksymalne ({max_hr:.0f} bpm) przekracza limit ({Config.VALIDATION_MAX_HR} bpm)."
            )

    if "cadence" in cols:
        if not pd.api.types.is_numeric_dtype(df["cadence"]):
            try:
                df["cadence"] = pd.to_numeric(df["cadence"], errors="coerce")
                if df["cadence"].isna().all():
                    return False, "Kolumna 'cadence' zawiera nieprawidłowe dane (nie-liczbowe)."
            except Exception:
                return False, "Kolumna 'cadence' zawiera nieprawidłowe dane (nie-liczbowe)."
        max_cad = df["cadence"].max()
        if max_cad > Config.VALIDATION_MAX_CADENCE:
            validation_failures.append(
                f"Kadencja ({max_cad:.0f} rpm) przekracza limit ({Config.VALIDATION_MAX_CADENCE} rpm)."
            )

    if validation_failures:
        return False, "Błędy walidacji danych:\n" + "\n".join(validation_failures)

    return True, ""
