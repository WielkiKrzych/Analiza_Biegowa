"""
Background task queue for long-running operations.

Provides a simple in-process task queue for running heavy computations
without blocking the main thread. Uses concurrent.futures for simplicity.

For production with multiple users, consider migrating to Celery or RQ.
"""

import uuid
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar
import threading

T = TypeVar("T")


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a background task."""

    id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0  # 0-100
    progress_message: str = ""


class BackgroundTaskManager:
    """
    Manager for background tasks.

    Usage:
        manager = BackgroundTaskManager(max_workers=4)

        # Submit a task
        task_id = manager.submit_task("analyze_data", heavy_function, data)

        # Check status
        task = manager.get_task(task_id)
        if task.status == TaskStatus.COMPLETED:
            result = task.result
    """

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, Task] = {}
        self.futures: Dict[str, Future] = {}
        self._lock = threading.Lock()

    def submit_task(self, name: str, func: Callable[..., T], *args, **kwargs) -> str:
        """
        Submit a task for background execution.

        Args:
            name: Human-readable task name
            func: Function to execute
            *args, **kwargs: Arguments for the function

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())

        with self._lock:
            task = Task(id=task_id, name=name)
            self.tasks[task_id] = task

        # Submit to executor
        future = self.executor.submit(self._run_task, task_id, func, *args, **kwargs)

        with self._lock:
            self.futures[task_id] = future

        return task_id

    def _run_task(self, task_id: str, func: Callable, *args, **kwargs):
        """Internal method to run a task and track its status."""
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

        try:
            # Run the actual function
            result = func(*args, **kwargs)

            with self._lock:
                task = self.tasks.get(task_id)
                if task:
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task.completed_at = datetime.now()
                    task.progress = 100

        except Exception as e:
            with self._lock:
                task = self.tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.completed_at = datetime.now()

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        with self._lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks."""
        with self._lock:
            return list(self.tasks.values())

    def get_active_tasks(self) -> List[Task]:
        """Get tasks that are pending or running."""
        with self._lock:
            return [
                task
                for task in self.tasks.values()
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            ]

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or running task.

        Returns:
            True if cancelled, False otherwise
        """
        with self._lock:
            future = self.futures.get(task_id)
            task = self.tasks.get(task_id)

            if future and not future.done():
                future.cancel()
                if task:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.now()
                return True

            return False

    def update_progress(self, task_id: str, progress: int, message: str = ""):
        """
        Update task progress.

        This can be called from within the running task.
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.progress = max(0, min(100, progress))
                if message:
                    task.progress_message = message

    def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Optional[Task]:
        """
        Wait for a task to complete.

        Args:
            task_id: Task ID to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Task object or None if timeout
        """
        future = None
        with self._lock:
            future = self.futures.get(task_id)

        if future:
            try:
                future.result(timeout=timeout)
            except Exception:
                pass

        return self.get_task(task_id)

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove completed tasks older than specified hours."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        with self._lock:
            to_remove = [
                task_id
                for task_id, task in self.tasks.items()
                if task.completed_at and task.completed_at.timestamp() < cutoff
            ]

            for task_id in to_remove:
                del self.tasks[task_id]
                if task_id in self.futures:
                    del self.futures[task_id]

    def shutdown(self, wait: bool = True):
        """Shutdown the task manager."""
        self.executor.shutdown(wait=wait)


# Global task manager instance
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """Get or create global task manager."""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager


def submit_background_task(name: str, func: Callable[..., T], *args, **kwargs) -> str:
    """
    Convenience function to submit a background task.

    Usage:
        task_id = submit_background_task(
            "Analyze Ramp Test",
            analyze_step_test,
            df,
            power_column="watts"
        )
    """
    manager = get_task_manager()
    return manager.submit_task(name, func, *args, **kwargs)


def get_task_status(task_id: str) -> Optional[TaskStatus]:
    """Get status of a task."""
    manager = get_task_manager()
    task = manager.get_task(task_id)
    return task.status if task else None


def get_task_result(task_id: str) -> Any:
    """
    Get result of a completed task.

    Returns None if task not found or not completed.
    """
    manager = get_task_manager()
    task = manager.get_task(task_id)

    if task and task.status == TaskStatus.COMPLETED:
        return task.result
    return None


# Progress callback helper


class ProgressCallback:
    """
    Helper class for reporting progress from within tasks.

    Usage:
        def long_task(data, progress_callback=None):
            for i, chunk in enumerate(data):
                process(chunk)
                if progress_callback:
                    progress_callback((i + 1) / len(data) * 100)
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.manager = get_task_manager()

    def __call__(self, progress: int, message: str = ""):
        self.manager.update_progress(self.task_id, progress, message)

    def update(self, progress: int, message: str = ""):
        """Update progress."""
        self.manager.update_progress(self.task_id, progress, message)
