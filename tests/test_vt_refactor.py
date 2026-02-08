
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.thresholds import detect_vt_transition_zone

def create_mock_data():
    """Create mock data simulating a ramp test (Trend + Low Noise)"""
    # 20 minutes (1200s), 1s interval
    time = np.arange(0, 1200, 1)
    
    # Power ramp: 100W to 400W
    watts = 100 + (time / 1200) * 300
    
    true_ve = np.zeros_like(time, dtype=float)
    current_val = 20.0
    
    # Construct piecewise linear trend
    for t in range(len(time)):
        if t < 400:
            slope = 0.02
        elif t < 800:
            slope = 0.06
        else:
            slope = 0.16
        
        if t > 0:
            current_val += slope
        
        true_ve[t] = current_val

    # Low noise to verify precision
    noise = np.random.normal(0, 0.1, size=len(time)) 
    ve = true_ve + noise
        
    df = pd.DataFrame({
        'time': time,
        'watts': watts,
        'tymeventilation': ve,
        'hr': 100 + (time/1200)*80 
    })
    
    return df

def test_detection():
    print("Generating clean mock data...")
    df = create_mock_data()
    
    print("Running detection...")
    vt1, vt2 = detect_vt_transition_zone(df)
    
    print("\nResults:")
    if vt1:
        print(f"VT1 Zone: {vt1.range_watts[0]:.1f}-{vt1.range_watts[1]:.1f}W (Conf: {vt1.confidence:.2f})")
    else:
        print("VT1: Not detected")
        
    if vt2:
        print(f"VT2 Zone: {vt2.range_watts[0]:.1f}-{vt2.range_watts[1]:.1f}W (Conf: {vt2.confidence:.2f})")
    else:
        print("VT2: Not detected")
        
    # Assertions for clean data
    if vt1:
        # Should be very close to 200W
        assert vt1.range_watts[0] > 180, f"VT1 start {vt1.range_watts[0]} too early"
        assert vt1.range_watts[1] < 220, f"VT1 end {vt1.range_watts[1]} too late"
    else:
        assert False, "VT1 not detected on clean data"

    if vt2:
        # Should be very close to 300W
        assert vt2.range_watts[0] > 280
        assert vt2.range_watts[1] < 320
    else:
        assert False, "VT2 not detected on clean data"

    print("\nVerification Passed!")

if __name__ == "__main__":
    test_detection()
