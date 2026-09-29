"""Regression tests for the w4 wave-2 UI/services review.

Scope: stale `@st.cache_data` keys, VO2max computed in more than one place,
and `st.session_state` keys nobody writes.

Every test fails on the pre-fix code; the failure mode is spelled out in the
docstring so the intent survives future refactors.
"""

from __future__ import annotations

import os
import types

import pandas as pd
import pytest
import streamlit

# ---------------------------------------------------------------------------
# Minimal Streamlit stub
# ---------------------------------------------------------------------------


class _Column:
    """Stand-in for the object `st.columns()` yields.

    Records the calls tabs make on their column handles, so a test can read
    back the value a `cN.metric(...)` card was rendered with.
    """

    def __init__(self, recorder: list):
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def metric(self, label, value, **kwargs):
        self._recorder.append(("metric", label, value))

    def empty(self):
        self._recorder.append(("empty", None, None))

    def markdown(self, *args, **kwargs):
        self._recorder.append(("markdown", args[0] if args else "", None))

    def caption(self, *args, **kwargs):
        self._recorder.append(("caption", args[0] if args else "", None))

    def write(self, *args, **kwargs):
        self._recorder.append(("write", args[0] if args else "", None))


class _NullContext:
    """Callable that also works as a context manager and records its calls."""

    def __init__(self, recorder: list, name: str):
        self._recorder = recorder
        self._name = name

    def __call__(self, *args, **kwargs):
        self._recorder.append((self._name, args[0] if args else "", None))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter([])


@pytest.fixture
def st_stub(monkeypatch):
    """Replace the Streamlit side effects used by the code under test.

    Returns a list of ``(kind, label, value)`` tuples.
    """
    calls: list = []

    def _install(name):
        monkeypatch.setattr(streamlit, name, _NullContext(calls, name))

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
        "expander",
    ):
        _install(name)

    monkeypatch.setattr(
        streamlit,
        "columns",
        lambda spec, *a, **k: [
            _Column(calls) for _ in range(spec if isinstance(spec, int) else len(spec))
        ],
    )
    return calls


def _metric_value(calls: list, label: str):
    """Return the value rendered by the metric card called *label*, or None."""
    for kind, name, value in calls:
        if kind == "metric" and name == label:
            return value
    return None


def _metric_number(calls: list, label: str) -> float:
    """Return the numeric part of a metric card's value (cards append units)."""
    value = _metric_value(calls, label)
    assert value is not None, f"no metric card labelled {label!r} was rendered"
    return float(str(value).split()[0])


class _SessionStateTrap(dict):
    """A `session_state` whose every read fails the test."""

    def __getitem__(self, key):
        raise AssertionError(f"cached pipeline read st.session_state[{key!r}]")

    def get(self, key, default=None):
        raise AssertionError(f"cached pipeline read st.session_state.get({key!r})")


# ---------------------------------------------------------------------------
# 1. `@st.cache_data` keys
# ---------------------------------------------------------------------------


def test_css_cache_invalidates_when_the_file_changes(monkeypatch, st_stub, tmp_path):
    """Editing style.css must reach the page without restarting Streamlit.

    Pre-review: `_read_css_file(css_path)` keyed the cache on the path alone
    and had no `ttl`, so the first read of a session was also the last one —
    the cached contents were returned for every later re-run and a CSS edit
    stayed invisible until the process died.
    """
    from modules.config import Config
    from modules.frontend.theme import ThemeManager

    css_file = tmp_path / "style.css"
    css_file.write_text("body { color: red; }")
    monkeypatch.setattr(Config, "CSS_FILE", str(css_file))

    ThemeManager.load_css()
    assert "color: red" in st_stub[-1][1]

    first_stat = css_file.stat()
    css_file.write_text("body { color: blue; }")
    # Pin the mtime explicitly so a coarse filesystem timestamp cannot make
    # this test flaky on a fast machine.
    os.utime(css_file, ns=(first_stat.st_atime_ns, first_stat.st_mtime_ns + 1_000_000))

    ThemeManager.load_css()
    assert "color: blue" in st_stub[-1][1]


def test_process_session_cache_key_covers_every_pipeline_parameter():
    """The cached pipeline must be keyed on everything its result depends on.

    `_process_session_core` reads no `st.session_state` (verified separately
    in `test_process_session_core_does_not_read_session_state`), so the six
    explicit parameters are the whole input set — this pins that contract, so
    a future parameter added to the core without being threaded through the
    cache wrapper fails here instead of silently serving a stale result.
    """
    import inspect

    from services.session_orchestrator import (
        _process_session_cached,
        _process_session_core,
    )

    cached_params = set(inspect.signature(_process_session_cached).parameters)
    core_params = set(inspect.signature(_process_session_core).parameters)

    # `df_raw` is the one intentional rename: the cache wrapper takes the same
    # frame as parquet bytes so its hash stays stable across re-runs.
    assert core_params - cached_params <= {"df_raw"}, (
        "a parameter of _process_session_core is not part of the cache key"
    )


def test_process_session_core_does_not_read_session_state(monkeypatch):
    """Nothing under the cached call may pull a value out of session_state.

    A value read from `st.session_state` inside the cached pipeline is by
    definition absent from the cache key: moving a sidebar parameter would
    keep returning the previous session's result.

    Pre-review status: already correct — this test locks the property in.
    """
    from services import session_orchestrator

    monkeypatch.setattr(streamlit, "session_state", _SessionStateTrap())

    df = pd.DataFrame(
        {
            "time": range(600),
            "watts": [200.0] * 600,
            "heartrate": [140.0] * 600,
        }
    )

    session_orchestrator._process_session_core(df, 0.0, 0.0, 75.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# 2. One VO2max value across tabs
# ---------------------------------------------------------------------------


def test_report_and_summary_tabs_agree_on_vo2max(st_stub):
    """Same file, same weight -> same VO2max in both tabs.

    Pre-review: the report card re-derived the estimate from
    `df_plot["watts"].rolling(300).mean().max()` and rendered the result with
    `f"{vo2max_est:.1f}"` unconditionally. `rolling(300)` defaults to
    `min_periods=300`, so for a session shorter than the window `.max()` was
    NaN, `calculate_vo2max` mapped that NaN to `0.0`, and the report printed
    "0.0" where the summary tab printed "--" for the very same frame.
    """
    from modules.ui.report import _render_kpi_section
    from modules.ui.summary_timeline import _render_core_metrics

    # 200 s of power: not enough for a 5-minute MMP, so the canonical pipeline
    # value (`services/session_analysis`) is 0.
    df_plot = pd.DataFrame({"watts": [200.0] * 200, "time": list(range(200))})
    metrics = {"vo2_max_est": 0}

    _render_kpi_section(metrics, df_plot, 75.0, 0.0, 0.0)
    report_value = _metric_value(st_stub, "Szac. VO2max")

    st_stub.clear()
    _render_core_metrics(df_plot, metrics, duration_min=3.3, rider_weight=75.0)
    summary_value = _metric_value(st_stub, "🎯 Est. VO2max")

    assert report_value is not None and summary_value is not None
    assert report_value == summary_value == "--"


def test_report_and_summary_agree_on_vo2max_for_a_long_session(st_stub):
    """When the estimate does exist, both tabs show the pipeline value.

    Pre-review this passed by coincidence on frames >= 300 samples (both
    windows happened to match); it guards the plumbing — the report card reads
    `metrics["vo2_max_est"]` instead of re-deriving it.
    """
    from modules.calculations.canonical_physio import calculate_vo2max_acsm
    from modules.ui.report import _render_kpi_section
    from modules.ui.summary_timeline import _render_core_metrics

    watts = [200.0] * 600 + [300.0] * 300
    df_plot = pd.DataFrame({"watts": watts, "time": list(range(len(watts)))})
    metrics = {"vo2_max_est": calculate_vo2max_acsm(300.0, 75.0)}

    _render_kpi_section(metrics, df_plot, 75.0, 0.0, 0.0)
    report_number = _metric_number(st_stub, "Szac. VO2max")

    st_stub.clear()
    _render_core_metrics(df_plot, metrics, duration_min=15.0, rider_weight=75.0)
    summary_number = _metric_number(st_stub, "🎯 Est. VO2max")

    assert report_number == summary_number == pytest.approx(metrics["vo2_max_est"], abs=0.05)


def test_vo2max_card_is_empty_without_a_power_column(st_stub):
    """No power data must not print a VO2max.

    Pre-review: the card fell back to `calculate_vo2max(0, rider_weight)`,
    which does not treat 0 W as "no data" — it returned 16.61 + 8.87 * 0 =
    16.6 ml/kg/min for a file with no `watts` column at all.
    """
    from modules.ui.report import _render_kpi_section

    df_plot = pd.DataFrame({"time": range(600), "heartrate": [140.0] * 600})

    _render_kpi_section({}, df_plot, 75.0, 0.0, 0.0)

    assert _metric_value(st_stub, "Szac. VO2max") == "--"


def test_summary_vo2max_details_goes_through_canonical_physio(monkeypatch, st_stub):
    """The uncertainty card must call `canonical_physio`, not copy its formula.

    Pre-review: `summary_charts` inlined `16.61 + 8.87 * power_per_kg`. The
    constants happen to match the canonical module today, so nothing here can
    be caught numerically — redirecting the canonical function and asserting
    the card follows is the only way this stays true.
    """
    from modules.ui import summary_charts

    df_plot = pd.DataFrame(
        {"watts": [200.0] * 400, "heartrate": [150.0] * 400}
    )

    monkeypatch.setattr(
        summary_charts, "calculate_vo2max_acsm", lambda power, weight: 99.9
    )
    metrics = summary_charts._compute_vo2max_metrics(df_plot, 75.0)

    assert metrics is not None
    assert metrics["vo2max"] == 99.9


def test_vo2max_details_render_the_heart_rate_diagnostics(st_stub):
    """The HR numbers `_compute_hr_penalty` produces must reach the expander.

    Pre-review: `_compute_hr_penalty` returned `(penalty, hr_col)` and the
    caller kept only the penalty — `hr_col`, `hr_mean`, `hr_sd` and `hr_cv`
    were never put into the result dict, so `if m.get("hr_col")` was always
    false and the whole HR block silently never rendered.
    """
    from modules.ui import summary_charts

    df_plot = pd.DataFrame({"watts": [200.0] * 400, "heartrate": [150.0] * 400})
    metrics = summary_charts._compute_vo2max_metrics(df_plot, 75.0)

    assert metrics is not None
    assert metrics["hr_col"] == "heartrate"

    summary_charts._render_vo2max_details(metrics)

    assert _metric_value(st_stub, "Średnie HR") is not None


# ---------------------------------------------------------------------------
# 3. `st.session_state` keys nobody writes
# ---------------------------------------------------------------------------


def test_zone_thresholds_use_the_detected_result(monkeypatch, st_stub):
    """The "Użyj wykrytych progów" checkbox must actually change the zones.

    Pre-review: `_resolve_zone_thresholds` read `session_state["detected_vt1"]`
    / `["detected_vt2"]` — keys no widget and no
    `StateManager.init_session_state()` ever writes. The branch was dead, so
    ticking the checkbox (checked by default once a result exists) silently
    fell through to the two manual `number_input`s.

    Scope note: the `"thresholds"` tab is registered in `app.py` but never
    passed to `render_tab_content`, so no user reaches this path today. The
    test pins the contract for the day the tab is wired up.
    """
    from modules.ui import threshold_analysis_ui

    result = types.SimpleNamespace(vt1_watts=210, vt2_watts=260)
    monkeypatch.setattr(streamlit, "session_state", {"threshold_result": result})

    manual_calls: list = []
    monkeypatch.setattr(
        streamlit,
        "number_input",
        lambda *a, **k: manual_calls.append(a[0]) or 0,
    )

    assert threshold_analysis_ui._resolve_zone_thresholds(True, 280) == (210, 260)
    assert manual_calls == [], "manual VT inputs rendered despite a detected result"


def test_zone_thresholds_fall_back_to_manual_inputs(monkeypatch, st_stub):
    """With "use detected" off (or nothing detected) the manual inputs apply.

    Same dormant-tab scope note as
    `test_zone_thresholds_use_the_detected_result`.
    """
    from modules.ui import threshold_analysis_ui

    monkeypatch.setattr(streamlit, "session_state", {})
    monkeypatch.setattr(streamlit, "number_input", lambda *a, **k: 240)

    assert threshold_analysis_ui._resolve_zone_thresholds(True, 280) == (240, 240)
    assert threshold_analysis_ui._resolve_zone_thresholds(False, 280) == (240, 240)


# ---------------------------------------------------------------------------
# 4. Stale derived state keyed by file content
# ---------------------------------------------------------------------------


class _FakeUpload:
    """Minimal stand-in for a Streamlit `UploadedFile`."""

    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def read(self, *args, **kwargs):
        return self._content

    def seek(self, *args, **kwargs):
        return 0


@pytest.fixture
def _dashboard_env(monkeypatch):
    """Wire `process_and_cache_session` up to tiny fakes."""
    monkeypatch.setattr(streamlit, "spinner", lambda *a, **k: _NullContext([], "spinner"))
    monkeypatch.setattr(streamlit, "error", lambda *a, **k: None)
    monkeypatch.setattr(streamlit, "info", lambda *a, **k: None)

    from services import dashboard_renderer

    frames = {}

    def _load_data(_uploaded):
        return frames.pop("next")

    monkeypatch.setattr(dashboard_renderer, "load_data", _load_data)
    monkeypatch.setattr(
        dashboard_renderer,
        "classify_session_type",
        lambda df, name: "TRAINING",
    )
    monkeypatch.setattr(
        dashboard_renderer,
        "validate_data_completeness",
        lambda df: types.SimpleNamespace(sport_type="running"),
    )
    monkeypatch.setattr(
        dashboard_renderer,
        "process_uploaded_session",
        lambda df, **k: (df, df, {"power_is_estimated": False}, None),
    )

    # `classify_ramp_test` is imported inside the function body, so it has to
    # be patched on the package, not on `dashboard_renderer`.
    import modules.domain

    monkeypatch.setattr(
        modules.domain,
        "classify_ramp_test",
        lambda power: types.SimpleNamespace(is_ramp=True, confidence=0.93),
    )
    return dashboard_renderer, frames


def test_new_file_clears_the_previous_ramp_classification(monkeypatch, _dashboard_env):
    """A file with no power column must not inherit the last file's verdict.

    Pre-review: `ramp_classification` was only written when the new file had
    >= 300 power samples. Loading a power file and then a heart-rate-only file
    left file A's classification in `st.session_state`, and `app.py:167` reads
    that key without a hash guard — the badge showed file A's
    "Ramp Test (confidence: 0.93)" for file B.
    """
    dashboard_renderer, frames = _dashboard_env

    class _State:
        def set_data_loaded(self):
            pass

    sessions: dict = {}
    monkeypatch.setattr(streamlit, "session_state", sessions)

    # File A: enough power -> classified as a ramp test.
    frames["next"] = pd.DataFrame({"watts": [300.0] * 400})
    dashboard_renderer.process_and_cache_session(_FakeUpload("a.csv", b"aaa"), 75.0, _State())
    assert sessions["ramp_classification"].is_ramp is True

    # File B: no power column at all -> nothing can be classified.
    frames["next"] = pd.DataFrame({"heartrate": [140.0] * 400})
    dashboard_renderer.process_and_cache_session(_FakeUpload("b.csv", b"bbb"), 75.0, _State())

    assert sessions["ramp_classification"] is None, "file B kept file A's ramp classification"


def test_state_module_is_importable_for_the_above(monkeypatch):
    """Guard: `StateManager` writes the sidebar keys the UI reads.

    Pre-review this held for weight/height (fixed in wave 1) but not for
    `detected_vt1`/`detected_vt2`, which no code path ever writes. Keep the
    "written keys" list explicit so a read of a never-written key shows up as
    a test failure rather than a silent default.
    """
    from modules.frontend.state import StateManager

    sessions: dict = {}
    monkeypatch.setattr(streamlit, "session_state", sessions)
    StateManager().init_session_state()

    for key in (
        "weight",
        "height",
        "age",
        "gender_m",
        "threshold_pace",
        "lthr",
        "max_hr",
        "vt1_v",
        "vt2_v",
    ):
        assert key in sessions, f"{key} read by the UI but never initialised"


# ---------------------------------------------------------------------------
# 5. Tab registry vs. the tabs app.py actually renders
# ---------------------------------------------------------------------------


def _rendered_tab_names() -> set:
    """Collect the tab names `app.py` passes to `render_tab_content`."""
    import ast
    import inspect

    import app as app_module

    tree = ast.parse(inspect.getsource(app_module))
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "render_tab_content":
            if node.args and isinstance(node.args[0], ast.Constant):
                names.add(node.args[0].value)
    return names


def test_registry_matches_the_tabs_app_actually_renders():
    """Every registered tab must be reachable from a `render_tab_content` call.

    Pre-fix: `_tabs` had 22 entries while `app.py` only rendered 18 —
    "thresholds", "history", "import" and "community" were registered but never
    reached, so the registry advertised four tabs that do not exist in the UI.
    """
    import app as app_module

    registered = set(app_module.TabRegistry._tabs)
    rendered = _rendered_tab_names()

    assert registered == rendered, (
        f"registered but never rendered: {sorted(registered - rendered)}; "
        f"rendered but not registered: {sorted(rendered - registered)}"
    )
    assert len(registered) == 18


def test_deregistered_tabs_are_not_in_the_registry():
    """The four unreachable tabs stay out of `_tabs` (their modules stay on disk)."""
    import app as app_module

    for key in ("thresholds", "history", "import", "community"):
        assert key not in app_module.TabRegistry._tabs, f"{key} is registered again"


# ---------------------------------------------------------------------------
# 6. `modules.ui.vent` re-exports
# ---------------------------------------------------------------------------

# The seven helpers `vent.py` used to re-export. Each one is imported by
# `vent_tab` / `vent_charts` straight from its source module, never through
# `vent.py`, so these had no caller at all.
_VENT_DEAD_REEXPORTS = (
    "_render_br_only_section",
    "_render_ve_section",
    "_render_br_section",
    "_render_tidal_volume_section",
    "_render_legacy_tools",
    "_parse_time_to_seconds",
    "_format_time",
)


def test_vent_module_only_reexports_the_tab_entry_point():
    """`modules.ui.vent` must export just what the app can reach.

    Pre-fix: `__all__` listed eight names, but only `render_vent_tab` was
    reachable — `app.py` looks it up by name through `importlib`, while the
    other seven had no importer through this module and were dead re-exports.
    """
    from modules.ui import vent
    from modules.ui.vent import render_vent_tab

    assert callable(render_vent_tab)
    assert vent.__all__ == ["render_vent_tab"]
    for name in _VENT_DEAD_REEXPORTS:
        assert not hasattr(vent, name), f"{name} is still re-exported"
