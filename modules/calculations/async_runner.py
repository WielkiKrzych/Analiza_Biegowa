"""
Async Calculation Runner.

Provides async wrappers for CPU-intensive calculations.
Uses ThreadPoolExecutor for parallel processing.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from functools import wraps
from typing import Callable, Any, Optional, TypeVar, ParamSpec
import threading

logger = logging.getLogger(__name__)

# Type hints for generics
P = ParamSpec('P')
T = TypeVar('T')

# Global thread pool (reused across calls)
_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def get_executor(max_workers: int = 4) -> ThreadPoolExecutor:
    """Get or create the global thread pool executor.
    
    Args:
        max_workers: Maximum number of worker threads
        
    Returns:
        ThreadPoolExecutor instance
    """
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=max_workers)
    return _executor


def shutdown_executor(wait: bool = True) -> None:
    """Shutdown the global executor."""
    global _executor
    with _executor_lock:
        if _executor is not None:
            _executor.shutdown(wait=wait)
            _executor = None


def run_in_thread(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run a function in a background thread and wait for result.
    
    Useful for CPU-bound calculations that block the main thread.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result
        
    Example:
        result = run_in_thread(calculate_w_prime_balance, df, cp, w_prime)
    """
    executor = get_executor()
    future = executor.submit(func, *args, **kwargs)
    return future.result()


def submit_task(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Future:
    """Submit a task to the thread pool without waiting.
    
    Returns a Future that can be checked for completion.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Future object
        
    Example:
        future = submit_task(heavy_calculation, data)
        # ... do other work ...
        result = future.result()  # Wait when needed
    """
    executor = get_executor()
    return executor.submit(func, *args, **kwargs)


async def run_async(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run a sync function asynchronously.
    
    Uses asyncio's run_in_executor for async/await compatibility.
    
    Args:
        func: Synchronous function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result (awaitable)
        
    Example:
        result = await run_async(calculate_pdc, df)
    """
    loop = asyncio.get_event_loop()
    executor = get_executor()
    
    # Wrap with kwargs if needed
    if kwargs:
        def wrapped():
            return func(*args, **kwargs)
        return await loop.run_in_executor(executor, wrapped)
    
    return await loop.run_in_executor(executor, func, *args)


def async_wrapper(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to make a function run in background thread.
    
    The decorated function will execute in a thread pool
    but return normally (blocking the caller).
    
    Use for heavy calculations that should not block UI.
    
    Example:
        @async_wrapper
        def heavy_calculation(data):
            # ... CPU intensive work ...
            return result
    """
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return run_in_thread(func, *args, **kwargs)
    return wrapper


class AsyncCalculationManager:
    """Manager for tracking multiple async calculations.
    
    Useful for running several calculations in parallel.
    
    Example:
        manager = AsyncCalculationManager()
        manager.submit("w_prime", calculate_w_prime_balance, df, cp, w_prime)
        manager.submit("pdc", calculate_pdc, df)
        
        # Wait for all
        results = manager.wait_all()
        w_prime_result = results["w_prime"]
        pdc_result = results["pdc"]
    """
    
    def __init__(self):
        self._futures: dict[str, Future] = {}
    
    def submit(self, name: str, func: Callable, *args, **kwargs) -> None:
        """Submit a named calculation."""
        self._futures[name] = submit_task(func, *args, **kwargs)
    
    def is_done(self, name: str) -> bool:
        """Check if a calculation is done."""
        if name not in self._futures:
            return False
        return self._futures[name].done()
    
    def get_result(self, name: str, timeout: Optional[float] = None) -> Any:
        """Get result of a calculation (blocking)."""
        if name not in self._futures:
            raise KeyError(f"No calculation named '{name}'")
        return self._futures[name].result(timeout=timeout)
    
    def wait_all(self, timeout: Optional[float] = None) -> dict[str, Any]:
        """Wait for all calculations and return results."""
        results = {}
        for name, future in self._futures.items():
            try:
                results[name] = future.result(timeout=timeout)
            except Exception as e:
                logger.error(f"Calculation '{name}' failed: {e}")
                results[name] = None
        return results
    
    def cancel_all(self) -> None:
        """Cancel all pending calculations."""
        for future in self._futures.values():
            future.cancel()
        self._futures.clear()


# Convenience function for Streamlit integration
def run_with_progress(
    func: Callable[P, T],
    progress_callback: Optional[Callable[[float], None]] = None,
    *args: P.args,
    **kwargs: P.kwargs
) -> T:
    """Run a calculation with optional progress callback.
    
    For Streamlit, progress_callback can update a progress bar.
    
    Args:
        func: Function to execute
        progress_callback: Optional callback(0.0-1.0) for progress
        *args, **kwargs: Function arguments
        
    Returns:
        Function result
    """
    if progress_callback:
        progress_callback(0.0)
    
    result = run_in_thread(func, *args, **kwargs)
    
    if progress_callback:
        progress_callback(1.0)
    
    return result
