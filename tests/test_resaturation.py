
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.kinetics import calculate_resaturation_metrics

def test_resaturation_metrics():
    print("=== Test Resaturation Metrics ===\n")
    
    # Create exponential recovery curve: y = 1 - e^(-t/tau)
    # Target Tau = 30s
    tau_target = 30.0
    time = np.arange(0, 120, 1) # 2 minutes
    # y goes from 0 to 1
    y = 1.0 * (1 - np.exp(-time / tau_target))
    
    s_time = pd.Series(time)
    s_smo2 = pd.Series(y)
    
    res = calculate_resaturation_metrics(s_time, s_smo2)
    
    print(f"Metrics for Tau={tau_target}s:")
    print(f"  Estimated Tau: {res['tau_est']:.2f}s")
    print(f"  T_half: {res['t_half']:.2f}s")
    print(f"  Recovery Score: {res['recovery_score']:.1f}")
    
    # Check if estimated tau is reasonably close (heuristic estimation T_half/ln2 is approx)
    # T_half for exp is tau * ln(2) = 30 * 0.693 = 20.79s
    assert abs(res['t_half'] - 20.8) < 1.0, f"T_half ({res['t_half']}) incorrect for Tau=30"
    assert abs(res['tau_est'] - 30.0) < 2.0, f"Estimated Tau ({res['tau_est']}) too far from 30"
    assert res['recovery_score'] > 95, "Fast recovery should have high score"
    
    # Test Slow Recovery (Tau = 60s)
    tau_slow = 60.0
    y_slow = 1.0 * (1 - np.exp(-time / tau_slow))
    res_slow = calculate_resaturation_metrics(s_time, pd.Series(y_slow))
    
    print(f"\nMetrics for Tau={tau_slow}s:")
    print(f"  Estimated Tau: {res_slow['tau_est']:.2f}s")
    print(f"  Score: {res_slow['recovery_score']:.1f}")
    
    assert res_slow['tau_est'] > res['tau_est'], "Slow tau should be higher"
    assert res_slow['recovery_score'] < res['recovery_score'], "Slow recovery should have lower score"
    
    print("\nResaturation Verification Passed!")

if __name__ == "__main__":
    test_resaturation_metrics()
