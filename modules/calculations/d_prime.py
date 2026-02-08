"""
SRP: D' (D-prime) anaerobic distance capacity module.

Running equivalent of W' in cycling.
D' is the finite distance that can be run above Critical Speed (CS).
"""

from typing import Union, Optional
import numpy as np
from .pace_utils import pace_to_speed, speed_to_pace, pace_array_to_speed_array


def calculate_d_prime_balance(
    pace_sec_per_km: np.ndarray,
    time_sec: np.ndarray,
    critical_speed_pace: float,
    d_prime_capacity: float,
    tau: float = 60.0
) -> np.ndarray:
    """
    Calculate D' balance over time.
    
    D' is depleted when running faster than Critical Speed (lower pace),
    and recharges when running slower.
    
    Args:
        pace_sec_per_km: Array of paces in sec/km
        time_sec: Array of time values in seconds
        critical_speed_pace: Critical Speed pace in sec/km
        d_prime_capacity: Total D' capacity in meters
        tau: Time constant for D' reconstitution (seconds, default 60s)
        
    Returns:
        Array of D' balance values (meters remaining)
    """
    n = len(pace_sec_per_km)
    if n == 0:
        return np.array([])
    
    # Convert paces to speeds
    speeds = pace_array_to_speed_array(pace_sec_per_km)  # m/s
    critical_speed = pace_to_speed(critical_speed_pace)  # m/s
    
    d_prime_balance = np.zeros(n)
    d_prime_balance[0] = d_prime_capacity
    
    for i in range(1, n):
        dt = time_sec[i] - time_sec[i-1]
        current_speed = speeds[i]
        
        if current_speed > critical_speed:
            # Above CS: deplete D' based on excess speed
            excess_speed = current_speed - critical_speed  # m/s
            depletion = excess_speed * dt  # meters
            d_prime_balance[i] = max(0, d_prime_balance[i-1] - depletion)
        else:
            # Below CS: recharge D'
            # Exponential recovery model
            recharge_rate = (d_prime_capacity - d_prime_balance[i-1]) / tau
            recharge = recharge_rate * dt
            d_prime_balance[i] = min(d_prime_capacity, d_prime_balance[i-1] + recharge)
    
    return d_prime_balance


def estimate_time_to_exhaustion_pace(
    target_pace: float,
    critical_speed_pace: float,
    d_prime: float
) -> float:
    """
    Estimate Time to Exhaustion (TTE) at given pace.
    
    Based on Critical Speed model: TTE = D' / (v - CS)
    where v is target speed, CS is critical speed.
    
    Args:
        target_pace: Target pace in sec/km
        critical_speed_pace: Critical Speed pace in sec/km
        d_prime: D' capacity in meters
        
    Returns:
        Time to exhaustion in seconds (inf if target <= CS)
        
    Example:
        >>> estimate_time_to_exhaustion_pace(240, 300, 200)  # 4:00 vs 5:00
        120.0  # ~2 minutes
    """
    if target_pace <= 0:
        raise ValueError(f"target_pace must be positive, got {target_pace}")
    if critical_speed_pace < 0:
        raise ValueError(f"critical_speed_pace cannot be negative, got {critical_speed_pace}")
    if d_prime < 0:
        raise ValueError(f"d_prime cannot be negative, got {d_prime}")
    
    # Convert to speeds
    target_speed = pace_to_speed(target_pace)
    critical_speed = pace_to_speed(critical_speed_pace)
    
    if target_speed <= critical_speed:
        return float("inf")
    
    if d_prime <= 0:
        return 0.0
    
    excess_speed = target_speed - critical_speed
    return d_prime / excess_speed


def count_surges(
    d_prime_balance: np.ndarray,
    d_prime_capacity: float,
    threshold_pct: float = 0.3,
    recovery_pct: float = 0.8
) -> int:
    """
    Count number of surges (significant D' depletions).
    
    A surge is counted when D' drops below threshold.
    
    Args:
        d_prime_balance: D' balance array (meters remaining)
        d_prime_capacity: Full D' capacity (meters)
        threshold_pct: Threshold as fraction of D' (default 30%)
        recovery_pct: Recovery threshold to count next surge (default 80%)
        
    Returns:
        Number of surges
    """
    if d_prime_balance is None or len(d_prime_balance) == 0 or d_prime_capacity <= 0:
        return 0
    
    threshold = d_prime_capacity * threshold_pct
    recovery = d_prime_capacity * recovery_pct
    
    surges = 0
    below_threshold = False
    
    for val in d_prime_balance:
        if val < threshold and not below_threshold:
            # Just dropped below threshold
            surges += 1
            below_threshold = True
        elif val >= recovery:
            # Recovered enough to count next drop as new surge
            below_threshold = False
    
    return surges


def calculate_d_prime_utilization(
    d_prime_balance: np.ndarray,
    d_prime_capacity: float
) -> dict:
    """
    Calculate D' utilization statistics.
    
    Args:
        d_prime_balance: D' balance array
        d_prime_capacity: Full capacity
        
    Returns:
        Dict with utilization stats
    """
    if len(d_prime_balance) == 0:
        return {}
    
    min_balance = np.min(d_prime_balance)
    max_depletion = d_prime_capacity - min_balance
    utilization_pct = (max_depletion / d_prime_capacity) * 100
    
    # Time below various thresholds
    time_below_50 = np.sum(d_prime_balance < d_prime_capacity * 0.5)
    time_below_25 = np.sum(d_prime_balance < d_prime_capacity * 0.25)
    
    return {
        "min_balance_m": round(min_balance, 1),
        "max_depletion_m": round(max_depletion, 1),
        "utilization_pct": round(utilization_pct, 1),
        "time_below_50pct_sec": int(time_below_50),
        "time_below_25pct_sec": int(time_below_25),
    }
