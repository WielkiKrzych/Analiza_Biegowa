"""CORE HSI is a measured signal, with exclusive time-weighted zones."""

import io

import pandas as pd
import pytest

from modules.calculations.thermal import (
    HSI_LABELS,
    calculate_thermal_drift_rate,
    summarize_core_hsi,
)
from modules.utils import load_data
from services.session_orchestrator import process_uploaded_session


def test_core_hsi_preserves_zone_boundaries_and_ignores_recording_pauses():
    frame = pd.DataFrame(
        {
            "time": [0, 2, 5, 45, 49],
            "heat_strain_index": [0.0, 1.0, 3.0, 7.0, 10.0],
        }
    )
    result = summarize_core_hsi(frame)
    assert result["peak"] == 10
    assert result["zone_seconds"] == dict(zip(HSI_LABELS, (2, 3, 0, 7), strict=True))
    assert result["mean"] == pytest.approx((2 * 0 + 3 * 1 + 4 * 7 + 3 * 10) / 12)


@pytest.mark.parametrize("values", [[-1, 10.1, "bad"], [None, None, None]])
def test_invalid_hsi_never_becomes_a_measured_value(values):
    frame = pd.DataFrame({"time": [0, 1, 2], "heat_strain_index": values})
    assert summarize_core_hsi(frame) is None


def test_raw_upload_does_not_confuse_ambient_temperature_and_core():
    csv = pd.DataFrame({"time": range(50), "pace": 300, "temp": 31, "HR": 160})
    frame = load_data(io.BytesIO(csv.to_csv(index=False).encode()))
    plot, _, metrics, error = process_uploaded_session(frame)
    assert error is None
    assert metrics["heat_strain"] is None
    assert metrics["avg_core"] is None
    assert "core_temperature" not in plot
    assert plot["ambient_temperature"].eq(31).all()


def test_hsi_only_sensor_data_is_available_without_core_temperature_or_hr():
    csv = pd.DataFrame({"time": range(0, 80, 2), "pace": 300, "HeatStrainIndex": 3})
    frame = load_data(io.BytesIO(csv.to_csv(index=False).encode()))
    plot, _, metrics, error = process_uploaded_session(frame)
    assert error is None
    assert metrics["heat_strain"]["peak"] == 3
    assert metrics["heat_strain"]["zone_seconds"][HSI_LABELS[2]] == 80
    assert plot["heat_strain_index"].iloc[0] == 3
    assert pd.isna(plot["heat_strain_index"].iloc[1])


def test_core_temperature_drift_distinguishes_missing_and_measured_slope():
    time = pd.Series(range(100))
    temperature = 37 + time / 1800
    assert calculate_thermal_drift_rate(temperature, time) == pytest.approx(2.0)
    assert calculate_thermal_drift_rate(temperature.iloc[:30], time.iloc[:30]) is None
