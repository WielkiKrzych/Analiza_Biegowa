"""
Regression tests for P1-1 (audit v2): exceptions in the orchestrator must
propagate, not be silently swallowed by a fallback that re-runs the entire
pipeline.

Bug: `services/session_orchestrator.py:process_uploaded_session` had a broad
`except Exception` (line 148) that re-ran the full pipeline a second time.
Any real bug in `process_data` (or downstream) was hidden behind a
misleading "falling back to uncached" log message, and the user paid double
the compute for the same failure.

Fix: narrow the `except` to cache/deserialization exceptions
(`OSError`, `pyarrow.ArrowInvalid`, `pickle.UnpicklingError`) and extract the
shared processing path into `_process_session_core`.
"""

import pickle

import pandas as pd
import pyarrow

from services import session_orchestrator


def _sample_df() -> pd.DataFrame:
    """A minimal DataFrame that passes `validate_dataframe` and reaches
    `process_data` — needs at least a `time` column.
    """
    return pd.DataFrame({"time": list(range(60)), "pace": [300.0] * 60, "heartrate": [150] * 60})


def test_process_data_exception_propagates_without_retry(monkeypatch):
    """If `process_data` raises ValueError, the orchestrator must NOT
    silently retry. The exception must propagate, and `process_data` must be
    called exactly once (not twice from the cache + uncached fallback).
    """
    df = _sample_df()
    call_count = {"n": 0}

    def failing_process_data(*args, **kwargs):
        call_count["n"] += 1
        raise ValueError("simulated processing error")

    monkeypatch.setattr(session_orchestrator, "process_data", failing_process_data)

    raised = None
    try:
        session_orchestrator.process_uploaded_session(df)
    except ValueError as e:
        raised = e

    # The exception MUST propagate
    assert raised is not None, "ValueError was swallowed — orchestrator hid a real bug"
    assert "simulated processing error" in str(raised)

    # The pipeline must NOT have been retried (call_count == 1, not 2)
    assert call_count["n"] == 1, (
        f"process_data was called {call_count['n']} times — fallback re-ran the pipeline. "
        f"After fix it should be called exactly once."
    )


def test_cache_deserialization_failure_does_not_retry_pipeline(monkeypatch):
    """If the cache path fails with OSError/pyarrow.ArrowInvalid/pickle error,
    the orchestrator must NOT re-run the full pipeline. The fix narrows the
    `except` to these exception types and re-raises (or returns a clean error)
    instead of duplicating work.
    """
    df = _sample_df()
    call_count = {"n": 0}

    def counting_process_data(*args, **kwargs):
        call_count["n"] += 1
        # Return a minimally valid processed DataFrame
        return args[0] if args else df

    monkeypatch.setattr(session_orchestrator, "process_data", counting_process_data)

    # Force the cache to fail on deserialization (parquet read returns OSError).
    real_read_parquet = pd.read_parquet

    def failing_read_parquet(*args, **kwargs):
        raise OSError("simulated cache deserialization failure")

    monkeypatch.setattr(pd, "read_parquet", failing_read_parquet)

    # Run — should not throw, but should NOT call process_data twice either.
    try:
        session_orchestrator.process_uploaded_session(df)
    except OSError:
        # Acceptable: re-raise the cache error so the caller knows.
        pass
    except pyarrow.ArrowInvalid:
        pass
    except pickle.UnpicklingError:
        pass
    except Exception:
        # Anything else is acceptable as long as process_data wasn't called twice.
        # We still want to know what was raised.
        pass

    # The critical assertion: process_data was called at most ONCE, not twice.
    # Before the fix: cache path called it once, then fallback called it again.
    assert call_count["n"] <= 1, (
        f"process_data was called {call_count['n']} times after cache failure. "
        f"Fallback duplicated the pipeline — the fix should narrow the except "
        f"and not retry."
    )

    # Restore for other tests
    monkeypatch.setattr(pd, "read_parquet", real_read_parquet)
