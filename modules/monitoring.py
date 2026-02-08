"""
Performance monitoring and metrics collection.

Provides timing, memory profiling, and metrics export for performance analysis.
"""

import time
import functools
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class TimingRecord:
    """Record of a timed operation."""

    function_name: str
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    args_hash: str = ""


class PerformanceMonitor:
    """
    Singleton performance monitor for tracking function execution times.

    Usage:
        @monitor.timed
        def expensive_function(data):
            return process(data)

        # Get statistics
        stats = monitor.get_stats()
    """

    _instance: Optional["PerformanceMonitor"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._timings: List[TimingRecord] = []
                    cls._instance._enabled = True
        return cls._instance

    def timed(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to time function execution."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not self._enabled:
                return func(*args, **kwargs)

            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000  # ms
                record = TimingRecord(function_name=func.__name__, duration_ms=duration)
                self._timings.append(record)

                # Log slow operations
                if duration > 1000:  # > 1 second
                    logger.warning(f"Slow operation: {func.__name__} took {duration:.1f}ms")

        return wrapper

    @contextmanager
    def timed_block(self, name: str):
        """Context manager for timing code blocks."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = (time.perf_counter() - start) * 1000
            record = TimingRecord(function_name=name, duration_ms=duration)
            self._timings.append(record)

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get timing statistics by function."""
        stats = defaultdict(
            lambda: {"count": 0, "total_ms": 0, "min_ms": float("inf"), "max_ms": 0}
        )

        for record in self._timings:
            func_stats = stats[record.function_name]
            func_stats["count"] += 1
            func_stats["total_ms"] += record.duration_ms
            func_stats["min_ms"] = min(func_stats["min_ms"], record.duration_ms)
            func_stats["max_ms"] = max(func_stats["max_ms"], record.duration_ms)

        # Calculate averages
        for func_name, func_stats in stats.items():
            if func_stats["count"] > 0:
                func_stats["avg_ms"] = func_stats["total_ms"] / func_stats["count"]

        return dict(stats)

    def get_slow_operations(self, threshold_ms: float = 1000) -> List[TimingRecord]:
        """Get operations slower than threshold."""
        return [t for t in self._timings if t.duration_ms > threshold_ms]

    def clear(self):
        """Clear all timing records."""
        self._timings.clear()

    def enable(self):
        """Enable monitoring."""
        self._enabled = True

    def disable(self):
        """Disable monitoring."""
        self._enabled = False

    def export_metrics(self) -> Dict[str, Any]:
        """Export metrics in Prometheus-compatible format."""
        stats = self.get_stats()
        metrics = []

        for func_name, func_stats in stats.items():
            metrics.append(
                {
                    "name": f'function_duration_ms{{function="{func_name}"}}',
                    "value": func_stats["avg_ms"],
                    "type": "gauge",
                }
            )
            metrics.append(
                {
                    "name": f'function_calls_total{{function="{func_name}"}}',
                    "value": func_stats["count"],
                    "type": "counter",
                }
            )

        return metrics


# Global monitor instance
monitor = PerformanceMonitor()


def timed(func: Callable[..., T]) -> Callable[..., T]:
    """Convenience decorator using global monitor."""
    return monitor.timed(func)


# Memory profiling (optional)

try:
    import psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


def get_memory_usage() -> Optional[Dict[str, float]]:
    """Get current memory usage."""
    if not _PSUTIL_AVAILABLE:
        return None

    process = psutil.Process()
    mem_info = process.memory_info()

    return {
        "rss_mb": mem_info.rss / 1024 / 1024,
        "vms_mb": mem_info.vms / 1024 / 1024,
        "percent": process.memory_percent(),
    }


@contextmanager
def memory_tracker(name: str):
    """Track memory usage of a code block."""
    if not _PSUTIL_AVAILABLE:
        yield
        return

    start_mem = get_memory_usage()
    yield
    end_mem = get_memory_usage()

    if start_mem and end_mem:
        delta = end_mem["rss_mb"] - start_mem["rss_mb"]
        if abs(delta) > 10:  # Log if > 10MB change
            logger.info(f"Memory change in {name}: {delta:+.1f} MB")


# Cache performance tracking


class CacheMetrics:
    """Track cache hit/miss rates."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

    def record_hit(self):
        with self._lock:
            self.hits += 1

    def record_miss(self):
        with self._lock:
            self.misses += 1

    def get_stats(self) -> Dict[str, float]:
        with self._lock:
            total = self.hits + self.misses
            if total == 0:
                return {"hits": 0, "misses": 0, "hit_rate": 0}

            return {"hits": self.hits, "misses": self.misses, "hit_rate": self.hits / total}


# Create global cache metrics
cache_metrics = CacheMetrics()


def track_cache_hit():
    """Record a cache hit."""
    cache_metrics.record_hit()


def track_cache_miss():
    """Record a cache miss."""
    cache_metrics.record_miss()


def get_cache_stats() -> Dict[str, float]:
    """Get cache statistics."""
    return cache_metrics.get_stats()


# Performance report generation


def generate_performance_report() -> str:
    """Generate a human-readable performance report."""
    stats = monitor.get_stats()
    cache_stats = get_cache_stats()
    memory = get_memory_usage()

    lines = [
        "=" * 60,
        "PERFORMANCE REPORT",
        "=" * 60,
        "",
        "Function Timing Statistics:",
        "-" * 40,
    ]

    # Sort by total time
    sorted_funcs = sorted(stats.items(), key=lambda x: x[1]["total_ms"], reverse=True)

    for func_name, func_stats in sorted_funcs[:10]:  # Top 10
        lines.append(f"  {func_name}:")
        lines.append(f"    Calls: {func_stats['count']}")
        lines.append(f"    Avg: {func_stats.get('avg_ms', 0):.1f}ms")
        lines.append(f"    Min: {func_stats['min_ms']:.1f}ms")
        lines.append(f"    Max: {func_stats['max_ms']:.1f}ms")
        lines.append(f"    Total: {func_stats['total_ms']:.1f}ms")
        lines.append("")

    lines.extend(
        [
            "Cache Statistics:",
            "-" * 40,
            f"  Hits: {cache_stats['hits']}",
            f"  Misses: {cache_stats['misses']}",
            f"  Hit Rate: {cache_stats['hit_rate'] * 100:.1f}%",
            "",
        ]
    )

    if memory:
        lines.extend(
            [
                "Memory Usage:",
                "-" * 40,
                f"  RSS: {memory['rss_mb']:.1f} MB",
                f"  VMS: {memory['vms_mb']:.1f} MB",
                f"  Percent: {memory['percent']:.1f}%",
                "",
            ]
        )

    lines.append("=" * 60)

    return "\n".join(lines)
