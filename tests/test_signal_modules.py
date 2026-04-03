# tests/test_signals.py
"""Comprehensive tests for signal validation, preprocessing, and conflict detection.

All tests use synthetic data — no external files or network required.
"""

import numpy as np
import pandas as pd
import pytest

from signals.conflicts import (
    ConflictAnalysisResult,
    ConflictSeverity,
    ConflictType,
    SignalConflict,
    detect_cardiac_drift,
    detect_decoupling,
    detect_dfa_anomaly,
    detect_signal_conflicts,
    detect_smo2_power_conflict,
)
from signals.preprocessing import (
    SeriesResult,
    SignalQualityFlags,
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
def clean_hr() -> pd.Series:
    np.random.seed(42)
    return pd.Series(140 + np.cumsum(np.random.normal(0, 1, 120)), name="heartrate")


@pytest.fixture
def clean_power() -> pd.Series:
    np.random.seed(42)
    return pd.Series(240 + np.random.normal(0, 5, 120), name="watts")


@pytest.fixture
def clean_smo2() -> pd.Series:
    np.random.seed(42)
    return pd.Series(70 - np.linspace(0, 15, 120) + np.random.normal(0, 0.5, 120), name="smo2")


@pytest.fixture
def noisy_signal() -> pd.Series:
    np.random.seed(0)
    return pd.Series(np.random.normal(100, 10, 200), name="signal")


@pytest.fixture
def signal_with_gaps() -> pd.Series:
    s = pd.Series(np.arange(1.0, 51.0))
    s.iloc[10:13] = np.nan
    s.iloc[30:35] = np.nan
    return s


# ============================================================
# Validation: detect_missing_data
# ============================================================


class TestDetectMissingData:
    def test_clean_signal_no_warning(self) -> None:
        assert detect_missing_data(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])) is None

    def test_none_series_returns_error(self) -> None:
        result = detect_missing_data(None)
        assert result is not None
        assert result.severity == Severity.ERROR
        assert result.code == "EMPTY_SIGNAL"

    def test_empty_series_returns_error(self) -> None:
        result = detect_missing_data(pd.Series([], dtype=float))
        assert result is not None
        assert result.code == "EMPTY_SIGNAL"

    def test_excessive_missing_returns_warning_or_error(self) -> None:
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

    def test_all_nan_returns_error(self) -> None:
        result = detect_missing_data(pd.Series([np.nan] * 10))
        assert result is not None
        assert result.code == "EXCESSIVE_MISSING_DATA"
        assert result.severity == Severity.ERROR

    @pytest.mark.parametrize(
        "ratio,expected_severity",
        [
            (0.21, Severity.WARNING),
            (0.49, Severity.WARNING),
            (0.51, Severity.ERROR),
            (0.8, Severity.ERROR),
        ],
    )
    def test_missing_ratio_severity_thresholds(
        self, ratio: float, expected_severity: Severity
    ) -> None:
        n = 100
        n_missing = int(n * ratio)
        data = [1.0] * (n - n_missing) + [np.nan] * n_missing
        np.random.shuffle(data)
        result = detect_missing_data(pd.Series(data), max_missing_ratio=0.2)
        assert result is not None
        assert result.severity == expected_severity


# ============================================================
# Validation: detect_artifacts
# ============================================================


class TestDetectArtifacts:
    def test_clean_signal_no_artifacts(self) -> None:
        s = pd.Series(np.sin(np.linspace(0, 10, 100)))
        indices, warning = detect_artifacts(s)
        assert warning is None
        assert indices == []

    def test_series_with_spike(self) -> None:
        data = np.ones(50)
        data[25] = 100.0
        s = pd.Series(data)
        indices, warning = detect_artifacts(s)
        assert warning is not None
        assert len(indices) > 0
        assert 25 in indices

    def test_short_series_returns_none(self) -> None:
        indices, warning = detect_artifacts(pd.Series([1.0, 2.0]))
        assert warning is None
        assert indices == []

    def test_none_series(self) -> None:
        indices, warning = detect_artifacts(None)
        assert warning is None
        assert indices == []

    def test_constant_series_no_artifacts(self) -> None:
        s = pd.Series([5.0] * 50)
        indices, warning = detect_artifacts(s)
        assert warning is None

    def test_artifact_ratio_threshold(self) -> None:
        data = np.ones(100)
        for i in range(0, 100, 2):
            data[i] = 50.0
        s = pd.Series(data)
        indices, warning = detect_artifacts(s)
        assert warning is not None
        ratio = len(indices) / len(s)
        assert warning.details is not None
        assert warning.details["artifact_ratio"] == pytest.approx(ratio, abs=0.05)

    def test_custom_spike_threshold(self) -> None:
        np.random.seed(0)
        s = pd.Series(np.random.normal(100, 1, 200))
        s.iloc[100] = 105.0
        _, warning_strict = detect_artifacts(s, z_threshold=3.0, spike_threshold=0.01)
        _, warning_loose = detect_artifacts(s, z_threshold=10.0, spike_threshold=1.0)
        assert warning_strict is not None
        assert warning_loose is None


# ============================================================
# Validation: check_minimum_length
# ============================================================


class TestCheckMinimumLength:
    def test_long_enough_returns_none(self) -> None:
        assert check_minimum_length(pd.Series(range(50)), min_length=30) is None

    def test_too_short_returns_error(self) -> None:
        result = check_minimum_length(pd.Series(range(10)), min_length=30)
        assert result is not None
        assert result.code == "SIGNAL_TOO_SHORT"
        assert result.severity == Severity.ERROR

    def test_none_returns_error(self) -> None:
        result = check_minimum_length(None)
        assert result is not None
        assert result.code == "NULL_SIGNAL"

    def test_exact_length_returns_none(self) -> None:
        assert check_minimum_length(pd.Series(range(30)), min_length=30) is None

    @pytest.mark.parametrize(
        "length,threshold,should_pass",
        [
            (29, 30, False),
            (30, 30, True),
            (100, 30, True),
            (0, 30, False),
        ],
    )
    def test_length_boundary(self, length: int, threshold: int, should_pass: bool) -> None:
        result = check_minimum_length(pd.Series(range(length)), min_length=threshold)
        if should_pass:
            assert result is None
        else:
            assert result is not None


# ============================================================
# Validation: check_data_range
# ============================================================


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
        assert check_data_range(pd.Series([1.0, 2.0, 3.0]), valid_range=None) is None

    def test_none_series_returns_none(self) -> None:
        assert check_data_range(None, valid_range=(0, 100)) is None

    def test_empty_series_returns_none(self) -> None:
        assert check_data_range(pd.Series([], dtype=float), valid_range=(0, 100)) is None

    def test_all_nan_returns_none(self) -> None:
        assert check_data_range(pd.Series([np.nan] * 10), valid_range=(0, 100)) is None

    def test_severity_based_on_ratio(self) -> None:
        mostly_ok = pd.Series([60.0] * 95 + [999.0] * 5)
        result = check_data_range(mostly_ok, valid_range=(0, 100))
        assert result is not None
        assert result.severity == Severity.WARNING

    def test_custom_column_name(self) -> None:
        s = pd.Series([60.0, 999.0])
        result = check_data_range(s, valid_range=(0, 100), column_name="heartrate")
        assert result is not None
        assert "heartrate" in result.message


# ============================================================
# Validation: validate_signal (integration)
# ============================================================


class TestValidateSignal:
    def test_valid_signal(self) -> None:
        np.random.seed(0)
        s = pd.Series(np.random.normal(100, 10, 100))
        result = validate_signal(s, valid_range=(50, 150))
        assert result.is_valid is True

    def test_short_invalid_signal(self) -> None:
        result = validate_signal(pd.Series([1.0, 2.0]), min_length=30)
        assert result.is_valid is False
        assert result.has_errors() is True

    def test_stats_populated(self) -> None:
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = validate_signal(s, min_length=3)
        assert result.stats["length"] == 5
        assert result.stats["mean"] == pytest.approx(30.0)

    def test_never_raises(self) -> None:
        result = validate_signal(None)
        assert isinstance(result, ValidationResult)

    def test_has_warnings_method(self) -> None:
        s = pd.Series([1.0, 2.0, np.nan, 4.0] * 10)
        result = validate_signal(s, min_length=3)
        assert isinstance(result.has_warnings(), bool)

    def test_get_messages_method(self) -> None:
        s = pd.Series([1.0, 2.0] * 5)
        result = validate_signal(s, min_length=30)
        messages = result.get_messages()
        assert isinstance(messages, list)

    def test_artifact_indices_populated(self) -> None:
        data = np.ones(100)
        data[50] = 100.0
        result = validate_signal(pd.Series(data), min_length=3)
        assert len(result.artifact_indices) > 0

    def test_valid_range_check(self) -> None:
        s = pd.Series([60.0, 80.0, 300.0, 100.0] * 10)
        result = validate_signal(s, valid_range=(0, 200))
        assert result.is_valid is False


# ============================================================
# Preprocessing: rolling_smooth
# ============================================================


class TestRollingSmooth:
    def test_smoothed_has_less_variance(self, noisy_signal: pd.Series) -> None:
        result = rolling_smooth(noisy_signal, window=20)
        assert isinstance(result, SeriesResult)
        assert len(result.data) == len(noisy_signal)
        assert result.data.std() < noisy_signal.std()

    def test_empty_series(self) -> None:
        result = rolling_smooth(pd.Series(dtype=float))
        assert len(result.data) == 0

    def test_median_method(self, noisy_signal: pd.Series) -> None:
        result = rolling_smooth(noisy_signal, window=10, method="median")
        assert result.parameters["method"] == "median"

    def test_method_field(self, noisy_signal: pd.Series) -> None:
        result = rolling_smooth(noisy_signal)
        assert result.method == "rolling_smooth"

    def test_parameters_recorded(self, noisy_signal: pd.Series) -> None:
        result = rolling_smooth(noisy_signal, window=15, center=True)
        assert result.parameters["window"] == 15
        assert result.parameters["center"] is True

    def test_none_series(self) -> None:
        result = rolling_smooth(None)
        assert len(result.data) == 0

    def test_preserves_length(self, noisy_signal: pd.Series) -> None:
        result = rolling_smooth(noisy_signal, window=30, center=True)
        assert len(result.data) == len(noisy_signal)


# ============================================================
# Preprocessing: exponential_smooth
# ============================================================


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

    def test_none_series(self) -> None:
        result = exponential_smooth(None)
        assert len(result.data) == 0

    def test_alpha_parameter(self) -> None:
        s = pd.Series(range(100))
        result = exponential_smooth(s, alpha=0.1)
        assert result.parameters["alpha"] == 0.1

    def test_adjust_parameter(self) -> None:
        s = pd.Series(range(100))
        result = exponential_smooth(s, alpha=0.3, adjust=False)
        assert result.parameters["adjust"] is False


# ============================================================
# Preprocessing: detrend_linear
# ============================================================


class TestDetrendLinear:
    def test_removes_linear_trend(self) -> None:
        trend = np.linspace(0, 100, 100)
        s = pd.Series(trend + np.random.normal(0, 1, 100))
        result = detrend_linear(s)
        assert isinstance(result, SeriesResult)
        assert abs(result.data.mean()) < 10

    def test_short_series(self) -> None:
        result = detrend_linear(pd.Series([1.0]))
        assert result.parameters["slope"] == 0

    def test_empty_series(self) -> None:
        result = detrend_linear(pd.Series(dtype=float))
        assert len(result.data) == 0

    def test_slope_recorded(self) -> None:
        s = pd.Series(np.linspace(0, 50, 100))
        result = detrend_linear(s)
        assert "slope" in result.parameters
        assert result.parameters["slope"] > 0

    def test_none_series(self) -> None:
        result = detrend_linear(None)
        assert len(result.data) == 0


# ============================================================
# Preprocessing: detrend_polynomial
# ============================================================


class TestDetrendPolynomial:
    def test_removes_quadratic_trend(self) -> None:
        x = np.linspace(-5, 5, 200)
        s = pd.Series(x**2 + np.random.normal(0, 0.5, 200))
        result = detrend_polynomial(s, degree=2)
        assert result.method == "detrend_polynomial"
        assert result.parameters["degree"] == 2

    def test_empty_series(self) -> None:
        result = detrend_polynomial(pd.Series(dtype=float))
        assert len(result.data) == 0

    def test_none_series(self) -> None:
        result = detrend_polynomial(None)
        assert len(result.data) == 0

    def test_insufficient_points_for_degree(self) -> None:
        s = pd.Series([1.0, 2.0])
        result = detrend_polynomial(s, degree=3)
        assert result.parameters["coefficients"] == []


# ============================================================
# Preprocessing: interpolate_gaps
# ============================================================


class TestInterpolateGaps:
    def test_fills_small_gaps(self) -> None:
        s = pd.Series([1.0, 2.0, np.nan, np.nan, 5.0, 6.0])
        result = interpolate_gaps(s, method="linear", max_gap=5)
        assert result.data.isna().sum() == 0

    def test_preserves_large_gaps(self) -> None:
        s = pd.Series([1.0] + [np.nan] * 10 + [12.0])
        result = interpolate_gaps(s, method="linear", max_gap=3)
        assert result.data.isna().sum() > 0

    def test_reports_gaps_filled(self) -> None:
        s = pd.Series([1.0, np.nan, 3.0])
        result = interpolate_gaps(s)
        assert result.parameters["gaps_filled"] == 1

    def test_empty_series(self) -> None:
        result = interpolate_gaps(pd.Series(dtype=float))
        assert len(result.data) == 0

    def test_no_gaps_unchanged(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = interpolate_gaps(s)
        assert result.data.equals(s)

    @pytest.mark.parametrize("method", ["linear", "nearest", "zero"])
    def test_interpolation_methods(self, method: str) -> None:
        s = pd.Series([1.0, np.nan, 3.0])
        result = interpolate_gaps(s, method=method, max_gap=5)
        assert result.data.isna().sum() == 0
        assert result.parameters["method"] == method

    def test_none_series(self) -> None:
        result = interpolate_gaps(None)
        assert len(result.data) == 0


# ============================================================
# Preprocessing: preprocess_signal (pipeline)
# ============================================================


class TestPreprocessSignal:
    def test_full_pipeline(self, noisy_signal: pd.Series) -> None:
        noisy_signal.iloc[10:13] = np.nan
        result = preprocess_signal(noisy_signal, interpolate=True, smooth=True, detrend=False)
        assert isinstance(result, SeriesResult)
        assert result.method == "preprocess_signal"
        assert result.data.isna().sum() < noisy_signal.isna().sum()

    def test_no_processing(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        result = preprocess_signal(s, interpolate=False, smooth=False, detrend=False)
        assert result.data.equals(s)

    def test_smooth_only(self, noisy_signal: pd.Series) -> None:
        result = preprocess_signal(noisy_signal, interpolate=False, smooth=True, detrend=False)
        assert result.data.std() < noisy_signal.std()

    def test_detrend_option(self) -> None:
        trend = pd.Series(np.linspace(0, 50, 100) + np.random.normal(0, 1, 100))
        result = preprocess_signal(trend, interpolate=False, smooth=False, detrend=True)
        assert abs(result.data.mean()) < abs(trend.mean())

    def test_ewma_smooth_method(self, noisy_signal: pd.Series) -> None:
        result = preprocess_signal(
            noisy_signal, smooth=True, smooth_method="ewma", smooth_window=20
        )
        assert result.parameters["smooth_method"] == "ewma"

    def test_median_smooth_method(self, noisy_signal: pd.Series) -> None:
        result = preprocess_signal(
            noisy_signal, smooth=True, smooth_method="median", smooth_window=10
        )
        assert result.parameters["smooth_method"] == "median"

    def test_parameters_recorded(self) -> None:
        s = pd.Series(range(50))
        result = preprocess_signal(s, interpolate=True, smooth=True, detrend=True)
        assert result.parameters["interpolate"] is True
        assert result.parameters["smooth"] is True
        assert result.parameters["detrend"] is True


# ============================================================
# Preprocessing: SignalQualityFlags
# ============================================================


class TestSignalQualityFlags:
    def test_clean_signal_usable(self) -> None:
        s = pd.Series(np.random.normal(100, 5, 200))
        flags = SignalQualityFlags.from_series(s)
        assert bool(flags.is_usable) is True
        assert flags.valid_ratio == pytest.approx(1.0)

    def test_empty_signal_not_usable(self) -> None:
        flags = SignalQualityFlags.from_series(pd.Series(dtype=float))
        assert bool(flags.is_usable) is False
        assert flags.valid_ratio == 0.0

    def test_gappy_signal(self) -> None:
        s = pd.Series([1.0] * 5 + [np.nan] * 5 + [1.0] * 5)
        flags = SignalQualityFlags.from_series(s)
        assert flags.gap_count >= 1
        assert flags.valid_ratio == pytest.approx(0.667, abs=0.01)

    def test_none_signal(self) -> None:
        flags = SignalQualityFlags.from_series(None)
        assert flags.is_usable is False
        assert flags.valid_ratio == 0.0

    def test_max_gap_duration(self) -> None:
        s = pd.Series([1.0] * 5 + [np.nan] * 10 + [1.0] * 5)
        flags = SignalQualityFlags.from_series(s)
        assert flags.max_gap_duration == 10

    def test_noise_level_clean(self) -> None:
        s = pd.Series(np.linspace(0, 100, 200))
        flags = SignalQualityFlags.from_series(s)
        assert flags.noise_level < 0.3

    def test_custom_thresholds(self) -> None:
        s = pd.Series([1.0] * 10 + [np.nan] * 90)
        flags = SignalQualityFlags.from_series(s, min_valid_ratio=0.5, max_noise_level=0.5)
        assert bool(flags.is_usable) is False


# ============================================================
# Conflicts: detect_cardiac_drift
# ============================================================
# Conflicts: detect_cardiac_drift
# ============================================================


class TestDetectCardiacDrift:
    def test_no_drift_stable_efficiency(self) -> None:
        hr = pd.Series(np.full(120, 150.0))
        power = pd.Series(np.full(120, 250.0))
        assert detect_cardiac_drift(hr, power) is None

    def test_drift_detected(self) -> None:
        hr = pd.Series(np.linspace(140, 160, 120))
        power = pd.Series(np.full(120, 250.0))
        result = detect_cardiac_drift(hr, power)
        assert result is not None
        assert result.conflict_type == ConflictType.CARDIAC_DRIFT

    def test_short_data_returns_none(self) -> None:
        assert detect_cardiac_drift(pd.Series([150.0] * 10), pd.Series([250.0] * 10)) is None

    def test_none_inputs(self) -> None:
        assert detect_cardiac_drift(None, pd.Series([1.0])) is None
        assert detect_cardiac_drift(pd.Series([1.0]), None) is None

    def test_severity_levels(self) -> None:
        minor_drift = pd.Series(np.linspace(140, 143, 120))
        power = pd.Series(np.full(120, 250.0))
        result = detect_cardiac_drift(minor_drift, power, threshold_pct=0.01)
        if result is not None:
            assert result.severity in (
                ConflictSeverity.MINOR,
                ConflictSeverity.MAJOR,
                ConflictSeverity.CRITICAL,
            )

    def test_conflict_details(self) -> None:
        hr = pd.Series(np.linspace(140, 165, 120))
        power = pd.Series(np.full(120, 250.0))
        result = detect_cardiac_drift(hr, power)
        assert result is not None
        assert "drift_pct" in result.details


# ============================================================
# Conflicts: detect_smo2_power_conflict
# ============================================================


class TestDetectSmo2PowerConflict:
    def test_no_conflict_decreasing_smo2(self) -> None:
        smo2 = pd.Series(np.linspace(70, 55, 120))
        power = pd.Series(np.linspace(200, 300, 120))
        assert detect_smo2_power_conflict(smo2, power) is None

    def test_conflict_rising_smo2_with_power(self) -> None:
        smo2 = pd.Series(np.linspace(55, 70, 120))
        power = pd.Series(np.linspace(200, 350, 120))
        result = detect_smo2_power_conflict(smo2, power)
        assert result is not None
        assert result.conflict_type == ConflictType.DIRECTION_CONFLICT

    def test_short_data_returns_none(self) -> None:
        assert detect_smo2_power_conflict(pd.Series(range(10)), pd.Series(range(10))) is None

    def test_none_inputs(self) -> None:
        assert detect_smo2_power_conflict(None, pd.Series([1.0])) is None
        assert detect_smo2_power_conflict(pd.Series([1.0]), None) is None

    def test_affected_zones_populated(self) -> None:
        smo2 = pd.Series(np.linspace(55, 70, 120))
        power = pd.Series(np.linspace(200, 350, 120))
        result = detect_smo2_power_conflict(smo2, power)
        assert result is not None
        assert "VT1" in result.affected_zones
        assert "VT2" in result.affected_zones


# ============================================================
# Conflicts: detect_dfa_anomaly
# ============================================================


class TestDetectDfaAnomaly:
    def test_no_anomaly_normal_values(self) -> None:
        dfa = pd.Series(np.random.uniform(0.5, 0.8, 100))
        power = pd.Series(np.random.uniform(100, 350, 100))
        assert detect_dfa_anomaly(dfa, power) is None

    def test_anomaly_high_dfa(self) -> None:
        dfa = pd.Series(np.where(np.arange(100) > 70, 1.2, 0.7))
        power = pd.Series(np.linspace(100, 350, 100))
        result = detect_dfa_anomaly(dfa, power)
        assert result is not None
        assert result.conflict_type == ConflictType.DFA_ANOMALY

    def test_short_data_returns_none(self) -> None:
        assert detect_dfa_anomaly(pd.Series(range(5)), pd.Series(range(5))) is None

    def test_none_inputs(self) -> None:
        assert detect_dfa_anomaly(None, pd.Series([1.0])) is None
        assert detect_dfa_anomaly(pd.Series([1.0]), None) is None

    def test_zero_power_returns_none(self) -> None:
        dfa = pd.Series([1.2] * 20)
        power = pd.Series([0.0] * 20)
        assert detect_dfa_anomaly(dfa, power) is None


# ============================================================
# Conflicts: detect_decoupling
# ============================================================


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

    def test_short_data_returns_none(self) -> None:
        assert detect_decoupling(pd.Series(range(10)), pd.Series(range(10)), "A", "B") is None

    def test_none_inputs(self) -> None:
        assert detect_decoupling(None, pd.Series([1.0]), "A", "B") is None
        assert detect_decoupling(pd.Series([1.0]), None, "A", "B") is None

    def test_correlation_in_details(self) -> None:
        np.random.seed(0)
        a = pd.Series(np.random.normal(0, 1, 100))
        b = pd.Series(np.random.normal(0, 1, 100))
        result = detect_decoupling(a, b, "A", "B")
        assert result is not None
        assert "correlation" in result.details


# ============================================================
# Conflicts: detect_signal_conflicts (integration)
# ============================================================


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

    def test_conflicts_reduce_agreement(self, clean_hr: pd.Series, clean_power: pd.Series) -> None:
        hr_drifting = clean_hr.copy()
        hr_drifting.iloc[60:] = clean_hr.iloc[60:] + 20
        df = pd.DataFrame({"heartrate": hr_drifting, "watts": clean_power})
        result = detect_signal_conflicts(df)
        assert result.has_conflicts is True
        assert result.agreement_score < 1.0

    def test_all_signals_analyzed(self) -> None:
        df = pd.DataFrame(
            {
                "heartrate": np.full(100, 150.0),
                "watts": np.full(100, 250.0),
                "smo2": np.full(100, 65.0),
                "alpha1": np.full(100, 0.7),
            }
        )
        result = detect_signal_conflicts(df)
        assert len(result.signals_analyzed) == 4

    def test_summary_no_conflicts(self) -> None:
        df = pd.DataFrame({"heartrate": np.full(100, 150.0)})
        result = detect_signal_conflicts(df)
        assert "zgodne" in result.get_summary()

    def test_recommendations_generated(self, clean_hr: pd.Series, clean_power: pd.Series) -> None:
        hr_drifting = clean_hr.copy()
        hr_drifting.iloc[60:] = clean_hr.iloc[60:] + 30
        df = pd.DataFrame({"heartrate": hr_drifting, "watts": clean_power})
        result = detect_signal_conflicts(df)
        assert len(result.recommendations) > 0

    def test_get_critical_conflicts(self) -> None:
        df = pd.DataFrame(
            {
                "heartrate": np.linspace(140, 180, 120),
                "watts": np.full(120, 250.0),
            }
        )
        result = detect_signal_conflicts(df)
        critical = result.get_critical_conflicts()
        assert isinstance(critical, list)


# ============================================================
# Dataclass / Enum Tests
# ============================================================


class TestDataclasses:
    def test_validation_warning_str(self) -> None:
        w = ValidationWarning(code="TEST", message="test msg", severity=Severity.WARNING)
        s = str(w)
        assert "TEST" in s
        assert "test msg" in s

    def test_signal_conflict_str(self) -> None:
        c = SignalConflict(
            signal_a="HR",
            signal_b="Power",
            conflict_type=ConflictType.CARDIAC_DRIFT,
            severity=ConflictSeverity.MAJOR,
            description="test drift",
        )
        s = str(c)
        assert "HR" in s
        assert "Power" in s

    def test_conflict_analysis_result_summary_no_conflicts(self) -> None:
        r = ConflictAnalysisResult(has_conflicts=False)
        assert "zgodne" in r.get_summary()

    def test_conflict_analysis_result_summary_with_conflicts(self) -> None:
        r = ConflictAnalysisResult(
            has_conflicts=True,
            conflicts=[
                SignalConflict("A", "B", ConflictType.DECOUPLING, ConflictSeverity.MINOR, "x"),
                SignalConflict(
                    "C", "D", ConflictType.CARDIAC_DRIFT, ConflictSeverity.CRITICAL, "y"
                ),
            ],
        )
        summary = r.get_summary()
        assert "krytycznych" in summary
        assert "drobnych" in summary

    def test_series_result_quality(self) -> None:
        s = pd.Series(np.random.normal(100, 5, 200))
        result = SeriesResult(
            data=s,
            quality=SignalQualityFlags.from_series(s),
            method="test",
        )
        assert bool(result.quality.is_usable) is True

    def test_severity_enum_values(self) -> None:
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"

    def test_conflict_severity_enum_values(self) -> None:
        assert ConflictSeverity.MINOR.value == "minor"
        assert ConflictSeverity.MAJOR.value == "major"
        assert ConflictSeverity.CRITICAL.value == "critical"
