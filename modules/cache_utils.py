"""
Caching layer for expensive computations.

Provides memoization for CPU-intensive operations with TTL support.
Uses diskcache as a simple alternative to Redis (no external dependencies).
"""

import hashlib
import json
import pickle
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
from pathlib import Path
import pandas as pd
import numpy as np

# Try to use diskcache (file-based, no external dependencies)
try:
    from diskcache import Cache

    _CACHE_AVAILABLE = True
except ImportError:
    _CACHE_AVAILABLE = False
    Cache = None

from modules.config import Config

T = TypeVar("T")

# Global cache instance
_cache: Optional[Cache] = None


def get_cache() -> Optional[Cache]:
    """Get or create global cache instance."""
    global _cache
    if not _CACHE_AVAILABLE:
        return None

    if _cache is None:
        cache_dir = (
            Path(Config.DB_PATH).parent / "cache" if hasattr(Config, "DB_PATH") else Path("./cache")
        )
        cache_dir.mkdir(exist_ok=True)
        _cache = Cache(str(cache_dir))

    return _cache


def cache_result(ttl: int = 3600, key_func: Optional[Callable] = None):
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds (default: 1 hour)
        key_func: Optional function to generate cache key from arguments

    Usage:
        @cache_result(ttl=3600)
        def expensive_calculation(df: pd.DataFrame, param: int) -> dict:
            return heavy_computation(df, param)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            cache = get_cache()
            if cache is None:
                return func(*args, **kwargs)

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(func.__name__, args, kwargs)

            # Try to get from cache
            try:
                result = cache.get(cache_key)
                if result is not None:
                    return result
            except Exception:
                pass

            # Compute and cache
            result = func(*args, **kwargs)
            try:
                cache.set(cache_key, result, expire=ttl)
            except Exception:
                pass

            return result

        # Add cache invalidation method
        wrapper.invalidate_cache = lambda *args, **kwargs: _invalidate_cache(
            func.__name__, args, kwargs, key_func
        )

        return wrapper

    return decorator


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a deterministic cache key from function arguments."""
    # Convert arguments to hashable form
    key_parts = [func_name]

    for arg in args:
        key_parts.append(_hash_arg(arg))

    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={_hash_arg(v)}")

    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def _hash_arg(arg: Any) -> str:
    """Convert argument to hashable string representation."""
    if isinstance(arg, pd.DataFrame):
        # Hash based on column names and shape (not full data for performance)
        cols = ",".join(sorted(arg.columns))
        return f"DF:{cols}:{len(arg)}"
    elif isinstance(arg, pd.Series):
        return f"SER:{arg.name}:{len(arg)}"
    elif isinstance(arg, np.ndarray):
        return f"ARR:{arg.shape}:{arg.dtype}"
    elif isinstance(arg, (list, tuple)):
        return f"LIST:{len(arg)}"
    elif isinstance(arg, dict):
        return f"DICT:{len(arg)}"
    else:
        return str(arg)


def _invalidate_cache(func_name: str, args: tuple, kwargs: dict, key_func: Optional[Callable]):
    """Invalidate cache entry for specific arguments."""
    cache = get_cache()
    if cache is None:
        return

    if key_func:
        cache_key = key_func(*args, **kwargs)
    else:
        cache_key = _generate_cache_key(func_name, args, kwargs)

    try:
        cache.delete(cache_key)
    except Exception:
        pass


def clear_cache():
    """Clear all cached results."""
    cache = get_cache()
    if cache:
        cache.clear()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    cache = get_cache()
    if cache is None:
        return {"enabled": False}

    try:
        return {"enabled": True, "size": len(cache), "volume": cache.volume()}
    except Exception:
        return {"enabled": True, "error": "Could not get stats"}


# Pre-configured cache decorators for common use cases

cache_1h = cache_result(ttl=3600)  # 1 hour
cache_24h = cache_result(ttl=86400)  # 24 hours
cache_7d = cache_result(ttl=604800)  # 7 days


# Cached versions of expensive operations


@cache_result(ttl=3600)
def cached_analyze_step_test(df: pd.DataFrame, **kwargs) -> Any:
    """Cached version of step test analysis."""
    from modules.calculations.thresholds import analyze_step_test

    return analyze_step_test(df, **kwargs)


@cache_result(ttl=3600)
def cached_detect_smo2_thresholds(df: pd.DataFrame, **kwargs) -> Any:
    """Cached version of SmO2 threshold detection."""
    from modules.calculations.smo2_advanced import detect_smo2_thresholds_moxy

    return detect_smo2_thresholds_moxy(df, **kwargs)


@cache_result(ttl=86400)  # 24 hours - CP doesn't change often
def cached_calculate_cp_wprime(df: pd.DataFrame, **kwargs) -> tuple:
    """Cached version of CP/W' calculation."""
    from modules.calculations.power import calculate_cp_wprime

    return calculate_cp_wprime(df, **kwargs)


@cache_result(ttl=3600)
def cached_generate_summary_pdf(*args, **kwargs) -> bytes:
    """Cached version of PDF generation."""
    from modules.reporting.pdf.summary_pdf import generate_summary_pdf

    return generate_summary_pdf(*args, **kwargs)
