"""
Comprehensive tests for data_validation service.

Tests cover all validation scenarios for the validate_dataframe function.
"""

import numpy as np
import pandas as pd
import pytest

from services.data_validation import validate_dataframe

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def valid_df() -> pd.DataFrame:
    """Create a valid DataFrame with all required columns."""
    return pd.DataFrame(
        {
            "time": np.arange(100, dtype=float),
            "watts": np.full(100, 200.0),
            "heartrate": np.full(100, 150.0),
        }
    )


@pytest.fixture
def valid_df_minimal() -> pd.DataFrame:
    """Create a minimal valid DataFrame with just time + one data column."""
    return pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "heartrate": np.full(20, 140.0),
        }
    )


@pytest.fixture
def valid_df_with_cadence() -> pd.DataFrame:
    """Create a valid DataFrame with cadence column."""
    return pd.DataFrame(
        {
            "time": np.arange(50, dtype=float),
            "cadence": np.full(50, 180.0),
        }
    )


# =============================================================================
# POSITIVE TESTS - Valid DataFrames should pass
# =============================================================================


def test_valid_dataframe_passes(valid_df: pd.DataFrame) -> None:
    """Valid DataFrame with time, watts, and heartrate should pass validation."""
    is_valid, message = validate_dataframe(valid_df)
    assert is_valid is True
    assert message == ""


def test_valid_minimal_dataframe_passes(valid_df_minimal: pd.DataFrame) -> None:
    """Minimal valid DataFrame (time + heartrate only) should pass."""
    is_valid, message = validate_dataframe(valid_df_minimal)
    assert is_valid is True
    assert message == ""


def test_valid_dataframe_with_cadence_passes(valid_df_with_cadence: pd.DataFrame) -> None:
    """DataFrame with time + cadence should pass validation."""
    is_valid, message = validate_dataframe(valid_df_with_cadence)
    assert is_valid is True
    assert message == ""


def test_dataframe_with_smo2_passes() -> None:
    """DataFrame with time + smo2 should pass validation."""
    df = pd.DataFrame(
        {
            "time": np.arange(30, dtype=float),
            "smo2": np.full(30, 75.0),
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


def test_dataframe_with_power_passes() -> None:
    """DataFrame with time + power should pass validation."""
    df = pd.DataFrame(
        {
            "time": np.arange(30, dtype=float),
            "power": np.full(30, 250.0),
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


def test_dataframe_exactly_at_min_length_passes() -> None:
    """DataFrame with exactly MIN_DF_LENGTH records should pass."""
    df = pd.DataFrame(
        {
            "time": np.arange(10, dtype=float),  # MIN_DF_LENGTH = 10
            "watts": np.full(10, 200.0),
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


# =============================================================================
# NEGATIVE TESTS - Invalid DataFrames should fail
# =============================================================================


def test_empty_dataframe_fails() -> None:
    """Empty DataFrame should fail validation."""
    is_valid, message = validate_dataframe(pd.DataFrame())
    assert is_valid is False
    assert "pusty" in message.lower() or "empty" in message.lower()


def test_none_dataframe_fails() -> None:
    """None DataFrame should fail validation."""
    is_valid, message = validate_dataframe(None)
    assert is_valid is False


def test_missing_time_column_fails() -> None:
    """DataFrame without 'time' column should fail."""
    df = pd.DataFrame({"watts": [100, 200, 300]})
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "time" in message.lower()


def test_missing_required_columns() -> None:
    """DataFrame missing required columns should fail."""
    df = pd.DataFrame(
        {
            "distance": [100, 200, 300],
            "speed": [10, 20, 30],
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "time" in message.lower()


def test_missing_all_data_columns_fails() -> None:
    """DataFrame with time but no data columns should fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "distance": np.arange(20, dtype=float),  # not in VALIDATION_DATA_COLS
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "danych" in message.lower() or "data" in message.lower()


def test_too_few_records_fails() -> None:
    """DataFrame with fewer than MIN_DF_LENGTH records should fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(5, dtype=float),  # Less than MIN_DF_LENGTH (10)
            "watts": np.full(5, 200.0),
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "mało" in message.lower() or "minimum" in message.lower() or "rekord" in message.lower()


# =============================================================================
# DATA TYPE VALIDATION TESTS
# =============================================================================


def test_non_numeric_time_column_fails() -> None:
    """Non-numeric time column should fail validation."""
    df = pd.DataFrame(
        {
            "time": ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o"],
            "watts": np.full(15, 200.0),
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "time" in message.lower() and "liczbow" in message.lower()


def test_all_nan_time_column_fails() -> None:
    """Time column with all NaN values should fail."""
    df = pd.DataFrame(
        {
            "time": np.full(15, np.nan),
            "watts": np.full(15, 200.0),
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "time" in message.lower() and ("pust" in message.lower() or "nan" in message.lower())


def test_non_numeric_watts_converts_or_fails() -> None:
    """Non-numeric watts column should be converted or fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(15, dtype=float),
            "watts": ["100", "200", "300"] * 5,
        }
    )
    # Should either convert successfully or fail gracefully
    is_valid, message = validate_dataframe(df)
    # If it converts, it passes; if not, it fails with proper message
    if not is_valid:
        assert "watts" in message.lower() and "nieprawidłow" in message.lower()


def test_non_numeric_heartrate_converts_or_fails() -> None:
    """Non-numeric heartrate column should be converted or fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(15, dtype=float),
            "heartrate": ["140", "150", "160"] * 5,
        }
    )
    is_valid, message = validate_dataframe(df)
    if not is_valid:
        assert "heartrate" in message.lower() and "nieprawidłow" in message.lower()


def test_non_numeric_cadence_converts_or_fails() -> None:
    """Non-numeric cadence column should be converted or fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(15, dtype=float),
            "cadence": ["170", "180", "190"] * 5,
        }
    )
    is_valid, message = validate_dataframe(df)
    if not is_valid:
        assert "cadence" in message.lower() and "nieprawidłow" in message.lower()


# =============================================================================
# RANGE VALIDATION TESTS
# =============================================================================


def test_watts_exceeds_max_limit_fails() -> None:
    """Watts exceeding VALIDATION_MAX_WATTS should fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "watts": np.full(20, 5000.0),  # Exceeds VALIDATION_MAX_WATTS (3000)
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "moc" in message.lower() or "watts" in message.lower() or "przekracza" in message.lower()


def test_heartrate_exceeds_max_limit_fails() -> None:
    """Heartrate exceeding VALIDATION_MAX_HR should fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "heartrate": np.full(20, 300.0),  # Exceeds VALIDATION_MAX_HR (250)
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "tętno" in message.lower() or "hr" in message.lower() or "bpm" in message.lower()


def test_cadence_exceeds_max_limit_fails() -> None:
    """Cadence exceeding VALIDATION_MAX_CADENCE should fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "cadence": np.full(20, 300.0),  # Exceeds VALIDATION_MAX_CADENCE (250)
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "kadencj" in message.lower() or "cadence" in message.lower() or "rpm" in message.lower()


def test_watts_at_max_limit_passes() -> None:
    """Watts at exactly VALIDATION_MAX_WATTS should pass."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "watts": np.full(20, 3000.0),  # Exactly VALIDATION_MAX_WATTS
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


def test_heartrate_at_max_limit_passes() -> None:
    """Heartrate at exactly VALIDATION_MAX_HR should pass."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "heartrate": np.full(20, 250.0),  # Exactly VALIDATION_MAX_HR
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


def test_cadence_at_max_limit_passes() -> None:
    """Cadence at exactly VALIDATION_MAX_CADENCE should pass."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "cadence": np.full(20, 250.0),  # Exactly VALIDATION_MAX_CADENCE
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


def test_dataframe_with_some_nan_values_passes() -> None:
    """DataFrame with some (but not all) NaN values in data columns should pass."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "watts": [200.0, np.nan, 210.0, np.nan] * 5,
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


def test_dataframe_with_negative_watts_passes() -> None:
    """DataFrame with negative watts (coasting) should pass."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "watts": [-10.0, 0.0, 50.0] + [200.0] * 17,
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


def test_dataframe_with_zero_heartrate_passes() -> None:
    """DataFrame with zero heartrate (sensor drop) should pass."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "heartrate": [0.0, 150.0] * 10,
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is True


def test_multiple_validation_failures_reported() -> None:
    """Multiple validation failures should all be reported."""
    df = pd.DataFrame(
        {
            "time": np.arange(20, dtype=float),
            "watts": np.full(20, 5000.0),  # Exceeds max
            "heartrate": np.full(20, 300.0),  # Exceeds max
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    # Should report both failures
    assert "watts" in message.lower() or "moc" in message.lower()
    assert "heartrate" in message.lower() or "tętno" in message.lower()


def test_all_invalid_watts_fails() -> None:
    """Watts column with all invalid (non-convertible) values should fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(15, dtype=float),
            "watts": ["invalid", "data", "here"] * 5,
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "watts" in message.lower() and "nieprawidłow" in message.lower()


def test_all_invalid_heartrate_fails() -> None:
    """Heartrate column with all invalid (non-convertible) values should fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(15, dtype=float),
            "heartrate": ["N/A", "N/A", "N/A"] * 5,
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "heartrate" in message.lower() and "nieprawidłow" in message.lower()


def test_all_invalid_cadence_fails() -> None:
    """Cadence column with all invalid (non-convertible) values should fail."""
    df = pd.DataFrame(
        {
            "time": np.arange(15, dtype=float),
            "cadence": ["--", "--", "--"] * 5,
        }
    )
    is_valid, message = validate_dataframe(df)
    assert is_valid is False
    assert "cadence" in message.lower() and "nieprawidłow" in message.lower()
