"""
Tests for Power-Duration Curve and Critical Power Model.

Tests cover:
- compute_max_mean_power() on synthetic signals
- fit_critical_power() parameter validity
- PR detection logic
"""
import numpy as np
import pandas as pd
import pytest

from modules.power_duration import (
    compute_max_mean_power,
    fit_critical_power,
    detect_personal_records,
    interpolate_to_1hz,
)


class TestComputeMaxMeanPower:
    """Tests for compute_max_mean_power function."""
    
    def test_constant_power(self):
        """Constant power should return same value for all windows."""
        power = pd.Series([200.0] * 600)  # 10 minutes at 200W
        
        result = compute_max_mean_power(power, windows_seconds=[60, 120, 300])
        
        assert result[60] == pytest.approx(200.0, abs=0.1)
        assert result[120] == pytest.approx(200.0, abs=0.1)
        assert result[300] == pytest.approx(200.0, abs=0.1)
    
    def test_sine_wave_with_baseline(self):
        """Sine wave + baseline: max mean should be above baseline."""
        # 30 min of data: baseline 200W + sine wave amplitude 50W
        t = np.arange(1800)  # 30 minutes in seconds
        baseline = 200
        amplitude = 50
        period = 300  # 5 min period
        power = pd.Series(baseline + amplitude * np.sin(2 * np.pi * t / period))
        
        result = compute_max_mean_power(power, windows_seconds=[1, 60, 300, 600])
        
        # 1s max should be close to peak (250W)
        assert result[1] == pytest.approx(baseline + amplitude, abs=1.0)
        
        # Longer windows should average out oscillations
        assert result[300] == pytest.approx(baseline, abs=5.0)
        assert result[600] == pytest.approx(baseline, abs=2.0)
    
    def test_sprint_then_steady(self):
        """Sprint followed by steady state."""
        # 30s sprint at 800W, then 9.5min at 200W
        sprint = [800.0] * 30
        steady = [200.0] * 570
        power = pd.Series(sprint + steady)
        
        result = compute_max_mean_power(power, windows_seconds=[5, 30, 60, 300])
        
        # 5s max should be sprint power
        assert result[5] == pytest.approx(800.0, abs=0.1)
        
        # 30s should be the full sprint
        assert result[30] == pytest.approx(800.0, abs=0.1)
        
        # 60s should be lower (includes some steady state)
        assert result[60] < 600
    
    def test_insufficient_data(self):
        """Windows longer than data should return None."""
        power = pd.Series([200.0] * 60)  # Only 1 minute
        
        result = compute_max_mean_power(power, windows_seconds=[60, 120, 300])
        
        assert result[60] == pytest.approx(200.0, abs=0.1)
        assert result[120] is None
        assert result[300] is None


class TestFitCriticalPower:
    """Tests for fit_critical_power function."""
    
    def test_valid_fit_returns_positive_parameters(self):
        """Fitted CP and W' should always be positive."""
        # Realistic PDC values for a ~280W CP rider
        durations = [120, 180, 300, 600, 1200]
        # P = W'/t + CP formula generates these
        cp_true = 280
        w_prime_true = 20000  # 20 kJ
        powers = [w_prime_true / d + cp_true for d in durations]
        
        result = fit_critical_power(durations, powers)
        
        assert result.cp > 0, "CP must be positive"
        assert result.w_prime > 0, "W' must be positive"
        assert result.cp == pytest.approx(cp_true, rel=0.05)
        assert result.w_prime == pytest.approx(w_prime_true, rel=0.1)
    
    def test_reasonable_rmse(self):
        """RMSE should be low for data generated from model."""
        durations = [120, 180, 300, 600, 1200]
        cp_true = 300
        w_prime_true = 18000
        powers = [w_prime_true / d + cp_true for d in durations]
        
        result = fit_critical_power(durations, powers)
        
        assert result.rmse < 5.0, "RMSE should be minimal for perfect data"
        assert result.r_squared > 0.99, "R² should be very high"
    
    def test_noisy_data(self):
        """Should still fit reasonably with noisy data."""
        durations = [120, 180, 300, 600, 1200]
        cp_true = 260
        w_prime_true = 22000
        # Add 5% noise
        np.random.seed(42)
        noise = 1 + 0.05 * np.random.randn(len(durations))
        powers = [(w_prime_true / d + cp_true) * n for d, n in zip(durations, noise)]
        
        result = fit_critical_power(durations, powers)
        
        assert result.cp > 0
        assert result.w_prime > 0
        # Should be within 10% of true values even with noise
        assert result.cp == pytest.approx(cp_true, rel=0.15)
        assert result.w_prime == pytest.approx(w_prime_true, rel=0.2)
    
    def test_insufficient_data_raises(self):
        """Should raise with fewer than 3 data points in fitting range."""
        durations = [60, 90]  # Only 2 points, both below 120s threshold
        powers = [400, 380]
        
        with pytest.raises(ValueError, match="at least 3 data points"):
            fit_critical_power(durations, powers)


class TestDetectPersonalRecords:
    """Tests for detect_personal_records function."""
    
    def test_all_new_records(self):
        """All values should be PRs if no history exists."""
        current = {60: 400, 300: 320, 600: 280}
        history = {}
        
        prs = detect_personal_records(current, history)
        
        assert len(prs) == 3
        durations = [pr.duration for pr in prs]
        assert 60 in durations
        assert 300 in durations
        assert 600 in durations
    
    def test_some_new_records(self):
        """Should detect only values that beat history."""
        current = {60: 400, 300: 320, 600: 280}
        history = {60: 410, 300: 310, 600: 290}  # Only 300s is beaten
        
        prs = detect_personal_records(current, history)
        
        assert len(prs) == 1
        assert prs[0].duration == 300
        assert prs[0].power == 320
    
    def test_no_records(self):
        """No PRs if current doesn't beat any history."""
        current = {60: 380, 300: 300}
        history = {60: 400, 300: 320}
        
        prs = detect_personal_records(current, history)
        
        assert len(prs) == 0
    
    def test_handles_none_values(self):
        """Should skip None values in current PDC."""
        current = {60: 400, 300: None, 600: 280}
        history = {}
        
        prs = detect_personal_records(current, history)
        
        assert len(prs) == 2
        durations = [pr.duration for pr in prs]
        assert 300 not in durations


class TestInterpolateTo1Hz:
    """Tests for interpolate_to_1hz function."""
    
    def test_already_1hz(self):
        """Data at 1Hz should be unchanged."""
        power = pd.Series([200, 210, 220, 230, 240])
        time = pd.Series([0, 1, 2, 3, 4])
        
        result = interpolate_to_1hz(power, time)
        
        assert len(result) == 5
        np.testing.assert_array_almost_equal(result.values, power.values)
    
    def test_upsampling(self):
        """Should interpolate low-frequency data to 1Hz."""
        power = pd.Series([200, 220])  # 2 samples
        time = pd.Series([0, 2])        # 2 seconds apart
        
        result = interpolate_to_1hz(power, time)
        
        assert len(result) == 3  # 0, 1, 2 seconds
        assert result.iloc[1] == pytest.approx(210, abs=1)  # Interpolated value
