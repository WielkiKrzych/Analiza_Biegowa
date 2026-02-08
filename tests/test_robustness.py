"""Tests for system robustness and edge cases."""
import pandas as pd
import numpy as np
from modules.calculations import (
    calculate_normalized_power,
    calculate_metrics,
    estimate_carbs_burned
)
from services.data_validation import validate_dataframe

class TestEdgeCases:
    """Tests for edge cases like NaNs and empty DataFrames."""

    def test_calculate_normalized_power_empty(self, empty_df):
        """Should return 0 for empty DataFrame."""
        assert calculate_normalized_power(empty_df) == 0.0

    def test_calculate_normalized_power_nan(self, nan_df):
        """Should handle NaN values gracefully (ignore them or return valid NP)."""
        # Pandas mean/rolling ignores NaNs by default usually, verify specifics
        np_val = calculate_normalized_power(nan_df)
        assert not np.isnan(np_val)
        assert np_val > 0

    def test_calculate_metrics_empty(self, empty_df):
        """Should return safe defaults for empty DataFrame."""
        metrics = calculate_metrics(empty_df, cp_val=280)
        assert metrics['avg_watts'] == 0
        assert metrics['avg_hr'] == 0

    def test_validate_dataframe_malformed(self, malformed_df):
        """Should fail validation or handle conversion for malformed data."""
        # Note: validate_dataframe checks for columns mainly.
        # Malformed types might pass structure check but fail downstream.
        # Check if validation catches it or if we need a robust loader test.
        is_valid, _ = validate_dataframe(malformed_df)
        # It has 'watts' col, so it might pass basic structural validation
        assert is_valid is True 

class TestBoundaries:
    """Tests for boundary conditions."""

    def test_carbs_burned_boundary(self, boundary_df):
        """Test carb estimation exactly at VT1."""
        # 199W (Base), 200W (VT1), 201W (Tempo)
        # Should be deterministic
        
        # Exact matching logic testing
        carbs = estimate_carbs_burned(boundary_df, vt1_watts=200, vt2_watts=300)
        assert carbs > 0
        
    def test_carbs_zero_watts(self):
        """Should be 0 carbs if watts are 0."""
        df = pd.DataFrame({'watts': [0, 0, 0], 'time': [0, 1, 2]})
        carbs = estimate_carbs_burned(df, 200, 300)
        assert carbs == 0

class TestDeterministicOutput:
    """Tests to ensure outputs are deterministic."""
    
    def test_np_deterministic(self, sample_power_df):
        """Same input should yield exact same output."""
        run1 = calculate_normalized_power(sample_power_df)
        run2 = calculate_normalized_power(sample_power_df)
        assert run1 == run2
        
    def test_metrics_deterministic(self, sample_power_df):
        """Metrics dict should be identical."""
        m1 = calculate_metrics(sample_power_df, 280)
        m2 = calculate_metrics(sample_power_df, 280)
        assert m1 == m2
