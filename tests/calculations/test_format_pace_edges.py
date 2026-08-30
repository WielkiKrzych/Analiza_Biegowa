"""
Regression tests for P1-2 (audit v2): single canonical pace formatter
`modules.calculations.pace_utils.format_pace`.

Before: 4 formatters existed
  - `pace_utils.format_pace`             (canonical, NaN-safe)
  - `frontend.components._format_pace_mmss` (rounded, NaN-UNSAFE — crash on NaN)
  - `ui.running.format_pace_for_display` (wrapper, dead since identical)
  - `reporting.figures.drift._format_pace_min_km` (dead code, 0 callers)

After: only `pace_utils.format_pace` remains. These tests pin its edge-case
behavior so future refactors don't reintroduce the divergences:
  - NaN/inf -> '--:--'  (must not crash)
  - 0 / negative -> '--:--'
  - 60.0 -> '1:00'  (must pad seconds)
  - 60.99 -> '1:00'  (truncation, not rounding)
  - 3600 -> '60:00'  (very slow, not capped)
"""


import pytest

from modules.calculations.pace_utils import format_pace


@pytest.mark.parametrize(
    "value,expected",
    [
        # Sanity
        (300, "5:00"),
        (305, "5:05"),
        (59, "0:59"),
        # Boundary: exactly 60 s/km must be 1:00, not 0:60
        (60, "1:00"),
        (60.0, "1:00"),
        # 60.99 truncates (pace_utils uses int(), not round())
        (60.99, "1:00"),
        # Slow paces
        (3600, "60:00"),
        (7200, "120:00"),
    ],
)
def test_format_pace_valid_inputs(value, expected):
    assert format_pace(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        0,
        0.0,
        -1,
        -300.0,
        float("nan"),
        float("inf"),
        -float("inf"),
    ],
)
def test_format_pace_invalid_inputs_return_placeholder(value):
    """NaN, inf, zero, negative must return '--:--' and must not crash."""
    result = format_pace(value)
    assert result == "--:--", f"format_pace({value!r}) returned {result!r}, expected '--:--'"


def test_format_pace_does_not_round_seconds():
    """The canonical formatter uses int() (truncation), not round()."""
    # 305.5 -> int(305.5 % 60) = int(5.5) = 5 (truncates)
    assert format_pace(305.5) == "5:05"
    # 305.9 -> int(305.9 % 60) = int(5.9) = 5
    assert format_pace(305.9) == "5:05"


def test_format_pace_handles_nan_safely():
    """NaN used to crash `_format_pace_mmss` because int(NaN) raises.
    The canonical formatter must not crash.
    """
    try:
        result = format_pace(float("nan"))
    except Exception as exc:
        pytest.fail(f"format_pace(NaN) raised {type(exc).__name__}: {exc}")
    assert result == "--:--"


