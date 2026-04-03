"""
Shared utilities for SmO2 advanced calculations.

Provides Numba-optimized gradient/curvature helpers and common constants
used by smo2_analysis and smo2_thresholds modules.
"""

import logging

import numpy as np

try:
    from numba import jit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    # Create dummy decorator if numba not available
    def jit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


logger = logging.getLogger("Tri_Dashboard.SmO2Advanced")


# =============================================================================
# NUMBA-OPTIMIZED FUNCTIONS
# =============================================================================

if NUMBA_AVAILABLE:

    @jit(nopython=True, cache=True)
    def _fast_gradient(smo2_vals, power_vals):
        """Fast gradient calculation using Numba."""
        n = len(smo2_vals)
        grad = np.zeros(n)
        for i in range(1, n - 1):
            dp = power_vals[i + 1] - power_vals[i - 1]
            if dp != 0:
                grad[i] = (smo2_vals[i + 1] - smo2_vals[i - 1]) / dp
        grad[0] = grad[1] if n > 1 else 0
        grad[-1] = grad[-2] if n > 1 else 0
        return grad

    @jit(nopython=True, cache=True)
    def _fast_curvature(smo2_vals, power_vals):
        """Fast curvature calculation using Numba."""
        n = len(smo2_vals)
        grad = _fast_gradient(smo2_vals, power_vals)
        curv = np.zeros(n)
        for i in range(1, n - 1):
            dp = power_vals[i + 1] - power_vals[i - 1]
            if dp != 0:
                curv[i] = (grad[i + 1] - grad[i - 1]) / dp
        curv[0] = curv[1] if n > 1 else 0
        curv[-1] = curv[-2] if n > 1 else 0
        return curv
else:

    def _fast_gradient(smo2_vals, power_vals):
        """Fallback gradient calculation."""
        return np.gradient(smo2_vals, power_vals)

    def _fast_curvature(smo2_vals, power_vals):
        """Fallback curvature calculation."""
        grad = np.gradient(smo2_vals, power_vals)
        return np.gradient(grad, power_vals)


__all__ = [
    "NUMBA_AVAILABLE",
    "logger",
    "_fast_gradient",
    "_fast_curvature",
]
