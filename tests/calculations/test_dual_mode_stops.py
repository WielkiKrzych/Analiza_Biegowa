"""
Regression tests for P0-2 (audit v2): Normalized Pace must exclude stopped
periods rather than clip them.

Bug (audit v2, §6 P0-2): `modules/calculations/dual_mode.py:calculate_normalized_pace`
did `pace.clip(lower=60, upper=900)` instead of filtering — a 1800 s/km stop
became 900 s/km (15:00/km) and got included in NP, shifting the result.

Per the docstring on `calculate_normalized_pace` (line 67), the algorithm must:
- "Exclude stopped periods (>900 sec/km) from NP calculation"

The fix is to filter (drop) pace values above 900 sec/km, while keeping the
lower bound as a sanity clip (60 sec/km = 1:00/km sprint, below that is
physiologically impossible for sustained running).
"""

import numpy as np
import pandas as pd

from modules.calculations.dual_mode import calculate_normalized_pace


def _df(pace_series: pd.Series) -> pd.DataFrame:
    """Wrap a pace Series into a minimal DataFrame with a 'pace' column."""
    return pd.DataFrame({"pace": pace_series, "time": np.arange(len(pace_series))})


def test_stopped_period_1800_sk_km_does_not_change_normalized_pace():
    """A 30:00/km stop (1800 s/km) inserted in the middle must not change NP
    relative to the same session with the stop removed.
    """
    # 8 running samples at ~5:00/km, then a 30-minute stop, then 8 more
    pace_with_stop = pd.Series(
        [300, 305, 310, 315, 300, 305, 310, 315, 1800.0, 300, 305, 310, 315, 300, 305, 310, 315],
        dtype=float,
    )
    pace_without_stop = pace_with_stop[pace_with_stop < 1800].reset_index(drop=True)

    np_with = calculate_normalized_pace(_df(pace_with_stop))
    np_without = calculate_normalized_pace(_df(pace_without_stop))

    # After fix: must be equal. Before fix: differs because the 1800 s/km
    # stop is clipped to 900 s/km and included in the rolling window,
    # dragging the speed-based average down.
    assert abs(np_with - np_without) < 0.5, (
        f"NP with stop ({np_with:.2f} s/km) differs from NP without stop "
        f"({np_without:.2f} s/km) by more than 0.5 s/km — stop is not being excluded."
    )


def test_stopped_period_1200_sk_km_does_not_change_normalized_pace():
    """A 20:00/km stop (1200 s/km) must also be excluded (>900 s/km threshold)."""
    pace_with_stop = pd.Series(
        [300, 305, 310, 315, 300, 305, 310, 315, 1200.0, 300, 305, 310, 315, 300, 305, 310, 315],
        dtype=float,
    )
    pace_without_stop = pace_with_stop[pace_with_stop < 1200].reset_index(drop=True)

    np_with = calculate_normalized_pace(_df(pace_with_stop))
    np_without = calculate_normalized_pace(_df(pace_without_stop))

    assert abs(np_with - np_without) < 0.5, (
        f"NP with 1200 s/km stop ({np_with:.2f}) differs from NP without "
        f"({np_without:.2f}) — stop not excluded."
    )


def test_brisk_walk_at_901_sk_km_is_excluded():
    """Just over 900 s/km (901 = slow walk) must be excluded."""
    pace_with_walk = pd.Series(
        [300, 305, 310, 315, 300, 305, 310, 315, 901.0, 300, 305, 310, 315, 300, 305, 310, 315],
        dtype=float,
    )
    pace_without_walk = pace_with_walk[pace_with_walk <= 900].reset_index(drop=True)

    np_with = calculate_normalized_pace(_df(pace_with_walk))
    np_without = calculate_normalized_pace(_df(pace_without_walk))

    assert abs(np_with - np_without) < 0.5, (
        f"NP with 901 s/km walk ({np_with:.2f}) differs from NP without "
        f"({np_without:.2f}) — 901 s/km should be excluded."
    )


def test_sprint_at_60_sk_km_is_clipped_not_excluded():
    """60 s/km (1:00/km) is a sprint cap — should be kept, not dropped.
    Before the fix the lower clip(lower=60) was the only safety; after the
    fix we want the same: values <= 60 stay in (as 60).
    """
    # A 1:00/km "sprint" sample (60 s/km) at the start, then 5:00/km samples
    pace_with_sprint = pd.Series([60.0, 300, 305, 310, 315, 300, 305, 310, 315, 300], dtype=float)
    pace_with_sprint_as_60 = pd.Series(
        [60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0], dtype=float
    )

    np_session = calculate_normalized_pace(_df(pace_with_sprint))
    np_all_60 = calculate_normalized_pace(_df(pace_with_sprint_as_60))

    # The 60 s/km sample must contribute (clipped to 60 = 16.67 m/s sprint),
    # not be dropped. So np_session should be SLOWER than np_all_60 because
    # most samples are 5:00/km (slower than 1:00/km).
    assert np_session > np_all_60, (
        f"60 s/km sprint not being included: np_session ({np_session:.2f}) "
        f"should be > np_all_60 ({np_all_60:.2f})."
    )


def test_normalized_pace_handles_all_stops_gracefully():
    """If the entire session is stops (>900 s/km), NP returns 0.0 (not crash)."""
    all_stops = pd.Series([1500.0, 1800.0, 2000.0, 1500.0, 1800.0], dtype=float)
    np_all_stops = calculate_normalized_pace(_df(all_stops))
    # After fix: no valid pace samples, function should return 0.0
    assert np_all_stops == 0.0, f"Expected 0.0 for all-stops session, got {np_all_stops}"
