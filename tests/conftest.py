# Tests configuration for Tri_Dashboard
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_power_df():
    """Sample cycling data with power, HR, cadence."""
    np.random.seed(42)
    n = 600  # 10 minutes of data
    
    return pd.DataFrame({
        'time': np.arange(n, dtype=float),
        'watts': np.random.normal(200, 30, n).clip(0, 400),
        'heartrate': np.random.normal(140, 10, n).clip(60, 200),
        'cadence': np.random.normal(90, 5, n).clip(60, 120),
        'smo2': np.random.normal(60, 10, n).clip(20, 95),
    })


@pytest.fixture
def sample_power_df_with_smooth(sample_power_df):
    """Sample data with smoothed columns."""
    df = sample_power_df.copy()
    df['watts_smooth'] = df['watts'].rolling(30, min_periods=1).mean()
    df['heartrate_smooth'] = df['heartrate'].rolling(30, min_periods=1).mean()
    df['cadence_smooth'] = df['cadence'].rolling(30, min_periods=1).mean()
    df['time_min'] = df['time'] / 60
    return df


@pytest.fixture
def sample_hrv_df():
    """Sample HRV data with R-R intervals."""
    np.random.seed(42)
    n = 500
    
    return pd.DataFrame({
        'time': np.arange(n, dtype=float),
        'rr': np.random.normal(800, 50, n).clip(600, 1200),  # R-R in ms
    })


@pytest.fixture
def cp_value():
    """Standard CP value for testing."""
    return 280  # Watts


@pytest.fixture
def w_prime_value():
    """Standard W' value for testing."""
    return 20000  # Joules


@pytest.fixture
def sample_long_ride_df():
    """Sample long ride data (30 minutes) for PDC testing."""
    np.random.seed(42)
    n = 1800  # 30 minutes of data
    
    # Simulate a ride with intervals
    watts = np.zeros(n)
    # Warmup (5 min at 150W)
    watts[:300] = np.random.normal(150, 10, 300)
    # Main set (20 min with intervals)
    for i in range(4):
        start = 300 + i * 300
        # 2min hard
        watts[start:start+120] = np.random.normal(300, 20, 120)
        # 3min recovery
        watts[start+120:start+300] = np.random.normal(150, 10, 180)
    # Cooldown (5 min at 120W)
    watts[1500:] = np.random.normal(120, 10, 300)
    
    return pd.DataFrame({
        'time': np.arange(n, dtype=float),
        'watts': watts.clip(0, 500),
        'heartrate': np.random.normal(140, 15, n).clip(60, 200),
        'cadence': np.random.normal(90, 5, n).clip(60, 120),
    })


@pytest.fixture
def sample_w_balance_array(w_prime_value):
    """Sample W' balance array with some deep dips."""
    n = 600
    w_bal = np.ones(n) * w_prime_value
    
    # Simulate 3 hard efforts that deplete W'
    # First effort: dips to 40%
    w_bal[100:150] = np.linspace(w_prime_value, w_prime_value * 0.4, 50)
    w_bal[150:200] = np.linspace(w_prime_value * 0.4, w_prime_value * 0.8, 50)
    
    # Second effort: dips to 20% (match burn!)
    w_bal[250:300] = np.linspace(w_prime_value * 0.8, w_prime_value * 0.2, 50)
    w_bal[300:380] = np.linspace(w_prime_value * 0.2, w_prime_value * 0.9, 80)
    
    # Third effort: dips to 25% (match burn!)
    w_bal[450:500] = np.linspace(w_prime_value * 0.9, w_prime_value * 0.25, 50)
    w_bal[500:] = np.linspace(w_prime_value * 0.25, w_prime_value * 0.7, 100)
    
    return w_bal


@pytest.fixture
def rider_params():
    """Standard rider parameters for testing."""
    return {
        'weight': 75.0,
        'age': 35,
        'vo2max': 55.0,
        'cp': 280,
        'w_prime': 20000
    }


@pytest.fixture
def empty_df():
    """Empty DataFrame with required columns but no rows."""
    return pd.DataFrame(columns=['time', 'watts', 'heartrate', 'cadence', 'smo2'])


@pytest.fixture
def malformed_df():
    """DataFrame with mixed types and missing values."""
    return pd.DataFrame({
        'time': range(15),
        'watts': ['100', 'nan', 200, None] + [100]*11,  # Mixed types
        'heartrate': [120, 130, 'invalid', 150] + [140]*11,
        'cadence': [80, 85, 90, 95] + [90]*11
    })


@pytest.fixture
def nan_df():
    """DataFrame with valid structure but NaN values."""
    return pd.DataFrame({
        'time': [0, 1, 2, 3, 4],
        'watts': [100, np.nan, 200, 250, np.nan],
        'heartrate': [120, np.nan, 140, 145, 150],
        'cadence': [80, 80, np.nan, 90, 90]
    })


@pytest.fixture
def boundary_df():
    """DataFrame with values exactly at thresholds."""
    return pd.DataFrame({
        'time': [0, 60, 120, 180],
        'watts': [199, 200, 201, 300], # Around VT1=200
        'heartrate': [160] * 4
    })
