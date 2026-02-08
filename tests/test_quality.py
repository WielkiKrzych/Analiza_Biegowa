
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.quality import check_step_test_protocol, check_signal_quality

def test_quality_checks():
    print("=== Test Quality Checks ===\n")
    
    # 1. Test Valid Ramp Protocol
    # Power increases linearly 100 -> 300
    t = np.arange(0, 600)
    w_ramp = np.linspace(100, 300, 600) + np.random.normal(0, 5, 600)
    df_valid = pd.DataFrame({'time': t, 'watts': w_ramp})
    
    res_valid = check_step_test_protocol(df_valid)
    print(f"Valid Ramp: Valid={res_valid['is_valid']}, R2={res_valid.get('r_squared')}")
    assert res_valid['is_valid'] == True, "Should be valid ramp"
    assert res_valid.get('r_squared') > 0.8, "High R2 expected"
    
    # 2. Test Invalid Protocol (Flat/Intervals)
    # 2 mins 150W, 2 mins 250W (Step, but overall R2 might be weird, or not strictly linear if analyzed as one line?)
    # A true flat ride
    w_flat = np.full_like(t, 200) + np.random.normal(0, 5, 600)
    df_flat = pd.DataFrame({'time': t, 'watts': w_flat})
    
    res_flat = check_step_test_protocol(df_flat)
    print(f"Flat Ride: Valid={res_flat['is_valid']}, Slope={res_flat.get('slope')}")
    # Slope should be ~0
    assert res_flat['is_valid'] == False, "Flat ride should be invalid for Ramp Test"
    assert "slope too low" in str(res_flat['issues']), "Issue should mention slope too low"
    
    # 3. Test Signal Quality (SmO2)
    # Valid
    s_clean = pd.Series(np.random.normal(60, 2, 100))
    q_clean = check_signal_quality(s_clean, "SmO2")
    print(f"Clean Signal: Valid={q_clean['is_valid']}, Score={q_clean['score']}")
    assert q_clean['is_valid'] == True, "Clean signal should be valid"
    
    # Bad (Dropouts)
    s_drop = s_clean.copy()
    s_drop.iloc[:30] = np.nan # 30% NaNs
    q_drop = check_signal_quality(s_drop, "SmO2")
    print(f"Dropout Signal: Valid={q_drop['is_valid']}, Score={q_drop['score']}")
    assert q_drop['is_valid'] == False, "30% dropouts should be invalid"
    assert q_drop['score'] < 0.6, "Score should be low"
    
    print("\nQuality Verification Passed!")

if __name__ == "__main__":
    test_quality_checks()
