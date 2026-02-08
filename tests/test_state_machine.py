
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.kinetics import generate_state_timeline

def create_interval_segment(start, duration, mode="STEADY"):
    t = np.arange(start, start+duration)
    
    # Initialize defaults
    watts = np.zeros_like(t, dtype=float)
    hr = np.zeros_like(t, dtype=float)
    smo2 = np.zeros_like(t, dtype=float)
    
    if mode == "STEADY" or mode == "STEADY_STATE":
        # Low, stable watts, stable HR, stable SmO2
        watts = np.full_like(t, 150.0) + np.random.normal(0, 5, len(t))
        hr = np.full_like(t, 120.0) + np.random.normal(0, 2, len(t))
        smo2 = np.full_like(t, 60.0) + np.random.normal(0, 1, len(t))
        
    elif mode == "NON_STEADY":
        # High watts, HR rising, SmO2 dropping
        watts = np.full_like(t, 250.0) + np.random.normal(0, 5, len(t))
        hr = np.linspace(140, 160, len(t)) + np.random.normal(0, 2, len(t))
        smo2 = np.linspace(60, 40, len(t)) + np.random.normal(0, 1, len(t))
        
    elif mode == "RECOVERY":
        # Low Watts, HR dropping, SmO2 rising
        watts = np.full_like(t, 100.0)
        hr = np.linspace(160, 120, len(t))
        smo2 = np.linspace(40, 60, len(t))
        
    return pd.DataFrame({'time': t, 'watts': watts, 'hr': hr, 'smo2': smo2})

def test_state_machine():
    print("=== Test State Machine ===\n")
    
    # Construct a session: Steady -> Work (Non-Steady) -> Rest (Recovery)
    # 0-180: Steady
    # 180-360: Work
    # 360-540: Rest
    df1 = create_interval_segment(0, 180, "STEADY_STATE")
    df2 = create_interval_segment(180, 180, "NON_STEADY")
    df3 = create_interval_segment(360, 180, "RECOVERY")
    
    full_df = pd.concat([df1, df2, df3], ignore_index=True)
    
    # Generate timeline
    timeline = generate_state_timeline(full_df, window_size_sec=30, step_sec=30)
    
    print("Detected Segments:")
    for seg in timeline:
        print(f"  {seg['start']}-{seg['end']}s: {seg['state']} (Conf: {seg['confidence']:.2f})")
        
    if not timeline:
        print("FAIL: No segments detected")
        sys.exit(1)

    # 1. First segment (should cover 0-100s range primarily)
    first_state = timeline[0]['state']
    assert first_state in ['STEADY_STATE', 'RAMP_UP'], f"Start should be STEADY, got {first_state}"
    
    # 2. Middle section (Work) ~ 180-360
    # Find any states that overlap significantly with the work interval
    mid_states = []
    for s in timeline:
        # Check overlap with 200-340 window (avoid boundaries)
        overlap_start = max(s['start'], 200)
        overlap_end = min(s['end'], 340)
        if overlap_end > overlap_start:
            mid_states.append(s['state'])
            
    print(f"Mid States overlap [200-340]: {mid_states}")
    has_non_steady = any(s in ['NON_STEADY', 'FATIGUE'] for s in mid_states)
    assert has_non_steady, "Middle section should contain NON_STEADY or FATIGUE"
    
    # 3. End section (Recovery) ~ 360+
    # Find overlapping states
    end_states = []
    for s in timeline:
        if s['end'] > 400: # Ends well into recovery
             end_states.append(s['state'])
             
    print(f"End States overlap [400+]: {end_states}")
    has_recovery = any(s == 'RECOVERY' for s in end_states)
    assert has_recovery, "End section should contain RECOVERY"
    
    print("\nState Machine Verification Passed!")

if __name__ == "__main__":
    test_state_machine()
