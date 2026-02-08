
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.thresholds import analyze_step_test

def create_sensitivity_data(noise_level=0.1):
    """
    Create mock data simulating a ramp test.
    Ramp Up: 0-600s (100W -> 400W).
    
    VT1 around 200W (t=200).
    VT2 around 300W (t=400).
    """
    time = np.arange(0, 601, 1) # 10 minutes
    watts = 100 + (time / 600) * 300 # 100 -> 400
    
    true_ve = np.zeros_like(time, dtype=float)
    current_val = 20.0
    
    for i, t in enumerate(time):
        w = watts[i]
        
        if w < 200:
            slope = 0.02
        elif w < 300:
            slope = 0.06
        else:
            slope = 0.16
            
        if i > 0:
            current_val += slope
        true_ve[i] = current_val

    # Add Noise
    noise = np.random.normal(0, noise_level, size=len(time)) 
    ve = true_ve + noise
        
    df = pd.DataFrame({
        'time': time,
        'watts': watts,
        'tymeventilation': ve,
        'hr': 100 + (watts/400)*80 
    })
    
    return df

def test_sensitivity():
    print("=== Test 1: Clean Data (Should be Stable) ===")
    df_clean = create_sensitivity_data(noise_level=0.2) # Low noise
    res_clean = analyze_step_test(df_clean, power_column='watts', time_column='time')
    sens_clean = res_clean.sensitivity
    
    print(f"VT1 Clean Variance: {sens_clean.vt1_variability_watts:.2f}W")
    print(f"VT1 Clean Score: {sens_clean.vt1_stability_score:.2f}")
    assert sens_clean.vt1_stability_score > 0.6, "Clean data should have acceptable stability score"
    assert not sens_clean.is_vt1_unreliable, "Clean data should be reliable"

    print("\n=== Test 2: Noisy Data (Should be Unstable) ===")
    df_noisy = create_sensitivity_data(noise_level=3.0) # High noise (3 L/min variance is huge)
    res_noisy = analyze_step_test(df_noisy, power_column='watts', time_column='time')
    sens_noisy = res_noisy.sensitivity
    
    print(f"VT1 Noisy Variance: {sens_noisy.vt1_variability_watts:.2f}W")
    print(f"VT1 Noisy Score: {sens_noisy.vt1_stability_score:.2f}")
    
    if sens_noisy.vt1_variability_watts > sens_clean.vt1_variability_watts:
        print("PASS: Noisy data has higher variability than clean data.")
    else:
        print("WARNING: Noisy data has similar variability. Logic might be too robust or noise model too simple.")
        
    assert sens_noisy.vt1_stability_score < sens_clean.vt1_stability_score, "Noisy data should have lower stability score"

    print("\nVerification Passed!")

if __name__ == "__main__":
    test_sensitivity()
