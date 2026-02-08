
import pandas as pd
import numpy as np
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.kinetics import classify_smo2_context, detect_smo2_trend

def create_mock_window(duration=60, watts_slope=0, hr_slope=0, cadence=90, smo2_slope=-0.05):
    """Create a mock dataframe window for testing context classification."""
    time = np.arange(0, duration)
    
    # Base values
    watts = 200 + watts_slope * time
    hr = 140 + hr_slope * time
    cad = np.full_like(time, cadence)
    
    # Smo2 (Normalized) - starts at 0.8
    smo2 = 0.8 + smo2_slope * time
    
    df = pd.DataFrame({
        'time': time,
        'watts': watts,
        'hr': hr,
        'cadence': cad,
        'smo2': smo2 # treated as normalized for trend detection
    })
    
    return df

def test_context_classification():
    print("=== Test Context Classification ===\n")

    # Scenario 1: Demand Driven
    # Power rising fast (>0.5 W/s), SmO2 dropping
    df_demand = create_mock_window(watts_slope=1.0, smo2_slope=-0.02, cadence=90)
    trend_res = detect_smo2_trend(df_demand['time'], df_demand['smo2'])
    ctx_demand = classify_smo2_context(df_demand, trend_res)
    print(f"Scenario 1 (Rising Power): {ctx_demand['cause']}")
    assert ctx_demand['cause'] == "Napędzany popytem", "Should identify as Demand Driven"
    
    # Scenario 2: Mechanical Occlusion (Grinding)
    # Power steady, Low Cadence (50), SmO2 dropping
    df_grind = create_mock_window(watts_slope=0, smo2_slope=-0.02, cadence=50) # < 65 rpm
    trend_res = detect_smo2_trend(df_grind['time'], df_grind['smo2'])
    ctx_grind = classify_smo2_context(df_grind, trend_res)
    print(f"Scenario 2 (Low Cadence): {ctx_grind['cause']}")
    assert ctx_grind['cause'] == "Okluzja mechaniczna", "Should identify as Mechanical Occlusion"

    # Scenario 3: Delivery Limitation
    # Power steady, HR steady (implied max or steady), SmO2 dropping
    df_limit = create_mock_window(watts_slope=0, smo2_slope=-0.02, cadence=90)
    trend_res = detect_smo2_trend(df_limit['time'], df_limit['smo2'])
    ctx_limit = classify_smo2_context(df_limit, trend_res)
    print(f"Scenario 3 (Steady Power): {ctx_limit['cause']}")
    assert ctx_limit['cause'] == "Ograniczenie dostawy", "Should identify as Delivery Limitation"
    
    # Scenario 4: Efficiency Loss (Fading)
    # Power dropping (< -0.5 W/s), but SmO2 STILL dropping!
    df_fade = create_mock_window(watts_slope=-1.0, smo2_slope=-0.02, cadence=80)
    trend_res = detect_smo2_trend(df_fade['time'], df_fade['smo2'])
    ctx_fade = classify_smo2_context(df_fade, trend_res)
    print(f"Scenario 4 (Dropping Power): {ctx_fade['cause']}")
    assert ctx_fade['cause'] == "Utrata efektywności", "Should identify as Efficiency Loss"

    print("\nAll Context Tests Passed!")

if __name__ == "__main__":
    test_context_classification()
