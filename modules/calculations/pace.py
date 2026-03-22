"""
SRP: Main pace module for running analysis.

Replaces power.py for running context.
Implements pace zones, pace duration curve, and phenotype classification.

PERFORMANCE: Uses Numba JIT for speed-critical calculations.
"""

from typing import Union, Any, Dict, Tuple, Optional
import numpy as np
import pandas as pd

from .pace_utils import pace_to_speed, speed_to_pace, format_pace
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
        # FIX: Z1 upper limit is infinity to catch ALL slow paces (walk/jog)
        zones = {
            "Z1 Recovery": (1.15, float('inf')),  # >15% slower than threshold (all slow paces)
            "Z2 Aerobic": (1.05, 1.15),    # 5-15% slower
            "Z3 Tempo": (0.95, 1.05),      # Within 5%
            "Z4 Threshold": (0.88, 0.95),  # 5-12% faster
            "Z5 Interval": (0.75, 0.88),   # 12-25% faster
            "Z6 Repetition": (0.0, 0.75),  # >25% faster
        }
    
    # NOTE: This function assumes 1Hz (1-second) sampled data.
    # mask.sum() counts rows, which equals seconds only at 1Hz.
    # Data MUST be resampled to 1s before calling this function.
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


def classify_running_phenotype(pdc: dict, weight: float = 0.0) -> str:
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
    if not pdc:
        return "unknown"

    # Get key pace values - PDC durations are in SECONDS (time-based)
    # These represent best pace sustained for a given duration, NOT distance
    p60s = pdc.get(60)      # best pace over 60-second effort
    p5min = pdc.get(300)    # best pace over 5-minute effort
    p10min = pdc.get(600)   # best pace over 10-minute effort
    p20min = pdc.get(1200)  # best pace over 20-minute effort
    p60min = pdc.get(3600)  # best pace over 60-minute effort

    if not any([p60s, p5min, p10min]):
        return "unknown"

    # Need at least 5min and 10min data for classification
    if p5min is None or p10min is None:
        return "unknown"

    # Calculate pace drop from 5min to 10min effort
    # Endurance runners maintain pace better (smaller drop)
    pace_drop_5_10 = (p10min - p5min) / p5min if p5min > 0 else 0

    # Calculate pace drop from 60s to 5min (if available)
    pace_drop_short_mid = None
    if p60s:
        pace_drop_short_mid = (p5min - p60s) / p60s if p60s > 0 else 0

    # Phenotype scoring
    scores = {
        "sprinter": 0,
        "middle_distance": 0,
        "marathoner": 0,
        "ultra_runner": 0,
        "all_rounder": 0
    }

    # Sprinter: High drop from short to mid effort (fast short, slow long)
    if pace_drop_short_mid and pace_drop_short_mid > 0.15:
        scores["sprinter"] += 2

    # Marathoner: Small drop from 5min to 10min, has long effort data
    if pace_drop_5_10 < 0.05:
        scores["marathoner"] += 2
    if p60min:
        scores["marathoner"] += 1

    # Ultra runner: Has 20min and 60min data, very small drop
    if p20min and p60min:
        pace_drop_20_60 = (p60min - p20min) / p20min if p20min > 0 else 1
        if pace_drop_20_60 < 0.10:
            scores["ultra_runner"] += 2

    # Middle distance: Balanced 5-10min, moderate drop
    if 0.03 <= pace_drop_5_10 <= 0.08:
        scores["middle_distance"] += 2

    # All-rounder: Has data across multiple durations, balanced
    available_durations = sum(1 for p in [p60s, p5min, p10min, p20min, p60min] if p is not None)
    if available_durations >= 3 and max(scores.values()) <= 2:
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


def estimate_vo2max_from_pace(vvo2max_pace: float, weight: float = 0.0) -> float:
    """
    Estimate VO2max from best ~5-6 minute effort pace using Jack Daniels model.

    The Daniels model has two components:
    1. VO2 at a given speed: VO2 = -4.60 + 0.182258*v + 0.000104*v²
    2. Fractional utilisation at a given duration:
       %VO2max = 0.8 + 0.1894393*e^(-0.012778*t) + 0.2989558*e^(-0.1932605*t)
       where t = duration in minutes

    VO2max = VO2(speed) / fractional_utilisation(duration)

    For a ~5-6 minute effort, fractional utilisation ≈ 97-99%.

    Args:
        vvo2max_pace: Pace of best ~5-6 min effort in sec/km
        weight: Runner weight in kg (unused, kept for API compatibility)

    Returns:
        Estimated VO2max in ml/kg/min
    """
    if vvo2max_pace <= 0:
        return 0.0

    # Convert pace to speed (m/min)
    speed_m_per_min = 1000.0 / vvo2max_pace * 60

    # VO2 at this speed (Daniels oxygen cost formula)
    v = speed_m_per_min
    vo2_at_speed = -4.60 + 0.182258 * v + 0.000104 * v * v

    # Fractional utilisation for ~5-6 min effort (t ≈ 5.5 min)
    import math
    t = 5.5  # minutes
    frac_util = 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)

    # VO2max = VO2 / fractional utilisation
    if frac_util <= 0:
        return 0.0

    vo2max = vo2_at_speed / frac_util

    # Clamp to reasonable range
    vo2max = max(20, min(95, vo2max))

    return round(vo2max, 1)


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
    p5min = pdc.get(300)   # 5-min effort pace
    p10min = pdc.get(600)  # 10-min effort pace

    if p5min is None or p10min is None or p5min <= 0:
        return 0.0

    return p10min / p5min


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


# ---------------------------------------------------------------------------
# Critical Speed / D' modelling  (Poole & Jones 2023, Exp Physiol)
# ---------------------------------------------------------------------------

_CS_DURATIONS = [120, 180, 300, 600, 900, 1200]


def fit_critical_speed_from_pdc(
    df: pd.DataFrame,
    pace_col: str = "pace",
    time_col: str = "time",
) -> Dict[str, object]:
    """Fit Critical Speed (CS) and D' from best efforts in activity data.

    Uses the linear distance-time model: distance = CS * time + D'.
    Reference: Poole & Jones 2023 (Experimental Physiology).
    """
    from scipy import stats as sp_stats

    pdc = calculate_pace_duration_curve(df, durations=_CS_DURATIONS)

    times = []
    distances = []
    for dur, best_pace in pdc.items():
        if best_pace is None or best_pace <= 0:
            continue
        speed = 1000.0 / best_pace          # m/s
        times.append(dur)
        distances.append(speed * dur)        # meters

    if len(times) < 2:
        return {
            "cs_m_s": 0.0, "cs_pace_s_km": 0.0, "cs_pace_str": "--:--",
            "d_prime_m": 0.0, "r_squared": 0.0, "data_points": len(times),
            "is_valid": False,
        }

    t_arr = np.array(times, dtype=np.float64)
    d_arr = np.array(distances, dtype=np.float64)

    slope, intercept, r_value, _p, _se = sp_stats.linregress(t_arr, d_arr)

    cs = max(slope, 0.0)
    d_prime = max(intercept, 0.0)
    r_sq = r_value ** 2
    cs_pace = speed_to_pace(cs) if cs > 0 else 0.0
    cs_str = format_pace(cs_pace) + " /km" if cs > 0 else "--:-- /km"

    return {
        "cs_m_s": round(cs, 4),
        "cs_pace_s_km": round(cs_pace, 1),
        "cs_pace_str": cs_str,
        "d_prime_m": round(d_prime, 1),
        "r_squared": round(r_sq, 4),
        "data_points": len(times),
        "is_valid": r_sq > 0.95 and cs > 0,
    }


def calculate_wbal_running(
    pace_series: pd.Series,
    cs_pace: float,
    d_prime_m: float,
    time_col: Optional[pd.Series] = None,
) -> pd.Series:
    """W'bal equivalent for running (D'bal) using Skiba's differential model.

    Depletes D' when speed exceeds CS and reconstitutes when below.
    tau = 546 * exp(-0.01 * (CS - speed)) + 316  (Skiba 2015).

    Args:
        pace_series: Pace in s/km (1 Hz assumed).
        cs_pace: Critical Speed expressed as pace in s/km.
        d_prime_m: D' capacity in metres.
        time_col: Unused, kept for API compatibility.

    Returns:
        pd.Series of D'bal values (metres remaining).
    """
    pace_arr = pace_series.values.astype(np.float64)
    n = len(pace_arr)

    # Convert pace (s/km) -> speed (m/s); guard against zero / nan
    with np.errstate(divide="ignore", invalid="ignore"):
        speed_arr = np.where((pace_arr > 0) & np.isfinite(pace_arr),
                             1000.0 / pace_arr, 0.0)

    cs_speed = 1000.0 / cs_pace if cs_pace > 0 else 0.0
    dt = 1.0  # 1 Hz sampling

    dbal = np.empty(n, dtype=np.float64)
    dbal[0] = d_prime_m

    for i in range(1, n):
        speed = speed_arr[i]
        prev = dbal[i - 1]

        if speed > cs_speed:
            # Depletion
            dbal[i] = max(prev - (speed - cs_speed) * dt, 0.0)
        else:
            # Reconstitution (Skiba 2015 tau model)
            diff = cs_speed - speed
            tau = 546.0 * np.exp(-0.01 * diff) + 316.0
            dbal[i] = prev + (d_prime_m - prev) * (1.0 - np.exp(-diff * dt / tau))

    return pd.Series(dbal, index=pace_series.index, name="dbal")
