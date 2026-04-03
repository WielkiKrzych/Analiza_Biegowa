"""
Tests for the Ramp Test Pipeline module.

Tests validate_test() function following TDD principles.
"""

import numpy as np
import pandas as pd
import pytest

from models.results import ValidityLevel
from modules.calculations.pipeline import validate_test


def _make_ramp_df(duration_sec: int = 600, power_range: float = 200.0) -> pd.DataFrame:
    """
    Create a test DataFrame simulating a ramp test.

    Args:
        duration_sec: Duration of the test in seconds
        power_range: Power increase range in watts (from 100W baseline)

    Returns:
        DataFrame with time, watts, and hr columns
    """
    time = np.arange(duration_sec, dtype=float)
    power = np.linspace(100.0, 100.0 + power_range, duration_sec)
    hr = np.linspace(100.0, 180.0, duration_sec)
    return pd.DataFrame({"time": time, "watts": power, "hr": hr})


def test_valid_ramp_test_passes() -> None:
    """A valid ramp test (>= 8 min, sufficient power range) should return VALID."""
    df = _make_ramp_df(duration_sec=600, power_range=200.0)
    result = validate_test(df)
    assert result.validity == ValidityLevel.VALID
    assert result.issues == []


def test_too_short_test_is_invalid() -> None:
    """A test shorter than 6 minutes should be INVALID."""
    df = _make_ramp_df(duration_sec=300)
    result = validate_test(df)
    assert result.validity == ValidityLevel.INVALID


def test_borderline_duration_is_conditional() -> None:
    """A test between 6-8 minutes should be CONDITIONAL."""
    df = _make_ramp_df(duration_sec=420)  # 7 minutes
    result = validate_test(df)
    assert result.validity == ValidityLevel.CONDITIONAL


def test_missing_time_column_is_invalid() -> None:
    """A DataFrame missing the time column should be INVALID."""
    df = pd.DataFrame({"watts": np.linspace(100, 300, 600), "hr": np.linspace(100, 180, 600)})
    result = validate_test(df)
    assert result.validity == ValidityLevel.INVALID


def test_missing_power_column_is_invalid() -> None:
    """A DataFrame missing the power column should be INVALID."""
    df = pd.DataFrame({"time": np.arange(600), "hr": np.linspace(100, 180, 600)})
    result = validate_test(df)
    assert result.validity == ValidityLevel.INVALID


def test_excessive_hr_artifacts_is_invalid() -> None:
    """A test with >20% HR artifacts should be INVALID."""
    df = _make_ramp_df(duration_sec=600)
    artifact_count = int(600 * 0.25)  # 25% artifacts
    df.loc[:artifact_count, "hr"] = 10.0  # Values < 40 are artifacts
    result = validate_test(df)
    assert result.validity == ValidityLevel.INVALID


def test_moderate_hr_artifacts_is_conditional() -> None:
    """A test with 5-20% HR artifacts should be CONDITIONAL."""
    df = _make_ramp_df(duration_sec=600)
    artifact_count = int(600 * 0.10)  # 10% artifacts
    df.loc[:artifact_count, "hr"] = 10.0  # Values < 40 are artifacts
    result = validate_test(df)
    assert result.validity == ValidityLevel.CONDITIONAL


def test_insufficient_power_range_is_conditional() -> None:
    """A test with < 150W power range should be CONDITIONAL."""
    df = _make_ramp_df(duration_sec=600, power_range=100.0)  # Only 100W range
    result = validate_test(df)
    assert result.validity == ValidityLevel.CONDITIONAL


def test_ramp_duration_recorded_correctly() -> None:
    """Test that ramp duration is recorded correctly in result."""
    df = _make_ramp_df(duration_sec=600)
    result = validate_test(df)
    assert result.ramp_duration_sec == 599  # max - min = 599 for 600 samples (0-599)


def test_power_range_recorded_correctly() -> None:
    """Test that power range is recorded correctly in result."""
    df = _make_ramp_df(duration_sec=600, power_range=200.0)
    result = validate_test(df)
    assert result.power_range_watts == pytest.approx(200.0, rel=0.01)


def test_signal_qualities_populated() -> None:
    """Test that signal qualities are populated for available signals."""
    df = _make_ramp_df(duration_sec=600)
    result = validate_test(df)
    assert "Power" in result.signal_qualities
    assert "HR" in result.signal_qualities


def test_valid_without_hr_column() -> None:
    """A test without HR column can still be valid if other checks pass."""
    df = pd.DataFrame({"time": np.arange(600), "watts": np.linspace(100.0, 300.0, 600)})
    result = validate_test(df)
    assert result.validity == ValidityLevel.VALID
