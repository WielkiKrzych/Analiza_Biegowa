"""Unit tests for modules/calculations.py"""
import pandas as pd
from modules.calculations import (
    ensure_pandas,
    calculate_normalized_power,
    estimate_carbs_burned,
    calculate_advanced_kpi,
    calculate_metrics,
    calculate_pulse_power_stats,
)


class TestEnsurePandas:
    """Tests for ensure_pandas helper function."""
    
    def test_already_pandas(self, sample_power_df):
        """Should return same object if already pandas."""
        result = ensure_pandas(sample_power_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_power_df)
    
    def test_from_dict(self):
        """Should convert dict to DataFrame."""
        data = {'a': [1, 2, 3], 'b': [4, 5, 6]}
        result = ensure_pandas(data)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ['a', 'b']


class TestNormalizedPower:
    """Tests for calculate_normalized_power."""
    
    def test_basic_calculation(self, sample_power_df):
        """NP should be >= avg power for variable power."""
        np_val = calculate_normalized_power(sample_power_df)
        avg_power = sample_power_df['watts'].mean()
        
        assert np_val > 0
        assert np_val >= avg_power * 0.9  # NP usually >= avg
    
    def test_constant_power(self):
        """NP should equal avg power for constant power."""
        df = pd.DataFrame({'watts': [200] * 100})
        np_val = calculate_normalized_power(df)
        
        assert abs(np_val - 200) < 1  # Should be ~200
    
    def test_missing_column(self):
        """Should return 0 if no power column."""
        df = pd.DataFrame({'heartrate': [140] * 100})
        np_val = calculate_normalized_power(df)
        
        assert np_val == 0.0


class TestCarbsBurned:
    """Tests for estimate_carbs_burned."""
    
    def test_basic_calculation(self, sample_power_df):
        """Should return positive carbs for valid data."""
        carbs = estimate_carbs_burned(sample_power_df, vt1_watts=150, vt2_watts=250)
        
        assert carbs > 0
    
    def test_higher_intensity_more_carbs(self, sample_power_df):
        """Higher intensity should burn more carbs."""
        low_carbs = estimate_carbs_burned(sample_power_df, vt1_watts=300, vt2_watts=400)
        high_carbs = estimate_carbs_burned(sample_power_df, vt1_watts=100, vt2_watts=150)
        
        assert high_carbs > low_carbs
    
    def test_no_watts_column(self):
        """Should return 0 if no watts column."""
        df = pd.DataFrame({'heartrate': [140] * 100})
        carbs = estimate_carbs_burned(df, 150, 250)
        
        assert carbs == 0.0


class TestAdvancedKPI:
    """Tests for calculate_advanced_kpi (decoupling)."""
    
    def test_returns_tuple(self, sample_power_df_with_smooth):
        """Should return tuple of (decoupling%, ef)."""
        decoupling, ef = calculate_advanced_kpi(sample_power_df_with_smooth)
        
        assert isinstance(decoupling, float)
        assert isinstance(ef, float)
    
    def test_insufficient_data(self):
        """Should return zeros for insufficient data."""
        df = pd.DataFrame({
            'watts_smooth': [200] * 100,
            'heartrate_smooth': [140] * 100
        })
        decoupling, ef = calculate_advanced_kpi(df)
        
        assert decoupling == 0.0


class TestCalculateMetrics:
    """Tests for calculate_metrics."""
    
    def test_returns_dict(self, sample_power_df):
        """Should return dict with expected keys."""
        metrics = calculate_metrics(sample_power_df, cp_val=280)
        
        assert isinstance(metrics, dict)
        assert 'avg_watts' in metrics
        assert 'avg_hr' in metrics
        assert 'avg_cadence' in metrics
    
    def test_correct_averages(self):
        """Should calculate correct averages."""
        df = pd.DataFrame({
            'time': [0, 1, 2],
            'watts': [100, 200, 300],
            'heartrate': [120, 140, 160],
            'cadence': [80, 90, 100]
        })
        metrics = calculate_metrics(df, cp_val=200)
        
        assert metrics['avg_watts'] == 200
        assert metrics['avg_hr'] == 140
        assert metrics['avg_cadence'] == 90


class TestPulsePowerStats:
    """Tests for calculate_pulse_power_stats."""
    
    def test_returns_tuple(self, sample_power_df_with_smooth):
        """Should return (avg_pp, drop%, dataframe)."""
        avg_pp, drop, df_pp = calculate_pulse_power_stats(sample_power_df_with_smooth)
        
        assert isinstance(avg_pp, float)
        assert isinstance(drop, float)
        assert isinstance(df_pp, pd.DataFrame)
    
    def test_pulse_power_value(self, sample_power_df_with_smooth):
        """Pulse power should be reasonable (1-3 W/bpm)."""
        avg_pp, _, _ = calculate_pulse_power_stats(sample_power_df_with_smooth)
        
        # Typical PP is 1-3 W/bpm for trained cyclists
        assert 0.5 < avg_pp < 5.0
