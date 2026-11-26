"""
Integration tests for running analysis pipeline.
"""

import numpy as np
import pandas as pd

from modules.calculations.dual_mode import calculate_running_stress_score, detect_available_metrics
from modules.calculations.gap import calculate_gap
from modules.calculations.pace import calculate_pace_duration_curve, calculate_pace_zones_time
from modules.calculations.running_dynamics import calculate_cadence_stats


def test_full_running_pipeline():
    """Test complete running analysis pipeline."""
    np.random.seed(42)
    n_samples = 600

    df = pd.DataFrame(
        {
            "time": np.arange(n_samples),
            "pace": 300 + np.random.normal(0, 10, n_samples),
            "heartrate": 150 + np.random.normal(0, 5, n_samples),
            "cadence": 170 + np.random.normal(0, 3, n_samples),
            "power": 250 + np.random.normal(0, 10, n_samples),
        }
    )

    # Test pace calculations
    zones = calculate_pace_zones_time(df, threshold_pace=300)
    assert len(zones) > 0

    # Test running dynamics
    cadence_stats = calculate_cadence_stats(df["cadence"].values)
    assert cadence_stats["mean_spm"] > 0

    # Test dual mode
    metrics = detect_available_metrics(df)
    assert metrics["has_pace"]
    assert metrics["has_power"]


def test_pace_duration_curve_integration():
    """Test pace duration curve with real-like data."""
    paces = np.concatenate(
        [
            np.full(120, 360),
            np.full(300, 300),
            np.full(180, 270),
        ]
    )

    df = pd.DataFrame({"pace": paces})
    pdc = calculate_pace_duration_curve(df)

    valid_paces = [v for v in pdc.values() if v is not None]
    assert len(valid_paces) > 0
    assert min(valid_paces) <= 310


def test_gap_calculation():
    """Test GAP calculation."""
    pace = 300  # 5:00 min/km

    # Uphill should make GAP faster
    gap_uphill = calculate_gap(pace, grade=5.0)
    assert gap_uphill < pace

    # Flat should stay the same
    gap_flat = calculate_gap(pace, grade=0.0)
    assert abs(gap_flat - pace) < 1

    # Downhill should make GAP slower
    gap_downhill = calculate_gap(pace, grade=-5.0)
    assert gap_downhill > pace


def test_rss_calculation():
    """Test Running Stress Score calculation."""
    df = pd.DataFrame(
        {
            "pace": np.full(600, 300)  # 10 min @ 5:00/km
        }
    )

    rss = calculate_running_stress_score(df, threshold_pace=300, duration_sec=600)

    # Should be positive
    assert rss > 0
    # Should be reasonable (10 min at threshold ~ 27 RSS)
    assert rss < 50
