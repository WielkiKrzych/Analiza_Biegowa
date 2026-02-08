import pytest
import numpy as np
from modules.calculations.d_prime import (
    calculate_d_prime_balance,
    estimate_time_to_exhaustion_pace,
    count_surges
)

def test_calculate_d_prime_balance():
    """Test D' balance calculation."""
    # 10 minutes of running
    time = np.arange(0, 600, 1)  # 0 to 599 seconds
    
    # Constant pace: 2 min above CS, 2 min below, repeat
    # CS = 300 sec/km (5:00 min/km)
    pace = np.concatenate([
        np.full(120, 240),  # 120s @ 4:00 (above CS = faster)
        np.full(120, 360),  # 120s @ 6:00 (below CS = recovery)
        np.full(120, 240),  # another surge
        np.full(240, 360),  # long recovery
    ])
    
    d_prime_balance = calculate_d_prime_balance(
        pace_sec_per_km=pace,
        time_sec=time,
        critical_speed_pace=300,  # 5:00 min/km
        d_prime_capacity=200  # 200m
    )
    
    # D' should decrease during fast sections
    assert d_prime_balance[0] == 200  # Start full
    assert d_prime_balance[60] < 200  # Depleted after 60s fast
    assert d_prime_balance[240] > d_prime_balance[120]  # Recovered

def test_estimate_time_to_exhaustion_pace():
    """Test TTE estimation from pace."""
    tte = estimate_time_to_exhaustion_pace(
        target_pace=240,  # 4:00 min/km
        critical_speed_pace=300,  # 5:00 min/km
        d_prime=200
    )
    
    # Should be able to hold 4:00 pace for limited time
    assert tte > 0
    assert tte < 600  # Less than 10 minutes
    
    # At CS, TTE should be infinite
    tte_at_cs = estimate_time_to_exhaustion_pace(
        target_pace=300,
        critical_speed_pace=300,
        d_prime=200
    )
    assert np.isinf(tte_at_cs)

def test_count_surges():
    """Test counting surges above threshold."""
    # Values drop below 30% threshold (60m), then recover above 80% (160m)
    d_prime_balance = np.array([200, 180, 150, 120, 100, 80, 59, 100, 140, 180, 200, 160, 120])
    
    surges = count_surges(d_prime_balance, d_prime_capacity=200, threshold_pct=0.3)
    
    # Should detect at least 1 surge (drops below 30% = 60m, then recovery)
    assert surges >= 1

def test_tte_invalid_inputs():
    """Test TTE with invalid inputs."""
    with pytest.raises(ValueError):
        estimate_time_to_exhaustion_pace(0, 300, 200)
    
    with pytest.raises(ValueError):
        estimate_time_to_exhaustion_pace(240, -1, 200)
    
    with pytest.raises(ValueError):
        estimate_time_to_exhaustion_pace(240, 300, -1)

def test_d_prime_balance_empty():
    """Test D' balance with empty array."""
    result = calculate_d_prime_balance(
        pace_sec_per_km=np.array([]),
        time_sec=np.array([]),
        critical_speed_pace=300,
        d_prime_capacity=200
    )
    assert len(result) == 0
