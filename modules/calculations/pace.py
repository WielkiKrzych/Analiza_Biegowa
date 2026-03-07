"""
SRP: Main pace module for running analysis.

Replaces power.py for running context.
Implements pace zones, pace duration curve, and phenotype classification.

PERFORMANCE: Uses Numba JIT for speed-critical calculations.
"""

from typing import Union, Any, Dict, Tuple, Optional
import numpy as np
import pandas as pd

from .pace_utils import pace_to_speed, speed_to_pace
from .common import ensure_pandas
from modules.numba_utils import is_numba_available

NUMBA_AVAILABLE = is_numba_available()

if NUMBA_AVAILABLE:
    from numba import njit, prange


def calculate_pace_zones_time(
    df_pl: Union[pd.DataFrame, Any], 
    threshold_pace: float,
    zones: dict = None
) -> dict:
    """
    Calculate time spent in each pace zone.
    
    Default zones based on % of threshold pace:
    - Z1 Recovery: >115% threshold (slower)
    - Z2 Aerobic: 105-115% threshold
    - Z3 Tempo: 95-105% threshold
    - Z4 Threshold: 88-95% threshold
    - Z5 Interval: 75-88% threshold
    - Z6 Repetition: <75% threshold (faster)
    
    Note: For pace, LOWER is FASTER, so percentages are inverted vs power.
    
    Args:
        df_pl: DataFrame with 'pace' column (sec/km)
        threshold_pace: Threshold pace in sec/km
        zones: Optional custom zone definitions (as % of threshold)
        
    Returns:
        Dict mapping zone name to seconds spent
    """
    df = ensure_pandas(df_pl)
    
    if "pace" not in df.columns or threshold_pace <= 0:
        return {}
    
    if zones is None:
        # Zones as % of threshold pace
        # Lower pace % = faster = higher zone
        zones = {
            "Z1 Recovery": (1.15, 2.0),    # >15% slower than threshold
            "Z2 Aerobic": (1.05, 1.15),    # 5-15% slower
            "Z3 Tempo": (0.95, 1.05),      # Within 5%
            "Z4 Threshold": (0.88, 0.95),  # 5-12% faster
            "Z5 Interval": (0.75, 0.88),   # 12-25% faster
            "Z6 Repetition": (0.0, 0.75),  # >25% faster
        }
    
    pace = df["pace"].fillna(threshold_pace * 2)  # NaN = very slow
    results = {}
    
    for zone_name, (low_pct, high_pct) in zones.items():
        low_pace = threshold_pace * low_pct
        high_pace = threshold_pace * high_pct
        
        # For pace: lower value = faster
        mask = (pace >= low_pace) & (pace < high_pace)
        seconds_in_zone = mask.sum()
        results[zone_name] = int(seconds_in_zone)
    
    return results


DEFAULT_PDC_DURATIONS = [60, 120, 180, 300, 600, 1200, 1800, 3600, 7200]


if NUMBA_AVAILABLE:
    @njit(cache=True)
    def _calculate_pdc_numba(pace: np.ndarray, durations: np.ndarray) -> np.ndarray:
        n = len(pace)
        m = len(durations)
        results = np.empty(m, dtype=np.float64)
        
        for i in range(m):
            duration = int(durations[i])
            if n < duration:
                results[i] = np.nan
                continue
            
            best_pace = np.inf
            for j in range(n - duration + 1):
                window_mean = np.mean(pace[j:j + duration])
                if window_mean < best_pace:
                    best_pace = window_mean
            
            if best_pace == np.inf:
                results[i] = np.nan
            else:
                results[i] = best_pace
        
        return results


def calculate_pace_duration_curve(
    df_pl: Union[pd.DataFrame, Any], 
    durations: list = None
) -> dict:
    """Calculate Pace Duration Curve (best pace for each duration).
    
    Similar to Power Duration Curve but for pace.
    Returns the BEST (lowest) pace achieved for each duration.
    """
    df = ensure_pandas(df_pl)
    
    if "pace" not in df.columns:
        return {}
    
    if durations is None:
        durations = DEFAULT_PDC_DURATIONS
    
    pace = df["pace"].ffill().bfill().values
    n = len(pace)
    
    if NUMBA_AVAILABLE and n > 100:
        try:
            durations_arr = np.array(durations, dtype=np.float64)
            results_arr = _calculate_pdc_numba(pace, durations_arr)
            
            results = {}
            for i, duration in enumerate(durations):
                val = results_arr[i]
                results[duration] = None if np.isnan(val) else float(val)
            return results
        except Exception:
            pass
    
    results = {}
    for duration in durations:
        if n < duration:
            results[duration] = None
            continue
        
        rolling = pd.Series(pace).rolling(window=duration, min_periods=duration).mean()
        best_pace = rolling.min()
        
        if pd.notna(best_pace):
            results[duration] = float(best_pace)
        else:
            results[duration] = None
    
    return results


def classify_running_phenotype(pdc: dict, weight: float) -> str:
    """
    Classify runner phenotype based on Pace Duration Curve.
    
    Phenotypes:
    - sprinter: Strong short distances (400m-1km)
    - middle_distance: Strong 5K-10K
    - marathoner: Strong half to full marathon
    - ultra_runner: Strong ultra distances
    - all_rounder: Balanced profile
    
    Args:
        pdc: Pace Duration Curve (duration sec -> pace sec/km)
        weight: Runner weight in kg
        
    Returns:
        Phenotype string identifier
    """
    if not pdc or weight <= 0:
        return "unknown"
    
    # Get key pace values - PDC durations are in SECONDS (time-based)
    p60s = pdc.get(60)    # 60-second effort
    p5min = pdc.get(300)  # 5-minute effort
    p10min = pdc.get(600) # 10-minute effort
    p20min = pdc.get(1200) # 20-minute effort (if available)
    p60min = pdc.get(3600) # 60-minute effort
    
    if not any([p1k, p5k, p10k]):
        return "unknown"
    
    # Need at least 5K and 10K data for classification
    if p5k is None or p10k is None:
        return "unknown"
    
    # Calculate pace drop from 5K to 10K
    # Marathoners maintain pace better (smaller drop)
    pace_drop_5k_10k = (p10k - p5k) / p5k if p5k > 0 else 0
    
    # Calculate pace drop from 1K to 5K (if available)
    pace_drop_1k_5k = None
    if p1k:
        pace_drop_1k_5k = (p5k - p1k) / p1k if p1k > 0 else 0
    
    # Phenotype scoring
    scores = {
        "sprinter": 0,
        "middle_distance": 0,
        "marathoner": 0,
        "ultra_runner": 0,
        "all_rounder": 0
    }
    
    # Sprinter: High drop from 1K to 5K (fast short, slow long)
    if pace_drop_1k_5k and pace_drop_1k_5k > 0.15:
        scores["sprinter"] += 2
    
    # Marathoner: Small drop from 5K to 10K, has marathon data
    if pace_drop_5k_10k < 0.05:
        scores["marathoner"] += 2
    if p42k:
        scores["marathoner"] += 1
    
    # Ultra runner: Has half marathon and marathon data, very small drop
    if p21k and p42k:
        pace_drop_21k_42k = (p42k - p21k) / p21k if p21k > 0 else 1
        if pace_drop_21k_42k < 0.10:
            scores["ultra_runner"] += 2
    
    # Middle distance: Balanced 5K-10K, moderate drop
    if 0.03 <= pace_drop_5k_10k <= 0.08:
        scores["middle_distance"] += 2
    
    # All-rounder: Has data across all distances, balanced
    available_distances = sum(1 for p in [p1k, p5k, p10k, p21k, p42k] if p is not None)
    if available_distances >= 3 and max(scores.values()) <= 2:
        scores["all_rounder"] += 2
    
    # Find highest scoring phenotype
    phenotype = max(scores, key=scores.get)
    
    if scores[phenotype] == 0:
        return "unknown"
    
    return phenotype


def get_phenotype_description(phenotype: str) -> tuple:
    """
    Get phenotype emoji, name, and description.
    
    Args:
        phenotype: Phenotype identifier
        
    Returns:
        Tuple of (emoji, name, description)
    """
    phenotypes = {
        "sprinter": (
            "⚡",
            "Sprinter",
            "Mocny w krótkich dystansach (400m-1km). Wysoka prędkość maksymalna."
        ),
        "middle_distance": (
            "🏃",
            "Średnie dystanse",
            "Specjalista 5K-10K. Dobre połączenie szybkości i wytrzymałości."
        ),
        "marathoner": (
            "🏃‍♂️",
            "Maratończyk",
            "Specjalista maratonu. Doskonała wytrzymałość i ekonomia biegu."
        ),
        "ultra_runner": (
            "🦶",
            "Ultra-biegacz",
            "Specjalista ultra. Niesamowita wytrzymałość i odporność."
        ),
        "all_rounder": (
            "🔄",
            "Wszechstronny",
            "Zbalansowany profil. Dobry na różnych dystansach."
        ),
        "unknown": (
            "❓",
            "Nieznany",
            "Za mało danych do klasyfikacji."
        )
    }
    
    return phenotypes.get(phenotype, phenotypes["unknown"])


def estimate_vo2max_from_pace(vvo2max_pace: float, weight: float) -> float:
    """
    Estimate VO2max from velocity at VO2max pace.
    
    Uses Jack Daniels approximation:
    VO2max ≈ (vVO2max_speed / 1000 * 60) * C + 7
    where C is the oxygen cost of running (~3.5 ml/kg/min per min/km)
    
    Args:
        vvo2max_pace: Pace at vVO2max in sec/km (typically 6-min race pace)
        weight: Runner weight in kg (for validation)
        
    Returns:
        Estimated VO2max in ml/kg/min
    """
    if vvo2max_pace <= 0 or weight <= 0:
        return 0.0
    
    # Convert pace to speed (m/min)
    speed_m_per_min = 1000.0 / vvo2max_pace * 60
    
    # Daniels formula: VO2 = -4.60 + 0.182258 * v + 0.000104 * v^2
    # where v is speed in meters/min
    v = speed_m_per_min
    vo2 = -4.60 + 0.182258 * v + 0.000104 * v * v
    
    # Clamp to reasonable range
    vo2 = max(20, min(90, vo2))
    
    return round(vo2, 1)


def calculate_fatigue_resistance_index_pace(
    pdc: Dict[int, float]
) -> float:
    """
    Calculate Fatigue Resistance Index for pace.
    
    FRI = pace_10k / pace_5k
    Lower is better (closer to 1.0 = better endurance)
    
    Args:
        pdc: Pace Duration Curve
        
    Returns:
        FRI ratio (typically 1.02-1.15)
    """
    # FRI uses time-based PDC: 300s (5-min) and 600s (10-min) efforts
    p5min = pdc.get(300)  # 5-min effort pace
    p10min = pdc.get(600) # 10-min effort pace
    
    if p5k is None or p10k is None or p5k <= 0:
        return 0.0
    
    return p10k / p5k


def get_fri_interpretation_pace(fri: float) -> str:
    """
    Get human-readable interpretation of FRI for pace.
    
    Args:
        fri: Fatigue Resistance Index
        
    Returns:
        Polish interpretation string
    """
    if fri <= 1.02:
        return "🟢 Wyjątkowa wytrzymałość"
    elif fri <= 1.05:
        return "🟢 Bardzo dobra wytrzymałość"
    elif fri <= 1.08:
        return "🟡 Dobra wytrzymałość"
    elif fri <= 1.12:
        return "🟠 Przeciętna"
    else:
        return "🔴 Niska wytrzymałość"
