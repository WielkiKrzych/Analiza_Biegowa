# tests/signals/test_signals.py
import numpy as np
import pandas as pd
import pytest

from signals.conflicts import (
    ConflictAnalysisResult,
    ConflictSeverity,
    ConflictType,
    SignalConflict,
    detect_cardiac_drift,
    detect_dfa_anomaly,
    detect_decoupling,
    detect_signal_conflicts,
    detect_smo2_power_conflict,
)
from signals.preprocessing import (
    SignalQualityFlags,
    SeriesResult,
    detrend_linear,
    detrend_polynomial,
    exponential_smooth,
    interpolate_gaps,
    preprocess_signal,
    rolling_smooth,
)
from signals.validation import (
    Severity,
    ValidationResult,
    ValidationWarning,
    check_data_range,
    check_minimum_length,
    detect_artifacts,
    detect_missing_data,
    validate_signal,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def clean_hr_series() -> pd.Series:
    """Clean heart rate data — 120 samples, realistic values."""
    np.random.seed(42)
    base = 140 + np.cumsum(np.random.normal(0, 1, 120))
    return pd.Series(base, name="heartrate")


@pytest.fixture
def clean_power_series() -> pd.Series:
    """Clean power data — 120 samples, steady state around 240W."""
    np.random.seed(42)
    base = 240 + np.random.normal(0, 5, 120)
    return pd.Series(base, name="watts")


@pytest.fixture
def clean_smo2_series() -> pd.Series:
    """Clean SmO2 data — 120 samples, decreasing trend."""
    np.random.seed(42)
    base = 70 - np.linspace(0, 15, 120) + np.random.normal(0, 0.5, 120)
    return pd.Series(base, name="smo2")


# ============================================================
# Validation Tests
# ============================================================


class TestDetectMissingData:
    def test_clean_signal_returns_none(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        assert detect_missing_data(s) is None

    def test_none_series_returns_error(self) -> None:
        result = detect_missing_data(None)
        assert result is not None
        assert result.severity == Severity.ERROR
        assert result.code == "EMPTY_SIGNAL"

    def test_excessive_missing_data(self) -> None:
        s = pd.Series([1.0, np.nan, np.nan, np.nan, np.nan, np.nan, 6.0])
        result = detect_missing_data(s)
        assert result is not None
        assert result.code == "EXCESSIVE_MISSING_DATA"
        assert result.severity in (Severity.WARNING, Severity.ERROR)

    def test_minor_missing_returns_info(self) -> None:
        s = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = detect_missing_data(s)
        assert result is not None
        assert result.code == "MISSING_DATA"
        assert result.severity == Severity.INFO


class TestDetectArtifacts:
    def test_clean_signal_no_artifacts(self) -> None:
        s = pd.Series(np.sin(np.linspace(0, 10, 100)))
        indices, warning = detect_artifacts(s)
        assert warning is None
        assert indices == []

    def test_series_with_spike(self) -> None:
        data = np.ones(50)
        data[25] = 100.0  # big spike
        s = pd.Series(data)
        indices, warning = detect_artifacts(s)
        assert warning is not None
        assert len(indices) > 0
        assert 25 in indices

    def test_short_series_returns_none(self) -> None:
        s = pd.Series([1.0, 2.0])
        indices, warning = detect_artifacts(s)
        assert warning is None


class TestCheckMinimumLength:
    def test_long_enough_returns_none(self) -> None:
        s = pd.Series(range(50))
        assert check_minimum_length(s, min_length=30) is None

    def test_too_short_returns_error(self) -> None:
        s = pd.Series(range(10))
        result = check_minimum_length(s, min_length=30)
        assert result is not None
        assert result.code == "SIGNAL_TOO_SHORT"
        assert result.severity == Severity.ERROR

    def test_none_returns_error(self) -> None:
        result = check_minimum_length(None)
        assert result is not None
        assert result.code == "NULL_SIGNAL"


class TestCheckDataRange:
    def test_in_range_returns_none(self) -> None:
        s = pd.Series([60.0, 80.0, 100.0, 120.0, 140.0])
        assert check_data_range(s, valid_range=(40, 200)) is None

    def test_out_of_range_returns_warning(self) -> None:
        s = pd.Series([60.0, 80.0, 100.0, 250.0, 120.0])
        result = check_data_range(s, valid_range=(40, 200))
        assert result is not None
        assert result.code == "OUT_OF_RANGE"

    def test_no_range_returns_none(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        assert check_data_range(s, valid_range=None) is None


class TestValidateSignal:
    def test_valid_signal(self) -> None:
        np.random.seed(0)
        s = pd.Series(np.random.normal(100, 10, 100))
        result = validate_signal(s, valid_range=(50, 150))
        assert result.is_valid is True

    def test_short_invalid_signal(self) -> None:
        s = pd.Series([1.0, 2.0])
        result = validate_signal(s, min_length=30)
        assert result.is_valid is False
        assert result.has_errors() is True

    def test_stats_populated(self) -> None:
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = validate_signal(s, min_length=3)
        assert result.stats["length"] == 5
        assert result.stats["mean"] == pytest.approx(30.0)

    def test_never_raises(self) -> None:
        """validate_signal should catch all exceptions internally."""
        result = validate_signal(None)
        assert isinstance(result, ValidationResult)


# ============================================================
# Preprocessing Tests
# ============================================================


class TestRollingSmooth:
    def test_smoothed_is_smoother(self) -> None:
        np.random.seed(0)
        noisy = pd.Series(np.random.normal(0, 10, 200))
        result = rolling_smooth(noisy, window=20)
        assert isinstance(result, SeriesResult)
        assert len(result.data) == len(noisy)
        assert result.method == "rolling_smooth"
        # Smoothed data should have less variance
        assert result.data.std() < noisy.std()

    def test_empty_series(self) -> None:
        result = rolling_smooth(pd.Series(dtype=float))
        assert len(result.data) == 0

    def test_median_method(self) -> None:
        np.random.seed(0)
        noisy = pd.Series(np.random.normal(0, 10, 100))
        result = rolling_smooth(noisy, window=10, method="median")
        assert result.parameters["method"] == "median"


class TestExponentialSmooth:
    def test_returns_series_result(self) -> None:
        s = pd.Series(range(50))
        result = exponential_smooth(s, alpha=0.3)
        assert isinstance(result, SeriesResult)
        assert result.method == "exponential_smooth"
        assert len(result.data) == 50

    def test_empty_series(self) -> None:
        result = exponential_smooth(pd.Series(dtype=float))
        assert len(result.data) == 0


class TestDetrendLinear:
    def test_removes_linear_trend(self) -> None:
        # Create series with known upward trend
        trend = np.linspace(0, 100, 100)
        s = pd.Series(trend + np.random.normal(0, 1, 100))
        result = detrend_linear(s)
        assert isinstance(result, SeriesResult)
        # Detrended series should have near-zero slope (mean close to 0)
        assert abs(result.data.mean()) < 10

    def test_short_series(self) -> None:
        s = pd.Series([1.0])
        result = detrend_linear(s)
        assert result.parameters["slope"] == 0


class TestDetrendPolynomial:
    def test_removes_quadratic_trend(self) -> None:
        x = np.linspace(-5, 5, 200)
        s = pd.Series(x**2 + np.random.normal(0, 0.5, 200))
        result = detrend_polynomial(s, degree=2)
        assert result.method == "detrend_polynomial"
        assert result.parameters["degree"] == 2


class TestInterpolateGaps:
    def test_fills_small_gaps(self) -> None:
        s = pd.Series([1.0, 2.0, np.nan, np.nan, 5.0, 6.0])
        result = interpolate_gaps(s, method="linear", max_gap=5)
        assert result.data.isna().sum() == 0

    def test_preserves_large_gaps(self) -> None:
        s = pd.Series([1.0] + [np.nan] * 10 + [12.0])
        result = interpolate_gaps(s, method="linear", max_gap=3)
        # Large gap should remain NaN
        assert result.data.isna().sum() > 0

    def test_reports_gaps_filled(self) -> None:
        s = pd.Series([1.0, np.nan, 3.0])
        result = interpolate_gaps(s)
        assert result.parameters["gaps_filled"] == 1


class TestPreprocessSignal:
    def test_full_pipeline(self) -> None:
        np.random.seed(0)
        noisy = pd.Series(np.random.normal(50, 5, 200))
        noisy.iloc[10:13] = np.nan  # small gap
        result = preprocess_signal(noisy, interpolate=True, smooth=True, detrend=False)
        assert isinstance(result, SeriesResult)
        assert result.method == "preprocess_signal"
        # Should have filled the gap
        assert result.data.isna().sum() < noisy.isna().sum()

    def test_no_processing(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        result = preprocess_signal(s, interpolate=False, smooth=False, detrend=False)
        # Data should be unchanged
        assert result.data.equals(s)


class TestSignalQualityFlags:
    def test_clean_signal_usable(self) -> None:
        s = pd.Series(np.random.normal(100, 5, 200))
        flags = SignalQualityFlags.from_series(s)
        assert bool(flags.is_usable) is True
        assert flags.valid_ratio == 1.0

    def test_empty_signal_not_usable(self) -> None:
        flags = SignalQualityFlags.from_series(pd.Series(dtype=float))
        assert flags.is_usable is False
        assert flags.valid_ratio == 0.0

    def test_gappy_signal(self) -> None:
        s = pd.Series([1.0] * 5 + [np.nan] * 5 + [1.0] * 5)
        flags = SignalQualityFlags.from_series(s)
        assert flags.gap_count >= 1
        assert flags.valid_ratio == pytest.approx(0.667, abs=0.01)


# ============================================================
# Conflict Detection Tests
# ============================================================


class TestDetectCardiacDrift:
    def test_no_drift_stable_efficiency(self) -> None:
        hr = pd.Series(np.full(120, 150.0))
        power = pd.Series(np.full(120, 250.0))
        assert detect_cardiac_drift(hr, power) is None

    def test_drift_detected(self) -> None:
        """HR increasing while power is stable should trigger drift."""
        hr = pd.Series(np.linspace(140, 160, 120))  # rising HR
        power = pd.Series(np.full(120, 250.0))  # stable power
        result = detect_cardiac_drift(hr, power)
        assert result is not None
        assert result.conflict_type == ConflictType.CARDIAC_DRIFT

    def test_short_data_returns_none(self) -> None:
        hr = pd.Series([150.0] * 10)
        power = pd.Series([250.0] * 10)
        assert detect_cardiac_drift(hr, power) is None

    def test_none_inputs(self) -> None:
        assert detect_cardiac_drift(None, pd.Series([1.0])) is None
        assert detect_cardiac_drift(pd.Series([1.0]), None) is None


class TestDetectSmo2PowerConflict:
    def test_no_conflict_decreasing_smo2(self) -> None:
        smo2 = pd.Series(np.linspace(70, 55, 120))
        power = pd.Series(np.linspace(200, 300, 120))
        assert detect_smo2_power_conflict(smo2, power) is None

    def test_conflict_rising_smo2_with_power(self) -> None:
        """Both SmO2 and Power rising = unusual direction conflict."""
        smo2 = pd.Series(np.linspace(55, 70, 120))
        power = pd.Series(np.linspace(200, 350, 120))
        result = detect_smo2_power_conflict(smo2, power)
        assert result is not None
        assert result.conflict_type == ConflictType.DIRECTION_CONFLICT

    def test_short_data_returns_none(self) -> None:
        smo2 = pd.Series(range(10))
        power = pd.Series(range(10))
        assert detect_smo2_power_conflict(smo2, power) is None


class TestDetectDfaAnomaly:
    def test_no_anomaly_normal_values(self) -> None:
        dfa = pd.Series(np.random.uniform(0.5, 0.8, 100))
        power = pd.Series(np.random.uniform(100, 350, 100))
        assert detect_dfa_anomaly(dfa, power) is None

    def test_anomaly_high_dfa(self) -> None:
        """DFA > 1.0 at high power should be flagged."""
        dfa = pd.Series(np.where(np.arange(100) > 70, 1.2, 0.7))
        power = pd.Series(np.linspace(100, 350, 100))
        result = detect_dfa_anomaly(dfa, power)
        assert result is not None
        assert result.conflict_type == ConflictType.DFA_ANOMALY


class TestDetectDecoupling:
    def test_correlated_signals_no_conflict(self) -> None:
        a = pd.Series(np.linspace(0, 100, 100))
        b = pd.Series(np.linspace(0, 100, 100))
        assert detect_decoupling(a, b, "A", "B") is None

    def test_uncorrelated_signals_conflict(self) -> None:
        np.random.seed(0)
        a = pd.Series(np.random.normal(0, 1, 100))
        b = pd.Series(np.random.normal(0, 1, 100))
        result = detect_decoupling(a, b, "A", "B")
        assert result is not None
        assert result.conflict_type == ConflictType.DECOUPLING


class TestDetectSignalConflicts:
    def test_no_conflicts_clean_data(self) -> None:
        df = pd.DataFrame(
            {
                "heartrate": np.full(100, 150.0),
                "watts": np.full(100, 250.0),
            }
        )
        result = detect_signal_conflicts(df)
        assert isinstance(result, ConflictAnalysisResult)
        assert result.has_conflicts is False
        assert result.agreement_score == 1.0

    def test_missing_columns_handled(self) -> None:
        df = pd.DataFrame({"heartrate": np.full(100, 150.0)})
        result = detect_signal_conflicts(df)
        assert isinstance(result, ConflictAnalysisResult)
        assert "HR" in result.signals_analyzed

    def test_conflicts_reduce_agreement_score(
        self, clean_hr_series: pd.Series, clean_power_series: pd.Series
    ) -> None:
        """Inject drift and verify agreement drops."""
        hr_drifting = clean_hr_series.copy()
        hr_drifting.iloc[60:] = clean_hr_series.iloc[60:] + 20  # drift up
        df = pd.DataFrame({"heartrate": hr_drifting, "watts": clean_power_series})
        result = detect_signal_conflicts(df)
        assert result.has_conflicts is True
        assert result.agreement_score < 1.0
