"""
Race Predictor Module.

Predicts finish times for various race distances using Riegel formula.
"""

from typing import Dict, Optional
import math


def riegel_predict(t1: float, d1: float, d2: float, exponent: float = 1.06) -> float:
    """
    Predict time for distance d2 based on performance at d1.
    Riegel formula: t2 = t1 * (d2/d1)^exponent
    """
    if t1 <= 0 or d1 <= 0 or d2 <= 0:
        return 0.0
    
    # Adjust exponent for ultra distances
    if d2 > 42:
        exponent = 1.15
    elif d2 > 21:
        exponent = 1.08
    
    return t1 * math.pow(d2 / d1, exponent)


def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"


def predict_race_times(known_distance_km: float, known_time_sec: float) -> Dict[str, float]:
    """Predict times for standard race distances."""
    distances = {
        "5K": 5,
        "10K": 10,
        "Half Marathon": 21.097,
        "Marathon": 42.195,
    }
    
    predictions = {}
    for name, distance in distances.items():
        if distance == known_distance_km:
            predictions[name] = known_time_sec
        else:
            predictions[name] = riegel_predict(known_time_sec, known_distance_km, distance)
    
    return predictions
