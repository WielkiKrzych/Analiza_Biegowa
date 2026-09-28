"""
Regression tests for the physiological calculations review (w2).

Each test pins a concrete wrong number that the previous implementation
produced silently.
"""

import numpy as np
import pandas as pd

from modules.calculations.pipeline import run_ramp_test_pipeline
from modules.calculations.step_detection import detect_step_test_range


def _staircase_with_warmup() -> pd.DataFrame:
    """Staircase test (5 steps x 180 s) preceded by a warm-up plateau.

    The warm-up sits at 130 W -- the same power as step 2 of the ramp -- but at
    a much lower HR (105 bpm vs 150 bpm), which is exactly what a real ramp
    recording looks like.
    """
    blocks = [
        (120, 130.0, 105.0),  # warm-up plateau at 130 W
        (180, 100.0, 130.0),  # step 1
        (180, 130.0, 150.0),  # step 2 -- same power as the warm-up, higher HR
        (180, 160.0, 160.0),
        (180, 190.0, 170.0),
        (180, 220.0, 180.0),
        (120, 50.0, 120.0),  # stop
    ]
    watts, hr = [], []
    for duration, power, heart_rate in blocks:
        watts.extend([power] * duration)
        hr.extend([heart_rate] * duration)

    return pd.DataFrame(
        {
            "time": np.arange(len(watts), dtype=float),
            "watts": np.array(watts, dtype=float),
            "hr": np.array(hr, dtype=float),
        }
    )


def test_manual_lt_hr_ignores_warmup_at_same_power() -> None:
    """The manual LT HR must come from the ramp, not from the warm-up.

    Regression: the lookup used ``idxmin`` over the whole recording, so the
    warm-up sample at 130 W won and the report showed 105 bpm instead of the
    150 bpm measured at 130 W inside the ramp.
    """
    df = _staircase_with_warmup()

    result = run_ramp_test_pipeline(df, smo2_manual_lt1=130.0, smo2_manual_lt2=190.0)

    step_range = detect_step_test_range(df)
    assert step_range is not None and step_range.is_valid
    assert step_range.start_time == 120.0
    assert result.smo2_manual_lt1_hr == 150.0
    # The second threshold has no warm-up twin; it pins that restricting the lookup
    # did not shift the ordinary case.
    assert result.smo2_manual_lt2_hr == 170.0
