
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.kinetics import calculate_signal_lag, analyze_temporal_sequence

def create_sine_wave(length=120, shift=0):
    t = np.arange(length)
    # Sine wave with period 60s
    y = np.sin(2 * np.pi * (t - shift) / 60)
    return pd.Series(y)

def test_correlation_lag():
    print("=== Test Signal Lag Correlation ===\n")
    
    length = 200
    
    # Reference (Power) - Base Sine
    s_ref = create_sine_wave(length, shift=0)
    
    # Target (HR) - Lagged by 20s
    expected_lag = 20
    s_lagged = create_sine_wave(length, shift=expected_lag)
    
    # Calculate Lag
    lag = calculate_signal_lag(s_ref, s_lagged, max_lag=50)
    
    print(f"Expected Lag: {expected_lag}s")
    print(f"Calculated Lag: {lag}s")
    
    # Allow small error due to discrete sampling
    assert abs(lag - expected_lag) < 2.0, f"Lag calculation failed. Got {lag}, expected {expected_lag}"
    
    # Test SmO2 Lag (Inverted response)
    # SmO2 usually drops when Power rises. 
    # So we create an inverted sine wave lagged by 10s
    expected_smo2_lag = 10
    # Inverted sine lagged by 10
    s_smo2 = -1 * create_sine_wave(length, shift=expected_smo2_lag)
    
    # Our function analyze_temporal_sequence handles inversion internally given a DF
    df = pd.DataFrame({
        'watts': s_ref,
        'hr': s_lagged,
        'smo2': s_smo2
    })
    
    res = analyze_temporal_sequence(df)
    
    print(f"Analyzed SmO2 Lag (Expect ~10s): {res['smo2_lag']}s")
    print(f"Analyzed HR Lag (Expect ~20s): {res['hr_lag']}s")
    
    # Verify SmO2 lag (Note: function returns positive lag if target lags)
    assert abs(res['smo2_lag'] - expected_smo2_lag) < 2.0, "SmO2 Lag incorrect"
    assert abs(res['hr_lag'] - expected_lag) < 2.0, "HR Lag incorrect"
    
    print("\nCorrelation Verification Passed!")

if __name__ == "__main__":
    test_correlation_lag()
