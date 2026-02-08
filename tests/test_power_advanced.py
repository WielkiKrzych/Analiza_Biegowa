"""
Unit tests for advanced power analytics.

Tests for:
- Power Duration Curve (PDC)
- Fatigue Resistance Index (FRI)
- Match Burns counting
- Power zones time
"""
import numpy as np
import pandas as pd
from modules.calculations import (
    calculate_power_duration_curve,
    calculate_fatigue_resistance_index,
    count_match_burns,
    calculate_power_zones_time,
    get_fri_interpretation,
)


class TestPowerDurationCurve:
    """Tests for calculate_power_duration_curve."""
    
    def test_returns_dict(self, sample_power_df):
        """Should return dict with duration -> power mapping."""
        pdc = calculate_power_duration_curve(sample_power_df)
        
        assert isinstance(pdc, dict)
        assert len(pdc) > 0
    
    def test_returns_all_requested_durations(self, sample_long_ride_df):
        """Should return values for all requested durations if data is sufficient."""
        durations = [1, 5, 30, 60, 300]
        pdc = calculate_power_duration_curve(sample_long_ride_df, durations)
        
        assert len(pdc) == len(durations)
        for d in durations:
            assert d in pdc
    
    def test_longer_duration_lower_power(self, sample_long_ride_df):
        """Longer durations should generally have lower or equal MMP."""
        pdc = calculate_power_duration_curve(sample_long_ride_df)
        
        # Filter out None values
        valid = {d: p for d, p in pdc.items() if p is not None}
        sorted_durations = sorted(valid.keys())
        
        # MMP should decrease (or stay same) as duration increases
        for i in range(len(sorted_durations) - 1):
            d1, d2 = sorted_durations[i], sorted_durations[i + 1]
            # Allow small tolerance for random data
            assert valid[d1] >= valid[d2] * 0.95, \
                f"MMP at {d1}s ({valid[d1]:.0f}W) should be >= MMP at {d2}s ({valid[d2]:.0f}W)"
    
    def test_returns_none_for_insufficient_data(self):
        """Should return None for durations longer than data."""
        df = pd.DataFrame({'watts': [200] * 30})  # Only 30 seconds
        pdc = calculate_power_duration_curve(df, [60, 300])
        
        assert pdc.get(60) is None
        assert pdc.get(300) is None
    
    def test_empty_dataframe(self):
        """Should handle empty DataFrame."""
        df = pd.DataFrame()
        pdc = calculate_power_duration_curve(df)
        
        assert pdc == {}
    
    def test_missing_watts_column(self):
        """Should return empty dict if no watts column."""
        df = pd.DataFrame({'heartrate': [140] * 100})
        pdc = calculate_power_duration_curve(df)
        
        assert pdc == {}
    
    def test_constant_power(self):
        """MMP should equal constant value for constant power."""
        df = pd.DataFrame({'watts': [250] * 600})
        pdc = calculate_power_duration_curve(df, [30, 60, 300])
        
        for duration, power in pdc.items():
            if power is not None:
                assert abs(power - 250) < 1, f"MMP at {duration}s should be ~250W"


class TestFatigueResistanceIndex:
    """Tests for calculate_fatigue_resistance_index."""
    
    def test_perfect_fri(self):
        """Equal 5min and 20min power = FRI of 1.0."""
        fri = calculate_fatigue_resistance_index(300, 300)
        assert fri == 1.0
    
    def test_typical_amateur(self):
        """Typical amateur has FRI around 0.80-0.85."""
        fri = calculate_fatigue_resistance_index(350, 280)
        assert 0.75 < fri < 0.85
    
    def test_pro_level(self):
        """Pro level has FRI > 0.90."""
        fri = calculate_fatigue_resistance_index(400, 380)
        assert fri >= 0.90
    
    def test_zero_mmp5_safe(self):
        """Should handle zero MMP5 without division error."""
        fri = calculate_fatigue_resistance_index(0, 280)
        assert fri == 0.0
    
    def test_none_values_safe(self):
        """Should handle None values."""
        fri = calculate_fatigue_resistance_index(None, 280)
        assert fri == 0.0
        
        fri = calculate_fatigue_resistance_index(350, None)
        assert fri == 0.0


class TestMatchBurns:
    """Tests for count_match_burns."""
    
    def test_counts_burns_correctly(self, sample_w_balance_array, w_prime_value):
        """Should count correct number of match burns."""
        burns = count_match_burns(sample_w_balance_array, w_prime_value, threshold_pct=0.3)
        
        # Based on fixture: 2 dips below 30%
        assert burns == 2
    
    def test_no_burns_when_above_threshold(self, w_prime_value):
        """Should return 0 if W' never drops below threshold."""
        w_bal = np.ones(100) * w_prime_value * 0.5  # Always at 50%
        burns = count_match_burns(w_bal, w_prime_value, threshold_pct=0.3)
        
        assert burns == 0
    
    def test_empty_array(self, w_prime_value):
        """Should handle empty array."""
        burns = count_match_burns(np.array([]), w_prime_value)
        assert burns == 0
    
    def test_zero_capacity(self):
        """Should handle zero W' capacity."""
        burns = count_match_burns(np.ones(100), 0)
        assert burns == 0
    
    def test_custom_threshold(self, w_prime_value):
        """Should respect custom threshold."""
        # Array that dips to 40% twice
        w_bal = np.ones(200) * w_prime_value
        w_bal[50:70] = w_prime_value * 0.4
        w_bal[150:170] = w_prime_value * 0.4
        
        # With 30% threshold, no burns
        burns_30 = count_match_burns(w_bal, w_prime_value, threshold_pct=0.3)
        assert burns_30 == 0
        
        # With 50% threshold, 2 burns
        burns_50 = count_match_burns(w_bal, w_prime_value, threshold_pct=0.5)
        assert burns_50 == 2


class TestPowerZonesTime:
    """Tests for calculate_power_zones_time."""
    
    def test_returns_all_zones(self, sample_power_df, cp_value):
        """Should return time for all default zones."""
        zones = calculate_power_zones_time(sample_power_df, cp_value)
        
        assert 'Z1 Recovery' in zones
        assert 'Z2 Endurance' in zones
        assert 'Z4 Threshold' in zones
    
    def test_total_equals_data_length(self, sample_power_df, cp_value):
        """Total time in zones should equal data length."""
        zones = calculate_power_zones_time(sample_power_df, cp_value)
        
        total = sum(zones.values())
        expected = len(sample_power_df)
        
        assert abs(total - expected) <= 1  # Allow 1 second tolerance
    
    def test_zero_cp_returns_empty(self, sample_power_df):
        """Should return empty dict for zero CP."""
        zones = calculate_power_zones_time(sample_power_df, 0)
        assert zones == {}
    
    def test_no_watts_returns_empty(self, cp_value):
        """Should return empty dict if no watts column."""
        df = pd.DataFrame({'heartrate': [140] * 100})
        zones = calculate_power_zones_time(df, cp_value)
        assert zones == {}


class TestFriInterpretation:
    """Tests for get_fri_interpretation."""
    
    def test_exceptional_endurance(self):
        """FRI >= 0.95 should indicate exceptional."""
        result = get_fri_interpretation(0.96)
        assert "diesel" in result.lower() or "wyjątkowa" in result.lower()
    
    def test_pro_level(self):
        """FRI 0.90-0.95 should indicate pro level."""
        result = get_fri_interpretation(0.92)
        assert "pro" in result.lower()
    
    def test_sprinter_profile(self):
        """FRI < 0.80 should indicate sprinter profile."""
        result = get_fri_interpretation(0.75)
        assert "sprint" in result.lower()
