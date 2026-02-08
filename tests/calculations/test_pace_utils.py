import pytest
import numpy as np
from modules.calculations.pace_utils import (
    pace_to_speed, speed_to_pace, format_pace, 
    pace_to_seconds, seconds_to_pace_str
)

def test_pace_to_speed():
    """Test converting min/km to m/s."""
    # 5:00 min/km = 300s/km = 3.33 m/s
    assert pace_to_speed(300) == pytest.approx(3.333, rel=0.01)
    # 4:00 min/km = 240s/km = 4.17 m/s
    assert pace_to_speed(240) == pytest.approx(4.167, rel=0.01)

def test_speed_to_pace():
    """Test converting m/s to min/km."""
    # 3.33 m/s = 300s/km = 5:00 min/km
    assert speed_to_pace(3.333) == pytest.approx(300, rel=0.01)
    # 4.17 m/s = 240s/km = 4:00 min/km
    assert speed_to_pace(4.167) == pytest.approx(240, rel=0.01)

def test_pace_speed_roundtrip():
    """Test that pace→speed→pace roundtrip works."""
    original_pace = 300  # 5:00 min/km
    speed = pace_to_speed(original_pace)
    recovered_pace = speed_to_pace(speed)
    assert original_pace == pytest.approx(recovered_pace, rel=0.001)

def test_format_pace():
    """Test formatting pace as mm:ss."""
    assert format_pace(300) == "5:00"
    assert format_pace(245) == "4:05"
    assert format_pace(367) == "6:07"
    assert format_pace(0) == "--:--"

def test_pace_to_seconds():
    """Test converting mm:ss string to seconds."""
    assert pace_to_seconds("5:00") == 300
    assert pace_to_seconds("4:30") == 270
    assert pace_to_seconds("6:15") == 375

def test_seconds_to_pace_str():
    """Test converting seconds to mm:ss string."""
    assert seconds_to_pace_str(300) == "5:00"
    assert seconds_to_pace_str(270) == "4:30"
