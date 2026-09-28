"""
Regression tests for the services-layer review (w1).

Defect: `services/data_validation.py::_ensure_numeric` coerced a non-numeric
column on a COPY of the frame and returned the copy. `validate_dataframe`
unpacked that copy into a local variable and then returned only `(True, "")`,
so the coercion was thrown away and the caller kept processing the original
object-dtype column.

Why that loses data: `modules/calculations/data_processing.py::resample_with_pace`
resamples only `df.select_dtypes(include=[np.number])`. An object-dtype
`watts` column is therefore dropped from the resampled frame, the power
column disappears from `df_plot`, and `ensure_power_column` then overwrites
it with a power value ESTIMATED from pace (`power_is_estimated=True`) — a
session recorded with a real power meter is silently reported as
"moc szacowana", with `avg_watts` stored as 0 in the session DB.

Fix: coerce in place on the frame that is about to be processed.
"""

import pandas as pd

from modules.calculations.data_processing import process_data
from services.data_validation import validate_dataframe


def _text_typed_df() -> pd.DataFrame:
    """A valid session whose `watts`/`heartrate` arrive as text.

    This is what a CSV with quoted numbers looks like after load: the values
    are numeric but the column dtype is `object`.
    """
    n = 60
    return pd.DataFrame(
        {
            "time": [float(i) for i in range(n)],
            "watts": [str(200 + i % 10) for i in range(n)],
            "heartrate": ["150"] * n,
        }
    )


def test_validate_dataframe_coerces_numeric_columns_in_place():
    """Validation must leave the frame it validated numerically usable.

    Before the fix the coerced copy was discarded, so `df["watts"]` stayed
    `object` even though `validate_dataframe` returned `(True, "")`.
    """
    df = _text_typed_df()
    assert not pd.api.types.is_numeric_dtype(df["watts"]), "fixture must start as object dtype"

    is_valid, message = validate_dataframe(df)

    assert is_valid, f"fixture should be a valid session, got: {message}"
    assert pd.api.types.is_numeric_dtype(df["watts"]), (
        "watts was validated as numeric but left as object dtype — "
        "validate_dataframe discarded the coerced copy"
    )
    assert pd.api.types.is_numeric_dtype(df["heartrate"])


def test_power_column_survives_processing_when_source_was_text():
    """End-to-end symptom: text-typed power must not vanish from the pipeline.

    `resample_with_pace` keeps numbers only, so an object-dtype `watts`
    column silently disappears from the processed frame. Downstream that
    means `ensure_power_column` reports the session as pace-estimated.
    """
    df = _text_typed_df()

    is_valid, message = validate_dataframe(df)
    assert is_valid, f"fixture should be a valid session, got: {message}"

    processed = process_data(df)

    assert "watts" in processed.columns, (
        "the watts column was dropped while resampling — the session would be "
        "reported as pace-estimated even though it carried real power"
    )
    assert processed["watts"].sum() > 0
    assert pd.api.types.is_numeric_dtype(processed["watts_smooth"])


def test_numeric_frames_are_not_copied_by_validation():
    """Validation stays a cheap predicate for already-numeric frames."""
    df = pd.DataFrame(
        {
            "time": [float(i) for i in range(60)],
            "watts": [200.0] * 60,
            "heartrate": [150] * 60,
        }
    )
    before_dtype = df["watts"].dtype
    before_values = df["watts"].tolist()

    is_valid, _ = validate_dataframe(df)

    assert is_valid
    # An already-numeric column must come out untouched. Asserting dtype+values
    # rather than object identity: identity relies on pandas' column cache, which
    # copy-on-write (pandas 3) removes, and the test would fail without a defect.
    assert df["watts"].dtype == before_dtype
    assert df["watts"].tolist() == before_values


def test_declared_data_columns_are_coerced_not_dropped() -> None:
    """A numeric-looking text column must survive validation.

    Regression: only watts/heartrate/cadence were coerced, so an object-dtype
    `pace` passed validation and was then dropped by `resample_with_pace`'s
    select_dtypes(include=[np.number]) — the running dashboard lost its main signal
    without a message.
    """
    df = pd.DataFrame(
        {
            "time": [float(i) for i in range(60)],
            "watts": [200.0] * 60,
            "pace": ["300.5"] * 60,
            "speed": [" 3.3 "] * 60,
        }
    )

    is_valid, error = validate_dataframe(df)

    assert is_valid, error
    assert pd.api.types.is_numeric_dtype(df["pace"])
    assert df["pace"].iloc[0] == 300.5
    assert pd.api.types.is_numeric_dtype(df["speed"])


def test_non_numeric_pace_is_logged_not_rejected(caplog) -> None:
    """Pace as "4:30" must not block the import (it did not before, either)."""
    df = pd.DataFrame(
        {
            "time": [float(i) for i in range(60)],
            "watts": [200.0] * 60,
            "pace": ["4:30"] * 60,
        }
    )

    with caplog.at_level("WARNING"):
        is_valid, error = validate_dataframe(df)

    assert is_valid, error
    assert any("pace" in record.getMessage() for record in caplog.records)
