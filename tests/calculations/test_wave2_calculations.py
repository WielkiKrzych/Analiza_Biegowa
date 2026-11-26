"""Regression tests for the calculation-layer hardening (w1).

Every test here pins a value the previous implementation reported silently
as if it were a real measurement, or a crash it raised on an input the
loader can genuinely produce (``utils._convert_numeric_types`` coerces a
text column to all-NaN, so "column present, every value NaN" is a normal
outcome of an uploaded file).
"""

import numpy as np
import pandas as pd

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
