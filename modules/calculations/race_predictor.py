"""
Race Predictor Module.

Multi-model race time prediction: Riegel, VDOT (Daniels 2022),
Critical Speed / D-prime, individualized exponent (George 2017).
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

STANDARD_DISTANCES: Dict[str, float] = {
    "5K": 5.0, "10K": 10.0, "Half Marathon": 21.0975, "Marathon": 42.195,
}

_WEIGHT_VDOT = 0.4
_WEIGHT_RIEGEL = 0.3
_WEIGHT_CS = 0.3
_CS_FATIGUE_ONSET_KM = 10.0
_CS_FATIGUE_RATE = 0.02


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


def vdot_from_race(distance_km: float, time_sec: float) -> float:
    """Compute VDOT from a race result (Daniels' Running Formula, 2022)."""
    if distance_km <= 0 or time_sec <= 0:
        raise ValueError("Distance and time must be positive.")

    t_min = time_sec / 60.0
    v = distance_km * 1000.0 / t_min  # meters per minute

    vo2 = -4.60 + 0.182258 * v + 0.000104 * v * v
    fraction = (0.8
                + 0.1894393 * math.exp(-0.012778 * t_min)
                + 0.2989558 * math.exp(-0.1932605 * t_min))

    if fraction <= 0:
        raise ValueError("Invalid fraction -- check inputs.")
    return vo2 / fraction


def vdot_predict(vdot: float, target_distance_km: float) -> float:
    """Predict race time (seconds) for a given VDOT via bisection search."""
    if vdot <= 0 or target_distance_km <= 0:
        raise ValueError("VDOT and target distance must be positive.")

    lo = target_distance_km * 120.0   # 2 min/km
    hi = target_distance_km * 900.0   # 15 min/km

    for _ in range(100):
        mid = (lo + hi) / 2.0
        if vdot_from_race(target_distance_km, mid) > vdot:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 0.1:
            break
    return (lo + hi) / 2.0


def fit_critical_speed(
    distances_km: List[float], times_sec: List[float],
) -> Dict[str, float]:
    """Fit CS and D' from 2+ time trials. Returns cs_m_s, d_prime_m, r_squared."""
    if len(distances_km) < 2 or len(distances_km) != len(times_sec):
        raise ValueError("Need at least 2 matching distance/time pairs.")

    distances_m = np.array([d * 1000.0 for d in distances_km])
    times = np.array(times_sec)
    coeffs = np.polyfit(times, distances_m, 1)

    predicted = np.polyval(coeffs, times)
    ss_res = float(np.sum((distances_m - predicted) ** 2))
    ss_tot = float(np.sum((distances_m - np.mean(distances_m)) ** 2))

    return {
        "cs_m_s": float(coeffs[0]),
        "d_prime_m": float(coeffs[1]),
        "r_squared": 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0,
    }


def critical_speed_predict(
    cs_m_s: float, d_prime_m: float, target_distance_km: float,
) -> float:
    """Predict time (seconds) via Critical Speed model with fatigue correction."""
    if cs_m_s <= 0:
        raise ValueError("Critical speed must be positive.")

    target_m = target_distance_km * 1000.0
    base_time = (target_m - d_prime_m) / cs_m_s

    if target_distance_km > _CS_FATIGUE_ONSET_KM:
        fatigue = 1.0 + _CS_FATIGUE_RATE * (target_distance_km - _CS_FATIGUE_ONSET_KM)
        return base_time * fatigue
    return base_time


def individualized_riegel_exponent(
    distances_km: List[float], times_sec: List[float],
) -> float:
    """Fit Riegel exponent from race history on log-log scale (George 2017)."""
    if len(distances_km) < 2 or len(distances_km) != len(times_sec):
        raise ValueError("Need at least 2 matching distance/time pairs.")

    coeffs = np.polyfit(np.log(distances_km), np.log(times_sec), 1)
    return max(1.03, min(float(coeffs[0]), 1.15))


def multi_model_predict(
    known_distance_km: float,
    known_time_sec: float,
    weight_kg: Optional[float] = None,
    race_history: Optional[List[Tuple[float, float]]] = None,
) -> Dict:
    """Combine Riegel, VDOT, and CS models into consensus predictions."""
    vdot = vdot_from_race(known_distance_km, known_time_sec)

    hist_d = [r[0] for r in race_history] if race_history else []
    hist_t = [r[1] for r in race_history] if race_history else []
    has_history = len(hist_d) >= 2

    exponent = individualized_riegel_exponent(hist_d, hist_t) if has_history else 1.06
    cs_params = fit_critical_speed(hist_d, hist_t) if has_history else None

    result: Dict = {}
    for name, dist_km in STANDARD_DISTANCES.items():
        riegel_time = riegel_predict(known_time_sec, known_distance_km, dist_km, exponent)
        vdot_time = vdot_predict(vdot, dist_km)

        cs_time: Optional[float] = None
        if cs_params is not None:
            cs_time = critical_speed_predict(
                cs_params["cs_m_s"], cs_params["d_prime_m"], dist_km,
            )

        if cs_time is not None:
            consensus = (
                _WEIGHT_VDOT * vdot_time
                + _WEIGHT_RIEGEL * riegel_time
                + _WEIGHT_CS * cs_time
            )
        else:
            w = _WEIGHT_VDOT + _WEIGHT_RIEGEL
            consensus = (_WEIGHT_VDOT * vdot_time + _WEIGHT_RIEGEL * riegel_time) / w

        result[name] = {
            "riegel": round(riegel_time, 1),
            "vdot": round(vdot_time, 1),
            "cs": round(cs_time, 1) if cs_time is not None else None,
            "consensus": round(consensus, 1),
        }

    result["vdot"] = round(vdot, 1)
    result["riegel_exponent"] = round(exponent, 4)
    return result
