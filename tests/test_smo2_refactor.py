
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.kinetics import normalize_smo2_series, detect_smo2_trend

def test_normalization():
    print("=== Test 1: Normalization ===")
    
    # Create synthetic series with known min/max (ignoring 2%/98% clipping for simplicity logic check)
    # Range 40 to 80.
    data = [40, 50, 60, 70, 80] 
    # Add outlier to check robustness
    data_with_outlier = [10, 40, 50, 60, 70, 80, 100] # 10 and 100 might be clipped by 2nd/98th percentile logic
    
    s = pd.Series(data)
    norm = normalize_smo2_series(s)
    
    print(f"Original: {data}")
    print(f"Norm: {norm.values}")
    
    # Check bounds
    assert norm.min() >= 0.0, "Normalization should not be negative"
    assert norm.max() <= 1.0, "Normalization should not exceed 1.0"
    
    # Check basic scaling (approximate due to percentile robustness)
    # The middle value (60) should be roughly 0.5
    mid = norm.iloc[2]
    print(f"Midpoint (60): {mid:.2f}")
    assert 0.4 <= mid <= 0.6, "Midpoint scaling incorrect"
    
    print("Normalization Passed!")

def test_trend_detection():
    print("\n=== Test 2: Trend Detection ===")
    
    time = np.arange(0, 100, 1) # 100s
    
    # Case A: Rapid Deox (Slope -0.1)
    smo2_rapid_deox = 100 - 0.1 * time
    res_a = detect_smo2_trend(time, pd.Series(smo2_rapid_deox))
    print(f"Rapid Deox Slope: {res_a['slope']:.4f} -> {res_a['category']}")
    assert "Szybka deoksygenacja" in res_a['category'] or "deoksygenacja" in res_a['category'], "Failed to detect Deoxygenation"

    # Case B: Stable / Equilibrium (Slope 0.0)
    smo2_stable = np.full_like(time, 50) + np.random.normal(0, 0.001, 100) # Tiny noise
    res_b = detect_smo2_trend(time, pd.Series(smo2_stable))
    print(f"Stable Slope: {res_b['slope']:.4f} -> {res_b['category']}")
    assert "Równowaga" in res_b['category'] or "Stabilny" in res_b['category'], "Failed to detect Equilibrium"
    
    # Case C: Reox (Slope +0.06)
    smo2_reox = 40 + 0.06 * time
    res_c = detect_smo2_trend(time, pd.Series(smo2_reox))
    print(f"Reox Slope: {res_c['slope']:.4f} -> {res_c['category']}")
    assert "Reoksygenacja" in res_c['category'] or "reoksygenacja" in res_c['category'].lower(), "Failed to detect Reoxygenation"

    print("Trend Detection Passed!")

if __name__ == "__main__":
    test_normalization()
    test_trend_detection()
