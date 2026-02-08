import pytest
import numpy as np
import pandas as pd
from modules.calculations.pace import (
    calculate_pace_zones_time,
    calculate_pace_duration_curve,
    classify_running_phenotype,
    estimate_vo2max_from_pace,
    get_phenotype_description
)

def test_calculate_pace_zones_time():
    """Test calculating time spent in each pace zone."""
    # Create sample dataframe with pace data
    df = pd.DataFrame({
        'pace': [300, 300, 330, 330, 330, 270, 270, 240]  # sec/km
    })
    
    # Threshold pace at 300 sec/km (5:00 min/km)
    zones = calculate_pace_zones_time(df, threshold_pace=300)
    
    # Should have 6 zones based on % of threshold
    assert "Z1 Recovery" in zones
    assert "Z2 Aerobic" in zones
    assert "Z3 Tempo" in zones
    assert "Z4 Threshold" in zones
    assert "Z5 Interval" in zones
    assert "Z6 Repetition" in zones
    
    # Check specific counts
    # Z3 Tempo: 95-105% of threshold (285-315 sec/km) -> 300, 300 = 2 samples
    assert zones["Z3 Tempo"] == 2
    # Z4 Threshold: 88-95% of threshold (264-285 sec/km) -> 270, 270 = 2 samples
    assert zones["Z4 Threshold"] == 2
    # Z5 Interval: 75-88% of threshold (225-264 sec/km) -> 240 = 1 sample
    assert zones["Z5 Interval"] == 1
    # Z2 Aerobic: 105-115% of threshold (315-345 sec/km) -> 330, 330, 330 = 3 samples
    assert zones["Z2 Aerobic"] == 3

def test_calculate_pace_duration_curve():
    """Test calculating pace duration curve."""
    # Create 10 minutes of data with varying pace
    np.random.seed(42)
    pace_data = np.concatenate([
        np.full(300, 330),  # 5 min @ 5:30
        np.full(300, 300),  # 5 min @ 5:00
    ])
    
    df = pd.DataFrame({'pace': pace_data})
    
    pdc = calculate_pace_duration_curve(df)
    
    # Should have entries for different durations
    assert len(pdc) > 0
    # Best (lowest) pace should be around 300 sec/km
    valid_paces = [v for v in pdc.values() if v is not None]
    assert min(valid_paces) <= 310

def test_classify_running_phenotype():
    """Test running phenotype classification."""
    # Marathoner profile: strong endurance, lower sprint
    pdc = {
        60: 240,    # 1 min: 4:00 min/km
        300: 255,   # 5 min: 4:15 min/km
        600: 270,   # 10 min: 4:30 min/km
        1200: 285,  # 20 min: 4:45 min/km
        3600: 300   # 60 min: 5:00 min/km
    }
    
    phenotype = classify_running_phenotype(pdc, weight=70)
    assert phenotype in ["marathoner", "ultra_runner", "all_rounder", "middle_distance", "unknown"]

def test_estimate_vo2max_from_pace():
    """Test VO2max estimation from pace."""
    # Using Daniels formula approximation
    vo2max = estimate_vo2max_from_pace(
        vvo2max_pace=240,  # 4:00 min/km at vVO2max
        weight=70
    )
    
    # Should be reasonable VO2max for trained runner (45-65)
    assert 40 <= vo2max <= 80

def test_get_phenotype_description():
    """Test phenotype description."""
    emoji, name, desc = get_phenotype_description("marathoner")
    assert emoji is not None
    assert "maraton" in name.lower() or "Marato" in name

def test_pace_zones_with_empty_dataframe():
    """Test handling empty dataframe."""
    df = pd.DataFrame()
    zones = calculate_pace_zones_time(df, threshold_pace=300)
    assert zones == {}

def test_pace_duration_curve_insufficient_data():
    """Test PDC with insufficient data."""
    df = pd.DataFrame({'pace': [300]})  # Only 1 sample
    pdc = calculate_pace_duration_curve(df, durations=[60, 300])
    
    # Should return None for durations > data length
    assert pdc[60] is None
    assert pdc[300] is None
