"""
Tests for Physio Drift Maps module.

Tests cover:
- scatter_power_hr on synthetic data
- scatter_power_smo2 graceful degradation
- drift detection accuracy on known slopes
"""
import numpy as np
import pandas as pd

from modules.physio_maps import (
    scatter_power_hr,
    scatter_power_smo2,
    detect_constant_power_segments,
    trend_at_constant_power,
    calculate_drift_metrics,
)


class TestScatterPowerHR:
    """Tests for scatter_power_hr function."""
    
    def test_returns_figure_with_valid_data(self):
        """Should return a Plotly figure with valid power and HR data."""
        df = pd.DataFrame({
            'watts': np.random.uniform(150, 300, 600),
            'heartrate': np.random.uniform(120, 170, 600)
        })
        
        fig = scatter_power_hr(df)
        
        assert fig is not None
        assert len(fig.data) >= 2  # scatter + trendline
    
    def test_missing_hr_returns_none(self):
        """Should return None if HR column is missing."""
        df = pd.DataFrame({
            'watts': np.random.uniform(150, 300, 600)
        })
        
        fig = scatter_power_hr(df)
        
        assert fig is None
    
    def test_insufficient_data_returns_none(self):
        """Should return None if less than 10 data points."""
        df = pd.DataFrame({
            'watts': [200, 210, 220],
            'heartrate': [140, 142, 144]
        })
        
        fig = scatter_power_hr(df)
        
        assert fig is None


class TestScatterPowerSmO2:
    """Tests for scatter_power_smo2 function."""
    
    def test_graceful_degradation_without_smo2(self):
        """Should return None if SmO2 column is missing (graceful degradation)."""
        df = pd.DataFrame({
            'watts': np.random.uniform(150, 300, 600),
            'heartrate': np.random.uniform(120, 170, 600)
        })
        
        fig = scatter_power_smo2(df)
        
        assert fig is None
    
    def test_returns_figure_with_smo2(self):
        """Should return a figure when SmO2 data is available."""
        df = pd.DataFrame({
            'watts': np.random.uniform(150, 300, 600),
            'smo2': np.random.uniform(40, 70, 600)
        })
        
        fig = scatter_power_smo2(df)
        
        assert fig is not None


class TestDetectConstantPowerSegments:
    """Tests for detect_constant_power_segments function."""
    
    def test_finds_constant_segment(self):
        """Should find a segment of constant power."""
        # 5 minutes at 200W, then 5 minutes at 300W
        watts_200 = [200] * 300
        watts_300 = [300] * 300
        df = pd.DataFrame({'watts': watts_200 + watts_300})
        
        segments = detect_constant_power_segments(df, tolerance_pct=5, min_duration_sec=120)
        
        assert len(segments) >= 2
        # First segment should be around 200W
        assert 190 < segments[0][2] < 210
    
    def test_no_segments_in_variable_data(self):
        """Should find no segments in highly variable data."""
        np.random.seed(42)
        df = pd.DataFrame({
            'watts': np.random.uniform(100, 400, 600)  # Highly variable
        })
        
        segments = detect_constant_power_segments(df, tolerance_pct=5, min_duration_sec=120)
        
        # May find some by chance, but likely very few
        assert len(segments) <= 2


class TestTrendAtConstantPower:
    """Tests for trend_at_constant_power function."""
    
    def test_detects_hr_drift(self):
        """Should detect HR drift slope accurately."""
        # 10 minutes at 200W with HR increasing by 0.5 bpm/min
        time = np.arange(600)
        df = pd.DataFrame({
            'watts': [200] * 600,
            'heartrate': 140 + time / 60 * 0.5  # 0.5 bpm/min drift
        })
        
        fig, metrics = trend_at_constant_power(df, power_target=200, tolerance_pct=10)
        
        assert fig is not None
        assert metrics is not None
        assert metrics.hr_drift_slope is not None
        # Should be approximately 0.5 bpm/min (with some tolerance)
        assert 0.4 < metrics.hr_drift_slope < 0.6
    
    def test_detects_smo2_decline(self):
        """Should detect SmO2 decline slope accurately."""
        # 10 minutes at 250W with SmO2 declining by 0.3%/min
        time = np.arange(600)
        df = pd.DataFrame({
            'watts': [250] * 600,
            'heartrate': [150] * 600,
            'smo2': 60 - time / 60 * 0.3  # -0.3 %/min decline
        })
        
        fig, metrics = trend_at_constant_power(df, power_target=250, tolerance_pct=10)
        
        assert metrics is not None
        assert metrics.smo2_slope is not None
        # Should be approximately -0.3 %/min
        assert -0.35 < metrics.smo2_slope < -0.25


class TestCalculateDriftMetrics:
    """Tests for calculate_drift_metrics function."""
    
    def test_returns_correlations(self):
        """Should return power-HR correlation."""
        # Generate correlated data
        np.random.seed(42)
        power = np.random.uniform(150, 300, 600)
        hr = 100 + power * 0.3 + np.random.normal(0, 5, 600)  # HR correlated with power
        
        df = pd.DataFrame({'watts': power, 'heartrate': hr})
        
        metrics = calculate_drift_metrics(df)
        
        assert metrics['correlation_power_hr'] is not None
        assert metrics['correlation_power_hr'] > 0.5  # Should be positively correlated
    
    def test_handles_missing_smo2(self):
        """Should handle missing SmO2 gracefully."""
        df = pd.DataFrame({
            'watts': np.random.uniform(150, 300, 600),
            'heartrate': np.random.uniform(120, 170, 600)
        })
        
        metrics = calculate_drift_metrics(df)
        
        assert metrics['correlation_power_smo2'] is None
        assert metrics['correlation_power_hr'] is not None
