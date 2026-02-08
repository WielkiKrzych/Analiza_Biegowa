
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.thresholds import analyze_step_test

def create_hysteresis_data():
    """
    Create mock data simulating a ramp test with hysteresis.
    Ramp Up: 0-600s (100W -> 400W). Peak at 600s.
    Ramp Down: 600-1200s (400W -> 100W).
    
    Hysteresis Model:
    Ramp Up: VT1 at 200W (slope ~0.05). Power at 200W is at t=200s (start 100W + 0.5W/s * 200s) -> 200
    Ramp Down: Fatigue causes VT1 to appear earlier/lower power. Say at 180W.
    """
    # 20 minutes (1200s), 1s interval
    time = np.arange(0, 1201, 1)
    peak_time = 600
    
    watts = np.zeros_like(time, dtype=float)
    # Ramp Up
    watts[:601] = 100 + (time[:601] / 600) * 300 # 100 -> 400
    # Ramp Down
    watts[601:] = 400 - ((time[601:] - 600) / 600) * 300 # 400 -> 100
    
    true_ve = np.zeros_like(time, dtype=float)
    current_val = 20.0
    
    # Generate VE based on watts, but with different thresholds for Up vs Down
    for i, t in enumerate(time):
        w = watts[i]
        is_up = t <= peak_time
        
        # Threshold definitions
        if is_up:
            vt1_thresh = 200 # Ramp Up Threshold
            vt2_thresh = 300
        else:
            vt1_thresh = 170 # Ramp Down Threshold (Fatigue shift 30W)
            vt2_thresh = 270 # Ramp Down Threshold (Fatigue shift 30W)
            
        # Slope logic based on power relative to threshold
        if w < vt1_thresh:
            slope = 0.02
        elif w < vt2_thresh:
            slope = 0.06
        else:
            slope = 0.16
            
        if i > 0:
            current_val += slope
        true_ve[i] = current_val

    # Low noise for clean detection testing
    noise = np.random.normal(0, 0.2, size=len(time)) 
    ve = true_ve + noise
        
    df = pd.DataFrame({
        'time': time,
        'watts': watts,
        'tymeventilation': ve,
        'hr': 100 + (watts/400)*80 # Dummy HR proportional to power
    })
    
    return df

def test_hysteresis():
    print("Generating Hysteresis Mock Data...")
    df = create_hysteresis_data()
    
    print("Running Analysis...")
    result = analyze_step_test(df, power_column='watts', time_column='time')
    
    print("\n=== Results ===")
    
    # Verify Ramp Up Zones
    vt1_up = result.vt1_zone
    if vt1_up:
        print(f"VT1 Up: {vt1_up.range_watts[0]:.0f}-{vt1_up.range_watts[1]:.0f}W")
        # Theoretical 200W
        assert 190 < vt1_up.range_watts[0] < 210, f"VT1 Up {vt1_up.range_watts[0]} expected ~200"
    else:
        print("VT1 Up: Not detected")
        assert False, "VT1 Up not detected"
        
    # Verify Hysteresis
    hyst = result.hysteresis
    if hyst and hyst.vt1_dec_zone:
        vt1_down = hyst.vt1_dec_zone
        print(f"VT1 Down: {vt1_down.range_watts[0]:.0f}-{vt1_down.range_watts[1]:.0f}W")
        
        # Theoretical 170W. Note: detecting on ramp down, power is decreasing.
        # The transition zone detection finds where slope is 0.05.
        # At 170W on way down, slope changes.
        
        # In Ramp Down: Time increases, Power decreases.
        # Slope Calculation: time always moves forward. VE always accumulates (positive slope).
        # But relation to Power is what matters. 
        # Our detector uses TIME windows.
        # At t=900 (approx), power drops past 170W.
        # Detector should find the zone around that time, and map avg power in that window.
        
        assert 160 < vt1_down.range_watts[0] < 185, f"VT1 Down {vt1_down.range_watts[0]} expected ~170"
        
        print(f"Shift: {hyst.vt1_shift_watts:.1f} W")
        assert hyst.vt1_shift_watts < -15, "Expected significant negative shift (hysteresis)"
        
    else:
        print("Hysteresis/Down Zone not detected")
        assert False, "VT1 Down not detected"

    print("\nVerification Passed!")

if __name__ == "__main__":
    test_hysteresis()
