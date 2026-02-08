"""Tests for TTE (Time-to-Exhaustion) detection module."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from modules.tte import (
    compute_tte,
    compute_tte_result,
    rolling_tte,
    format_tte,
    TTEResult
)


class TestComputeTTE:
    """Tests for compute_tte function."""
    
    def test_simple_block(self):
        """Test detection of a single continuous block at target power."""
        ftp = 250
        # Create 120 seconds at exactly 100% FTP
        power = pd.Series([250] * 120)
        
        result = compute_tte(power, target_pct=100, ftp=ftp, tol_pct=5)
        
        assert result == 120
    
    def test_block_with_tolerance(self):
        """Test that values within tolerance are counted."""
        ftp = 250
        # Power oscillating within 5% of FTP (237.5 - 262.5 W)
        power = pd.Series([245, 255, 248, 252, 250] * 20)  # 100 samples
        
        result = compute_tte(power, target_pct=100, ftp=ftp, tol_pct=5)
        
        assert result == 100
    
    def test_multiple_blocks_returns_longest(self):
        """Test that the longest block is returned when multiple exist."""
        ftp = 250
        # Block 1: 30s at FTP, then break, then Block 2: 60s at FTP
        power = pd.Series(
            [250] * 30 +    # First block
            [100] * 10 +    # Recovery (below range)
            [250] * 60      # Second block (longest)
        )
        
        result = compute_tte(power, target_pct=100, ftp=ftp, tol_pct=5)
        
        assert result == 60
    
    def test_no_valid_blocks(self):
        """Test that 0 is returned when no power is in range."""
        ftp = 250
        # All power below target range
        power = pd.Series([100] * 100)
        
        result = compute_tte(power, target_pct=100, ftp=ftp, tol_pct=5)
        
        assert result == 0
    
    def test_empty_series(self):
        """Test handling of empty power series."""
        result = compute_tte(pd.Series([]), target_pct=100, ftp=250, tol_pct=5)
        assert result == 0
    
    def test_none_series(self):
        """Test handling of None input."""
        result = compute_tte(None, target_pct=100, ftp=250, tol_pct=5)
        assert result == 0
    
    def test_nan_values(self):
        """Test that NaN values are treated as breaks."""
        ftp = 250
        power = pd.Series([250] * 30 + [np.nan] * 5 + [250] * 40)
        
        result = compute_tte(power, target_pct=100, ftp=ftp, tol_pct=5)
        
        assert result == 40  # Second block is longer
    
    def test_different_target_percentages(self):
        """Test TTE at 90% and 110% FTP."""
        ftp = 250
        
        # 90% FTP = 225W, range = 213.75 - 236.25
        power_90 = pd.Series([225] * 60)
        result_90 = compute_tte(power_90, target_pct=90, ftp=ftp, tol_pct=5)
        assert result_90 == 60
        
        # 110% FTP = 275W, range = 261.25 - 288.75
        power_110 = pd.Series([275] * 45)
        result_110 = compute_tte(power_110, target_pct=110, ftp=ftp, tol_pct=5)
        assert result_110 == 45


class TestComputeTTEResult:
    """Tests for compute_tte_result function."""
    
    def test_returns_tte_result(self):
        """Test that function returns TTEResult dataclass."""
        power = pd.Series([250] * 60)
        result = compute_tte_result(power, target_pct=100, ftp=250, tol_pct=5)
        
        assert isinstance(result, TTEResult)
        assert result.tte_seconds == 60
        assert result.target_pct == 100
        assert result.ftp == 250
        assert result.tolerance_pct == 5
        assert result.target_power_min == 237.5
        assert result.target_power_max == 262.5


class TestRollingTTE:
    """Tests for rolling_tte function."""
    
    def test_empty_history(self):
        """Test with empty history list."""
        result = rolling_tte([])
        assert result["count"] == 0
    
    def test_single_entry(self):
        """Test with single history entry."""
        history = [{"date": datetime.now().isoformat(), "tte_seconds": 120}]
        result = rolling_tte(history, window_days=30)
        
        assert result["median"] == 120
        assert result["count"] == 1
    
    def test_filters_old_entries(self):
        """Test that entries outside window are filtered."""
        now = datetime.now()
        history = [
            {"date": (now - timedelta(days=10)).isoformat(), "tte_seconds": 120},
            {"date": (now - timedelta(days=50)).isoformat(), "tte_seconds": 180},  # Outside 30-day window
        ]
        
        result = rolling_tte(history, window_days=30)
        
        assert result["count"] == 1
        assert result["median"] == 120
    
    def test_computes_correct_stats(self):
        """Test that median/mean/max/min are computed correctly."""
        now = datetime.now()
        history = [
            {"date": now.isoformat(), "tte_seconds": 60},
            {"date": now.isoformat(), "tte_seconds": 120},
            {"date": now.isoformat(), "tte_seconds": 180},
        ]
        
        result = rolling_tte(history, window_days=30)
        
        assert result["median"] == 120
        assert result["mean"] == 120
        assert result["max"] == 180
        assert result["min"] == 60
        assert result["count"] == 3


class TestFormatTTE:
    """Tests for format_tte function."""
    
    def test_formats_correctly(self):
        assert format_tte(0) == "00:00"
        assert format_tte(30) == "00:30"
        assert format_tte(60) == "01:00"
        assert format_tte(90) == "01:30"
        assert format_tte(3600) == "60:00"
    
    def test_negative_returns_zero(self):
        assert format_tte(-10) == "00:00"
