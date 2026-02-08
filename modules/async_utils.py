"""
Async I/O utilities for non-blocking operations.

Provides async wrappers for CPU-intensive and I/O-bound operations
to keep the UI responsive during heavy computations.
"""

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar, Optional
import pandas as pd
from pathlib import Path

# Global thread pool for CPU-bound operations
_executor = ThreadPoolExecutor(max_workers=4)

T = TypeVar("T")


def run_in_thread(func: Callable[..., T]) -> Callable[..., asyncio.Future[T]]:
    """
    Decorator to run a synchronous function in a thread pool.

    Usage:
        @run_in_thread
        def heavy_computation(data):
            return expensive_operation(data)

        result = await heavy_computation(data)
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, functools.partial(func, *args, **kwargs))

    return wrapper


async def load_data_async(file, chunk_size: Optional[int] = None) -> pd.DataFrame:
    """
    Async wrapper for data loading.

    Loads data in a separate thread to prevent blocking the main event loop.
    """
    from modules.utils import load_data

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, load_data, file, chunk_size)


async def analyze_ramp_test_async(df: pd.DataFrame, **kwargs) -> dict:
    """
    Async wrapper for ramp test analysis.

    Performs heavy threshold detection in a background thread.
    """
    from modules.calculations.thresholds import analyze_step_test

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, functools.partial(analyze_step_test, df, **kwargs))


async def detect_smo2_thresholds_async(df: pd.DataFrame, **kwargs) -> Any:
    """
    Async wrapper for SmO2 threshold detection.
    """
    from modules.calculations.smo2_advanced import detect_smo2_thresholds_moxy

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, functools.partial(detect_smo2_thresholds_moxy, df, **kwargs)
    )


async def generate_pdf_async(*args, **kwargs) -> bytes:
    """
    Async wrapper for PDF generation.

    PDF generation is CPU-intensive and should run in background.
    """
    from modules.reporting.pdf.summary_pdf import generate_summary_pdf

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, functools.partial(generate_summary_pdf, *args, **kwargs)
    )


class AsyncProgressTracker:
    """
    Tracks progress of async operations.

    Usage:
        tracker = AsyncProgressTracker()
        async for progress in tracker.track_operation(long_operation()):
            update_progress_bar(progress)
    """

    def __init__(self, total_steps: int = 100):
        self.total_steps = total_steps
        self.current_step = 0
        self._callbacks: list[Callable[[int], None]] = []

    def add_callback(self, callback: Callable[[int], None]):
        """Add a callback to be called on progress updates."""
        self._callbacks.append(callback)

    def update(self, step: int):
        """Update progress and notify callbacks."""
        self.current_step = min(step, self.total_steps)
        for callback in self._callbacks:
            callback(self.current_step)

    async def track_operation(self, coro) -> Any:
        """Track progress of an async operation."""
        self.update(0)
        try:
            result = await coro
            self.update(self.total_steps)
            return result
        except Exception as e:
            self.update(0)
            raise e


def shutdown_executor():
    """Shutdown the global thread pool executor. Call on app exit."""
    _executor.shutdown(wait=True)
