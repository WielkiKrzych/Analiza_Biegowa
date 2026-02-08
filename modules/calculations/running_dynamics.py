"""
Running Dynamics Analysis Module.

Analyzes biomechanical metrics from Garmin/Stryd:
- Cadence (SPM - steps per minute)
- Ground Contact Time (GCT)
- Vertical Oscillation
- Stride Length
- Running Effectiveness
"""

from typing import Dict, Optional, Union, Any
import numpy as np
import pandas as pd
from .pace_utils import pace_to_speed


def calculate_cadence_stats(cadence_spm: np.ndarray) -> Dict:
    """Calculate cadence statistics."""
    valid_cadence = cadence_spm[(cadence_spm > 50) & (cadence_spm < 300)]
    
    if len(valid_cadence) == 0:
        return {"mean_spm": 0.0, "std_spm": 0.0, "zone": "unknown"}
    
    mean_spm = float(np.mean(valid_cadence))
    std_spm = float(np.std(valid_cadence))
    
    if mean_spm < 160:
        zone = "low"
    elif mean_spm < 170:
        zone = "low-moderate"
    elif mean_spm < 180:
        zone = "optimal"
    elif mean_spm < 190:
        zone = "high"
    else:
        zone = "very-high"
    
    return {
        "mean_spm": round(mean_spm, 1),
        "std_spm": round(std_spm, 1),
        "min_spm": int(np.min(valid_cadence)),
        "max_spm": int(np.max(valid_cadence)),
        "zone": zone,
        "cv_pct": round(std_spm / mean_spm * 100, 1) if mean_spm > 0 else 0
    }


def calculate_gct_stats(gct_ms: np.ndarray) -> Dict:
    """Calculate Ground Contact Time statistics."""
    valid_gct = gct_ms[(gct_ms > 100) & (gct_ms < 400)]
    
    if len(valid_gct) == 0:
        return {"mean_ms": 0.0, "classification": "unknown"}
    
    mean_ms = float(np.mean(valid_gct))
    
    if mean_ms < 200:
        classification = "excellent"
    elif mean_ms < 220:
        classification = "good"
    elif mean_ms < 240:
        classification = "average"
    else:
        classification = "needs-improvement"
    
    return {
        "mean_ms": round(mean_ms, 1),
        "std_ms": round(float(np.std(valid_gct)), 1),
        "min_ms": int(np.min(valid_gct)),
        "max_ms": int(np.max(valid_gct)),
        "classification": classification
    }


def calculate_stride_metrics(df_pl: Union[pd.DataFrame, Any], runner_height: float) -> Dict:
    """Calculate stride length and related metrics."""
    df = df_pl if isinstance(df_pl, pd.DataFrame) else df_pl.to_pandas()
    
    if "cadence" not in df.columns or "pace" not in df.columns:
        return {}
    
    valid = df[(df["cadence"] > 50) & (df["cadence"] < 300) & (df["pace"] > 0)]
    
    if len(valid) == 0:
        return {}
    
    speed_m_s = pace_to_speed(valid["pace"].values)
    cadence_spm = valid["cadence"].values
    
    # Stride length = speed / (cadence / 60) * 2
    stride_length_m = speed_m_s / (cadence_spm / 60) * 2
    
    mean_stride = float(np.mean(stride_length_m))
    height_m = runner_height / 100
    
    return {
        "stride_length_m": round(mean_stride, 3),
        "stride_length_std_m": round(float(np.std(stride_length_m)), 3),
        "height_ratio": round(mean_stride / height_m, 2),
        "samples": len(valid)
    }


def analyze_cadence_drift(cadence_spm: np.ndarray, min_samples: int = 100) -> Dict:
    """Analyze cadence drift over workout."""
    valid = cadence_spm[(cadence_spm > 50) & (cadence_spm < 300)]
    
    if len(valid) < min_samples:
        return {"drift_spm": 0.0, "classification": "insufficient-data"}
    
    mid = len(valid) // 2
    mean_first = float(np.mean(valid[:mid]))
    mean_second = float(np.mean(valid[mid:]))
    
    drift_spm = mean_second - mean_first
    drift_pct = (drift_spm / mean_first) * 100 if mean_first > 0 else 0
    
    if drift_pct < -5:
        classification = "significant-drop"
    elif drift_pct < -2:
        classification = "moderate-drop"
    elif drift_pct < 2:
        classification = "stable"
    else:
        classification = "increased"
    
    return {
        "drift_spm": round(drift_spm, 1),
        "drift_pct": round(drift_pct, 1),
        "classification": classification
    }


def calculate_running_effectiveness(pace_sec_per_km: float, running_power: float, weight_kg: float) -> float:
    """Calculate Running Effectiveness (RE). RE = Speed (m/s) / Power (W/kg)."""
    if pace_sec_per_km <= 0 or running_power <= 0 or weight_kg <= 0:
        return 0.0
    
    speed = pace_to_speed(pace_sec_per_km)
    power_per_kg = running_power / weight_kg
    
    return speed / power_per_kg
