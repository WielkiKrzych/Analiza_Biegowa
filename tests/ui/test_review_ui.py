"""Regression tests for the w4 UI review (app.py / modules/ui / modules/frontend).

Each test below fails on the pre-review code; the failure is noted in the
docstring so the intent survives future refactors.
"""

from __future__ import annotations

import sys
import types

import pytest
import streamlit

import app as app_module
from modules.config import Config
from modules.frontend.state import StateManager

# ---------------------------------------------------------------------------
# Minimal Streamlit stub
# ---------------------------------------------------------------------------


class _NullContext:
    """Callable that also works as a context manager and stores call args."""

    def __init__(self, recorder: list, name: str):
        self._recorder = recorder
        self._name = name
        self._value = None

    def __call__(self, *args, **kwargs):
        self._recorder.append((self._name, args, kwargs))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter([])


@pytest.fixture
def st_stub(monkeypatch):
    """Replace the streamlit side-effect functions used by the code under test.

    Returns the recorder list of ``(name, args, kwargs)`` tuples.
    """
    calls: list = []

    def _install(name, value=None):
        if value is None:
            value = _NullContext(calls, name)
        monkeypatch.setattr(streamlit, name, value)

    for name in (
        "header",
        "subheader",
        "markdown",
        "caption",
        "divider",
        "error",
        "warning",
        "info",
        "success",
        "plotly_chart",
        "metric",
    ):
        _install(name)
    _install("expander")
    _install("columns", lambda spec, *a, **k: [_NullContext(calls, "column") for _ in range(
        spec if isinstance(spec, int) else len(spec)
    )])
    return calls


# ---------------------------------------------------------------------------
# 1. Tab error boundary (app.py)
# ---------------------------------------------------------------------------


class _TabRaiser:
    """Holder so a test can pick the exception the fake tab raises."""

    exc: BaseException = RuntimeError("fake_tab.exc not set")


@pytest.fixture
def fake_tab(monkeypatch):
    """Register a throwaway tab whose render function raises ``fake_tab.exc``."""
    raiser = _TabRaiser()
    module = types.ModuleType("tests_ui_fake_tab")

    def _render(*args, **kwargs):
        raise raiser.exc

    module.render = _render
    monkeypatch.setitem(sys.modules, "tests_ui_fake_tab", module)
    monkeypatch.setitem(app_module.TabRegistry._tabs, "fake", ("tests_ui_fake_tab", "render"))
    return raiser


@pytest.mark.parametrize(
    "exc",
    [
        KeyError("'pace'"),
        ValueError("cannot convert"),
        TypeError("unsupported operand"),
        IndexError("list index out of range"),
    ],
)
def test_tab_error_boundary_catches_data_errors(st_stub, fake_tab, exc):
    """A tab raising on a missing column must not take the whole page down.

    Pre-review: only ImportError/AttributeError/RuntimeError were caught, so
    the exception escaped ``TabRegistry.render`` and Streamlit killed the page.
    """
    fake_tab.exc = exc
    assert app_module.TabRegistry.render("fake") is None
    messages = [c[1][0] for c in st_stub if c[0] == "error"]
    assert any("fake" in str(m) for m in messages), messages


def test_tab_error_boundary_still_propagates_programmer_bugs(st_stub, fake_tab):
    """The boundary is a typed tuple, not ``except Exception``."""
    fake_tab.exc = ZeroDivisionError("division by zero")
    with pytest.raises(ZeroDivisionError):
        app_module.TabRegistry.render("fake")


# ---------------------------------------------------------------------------
# 2. Sidebar defaults (modules/frontend/state.py)
# ---------------------------------------------------------------------------


def test_session_defaults_match_config(monkeypatch):
    """Pre-seeded keys must not override the Config defaults.

    Pre-review: state.py hardcoded weight=95.0 while the sidebar widget asked
    for Config.DEFAULT_BODY_WEIGHT_KG (75.0). Streamlit ignores a widget's
    ``value=`` when the key already exists in session state, so the sidebar
    showed 95 kg and every downstream power estimate was 27% too high.
    """
    state: dict = {}
    monkeypatch.setattr(streamlit, "session_state", state)
    StateManager().init_session_state()

    assert state["weight"] == Config.DEFAULT_BODY_WEIGHT_KG
    assert state["height"] == Config.DEFAULT_RUNNER_HEIGHT_CM
    assert state["age"] == Config.DEFAULT_RUNNER_AGE_YEARS
    assert state["threshold_pace"] == Config.DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    assert state["lthr"] == Config.DEFAULT_LTHR_BPM
    assert state["max_hr"] == Config.DEFAULT_MAX_HR_BPM


# ---------------------------------------------------------------------------
# 3. Biomech tab reads the sidebar weight/height (modules/ui/biomech.py)
# ---------------------------------------------------------------------------


def test_biomech_uses_sidebar_weight_and_height(monkeypatch, st_stub):
    """Biomech must read the keys the sidebar actually writes.

    Pre-review: it looked up "rider_weight"/"runner_height" — keys no widget
    ever writes — so it silently used 70 kg / 175 cm while the summary tab
    called the very same ``_render_running_effectiveness_section`` with the
    sidebar weight, printing a different number for the same file.
    """
    from modules.ui import biomech

    captured: dict = {}
    monkeypatch.setattr(streamlit, "session_state", {"weight": 88.0, "height": 190})
    monkeypatch.setattr(biomech, "render_biomech_tab", biomech.render_biomech_tab)
    for helper in (
        "_render_cadence_section",
        "_render_gct_section",
        "_render_stance_balance_section",
        "_render_vertical_ratio_section",
        "_render_vertical_oscillation_section",
    ):
        monkeypatch.setattr(biomech, helper, lambda *a, **k: None)
    monkeypatch.setattr(
        biomech,
        "_render_stride_length_section",
        lambda df, height: captured.setdefault("height", height),
    )
    monkeypatch.setattr(
        biomech,
        "_render_running_effectiveness_section",
        lambda df, weight: captured.setdefault("weight", weight),
    )

    import pandas as pd

    biomech.render_biomech_tab(pd.DataFrame({"pace": [300.0]}), pd.DataFrame({"pace": [300.0]}))

    assert captured == {"height": 190, "weight": 88.0}


def test_vo_pace_effectiveness_uses_sidebar_height(monkeypatch, st_stub):
    """The second height lookup in the same tab must use the same key.

    Pre-review: this call site defaulted to 180 while the first one defaulted
    to 175, so one biomech metric used a different runner height than the next.
    """
    import pandas as pd

    from modules.ui import biomech

    monkeypatch.setattr(streamlit, "session_state", {"height": 190})
    captured: dict = {}

    biomech._render_vo_pace_effectiveness(
        pd.DataFrame({"pace": [300.0, 301.0]}),
        {"mean_vo": 2.5},
        lambda pace, vo, height: captured.setdefault("height", height) and None,
    )
    assert captured["height"] == 190


# ---------------------------------------------------------------------------
# 4. Manual time-range feedback (vent_tab / vent_charts / smo2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_name, func_name, start_key",
    [
        ("modules.ui.vent_tab", "_render_manual_range", "vent_start_sec"),
        ("modules.ui.smo2", "_render_manual_range_input", "smo2_start_sec"),
        ("modules.ui.vent_charts", "_render_br_manual_input", "br_start_sec"),
    ],
)
def test_invalid_manual_range_reports_error(
    monkeypatch, st_stub, module_name, func_name, start_key
):
    """An unparseable time string must produce a visible message.

    Pre-review: ``_parse_time_to_seconds`` returned None and the handler simply
    did nothing — no success, no error. The user clicked "Zastosuj ręczny
    zakres", the chart kept the old range, and nothing explained why.
    """
    import importlib

    module = importlib.import_module(module_name)
    monkeypatch.setattr(streamlit, "session_state", {start_key: 600})
    monkeypatch.setattr(streamlit, "text_input", lambda *a, **k: "10 min")
    monkeypatch.setattr(streamlit, "button", lambda *a, **k: True)

    getattr(module, func_name)()

    messages = [c[1][0] for c in st_stub if c[0] == "error"]
    assert messages, "invalid time input produced no feedback at all"
    assert any("format" in str(m).lower() for m in messages), messages
    assert streamlit.session_state[start_key] == 600, "range changed despite parse failure"
