"""Regression tests for the calculation-layer hardening (w1).

Every test here pins a value the previous implementation reported silently
as if it were a real measurement, or a crash it raised on an input the
loader can genuinely produce (``utils._convert_numeric_types`` coerces a
text column to all-NaN, so "column present, every value NaN" is a normal
outcome of an uploaded file).
"""

import numpy as np
import pandas as pd
import pytest

import modules.calculations.canonical_physio as canonical_physio
from modules.calculations.canonical_physio import calculate_vo2max_acsm
from modules.calculations.data_processing import resample_with_pace
from modules.calculations.pace_utils import pace_to_seconds

# ---------------------------------------------------------------------------
# Parse only real pace values


def test_pace_to_seconds_rejects_unparseable_input() -> None:
    """An unrecognised pace string must not come back as 0 s/km.

    Pre-fix: the handler fell through to ``return 0.0``, i.e. the same value a
    legitimate ``"0:00"`` produces, so a junk manual pace entry was plotted as
    a real one.
    """
    assert np.isnan(pace_to_seconds("abc"))
    assert np.isnan(pace_to_seconds("5:00:30"))
    # Valid input is untouched.
    assert pace_to_seconds("5:00") == 300


# ---------------------------------------------------------------------------


def test_resample_with_pace_does_not_mutate_input_frame() -> None:
    """The ``_speed_ms`` scratch column must stay out of the caller's frame.

    Pre-fix: the helper wrote ``df_pd["_speed_ms"]`` directly into the frame it
    was given, so any caller that still held the input gained a surprise column.
    """
    df = pd.DataFrame(
        {"pace": [300.0, 300.0, 300.0]},
        index=pd.to_timedelta(np.arange(3), unit="s"),
    )

    out = resample_with_pace(df)

    assert "_speed_ms" not in df.columns
    assert "pace" in out.columns


# ---------------------------------------------------------------------------
# canonical_physio - the ACSM terms are named constants, not inline literals
# ---------------------------------------------------------------------------


def test_vo2max_acsm_constants_are_exported() -> None:
    """The named constants are a contract with the UI layer.

    ``modules/ui/summary_charts.py`` imports ``VO2MAX_ACSM_SLOPE`` to propagate
    the formula's slope into its uncertainty band, so the name has to exist and
    to be exported.
    """
    assert canonical_physio.VO2MAX_ACSM_SLOPE == 8.87
    assert canonical_physio.VO2MAX_ACSM_INTERCEPT == 16.61
    assert "VO2MAX_ACSM_SLOPE" in canonical_physio.__all__
    assert "VO2MAX_ACSM_INTERCEPT" in canonical_physio.__all__


@pytest.mark.parametrize(
    ("power_watts", "weight_kg"),
    [(300.0, 75.0), (250.0, 70.0), (420.0, 82.5), (1.0, 3.0), (0.5, 100.0)],
)
def test_vo2max_acsm_matches_the_inline_literals_bit_for_bit(
    power_watts: float, weight_kg: float
) -> None:
    """Extracting the literals into constants must not move a single bit.

    The expected value is the pre-change expression, evaluated here from the
    literals themselves.
    """
    expected = 16.61 + 8.87 * (power_watts / weight_kg)

    assert calculate_vo2max_acsm(power_watts, weight_kg) == expected


def test_vo2max_acsm_still_rejects_non_positive_input() -> None:
    """The guard in front of the formula is untouched by the extraction."""
    assert calculate_vo2max_acsm(0.0, 75.0) == 0.0
    assert calculate_vo2max_acsm(300.0, 0.0) == 0.0
