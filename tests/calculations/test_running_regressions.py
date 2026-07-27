"""Regression tests for running-specific analysis correctness.

Each test here pins down a bug that was found in review and fixed:

1. GAP used a hand-typed cost table that did not match Minetti (2002): it
   over-credited uphills and inverted the sign of the correction on steep
   downhills (a -45% descent came out as a 5x faster flat-equivalent pace).
2. The Pace Duration Curve averaged pace arithmetically and treated a stop
   (pace == 0) as an infinitely fast sample, inventing "best efforts".
3. Pace zones put stopped samples (pace == 0) into Z6 Repetition.
4. Average pace was the arithmetic mean of pace instead of distance / time.
"""

import numpy as np
import pandas as pd
import pytest

from modules.calculations.gap import calculate_gap, pace_to_gap_factor
from modules.calculations.pace import (
    calculate_pace_duration_curve,
    calculate_pace_zones_time,
)
from modules.ui.running import calculate_pace_summary_stats


def _minetti_cr(grade_pct: float) -> float:
    """Reference implementation of Minetti (2002) running cost, J/kg/m."""
    i = grade_pct / 100.0
    return 155.4 * i**5 - 30.4 * i**4 - 43.3 * i**3 + 46.3 * i**2 + 19.5 * i + 3.6


# --------------------------------------------------------------------------
# 1. GAP / Minetti
# --------------------------------------------------------------------------


@pytest.mark.parametrize("grade", [-45, -30, -20, -10, -5, 0, 5, 10, 20, 30, 45])
def test_gap_factor_matches_minetti_polynomial(grade):
    """GAP factor must equal cost_flat / cost_grade from the cited paper."""
    expected = _minetti_cr(0.0) / _minetti_cr(grade)
    expected = min(max(expected, 0.2), 2.0)  # same safety clamp as production
    assert float(pace_to_gap_factor(grade)) == pytest.approx(expected, rel=0.02)


def test_gap_flat_is_identity():
    assert float(calculate_gap(300.0, 0.0)) == pytest.approx(300.0)


def test_gap_uphill_is_faster_than_actual_pace():
    """Running uphill at a given pace is worth a faster flat-equivalent pace."""
    assert float(calculate_gap(300.0, 10.0)) < 300.0


def test_gap_downhill_is_slower_than_actual_pace():
    """Running downhill at a given pace is worth a slower flat-equivalent pace."""
    assert float(calculate_gap(300.0, -10.0)) > 300.0


def test_gap_metabolic_minimum_is_near_minus_20_percent():
    """Minetti's running cost minimum sits near -20%, so GAP is slowest there."""
    grades = np.arange(-45.0, 0.0, 0.5)
    factors = np.asarray(pace_to_gap_factor(grades), dtype=float)
    assert -25.0 <= grades[int(np.argmax(factors))] <= -15.0


def test_steep_downhill_is_not_reported_as_a_sprint():
    """Regression: -45% used to yield GAP = pace * 0.2, i.e. 1:00/km from 5:00/km."""
    gap = float(calculate_gap(300.0, -45.0))
    assert gap > 240.0, f"steep descent collapsed to {gap:.0f} s/km"


def test_gap_is_monotonic_on_the_uphill_side():
    grades = np.arange(0.0, 45.5, 0.5)
    gaps = np.asarray(calculate_gap(300.0, grades), dtype=float)
    assert np.all(np.diff(gaps) <= 1e-9)


# --------------------------------------------------------------------------
# 2. Pace Duration Curve
# --------------------------------------------------------------------------


def test_pdc_ignores_stops_instead_of_inventing_best_efforts():
    """A 30 s stop inside a steady 5:00/km run must not create a 2:30/km best."""
    pace = np.full(600, 300.0)
    pace[100:130] = 0.0  # device wrote 0 while standing still

    result = calculate_pace_duration_curve(pd.DataFrame({"pace": pace}), [60, 300])

    assert result[60] == pytest.approx(300.0, rel=1e-6)
    assert result[300] == pytest.approx(300.0, rel=1e-6)


def test_pdc_handles_nan_stops():
    pace = np.full(600, 300.0)
    pace[200:240] = np.nan

    result = calculate_pace_duration_curve(pd.DataFrame({"pace": pace}), [60])
    assert result[60] == pytest.approx(300.0, rel=1e-6)


def test_pdc_uses_distance_over_time_not_arithmetic_mean():
    """Alternating 30 s at 3:20/km and 30 s at 6:40/km.

    Distance covered in 60 s = 30*5.0 + 30*2.5 = 225 m -> 266.7 s/km.
    The arithmetic mean of pace would wrongly report 300 s/km.
    """
    pace = np.tile(np.concatenate([np.full(30, 200.0), np.full(30, 400.0)]), 10)

    result = calculate_pace_duration_curve(pd.DataFrame({"pace": pace}), [60])
    assert result[60] == pytest.approx(266.67, rel=1e-3)


def test_pdc_returns_none_when_window_longer_than_activity():
    result = calculate_pace_duration_curve(pd.DataFrame({"pace": np.full(60, 300.0)}), [3600])
    assert result[3600] is None


def test_pdc_all_stopped_returns_none():
    result = calculate_pace_duration_curve(pd.DataFrame({"pace": np.zeros(300)}), [60])
    assert result[60] is None


# --------------------------------------------------------------------------
# 3. Pace zones
# --------------------------------------------------------------------------


def test_stops_do_not_land_in_the_fastest_zone():
    """Regression: pace == 0 used to be counted as Z6 Repetition."""
    pace = np.full(600, 300.0)
    pace[100:130] = 0.0

    zones = calculate_pace_zones_time(pd.DataFrame({"pace": pace}), threshold_pace=270.0)

    assert zones["Z6 Repetition"] == 0
    assert zones["Z1 Recovery"] == 30
    assert sum(zones.values()) == 600


# --------------------------------------------------------------------------
# 4. Average pace
# --------------------------------------------------------------------------


def test_average_pace_is_distance_over_time():
    """30 min at 4:00/km + 30 min at 6:00/km = 4:48/km, not 5:00/km."""
    pace = np.concatenate([np.full(1800, 240.0), np.full(1800, 360.0)])

    stats = calculate_pace_summary_stats(pd.DataFrame({"pace": pace}), threshold_pace=270.0)

    assert stats["avg_pace"] == pytest.approx(288.0, rel=1e-6)


def test_average_pace_excludes_stops():
    pace = np.concatenate([np.full(1800, 300.0), np.zeros(600)])

    stats = calculate_pace_summary_stats(pd.DataFrame({"pace": pace}), threshold_pace=270.0)

    assert stats["avg_pace"] == pytest.approx(300.0, rel=1e-6)
    assert stats["min_pace"] == pytest.approx(300.0)
    assert stats["max_pace"] == pytest.approx(300.0)
