"""
Numba JIT-compiled functions for performance-critical operations.

Provides 10-100x speedup for numerical computations by compiling
Python code to machine code at runtime.
"""

import numpy as np
from typing import Tuple

# Try to import Numba
try:
    from numba import jit, njit, prange

    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

    # Create dummy decorators if Numba not available
    def jit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator if args and callable(args[0]) else decorator

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator if args and callable(args[0]) else decorator

    prange = range


# Rolling statistics
@njit(cache=True)
def rolling_mean_numba(arr: np.ndarray, window: int) -> np.ndarray:
    """
    Fast rolling mean using Numba.

    10-50x faster than Pandas rolling().mean()
    """
    n = len(arr)
    result = np.empty(n)

    for i in range(n):
        start = max(0, i - window + 1)
        end = i + 1
        result[i] = np.mean(arr[start:end])

    return result


@njit(cache=True)
def rolling_std_numba(arr: np.ndarray, window: int) -> np.ndarray:
    """Fast rolling standard deviation."""
    n = len(arr)
    result = np.empty(n)

    for i in range(n):
        start = max(0, i - window + 1)
        end = i + 1
        result[i] = np.std(arr[start:end])

    return result


@njit(cache=True)
def rolling_max_numba(arr: np.ndarray, window: int) -> np.ndarray:
    """Fast rolling maximum."""
    n = len(arr)
    result = np.empty(n)

    for i in range(n):
        start = max(0, i - window + 1)
        end = i + 1
        result[i] = np.max(arr[start:end])

    return result


# Mathematical operations
@njit(cache=True)
def piecewise_linear_numba(
    x: np.ndarray, breakpoints: np.ndarray, slopes: np.ndarray
) -> np.ndarray:
    """
    Fast piecewise linear function evaluation.

    Used in SmO2 breakpoint detection.
    """
    n = len(x)
    result = np.empty(n)

    for i in range(n):
        xi = x[i]

        # Find which segment xi belongs to
        segment = 0
        for j in range(len(breakpoints)):
            if xi >= breakpoints[j]:
                segment = j + 1

        # Calculate value based on segment
        if segment == 0:
            result[i] = slopes[0] * xi
        elif segment >= len(slopes):
            result[i] = slopes[-1] * xi
        else:
            # Interpolate between segments
            bp = breakpoints[segment - 1]
            result[i] = slopes[segment] * (xi - bp) + slopes[segment - 1] * bp

    return result


@njit(cache=True)
def calculate_rss_numba(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate Residual Sum of Squares."""
    n = len(y_true)
    rss = 0.0

    for i in range(n):
        diff = y_true[i] - y_pred[i]
        rss += diff * diff

    return rss


@njit(cache=True)
def linear_regression_numba(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """
    Fast linear regression: y = slope * x + intercept

    Returns: (slope, intercept)
    """
    n = len(x)

    # Calculate means
    x_mean = 0.0
    y_mean = 0.0
    for i in range(n):
        x_mean += x[i]
        y_mean += y[i]
    x_mean /= n
    y_mean /= n

    # Calculate slope and intercept
    numerator = 0.0
    denominator = 0.0
    for i in range(n):
        x_diff = x[i] - x_mean
        y_diff = y[i] - y_mean
        numerator += x_diff * y_diff
        denominator += x_diff * x_diff

    if denominator == 0:
        return 0.0, y_mean

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    return slope, intercept


# Signal processing
@njit(cache=True)
def savgol_filter_numba(arr: np.ndarray, window: int, polyorder: int) -> np.ndarray:
    """
    Simplified Savitzky-Golay filter.

    Uses moving polynomial fitting.
    """
    n = len(arr)
    result = np.empty(n)
    half_window = window // 2

    for i in range(n):
        start = max(0, i - half_window)
        end = min(n, i + half_window + 1)

        # Simple polynomial fit (degree 1 for speed)
        x = np.arange(start, end, dtype=np.float64)
        y = arr[start:end]

        slope, intercept = linear_regression_numba(x, y)
        result[i] = slope * i + intercept

    return result


@njit(cache=True)
def find_peaks_numba(arr: np.ndarray, min_height: float, min_distance: int) -> np.ndarray:
    """
    Find peaks in signal.

    Returns indices of peaks.
    """
    n = len(arr)
    peaks = []

    for i in range(1, n - 1):
        # Check if peak
        if arr[i] > min_height and arr[i] > arr[i - 1] and arr[i] > arr[i + 1]:
            # Check minimum distance from last peak
            if not peaks or i - peaks[-1] >= min_distance:
                peaks.append(i)

    return np.array(peaks, dtype=np.int32)


# Power calculations
@njit(cache=True)
def calculate_w_prime_balance_numba(
    power: np.ndarray, cp: float, w_prime: float, tau: float = 546.0
) -> np.ndarray:
    """
    Calculate W' balance using Skiba's algorithm.

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


# Convenience functions that work with or without Numba


def fast_rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    """Fast rolling mean with Numba fallback."""
    if _NUMBA_AVAILABLE:
        return rolling_mean_numba(arr, window)
    else:
        # Fallback to Pandas
        import pandas as pd

        return pd.Series(arr).rolling(window=window, min_periods=1).mean().values


def fast_rolling_std(arr: np.ndarray, window: int) -> np.ndarray:
    """Fast rolling std with Numba fallback."""
    if _NUMBA_AVAILABLE:
        return rolling_std_numba(arr, window)
    else:
        import pandas as pd

        return pd.Series(arr).rolling(window=window, min_periods=1).std().values


def fast_linear_regression(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Fast linear regression with Numba fallback."""
    if _NUMBA_AVAILABLE:
        return linear_regression_numba(x, y)
    else:
        # Use numpy
        coeffs = np.polyfit(x, y, 1)
        return coeffs[0], coeffs[1]


def is_numba_available() -> bool:
    """Check if Numba is available."""
    return _NUMBA_AVAILABLE
