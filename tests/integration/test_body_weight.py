"""
Regression tests for P0-3 (audit v2): default body weight must be a single
source of truth in `modules.config.Config`.

Bug: three call-sites hard-coded different defaults:
  - `modules/frontend/layout.py:38` sidebar `value=95.0`
  - `services/session_orchestrator.py:106` `rider_weight: float = 75.0`
  - `modules/calculations/running_power.py:56` `weight_kg: float = 75.0`

The estimated power scales linearly with body weight, so a session via UI vs
via API could differ by 27% (95/75 - 1 = 26.7%). After the fix, all three
sites must read from `Config.DEFAULT_BODY_WEIGHT_KG`.
"""

import pandas as pd

from modules.calculations.running_power import estimate_running_power
from modules.config import Config


def _df_at_pace(pace_sec_per_km: float, n: int = 60) -> pd.DataFrame:
    """Build a minimal DataFrame with a constant `pace` column (s/km).

    `running_power` accepts `pace` in s/km (5:00/km = 300). It also accepts
    `gap` (m/s) or `speed` (m/s) but those need a different format.
    """
    return pd.DataFrame({"pace": [pace_sec_per_km] * n, "time": list(range(n))})


def test_config_exposes_default_body_weight_kg():
    """Config must expose a single DEFAULT_BODY_WEIGHT_KG attribute."""
    assert hasattr(Config, "DEFAULT_BODY_WEIGHT_KG"), (
        "Config.DEFAULT_BODY_WEIGHT_KG missing — body weight has no single source of truth."
    )
    assert isinstance(Config.DEFAULT_BODY_WEIGHT_KG, float)
    assert 30.0 <= Config.DEFAULT_BODY_WEIGHT_KG <= 200.0, (
        f"Config.DEFAULT_BODY_WEIGHT_KG = {Config.DEFAULT_BODY_WEIGHT_KG} kg is outside plausible range"
    )


def test_running_power_default_matches_config():
    """`estimate_running_power(df)` without explicit weight must use Config."""
    df = _df_at_pace(pace_sec_per_km=300.0)  # 5:00/km — well within (120, 1200)

    # Call without weight — must fall back to Config.DEFAULT_BODY_WEIGHT_KG
    power_default = estimate_running_power(df)
    power_explicit = estimate_running_power(df, weight_kg=Config.DEFAULT_BODY_WEIGHT_KG)

    assert power_default is not None and power_explicit is not None, (
        "estimate_running_power returned None — pace column not picked up"
    )
    # Default-call and explicit-Config call must produce the same Series
    pd.testing.assert_series_equal(power_default, power_explicit)


def test_ensure_power_column_default_matches_config():
    """`ensure_power_column(df)` without explicit weight must use Config.

    Note: `ensure_power_column` writes to `df['watts']` (not 'power') when
    there is no measured power column. It mutates the input in place.
    """
    from modules.calculations.running_power import ensure_power_column

    df_default = _df_at_pace(pace_sec_per_km=300.0)
    df_explicit = _df_at_pace(pace_sec_per_km=300.0)

    ok_default = ensure_power_column(df_default)
    ok_explicit = ensure_power_column(df_explicit, weight_kg=Config.DEFAULT_BODY_WEIGHT_KG)

    assert ok_default and ok_explicit, "ensure_power_column must return True for valid pace-only df"
    assert "watts" in df_default.columns
    assert "watts" in df_explicit.columns
    pd.testing.assert_series_equal(df_default["watts"], df_explicit["watts"])


def test_power_scales_linearly_with_weight():
    """Power estimate is P = 1.04 * mass * speed, so doubling mass doubles power."""
    df = _df_at_pace(pace_sec_per_km=300.0)

    power_50 = estimate_running_power(df, weight_kg=50.0)
    power_100 = estimate_running_power(df, weight_kg=100.0)

    assert power_50 is not None and power_100 is not None

    # Each is a Series of length 60 (constant pace). Take the first value.
    val_50 = float(power_50.iloc[0])
    val_100 = float(power_100.iloc[0])

    # 2x weight should give 2x power
    assert abs(val_100 - 2 * val_50) < 0.5, (
        f"Power not linear in weight: P(50kg)={val_50:.1f} W, P(100kg)={val_100:.1f} W"
    )


def test_orchestrator_default_matches_config():
    """`process_uploaded_session(rider_weight=...)` default must equal Config."""
    import inspect

    from services.session_orchestrator import process_uploaded_session

    sig = inspect.signature(process_uploaded_session)
    orchestrator_default = sig.parameters["rider_weight"].default

    assert orchestrator_default == Config.DEFAULT_BODY_WEIGHT_KG, (
        f"Orchestrator rider_weight default ({orchestrator_default}) "
        f"!= Config.DEFAULT_BODY_WEIGHT_KG ({Config.DEFAULT_BODY_WEIGHT_KG})"
    )
