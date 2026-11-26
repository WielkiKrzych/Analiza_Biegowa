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
            df_raw, threshold_pace=300
        )

        # === Step 3: validation ===
        assert error_msg is None, f"Pipeline returned error: {error_msg}"
        assert df_plot is not None and not df_plot.empty
        assert metrics is not None
        assert "watts" not in df_plot
        assert 290 < metrics["avg_pace"] < 310
        assert metrics["distance_km"] > 1.9
        assert metrics["rss"] > 0
        # Avg HR should land near 150 (we seeded it that way)
        assert 140 < metrics.get("avg_hr", 0) < 160, (
            f"avg_hr {metrics.get('avg_hr')} outside [140, 160] — something is off"
        )


def test_csv_with_measured_power_keeps_raw_values_without_changing_metrics():
    """The watch or footpod channel survives CSV normalization without driving any metric."""
    import io

    n = 320
    df = pd.DataFrame({"time": range(n), "pace": 310.0, "heartrate": 148.0, "Power": range(n)})
    raw = load_data(io.BytesIO(df.to_csv(index=False).encode()))
    with_power, _, metrics, error = process_uploaded_session(raw, threshold_pace=300)
    assert error is None
    without_power, _, baseline, error = process_uploaded_session(
        raw.drop(columns="watts"), threshold_pace=300
    )
    assert error is None
    assert metrics == baseline
    pd.testing.assert_series_equal(with_power["watts"], raw["watts"], check_dtype=False)
    assert "watts" not in without_power


def test_semicolon_file_derives_pace_from_speed():
    import io

    data = "time;speed_m_s;power\n" + "".join(f"{i};3.25;220\n" for i in range(60))
    raw = load_data(io.BytesIO(data.encode()))
    result, _, _, error = process_uploaded_session(raw)
    assert error is None
    assert abs(result["pace"].iloc[0] - 1000 / 3.25) < 0.01


def test_processing_preserves_stops_and_recording_gaps_in_pace():
    df = pd.DataFrame(
        {
            "time": [0, 1, 2, 3, 4, 5, 15, 16, 17, 18, 19, 20],
            "pace": [300.0, 300.0, 0.0, 300.0, 300.0, 300.0] * 2,
        }
    )
    result, _, _, error = process_uploaded_session(df)
    assert error is None
    assert result.loc[2, "pace"] == 0
    assert result.loc[6:14, "pace"].eq(0).all()
    assert result.loc[15, "pace"] == 300


def test_upload_without_pace_or_speed_is_rejected_even_with_sensor_channels():
    df = pd.DataFrame({"time": range(60), "watts": 225, "heartrate": 150, "cadence": 175})
    plot, _, metrics, error = process_uploaded_session(df)
    assert plot is None and metrics is None
    assert "tempa" in error and "prędkości" in error
