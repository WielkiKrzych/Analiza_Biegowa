"""
End-to-end test: CSV file → processed session with metrics (P2-5, audit v2).

Before this test, the existing `tests/integration/test_running_pipeline.py`
verified individual calculation steps in isolation, but no test covered
the full path `load_data(csv_bytes) → process_uploaded_session → metrics`.

This test:
  1. Writes a synthetic running CSV to a temp file
  2. Loads it via `modules.utils.load_data`
  3. Runs the full orchestrator pipeline
  4. Verifies metrics are present and plausible (NP > 0, distance > 0, etc.)
"""

import os
import tempfile

import numpy as np
import pandas as pd

from modules.utils import load_data
from services.session_orchestrator import process_uploaded_session


def _write_synthetic_running_csv(path: str, n_samples: int = 600) -> None:
    """Write a synthetic running session to a CSV file.

    10 minutes at 5:00/km with normal-distributed noise. Includes all the
    columns `load_data` is expected to recognize.
    """
    np.random.seed(42)
    time_s = np.arange(n_samples, dtype=float)  # 1 Hz
    pace = 300 + np.random.normal(0, 5, n_samples)  # ~5:00/km
    heartrate = 150 + np.random.normal(0, 3, n_samples)
    cadence = 170 + np.random.normal(0, 2, n_samples)

    df = pd.DataFrame(
        {
            "time": time_s,
            "pace": pace,
            "heartrate": heartrate,
            "cadence": cadence,
        }
    )
    df.to_csv(path, index=False)


def test_csv_file_to_processed_session():
    """A 10-min running CSV loads and produces sensible metrics."""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "session.csv")
        _write_synthetic_running_csv(csv_path, n_samples=600)

        # === Step 1: load ===
        with open(csv_path, "rb") as f:
            df_raw = load_data(f)
        assert not df_raw.empty
        assert "time" in df_raw.columns
        assert "pace" in df_raw.columns

        # === Step 2: full pipeline ===
        df_plot, df_plot_resampled, metrics, error_msg = process_uploaded_session(
            df_raw, rider_weight=75.0, vt1_watts=0, vt2_watts=0
        )

        # === Step 3: validation ===
        assert error_msg is None, f"Pipeline returned error: {error_msg}"
        assert df_plot is not None and not df_plot.empty
        assert metrics is not None
        # The estimator kicks in for pace-only data
        assert metrics.get("power_is_estimated") is True
        # Average watts is now estimated from pace via the body-weight power model
        assert "avg_watts" in metrics
        assert metrics["avg_watts"] > 100, (
            f"Estimated power {metrics['avg_watts']:.0f} W is implausibly low for 5:00/km"
        )
        # Avg HR should land near 150 (we seeded it that way)
        assert 140 < metrics.get("avg_hr", 0) < 160, (
            f"avg_hr {metrics.get('avg_hr')} outside [140, 160] — something is off"
        )
        # Auto-save metadata
        assert "_decoupling_percent" in metrics


def test_csv_with_power_column_uses_measured_power():
    """When the CSV has a real `watts` column, estimated-power flag stays False."""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "power.csv")
        np.random.seed(7)
        df = pd.DataFrame(
            {
                "time": np.arange(300, dtype=float),
                "watts": 220 + np.random.normal(0, 10, 300),
                "heartrate": 145 + np.random.normal(0, 3, 300),
                "cadence": 90 + np.random.normal(0, 1, 300),
            }
        )
        df.to_csv(csv_path, index=False)

        with open(csv_path, "rb") as f:
            df_raw = load_data(f)
        _, _, metrics, error_msg = process_uploaded_session(
            df_raw, rider_weight=75.0, vt1_watts=0, vt2_watts=0
        )

        assert error_msg is None
        assert metrics.get("power_is_estimated") is False, (
            "Measured power should not be marked as estimated"
        )
        # Measured 220W +/- 10W -> avg should be near 220
        assert 200 < metrics.get("avg_watts", 0) < 240
