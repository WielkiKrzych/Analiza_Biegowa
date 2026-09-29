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
import modules.calculations.polars_adapter as polars_adapter
from modules.calculations.canonical_physio import calculate_vo2max_acsm
from modules.calculations.cardio_advanced import calculate_hr_recovery
from modules.calculations.data_processing import resample_with_pace
from modules.calculations.pace_utils import pace_to_seconds
from modules.calculations.smo2_analysis import calculate_halftime_reoxygenation
from modules.calculations.smo2_breakpoints import detect_smo2_breakpoints_segmented
from modules.calculations.step_detection import segment_load_phases

# ---------------------------------------------------------------------------
# fast_power_duration_curve - "cannot read the column" vs "no power here"
# ---------------------------------------------------------------------------


def test_power_duration_curve_missing_column_reports_no_result(monkeypatch) -> None:
    """An unreadable power column must not look like an empty window.

    Pre-fix: the handler returned ``{dur: None for dur in durations}``, which is
    exactly what the function returns for a real recording whose windows are
    shorter than the requested durations - so a broken frame reached the UI as
    "no power in this window" instead of "no result".

    ``POLARS_AVAILABLE`` is forced off because with Polars installed the same
    call raises ``ColumnNotFoundError`` before the handler runs.
    """
    monkeypatch.setattr(polars_adapter, "POLARS_AVAILABLE", False)
    df = pd.DataFrame({"heartrate": [120.0] * 600})

    assert polars_adapter.fast_power_duration_curve(df, [60, 300]) == {}


def test_power_duration_curve_missing_column_same_with_and_without_polars(monkeypatch) -> None:
    """A missing column must give the same answer on both Polars installs.

    Pre-fix: with Polars installed the same call raised
    ``ColumnNotFoundError`` (polars 1.38.0: ``ColumnNotFoundError`` ->
    ``PolarsError`` -> ``Exception``, so neither the ``KeyError`` nor the
    ``ValueError`` in the handler matched) while a machine without Polars went
    down the Pandas path and returned ``{}``.
    """
    df = pd.DataFrame({"heartrate": [120.0] * 600})

    with_polars = polars_adapter.fast_power_duration_curve(df, [60, 300])

    monkeypatch.setattr(polars_adapter, "POLARS_AVAILABLE", False)
    without_polars = polars_adapter.fast_power_duration_curve(df, [60, 300])

    assert with_polars == without_polars == {}


def test_rolling_mean_missing_column_same_with_and_without_polars(monkeypatch) -> None:
    """The other four Polars fast paths unify the same way.

    Pre-fix: the Polars path escaped with ``ColumnNotFoundError`` before the
    Pandas fallback could run, so a missing column failed with a different
    exception type depending on whether Polars was installed. Now the Polars
    failure hands over to Pandas, which is what the no-Polars machine did all
    along.
    """
    df = pd.DataFrame({"cadence": [90.0] * 60})

    with pytest.raises(KeyError):
        polars_adapter.fast_rolling_mean(df, "watts", 30)

    monkeypatch.setattr(polars_adapter, "POLARS_AVAILABLE", False)
    with pytest.raises(KeyError):
        polars_adapter.fast_rolling_mean(df, "watts", 30)


def test_power_duration_curve_short_recording_keeps_per_duration_none() -> None:
    """The distinction the fix introduces: a real window that is too short.

    This is the behaviour the broken return value was indistinguishable from,
    so it must keep reporting one ``None`` per requested duration.
    """
    df = pd.DataFrame({"watts": [200.0] * 600})

    assert polars_adapter.fast_power_duration_curve(df, [3600]) == {3600: None}


# ---------------------------------------------------------------------------
# pace_to_seconds - 0.0 is a legal pace, so it cannot mean "unparseable"
# ---------------------------------------------------------------------------


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
# _resolve_time_array - sample index presented as seconds
# ---------------------------------------------------------------------------


def _recovery_frame_with_unparseable_time() -> pd.DataFrame:
    """Ramp ending at sample 169 followed by 31 recovery samples.

    The `time` column holds free text, so ``pd.to_timedelta`` cannot read it.
    """
    power = np.concatenate([100.0 + np.arange(169), np.zeros(31)])
    smo2 = np.concatenate([70.0 - np.arange(169) * 0.1, np.full(31, 65.0)])
    return pd.DataFrame(
        {
            "watts": power,
            "SmO2": smo2,
            "time": ["lap-%d" % i for i in range(200)],
        }
    )


def test_halftime_reoxygenation_rejects_unparseable_time_column() -> None:
    """An unreadable time column must yield None, not sample numbers as seconds.

    Pre-fix: ``_resolve_time_array`` fell back to ``np.arange(len(df))``, so the
    reoxygenation half-time was computed from row indices and returned as a
    number of seconds the athlete never produced.
    """
    df = _recovery_frame_with_unparseable_time()

    assert calculate_halftime_reoxygenation(df) is None


def _recovery_frame_with_numeric_time() -> pd.DataFrame:
    """Ramp peaking at sample 168, then 31 s of recovery at zero power.

    `time` is the numeric, seconds-valued column that
    ``time_index.prepare_time_index`` writes - and there is no `seconds` column
    alongside it.
    """
    ramp_len = 169
    power = np.concatenate([100.0 + np.arange(ramp_len), np.zeros(31)])
    smo2 = np.concatenate(
        [
            np.linspace(70.0, 50.0, ramp_len),
            np.concatenate([np.full(2, 55.0), np.full(29, 64.0)]),
        ]
    )
    return pd.DataFrame({"watts": power, "SmO2": smo2, "time": np.arange(200, dtype=float)})


def test_halftime_reoxygenation_reads_numeric_time_as_seconds() -> None:
    """A numeric `time` column is already in seconds and must not be rescaled.

    Pre-fix: liczbowa kolumna time byla czytana jako nanosekundy (0, 1e-9, 2e-9),
    so the half-time came back as ~3e-9 s instead of the real value.

    The recovery SmO2 crosses the 50% target 3 s after the peak, so the honest
    answer is exactly 3.0 seconds.
    """
    df = _recovery_frame_with_numeric_time()

    assert calculate_halftime_reoxygenation(df) == pytest.approx(3.0)


def test_halftime_reoxygenation_uses_a_readable_time_column() -> None:
    """The guard must not swallow the ordinary path."""
    df = _recovery_frame_with_unparseable_time().drop(columns=["time"])
    df["seconds"] = np.arange(len(df), dtype=float)

    result = calculate_halftime_reoxygenation(df)

    assert result is not None and result >= 0


# ---------------------------------------------------------------------------
# All-NaN columns: what the loader produces for a text power / HR column
# ---------------------------------------------------------------------------


def test_hr_recovery_all_nan_hr_column_returns_none() -> None:
    """An all-NaN HR column must report "no recovery", not raise.

    Pre-fix: ``idxmax()`` returns NaN for an all-NaN column and ``df.loc[nan]``
    then raised ``KeyError: nan`` out of the analysis.
    """
    df = pd.DataFrame({"hr": [np.nan] * 100, "watts": [200.0] * 100})

    assert calculate_hr_recovery(df, "hr") is None


def test_hr_recovery_empty_frame_returns_none() -> None:
    """An empty frame must report "no recovery", not raise.

    Pre-fix: ``df[hr_col].idxmax()`` raised ``ValueError: attempt to get argmax
    of an empty sequence``.
    """
    df = pd.DataFrame({"hr": pd.Series([], dtype=float)})

    assert calculate_hr_recovery(df, "hr") is None


def test_smo2_breakpoints_all_nan_power_column_is_not_valid() -> None:
    """An all-NaN power column must come back as a labelled empty result.

    Pre-fix: ``idxmax()`` returned NaN and ``df.iloc[:nan]`` then raised
    ``TypeError: cannot do positional indexing ... with these indexers [nan]``.
    """
    df = pd.DataFrame({"watts": [np.nan] * 200, "smo2": [60.0] * 200})

    result = detect_smo2_breakpoints_segmented(df)

    assert result.is_valid is False
    assert result.bp1_power is None
    assert "No valid power data" in result.notes


def _ramp_then_recovery() -> pd.DataFrame:
    """300 s ramp (50 -> 450 W) followed by 100 s of recovery at 50 W.

    SmO2 desaturates with two slope changes, at roughly 290 W and 380 W.
    """
    power = np.concatenate([np.linspace(50.0, 450.0, 300), np.full(100, 50.0)])
    ramp = np.linspace(50.0, 450.0, 300)
    smo2 = np.concatenate(
        [
            70.0
            - 0.010 * ramp
            - 0.030 * np.maximum(ramp - 290.0, 0.0)
            - 0.020 * np.maximum(ramp - 380.0, 0.0),
            np.full(100, 68.0),
        ]
    )
    return pd.DataFrame({"watts": power, "smo2": smo2})


def test_smo2_breakpoints_do_not_read_an_index_label_as_a_position() -> None:
    """The ramp slice must be positional, so a shifted index cannot change it.

    Pre-fix: the slice was ``df.iloc[:df[power_col].idxmax()]``, i.e. a *label*
    fed to positional indexing. With an index offset by 1000 the label (1299)
    exceeded the frame length, so the whole recovery phase was pulled into the
    ramp and the detected breakpoints moved. A 0-based RangeIndex is the only
    index where the two coincide, which is why this went unnoticed.
    """
    base = _ramp_then_recovery()
    shifted = base.copy()
    shifted.index = shifted.index + 1000

    base_result = detect_smo2_breakpoints_segmented(base)
    shifted_result = detect_smo2_breakpoints_segmented(shifted)

    # The comparison is only meaningful if a breakpoint is actually found.
    assert base_result.bp1_power is not None
    assert shifted_result == base_result


def test_segment_load_phases_all_nan_power_column_returns_empty() -> None:
    """An all-NaN power column must yield no phases, not raise.

    Pre-fix: ``s_watts.idxmax()`` returned NaN and ``df.loc[nan, time_col]``
    raised ``KeyError: nan``.
    """
    df = pd.DataFrame(
        {"watts": [np.nan] * 200, "time": np.arange(200, dtype=float)}
    )

    increasing, decreasing = segment_load_phases(df)

    assert increasing is df
    assert decreasing.empty


# ---------------------------------------------------------------------------
# resample_with_pace - the scratch column must not leak into the caller's frame
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
