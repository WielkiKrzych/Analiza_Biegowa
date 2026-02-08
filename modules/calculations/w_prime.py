"""
SRP: Moduł odpowiedzialny za obliczenia W' Balance (Skarbiec Beztlenowy).
"""
from typing import Union
import numpy as np
import pandas as pd
import io
from numba import jit

from ..utils import _serialize_df_to_parquet_bytes


@jit(nopython=True, fastmath=True)
def calculate_w_prime_fast(watts, time, cp, w_prime_cap):
    """Szybkie obliczenie W' Balance przy użyciu Numba JIT.
    
    Implementacja modelu różnicowego W' Skiba/Morton.
    
    Args:
        watts: Tablica mocy [W]
        time: Tablica czasów [s]
        cp: Critical Power [W]
        w_prime_cap: Pojemność W' [J]
    
    Returns:
        Tablica wartości W' Balance w czasie
    """
    n = len(watts)
    w_bal = np.empty(n, dtype=np.float64)
    curr_w = w_prime_cap
    
    prev_time = time[0]
    
    for i in range(n):
        if i == 0:
            dt = 1.0
        else:
            dt = time[i] - prev_time
            if dt <= 0: dt = 1.0
            prev_time = time[i]
            
        # Differential W' Model: dW/dt = CP - P
        delta = (cp - watts[i]) * dt
        
        # Integral
        curr_w += delta
        
        # Boundary conditions
        if curr_w > w_prime_cap:
            curr_w = w_prime_cap
        elif curr_w < 0:
            curr_w = 0.0
            
        w_bal[i] = curr_w
        
    return w_bal


def _calculate_w_prime_balance_cached(df_bytes: bytes, cp: float, w_prime: float):
    """Cached version of W' Balance calculation."""
    try:
        bio = io.BytesIO(df_bytes)
        try:
            df_pd = pd.read_parquet(bio)
        except Exception:
            bio.seek(0)
            df_pd = pd.read_csv(bio)

        if 'watts' not in df_pd.columns:
            df_pd['w_prime_balance'] = np.nan
            return df_pd

        watts_arr = df_pd['watts'].to_numpy(dtype=np.float64)
        
        if 'time' in df_pd.columns:
            time_arr = df_pd['time'].to_numpy(dtype=np.float64)
        else:
            time_arr = np.arange(len(watts_arr), dtype=np.float64)

        w_bal = calculate_w_prime_fast(watts_arr, time_arr, float(cp), float(w_prime))

        df_pd['w_prime_balance'] = w_bal
        return df_pd

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"W' calculation failed: {e}")
        # Try to return DataFrame with zero W' balance
        try:
            bio = io.BytesIO(df_bytes)
            try:
                df_pd = pd.read_parquet(bio)
            except (ImportError, ValueError):
                bio.seek(0)
                df_pd = pd.read_csv(bio)
            df_pd['w_prime_balance'] = 0.0
            return df_pd
        except (pd.errors.ParserError, ValueError, KeyError) as recovery_error:
            logging.getLogger(__name__).error(f"W' recovery failed: {recovery_error}")
            return pd.DataFrame({'w_prime_balance': []})


def calculate_w_prime_balance(_df_pl_active, cp: float, w_prime: float) -> pd.DataFrame:
    """Calculate W' Balance for the entire workout.
    
    Args:
        _df_pl_active: DataFrame with workout data
        cp: Critical Power [W]
        w_prime: W' capacity [J]
    
    Returns:
        DataFrame with added 'w_prime_balance' column
    """
    if isinstance(_df_pl_active, dict):
        df_pd = pd.DataFrame(_df_pl_active)
    elif hasattr(_df_pl_active, 'to_pandas'):
        df_pd = _df_pl_active.to_pandas()
    else:
        df_pd = _df_pl_active.copy()
    
    if 'time' not in df_pd.columns:
        df_pd['time'] = np.arange(len(df_pd), dtype=float)
    
    df_bytes = _serialize_df_to_parquet_bytes(df_pd)
    result_df = _calculate_w_prime_balance_cached(df_bytes, float(cp), float(w_prime))
    return result_df


# ============================================================
# NEW: Recovery Score - TrainerRoad Readiness Inspired
# ============================================================

def calculate_recovery_score(
    w_bal_end: float,
    w_prime_capacity: float,
    time_since_effort_sec: int = 0,
    tau_seconds: float = 400.0,
    time_bonus_max: float = 30.0,
    return_rich: bool = False
) -> Union[float, 'RecoveryScoreResult']:
    """Calculate Recovery Score based on W' balance state.
    
    Estimates readiness for next high-intensity effort based on
    current W' balance and time since last effort.
    
    Recovery Score 0-100:
    - 90-100: Fully recovered, ready for any intensity
    - 70-90: Well recovered, can do threshold work
    - 50-70: Partially recovered, endurance zone preferred
    - 30-50: Fatigued, recovery ride only
    - <30: Exhausted, rest needed
    
    Args:
        w_bal_end: Current W' balance (J)
        w_prime_capacity: Full W' capacity (J)
        time_since_effort_sec: Time since last high-intensity effort
        tau_seconds: Time constant for W' reconstitution (default: 400s)
        time_bonus_max: Maximum time bonus points (default: 30)
        return_rich: If True, return RecoveryScoreResult; if False, return float
        
    Returns:
        RecoveryScoreResult object (or float if return_rich=False)
    """
    from models import RecoveryScoreResult
    
    if w_prime_capacity <= 0:
        if return_rich:
            return RecoveryScoreResult(
                score=0.0, w_pct=0.0, time_bonus=0.0,
                tau_seconds=tau_seconds, time_bonus_max=time_bonus_max,
                recommendation=("❌ Brak danych", "Brak danych W'")
            )
        return 0.0
    
    # Base score from W' percentage
    w_pct = (w_bal_end / w_prime_capacity) * 100
    
    # Time bonus (W' recovers over time)
    time_bonus = 0.0
    if time_since_effort_sec > 0:
        # Exponential recovery model
        recovery_factor = 1 - np.exp(-time_since_effort_sec / tau_seconds)
        time_bonus = recovery_factor * time_bonus_max
    
    score = min(100, w_pct + time_bonus)
    score = round(max(0, score), 0)
    
    if return_rich:
        recommendation = get_recovery_recommendation(score)
        return RecoveryScoreResult(
            score=score,
            w_pct=w_pct,
            time_bonus=time_bonus,
            tau_seconds=tau_seconds,
            time_bonus_max=time_bonus_max,
            recommendation=recommendation
        )
    return score


def get_recovery_recommendation(score: float) -> tuple:
    """Get training recommendation based on Recovery Score.
    
    Args:
        score: Recovery Score (0-100)
        
    Returns:
        Tuple of (zone_recommendation, description)
    """
    if score >= 90:
        return ("🟢 Pełna gotowość", "Możesz wykonać dowolny trening, włącznie z VO2max i sprintami.")
    elif score >= 70:
        return ("🟢 Dobra gotowość", "Trening progowy lub Sweet Spot OK. Unikaj maksymalnych wysiłków.")
    elif score >= 50:
        return ("🟡 Częściowe odzyskanie", "Zalecana strefa Z2/Z3. Skup się na objętości, nie intensywności.")
    elif score >= 30:
        return ("🟠 Zmęczenie", "Tylko łatwa jazda regeneracyjna (Z1). Odpoczywaj.")
    else:
        return ("🔴 Wyczerpanie", "Dzień wolny lub bardzo łatwa aktywność. Priorytet: regeneracja.")


def estimate_w_prime_reconstitution(
    depleted_pct: float,
    recovery_time_sec: int,
    tau: float = 400
) -> float:
    """Estimate W' reconstitution after recovery period.
    
    Uses exponential recovery model: W'(t) = W'_depleted * (1 - e^(-t/tau))
    
    Args:
        depleted_pct: How much W' was depleted (0-100%)
        recovery_time_sec: Recovery time in seconds
        tau: Time constant for W' reconstitution (default 400s)
        
    Returns:
        Estimated W' as percentage of capacity after recovery
    """
    remaining_pct = 100 - depleted_pct
    
    # How much of the depletion is recovered
    recovery_factor = 1 - np.exp(-recovery_time_sec / tau)
    recovered = depleted_pct * recovery_factor
    
    return round(remaining_pct + recovered, 1)

