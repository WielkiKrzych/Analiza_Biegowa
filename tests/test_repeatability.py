
import sys

# Add project root to path
sys.path.append('/Users/wielkikrzych/Desktop/Tri_Dashboard')

from modules.calculations.repeatability import (
    calculate_repeatability_metrics,
    compare_session_to_baseline
)

def test_repeatability():
    print("=== Test Repeatability Analysis ===\n")
    
    # 1. Create a stable baseline (Low CV)
    # VT1 = 200, 202, 198
    sessions = [
        {'vt1': 200, 'tau': 30},
        {'vt1': 202, 'tau': 32},
        {'vt1': 198, 'tau': 29}
    ]
    
    stats = calculate_repeatability_metrics(sessions)
    vt1_stats = stats['vt1']
    
    print(f"VT1 Stats: Mean={vt1_stats['mean']}, CV={vt1_stats['cv']}%, Class={vt1_stats['class']}")
    
    # Check Math
    # Mean = 200
    # Std = sqrt( ((0)^2 + (2)^2 + (-2)^2) / 2 ) = sqrt(8/2) = 2.0
    # CV = 2/200 = 1.0%
    assert abs(vt1_stats['mean'] - 200.0) < 0.1, "Mean calculation failed"
    assert abs(vt1_stats['cv'] - 1.0) < 0.1, "CV calculation failed"
    assert vt1_stats['class'] == "Excellent", "Should be Excellent (<3%)"
    
    # 2. Compare Current Session (Significant Change)
    # Current VT1 = 215 (Change = +15, +7.5%)
    # Baseline CV is 1%. Change is 7.5%. This is > 1.5*CV. Should be significant.
    current = {'vt1': 215}
    comp = compare_session_to_baseline(current, stats)
    
    res = comp['vt1']
    print(f"Comparison: Current={res['current']}, Diff={res['pct_diff']}%, Sig={res['is_significant']}")
    
    assert res['is_significant'] == True, "Should be significant change"
    assert "Change" in res['status'], "Status text should reflect change"
    
    # 3. Create Unstable Metric (High CV)
    # Tau = 30, 45, 20
    sessions_unstable = [
        {'tau': 30},
        {'tau': 45},
        {'tau': 20}
    ]
    stats_u = calculate_repeatability_metrics(sessions_unstable)
    tau_u = stats_u['tau']
    print(f"Tau Unstable Stats: Mean={tau_u['mean']}, CV={tau_u['cv']}%, Class={tau_u['class']}")
    
    # Mean ~ 31.6, Std ~ 12.5
    # CV ~ 40%
    assert tau_u['cv'] > 10.0, "CV should be high"
    assert tau_u['class'] == "Unstable", "Should be Unstable"
    
    print("\nRepeatability Verification Passed!")

if __name__ == "__main__":
    test_repeatability()
