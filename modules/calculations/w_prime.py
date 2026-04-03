"""
W' (W Prime) Balance Calculations.

Implements Skiba's W' balance algorithm for tracking anaerobic capacity
depletion and reconstitution during exercise.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Try to use Numba-accelerated version if available
try:
    from modules.numba_utils import calculate_w_prime_balance_numba

    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False


def _w_prime_balance_python(
    power: np.ndarray, cp: float, w_prime: float, tau: float = 546.0
) -> np.ndarray:
    """
    Pure-Python fallback for W' balance (Skiba's algorithm).

    Args:
        power: Power values in Watts
        cp: Critical Power
        w_prime: W' (Anaerobic Work Capacity) in Joules
        tau: Recovery time constant

    Returns:
        W' balance array
    """
    n = len(power)
    w_bal = np.empty(n)
    w_bal[0] = w_prime

    for i in range(1, n):
        dt = 1.0  # Assume 1-second intervals

        if power[i] > cp:
            # Depletion
            w_bal[i] = w_bal[i - 1] - (power[i] - cp) * dt
        else:
            # Reconstitution
            w_bal[i] = w_bal[i - 1] + (w_prime - w_bal[i - 1]) * (1 - np.exp(-dt / tau))

        # Clamp to valid range
        w_bal[i] = max(0.0, min(w_prime, w_bal[i]))

    return w_bal


def calculate_w_prime_balance(
    df: pd.DataFrame, cp: float, w_prime: float, tau: float = 546.0
) -> pd.DataFrame:
    """
    Calculate W' balance for the session and add it to the DataFrame.

    Args:
        df: DataFrame with a 'watts' column (1-second data)
        cp: Critical Power in Watts
        w_prime: W' (Anaerobic Work Capacity) in Joules
        tau: Recovery time constant (default 546s per Skiba)

    Returns:
        DataFrame with 'w_prime_balance' column added
    """
    df = df.copy()

    if cp <= 0 or w_prime <= 0:
        logger.warning("CP or W' not set, skipping W' balance calculation.")
        df["w_prime_balance"] = np.nan
        return df

    if "watts" not in df.columns:
        logger.warning("No 'watts' column found, skipping W' balance calculation.")
        df["w_prime_balance"] = np.nan
        return df

    power = df["watts"].fillna(0).values.astype(np.float64)

    if _HAS_NUMBA:
        w_bal = calculate_w_prime_balance_numba(power, cp, w_prime, tau)
    else:
        w_bal = _w_prime_balance_python(power, cp, w_prime, tau)

    df["w_prime_balance"] = w_bal
    return df


def calculate_w_prime_fast(
    power: np.ndarray, cp: float, w_prime: float, tau: float = 546.0
) -> np.ndarray:
    """
    Calculate W' balance array directly from power data (no DataFrame).

    Args:
        power: Power values in Watts
        cp: Critical Power
        w_prime: W' in Joules
        tau: Recovery time constant

    Returns:
        W' balance array
    """
    if _HAS_NUMBA:
        return calculate_w_prime_balance_numba(power, cp, w_prime, tau)
    return _w_prime_balance_python(power, cp, w_prime, tau)


def calculate_recovery_score(w_bal: np.ndarray, w_prime: float) -> float:
    """
    Calculate a recovery score based on W' balance history.

    Higher score = better recovery capability.

    Args:
        w_bal: W' balance array
        w_prime: Initial W' capacity

    Returns:
        Recovery score (0-100)
    """
    if w_prime <= 0 or len(w_bal) == 0:
        return 0.0

    mean_w_bal = np.nanmean(w_bal)
    score = (mean_w_bal / w_prime) * 100
    return round(max(0.0, min(100.0, score)), 1)


def get_recovery_recommendation(recovery_score: float) -> str:
    """
    Get training recommendation based on recovery score.

    Args:
        recovery_score: Recovery score (0-100)

    Returns:
        Recommendation string
    """
    if recovery_score >= 80:
        return "Excellent recovery – ready for high-intensity work."
    elif recovery_score >= 60:
        return "Good recovery – moderate intensity recommended."
    elif recovery_score >= 40:
        return "Fair recovery – consider reduced volume."
    else:
        return "Poor recovery – rest or very easy session recommended."


def estimate_w_prime_reconstitution(w_bal: np.ndarray, w_prime: float, cp: float) -> float:
    """
    Estimate W' reconstitution rate from session data.

    Args:
        w_bal: W' balance array
        w_prime: W' capacity in Joules
        cp: Critical Power

    Returns:
        Estimated reconstitution time constant (tau) in seconds
    """
    if w_prime <= 0 or len(w_bal) < 10:
        return 546.0  # Default tau

    # Find recovery segments (where W' is increasing)
    diffs = np.diff(w_bal)
    recovery_mask = diffs > 0
    recovery_rates = diffs[recovery_mask]

    if len(recovery_rates) == 0:
        return 546.0

    # Estimate tau from average recovery rate
    mean_recovery = np.mean(recovery_rates)
    if mean_recovery > 0:
        tau = (w_prime - np.mean(w_bal[:-1][recovery_mask])) / mean_recovery
        return max(100.0, min(2000.0, tau))

    return 546.0
