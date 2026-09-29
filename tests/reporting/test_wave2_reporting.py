"""Regression tests for wave 2 of the reporting-layer review.

Covers three things:
1. the silent exception handlers listed for this wave — each one either stayed
   silent while a value lied, or was judged correct and is now pinned by a test,
2. the unit audit of ``modules/reporting/**`` (a card may not print a number for
   a measurement that does not exist),
3. save → load symmetry: what ``save_ramp_test_report`` writes must be readable,
   in full, by ``load_ramp_test_report`` and by the PDF mapper.
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Spacer, Table

from modules.reporting.pdf.layout import build_page_biomech
from modules.reporting.pdf.styles import create_styles

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _page_text(elements) -> str:
    """Flatten flowables into plain text for assertions."""
    parts = []
    for el in elements:
        if isinstance(el, Paragraph):
            parts.append(el.getPlainText())
        elif isinstance(el, Table):
            for row in el._cellvalues:
                parts.append(_page_text(row))
        elif isinstance(el, (list, tuple)):
            parts.append(_page_text(el))
        elif isinstance(el, str):
            # Table cells holding bare strings, not Paragraphs.
            parts.append(el)
        elif isinstance(el, Spacer):
            continue
    return "\n".join(p for p in parts if p)


def _messages(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# HANDLER 1 — builder._deep_get_num: a range that does not parse
# ---------------------------------------------------------------------------


def test_deep_get_num_logs_a_range_it_cannot_format(caplog):
    """Pre-fix: ``except (ValueError, TypeError): pass`` swallowed the parse failure,
    so a non-numeric range reached the PDF verbatim with nothing in the log."""
    from modules.reporting.pdf.builder import _deep_get_num

    report = {"thresholds": {"vt1": {"range_watts": ["n/a", "n/a"]}}}

    with caplog.at_level(logging.WARNING, logger="modules.reporting.pdf.builder"):
        out = _deep_get_num(report, "thresholds", "vt1", ["vt1", "range_watts"])

    assert out == "['n/a', 'n/a']"  # fallback behaviour is unchanged
    assert "range_watts" in _messages(caplog)


def test_deep_get_num_logs_nothing_for_a_valid_range(caplog):
    """The warning must be reserved for the failure, not fired on every range."""
    from modules.reporting.pdf.builder import _deep_get_num

    report = {"thresholds": {"vt1": {"range_watts": [180.0, 195.0]}}}

    with caplog.at_level(logging.WARNING, logger="modules.reporting.pdf.builder"):
        out = _deep_get_num(report, "thresholds", "vt1", ["vt1", "range_watts"])

    assert out == "180–195"
    assert not caplog.records


# ---------------------------------------------------------------------------
# HANDLER 2 — builder._add_page_footer: restoreState must run in every path
# ---------------------------------------------------------------------------


class _CanvasSpy:
    """Counts saveState/restoreState pairs and can fail drawImage on demand."""

    def __init__(self, canvas: Canvas, fail_draw: bool = False):
        self._canvas = canvas
        self._fail_draw = fail_draw
        self.saves = 0
        self.restores = 0

    def saveState(self):
        self.saves += 1
        return self._canvas.saveState()

    def restoreState(self):
        self.restores += 1
        return self._canvas.restoreState()

    def drawImage(self, *args, **kwargs):
        if self._fail_draw:
            raise OSError("simulated unreadable watermark")
        return self._canvas.drawImage(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._canvas, name)


class _DocStub:
    page = 1


@pytest.mark.parametrize("fail_draw", [False, True])
def test_page_footer_balances_canvas_state(fail_draw, caplog, tmp_path):
    """Pre-fix: the watermark's ``restoreState()`` sat inside the try, so a failing
    ``drawImage`` skipped it and left the outer ``saveState()`` unpopped — the
    reduced fill alpha stayed active for the footer drawn right after."""
    from modules.reporting.pdf.builder import _add_page_footer

    canvas = _CanvasSpy(Canvas(str(tmp_path / "probe.pdf"), pagesize=A4), fail_draw=fail_draw)

    with caplog.at_level(logging.WARNING, logger="modules.reporting.pdf.builder"):
        _add_page_footer(canvas, _DocStub())

    assert canvas.saves == canvas.restores
    if fail_draw:
        assert "watermark" in _messages(caplog)
    else:
        assert not caplog.records


# ---------------------------------------------------------------------------
# HANDLER 3/4 — layout fmt() fallbacks stay verbatim (no change in behaviour)
# ---------------------------------------------------------------------------


def test_vt_threshold_table_prints_a_non_numeric_range_verbatim():
    """Pins the ``fmt`` fallback: a display string stays a display string."""
    from modules.reporting.pdf.layout import build_page_thresholds

    text = _page_text(
        build_page_thresholds(
            thresholds={"vt1_range_watts": "180–195", "vt1_watts": "~188"},
            smo2={},
            figure_paths={},
            styles=create_styles(),
        )
    )

    assert "180–195" in text


# ---------------------------------------------------------------------------
# HANDLER 5 — styles.register_fonts: Helvetica fallback is now logged
# ---------------------------------------------------------------------------


def test_font_fallback_is_logged(monkeypatch, caplog):
    """Pre-fix: the failure returned the Helvetica tuple with no log at all, so a
    PDF that cannot render Polish diacritics was produced silently."""
    from modules.reporting.pdf import styles

    def _boom(*args, **kwargs):
        raise OSError("font file missing")

    monkeypatch.setattr(styles.pdfmetrics, "registerFont", _boom)

    with caplog.at_level(logging.WARNING, logger="modules.reporting.pdf.styles"):
        fonts = styles.register_fonts()

    assert fonts[0] == "Helvetica"
    assert "Helvetica" in _messages(caplog)


# ---------------------------------------------------------------------------
# HANDLER 6 — figures.thermal: a dropped trend line is now logged
# ---------------------------------------------------------------------------


def test_thermal_trend_failure_is_logged(monkeypatch, caplog):
    """Pre-fix: ``except ...: pass`` dropped the trend line from a chart that ships
    inside the PDF, with no trace anywhere."""
    from modules.reporting.figures import thermal

    df = pd.DataFrame(
        {
            "watts": [200.0, 220.0, 240.0, 210.0, 230.0],
            "heartrate": [140.0, 150.0, 160.0, 145.0, 155.0],
            "core_temperature": [37.1, 37.4, 37.8, 37.5, 38.0],
        }
    )

    def _boom(*args, **kwargs):
        raise ValueError("SVD did not converge")

    monkeypatch.setattr(thermal.np, "polyfit", _boom)

    with caplog.at_level(logging.WARNING, logger="modules.reporting.figures.thermal"):
        thermal.generate_efficiency_chart({}, source_df=df)

    assert "trend line omitted" in _messages(caplog)


# ---------------------------------------------------------------------------
# HANDLER 7 — figures.limiters: 0.0 is the documented "no VT2 VE" sentinel
# ---------------------------------------------------------------------------


def test_vt2_ve_failure_falls_back_to_observed_max():
    """Pins the sentinel: a missing VT2 VE must not become a hard 0 % ceiling."""
    from modules.reporting.figures.limiters import _extract_vt2_ve

    assert _extract_vt2_ve({"thresholds": {"vt2": {"ve": None}}}) == 0.0
    assert _extract_vt2_ve({}) == 0.0
    assert _extract_vt2_ve({"thresholds": {"vt2": {"ve": 120.0}}}) == 120.0


# ---------------------------------------------------------------------------
# HANDLER 8 — persistence_load.check_git_tracking: the privacy check now speaks
# ---------------------------------------------------------------------------


def test_git_check_failure_is_logged(monkeypatch, caplog, tmp_path):
    """Pre-fix: ``except (OSError, subprocess.SubprocessError): pass`` made the
    subject-data privacy warning vanish without a trace whenever git was missing."""
    from modules.reporting import persistence_load

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    def _boom(*args, **kwargs):
        raise FileNotFoundError("git not installed")

    monkeypatch.setattr(persistence_load.subprocess, "run", _boom)

    with caplog.at_level(logging.WARNING, logger="modules.reporting.persistence_load"):
        persistence_load.check_git_tracking("reports/ramp_tests")

    message = _messages(caplog)
    assert "tracked by git" in message
    assert "did not run" in message


def test_git_check_failure_reaches_the_interface(monkeypatch, caplog, tmp_path):
    """Pre-fix: the failure was logged to a console nobody reads in Streamlit, so the
    user was never told that the subject-data privacy check did not run."""
    import streamlit

    from modules.reporting import persistence_load

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    def _boom(*args, **kwargs):
        raise OSError("git not installed")

    warnings = []
    monkeypatch.setattr(persistence_load.subprocess, "run", _boom)
    monkeypatch.setattr(streamlit, "warning", lambda msg: warnings.append(msg))

    persistence_load.check_git_tracking("reports/ramp_tests")

    assert warnings, "the user was never told the privacy check failed"
    assert "Kontrola prywatności nie została wykonana" in warnings[0]


def test_git_check_reports_tracked_subject_data(monkeypatch, tmp_path):
    """The happy path still raises the Streamlit privacy warning."""
    import streamlit

    from modules.reporting import persistence_load

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    errors = []
    monkeypatch.setattr(streamlit, "error", lambda msg: errors.append(msg))

    class _Result:
        returncode = 0
        stdout = "reports/ramp_tests/2026/01/ramp_test_2026-01-15_abc.json\n"

    monkeypatch.setattr(persistence_load.subprocess, "run", lambda *a, **k: _Result())

    persistence_load.check_git_tracking("reports/ramp_tests")

    assert errors and "SECURITY WARNING" in errors[0]


# ---------------------------------------------------------------------------
# HANDLER 9 — persistence_save._parse_test_date: the invented date is logged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["03.01.2026", "2026/01/03", "", None])
def test_invalid_test_date_falls_back_to_today_and_is_logged(bad, caplog):
    """Pre-fix: a malformed date silently became "today", so the report was filed
    under a measurement date that never happened, with no trace in the log."""
    from modules.reporting.persistence_save import _parse_test_date

    now = datetime(2026, 3, 4, 12, 0)

    with caplog.at_level(logging.WARNING, logger="modules.reporting.persistence_save"):
        parsed, inferred = _parse_test_date(bad, now)

    assert parsed == date(2026, 3, 4)
    assert inferred is True
    assert "2026-03-04" in _messages(caplog)


def test_valid_test_date_is_used_without_a_warning(caplog):
    from modules.reporting.persistence_save import _parse_test_date

    with caplog.at_level(logging.WARNING, logger="modules.reporting.persistence_save"):
        parsed, inferred = _parse_test_date("2026-01-15", datetime(2026, 3, 4, 12, 0))

    assert parsed == date(2026, 1, 15)
    assert inferred is False
    assert not caplog.records


# ---------------------------------------------------------------------------
# LOAD — a file that is not a report at all
# ---------------------------------------------------------------------------


def test_load_rejects_a_non_object_json(tmp_path):
    """Pre-fix: a top-level list reached ``report.get(...)`` and died on AttributeError,
    which tells the user nothing about the file being the wrong shape."""
    from modules.reporting.persistence_load import load_ramp_test_report

    path = tmp_path / "not_a_report.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError, match="oczekiwano obiektu JSON"):
        load_ramp_test_report(path)


# ---------------------------------------------------------------------------
# UNIT AUDIT — the biomechanics page may not invent running dynamics
# ---------------------------------------------------------------------------


def _canonical_occlusion() -> dict:
    """Built by the real producer, so the fixture cannot drift from the schema."""
    from modules.calculations.biomech_occlusion import (
        OcclusionProfile,
        format_occlusion_for_report,
    )

    return format_occlusion_for_report(
        OcclusionProfile(
            occlusion_index=0.31,
            regression_slope=-0.42,
            regression_r2=0.81,
            smo2_baseline=68.5,
            torque_at_baseline=41.0,
            torque_at_minus_10=47.5,
            torque_at_minus_20=0.0,
            classification="high",
            classification_color="#E74C3C",
            data_points=900,
            confidence=0.72,
        )
    )


def test_biomech_page_marks_missing_running_dynamics():
    """Pre-fix: gct/stance_balance/vertical_oscillation were read with numeric
    defaults off a dict that never carries them, so every report printed
    "0 ms / Krótki kontakt", "50.0 % / Symetryczny" and "0.0 cm / Niska"."""
    occlusion = _canonical_occlusion()
    assert "gct_avg" not in occlusion

    text = _page_text(
        build_page_biomech(
            biomech_data=occlusion, figure_paths={}, styles=create_styles()
        )
    )

    assert "Brak danych" in text
    assert "Krótki kontakt" not in text
    assert "Symetryczny" not in text
    assert "0.0" not in text


def test_biomech_page_renders_running_dynamics_when_they_exist():
    """The other direction: real values must still reach the cards."""
    text = _page_text(
        build_page_biomech(
            biomech_data={"gct_avg": 320.0, "stance_balance": 51.2, "vertical_oscillation": 8.4},
            figure_paths={},
            styles=create_styles(),
        )
    )

    assert "320" in text
    assert "51.2" in text
    assert "8.4" in text
    assert "Długi kontakt" in text


@pytest.mark.parametrize("value,forbidden", [(float("nan"), "nan"), (True, "True"), (float("inf"), "inf")])
def test_biomech_page_treats_nan_bool_and_inf_as_missing(value, forbidden):
    """Pre-fix: ``isinstance(x, (int, float))`` is True for bool and passes NaN/inf, so
    the card printed "nan ms" and coloured it as if a measurement had arrived."""
    text = _page_text(
        build_page_biomech(
            biomech_data={"gct_avg": value, "stance_balance": value, "vertical_oscillation": value},
            figure_paths={},
            styles=create_styles(),
        )
    )

    assert text.count("Brak danych") >= 3
    assert forbidden not in text


# ---------------------------------------------------------------------------
# SAVE → LOAD ROUND-TRIP
# ---------------------------------------------------------------------------


def _run_save(monkeypatch, tmp_path, test_date, extra_columns=None):
    """Run the real save path and return (path, session_id, returned_dict)."""
    import streamlit

    from models.results import RampTestResult, TestValidity, ThresholdRange, ValidityLevel
    from modules.domain import SessionType
    from modules.reporting.persistence_save import save_ramp_test_report

    monkeypatch.setattr(streamlit, "session_state", {"report_generation_requested": True})

    n = 400
    seconds = np.arange(n)
    source_df = pd.DataFrame(
        {
            "time": seconds,
            "watts": 150.0 + seconds * 0.35,
            "hr": 120.0 + seconds * 0.08,
            "smo2": 70.0 - seconds * 0.02,
            "tymeventilation": 45.0 + seconds * 0.05,
            "cadence": 85.0,
        }
    )
    for column, value in (extra_columns or {}).items():
        source_df[column] = value

    result = RampTestResult(
        validity=TestValidity(
            validity=ValidityLevel.VALID,
            ramp_duration_sec=780,
            power_range_watts=260.0,
        ),
        vt1=ThresholdRange(
            lower_watts=180.0,
            upper_watts=195.0,
            midpoint_watts=188.0,
            confidence=0.8,
            midpoint_hr=158.0,
            midpoint_ve=78.5,
        ),
        vt2=ThresholdRange(
            lower_watts=250.0,
            upper_watts=265.0,
            midpoint_watts=258.0,
            confidence=0.75,
        ),
        cp_watts=255.0,
        w_prime_joules=18000.0,
        overall_confidence=0.8,
        protocol="Ramp 25W/min",
        test_date=test_date,
        rider_weight=78.0,
        max_hr=192.0,
    )

    saved = save_ramp_test_report(
        result,
        output_base_dir=str(tmp_path),
        athlete_id="athlete-001",
        notes="Wave 2 round-trip",
        dev_mode=True,
        session_type=SessionType.RAMP_TEST,
        ramp_confidence=0.9,
        source_df=source_df,
    )

    assert saved.get("gated") is not True, saved
    return Path(saved["path"]), saved["session_id"], saved


@pytest.fixture
def saved_ramp_report(monkeypatch, tmp_path):
    """A report saved through the real path, dated by a parseable test_date."""
    return _run_save(monkeypatch, tmp_path, test_date="2026-01-15")


def test_inferred_test_date_is_flagged_in_metadata(monkeypatch, tmp_path):
    """Pre-fix: an unusable date became "today" and nothing in the file said so, so a
    report nobody dated was indistinguishable from a measured one."""
    path, _, _ = _run_save(monkeypatch, tmp_path, test_date=None)

    metadata = json.loads(path.read_text(encoding="utf-8"))["metadata"]

    assert metadata["test_date_inferred"] is True


def test_parsed_test_date_leaves_no_flag(monkeypatch, tmp_path):
    """The flag is added only when the date was guessed — old reports keep their shape."""
    path, _, _ = _run_save(monkeypatch, tmp_path, test_date="2026-01-15")

    metadata = json.loads(path.read_text(encoding="utf-8"))["metadata"]

    assert "test_date_inferred" not in metadata
    assert metadata["test_date"] == "2026-01-15"


def test_title_page_marks_an_inferred_test_date():
    """The flag has to reach the page: the operator reads the PDF, not the JSON."""
    from modules.reporting.pdf.builder import _extract_metadata
    from modules.reporting.pdf.layout_title import build_title_page

    mapped = _extract_metadata(
        {"metadata": {"test_date": "2026-03-04", "test_date_inferred": True}}, {}
    )

    text = _page_text(build_title_page(metadata=mapped, styles=create_styles()))

    assert "(data przyjęta automatycznie)" in text


def test_title_page_has_no_marker_for_a_parsed_date():
    from modules.reporting.pdf.builder import _extract_metadata
    from modules.reporting.pdf.layout_title import build_title_page

    mapped = _extract_metadata({"metadata": {"test_date": "2026-01-15"}}, {})

    text = _page_text(build_title_page(metadata=mapped, styles=create_styles()))

    assert "2026-01-15" in text
    assert "automatycznie" not in text


def test_manual_date_override_drops_the_inferred_marker():
    """An operator-supplied date is not the guessed one — the marker would be a lie."""
    from modules.reporting.pdf.builder import _extract_metadata

    mapped = _extract_metadata(
        {"metadata": {"test_date": "2026-03-04", "test_date_inferred": True}},
        {"test_date_override": "2026-02-11"},
    )

    assert mapped["test_date"] == "2026-02-11"
    assert mapped["test_date_inferred"] is False


def test_roundtrip_load_is_lossless(saved_ramp_report):
    """Nothing the saver writes may be reshaped or dropped on the way back in."""
    from modules.reporting.persistence_load import load_ramp_test_report

    path, _, _ = saved_ramp_report
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    loaded = load_ramp_test_report(path)

    assert loaded == on_disk


def test_roundtrip_preserves_schema_and_method_version(saved_ramp_report):
    """``$schema``/``version``/``method_version`` are written and must come back."""
    from modules.reporting.persistence_constants import (
        CANONICAL_SCHEMA,
        CANONICAL_VERSION,
        METHOD_VERSION,
    )
    from modules.reporting.persistence_load import load_ramp_test_report

    path, session_id, _ = saved_ramp_report
    loaded = load_ramp_test_report(path)

    assert loaded["$schema"] == CANONICAL_SCHEMA
    assert loaded["version"] == CANONICAL_VERSION
    assert loaded["metadata"]["method_version"] == METHOD_VERSION
    assert loaded["metadata"]["session_id"] == session_id
    assert loaded["metadata"]["test_date"] == "2026-01-15"
    assert loaded["metadata"]["athlete_id"] == "athlete-001"


def test_roundtrip_keeps_every_section_the_result_serialises(saved_ramp_report):
    """Every section produced by RampTestResult.to_dict() survives the round trip."""
    from modules.reporting.persistence_load import load_ramp_test_report

    path, _, _ = saved_ramp_report
    loaded = load_ramp_test_report(path)

    expected_sections = {
        "$schema",
        "version",
        "test_validity",
        "thresholds",
        "smo2_context",
        "cp_model",
        "smo2_manual",
        "power_duration_curve",
        "conflicts",
        "interpretation",
        "metadata",
    }
    assert expected_sections <= set(loaded)

    assert loaded["thresholds"]["vt1"]["midpoint_watts"] == 188.0
    assert loaded["thresholds"]["vt2"]["range_watts"] == [250.0, 265.0]
    assert loaded["cp_model"]["w_prime_joules"] == 18000.0


def test_roundtrip_time_series_uses_canonical_column_names(saved_ramp_report):
    """The _TS_COLUMN_MAP aliases must land under the canonical keys on disk."""
    from modules.reporting.persistence_load import load_ramp_test_report

    path, _, _ = saved_ramp_report
    time_series = load_ramp_test_report(path).get("time_series")

    assert time_series is not None, "save dropped the time series"
    assert len(time_series["time_sec"]) == 400
    assert time_series["power_watts"][0] == pytest.approx(150.0)
    assert time_series["hr_bpm"][0] == pytest.approx(120.0)
    assert time_series["smo2_pct"][0] == pytest.approx(70.0)
    assert time_series["ve_lmin"][0] == pytest.approx(45.0)
    assert time_series["cadence_rpm"][0] == pytest.approx(85.0)


def test_roundtrip_feeds_the_pdf_mapper(saved_ramp_report):
    """The real consumer of load_ramp_test_report must be able to build a story."""
    from modules.reporting.pdf.builder import _build_pdf_story, map_ramp_json_to_pdf_data
    from modules.reporting.pdf.styles import PDFConfig
    from modules.reporting.persistence_load import load_ramp_test_report

    path, _, _ = saved_ramp_report
    pdf_data = map_ramp_json_to_pdf_data(load_ramp_test_report(path))

    story = _build_pdf_story(pdf_data, {}, create_styles(), PDFConfig(), compact_mode=True)

    assert story
    assert pdf_data["thresholds"]["vt1_watts"] == "188"


# ---------------------------------------------------------------------------
# METABOLIC ENGINE PAGE — hidden unless the data it prints exists
# ---------------------------------------------------------------------------


def _story_for(saved_ramp_report, extra_sections=None):
    """Map a saved report through the real mapper and build the real story."""
    from modules.reporting.pdf.builder import _build_pdf_story, map_ramp_json_to_pdf_data
    from modules.reporting.pdf.styles import PDFConfig
    from modules.reporting.persistence_load import load_ramp_test_report

    path, _, _ = saved_ramp_report
    report = load_ramp_test_report(path)
    report.update(extra_sections or {})

    pdf_data = map_ramp_json_to_pdf_data(report)
    return _build_pdf_story(pdf_data, {}, create_styles(), PDFConfig(), compact_mode=True)


def test_metabolic_page_is_omitted_when_its_keys_are_absent(saved_ramp_report):
    """Pre-fix: the page was included whenever ``metabolic_strategy`` was non-empty,
    and it printed "0 W / 0% tłuszczów", "0–0 W" and "NIEOKREŚLONY 0%" from keys no
    producer writes — a fabricated page in every report."""
    story = _story_for(saved_ramp_report)
    text = _page_text(story)

    assert story, "the document must still build without the page"
    assert "SILNIK METABOLICZNY" not in text
    # None of the page's fabricated cards may survive.
    assert "FATMAX" not in text
    assert "STREFA TŁUSZCZÓW" not in text
    # ...and the table of contents must not advertise the missing page either.
    assert "Silnik metaboliczny" not in text


def test_metabolic_page_appears_when_its_keys_are_present(saved_ramp_report):
    """The other direction: a producer that fills the keys gets its page back."""
    story = _story_for(
        saved_ramp_report,
        {
            "metabolic_strategy": {
                "fat_max_watts": 210.0,
                "fat_max_pct": 62.0,
                "cho_crossover_watts": 268.0,
                "fat_burning_zone": {"low": 150.0, "high": 220.0},
                "cho_zone": {"low": 268.0, "high": 400.0},
                "metabolic_status": "efficient",
                "metabolic_confidence": 0.7,
            }
        },
    )
    text = _page_text(story)

    assert "SILNIK METABOLICZNY" in text
    assert "FATMAX" in text
    assert "210" in text
    assert "EFEKTYWNY" in text
    assert "Silnik metaboliczny" in text


def _toc_pages(story) -> dict:
    """Title -> printed page number, read from the contents table in ``story``."""
    from reportlab.platypus import Table

    for flowable in story:
        if not isinstance(flowable, Table):
            continue
        rows = [row for row in flowable._cellvalues if len(row) == 2]
        if not rows or "PODSUMOWANIE WYKONAWCZE" not in rows[0][0].getPlainText():
            continue
        return {
            row[0].getPlainText().replace("•", "").strip(): row[1].getPlainText().strip()
            for row in rows
        }
    raise AssertionError("no table of contents found in the story")


def test_hiding_the_page_also_shifts_the_contents_below_it(saved_ramp_report):
    """Pre-fix: dropping the entry left every later number one page too high. The numbers
    are also the link targets, so the last one pointed past the end of the file and
    ReportLab refused to write the document at all — the report lost its PDF, not just a
    line of the contents ("undefined destination target for 'page_25'")."""
    entries = _toc_pages(_story_for(saved_ramp_report))

    assert "2.4 Silnik metaboliczny" not in entries
    # Entries above the hidden page keep their number...
    assert entries["2.3 Model metaboliczny"] == "7"
    # ...everything below it moves one page up.
    assert entries["2.5 Krzywa mocy (PDC)"] == "9"
    assert entries["5.5 Ograniczenia interpretacji"] == "24"


# ---------------------------------------------------------------------------
# BIOMECH CHART — the key figures/__init__.py actually registers
# ---------------------------------------------------------------------------


def test_biomech_page_embeds_the_registered_chart(tmp_path):
    """Pre-fix: the page looked up ``figure_paths["biomech_profile"]``, a key no figure
    generator produces, so the biomechanics chart never reached the PDF."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.platypus import Image as RLImage

    chart = tmp_path / "biomech_summary.png"
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    fig.savefig(chart)
    plt.close(fig)

    elements = build_page_biomech(
        biomech_data={}, figure_paths={"biomech_summary": str(chart)}, styles=create_styles()
    )

    assert any(isinstance(el, RLImage) for el in elements)
    assert "brak wykresu" not in _page_text(elements)


def test_the_orchestrator_really_produces_the_biomech_summary_key(tmp_path):
    """Pins the other end of the contract: the key the page now reads is the one the
    real figure orchestrator writes."""
    from modules.reporting.figures import generate_all_ramp_figures

    source_df = pd.DataFrame(
        {
            "time": range(200),
            "watts": 200.0,
            "cadence": 85.0,
            "hr": 150.0,
            "smo2": 65.0,
        }
    )

    paths = generate_all_ramp_figures(
        {}, str(tmp_path), {"method_version": "1.0.0"}, source_df=source_df
    )

    assert "biomech_summary" in paths
    assert Path(paths["biomech_summary"]).exists()


# ---------------------------------------------------------------------------
# THERMAL PAGE — same defect as the biomech cards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,forbidden", [(float("nan"), "nan"), (True, "True"), (float("inf"), "inf")]
)
def test_thermal_page_treats_nan_bool_and_inf_as_missing(value, forbidden):
    """Pre-fix: ``_num`` formatted with ``f"{nan:.1f}"`` and the colour branches used a
    bare isinstance, so a NaN or a bool printed as a measurement."""
    from modules.reporting.pdf.layout import build_page_thermal

    text = _page_text(
        build_page_thermal(
            thermal_data={
                "metrics": {
                    "max_core_temp": value,
                    "min_core_temp": value,
                    "peak_hsi": value,
                    "delta_per_10min": value,
                }
            },
            figure_paths={},
            styles=create_styles(),
        )
    )

    assert forbidden not in text
    assert "brak danych" in text


# ---------------------------------------------------------------------------
# INFERRED DATE — the stored date must be the one actually used
# ---------------------------------------------------------------------------


def test_unparseable_date_is_stored_as_the_date_actually_used(monkeypatch, tmp_path):
    """Pre-fix (round 1): the metadata kept the unparseable text, so the PDF read
    "03.01.2026 (data przyjęta automatycznie)" while the file itself was filed under
    today's date. The stored date must now match the annotation and the directory."""
    path, _, _ = _run_save(monkeypatch, tmp_path, test_date="03.01.2026")

    metadata = json.loads(path.read_text(encoding="utf-8"))["metadata"]
    today = datetime.now().date()

    assert metadata["test_date"] == today.isoformat()
    assert metadata["test_date_inferred"] is True
    assert metadata["test_date_raw"] == "03.01.2026"
    # The date on the report agrees with the directory it was filed in.
    assert path.parent.name == f"{today.month:02d}"
    assert today.isoformat() in path.name


# ---------------------------------------------------------------------------
# DEAD DOCX PATH — removed from persistence_pdf
# ---------------------------------------------------------------------------


def test_save_never_attempts_the_missing_docx_builder(monkeypatch, tmp_path, caplog):
    """Pre-fix: both PDF paths imported ``.docx_builder``, which does not exist in the
    repo, so every generated report logged a DOCX failure for a module nobody wrote."""
    with caplog.at_level(logging.DEBUG):
        # A pace column keeps the report out of the "invalid" branch, so the PDF — and
        # with it the removed DOCX block — is actually attempted.
        saved = _run_save(
            monkeypatch, tmp_path, test_date="2026-01-15", extra_columns={"pace": 305.0}
        )

    messages = _messages(caplog)

    assert "DOCX" not in messages
    assert saved[2].get("pdf_path"), saved[2]


def test_smo2_power_chart_survives_a_null_smo2_context(tmp_path):
    """Pre-fix: ``report_data.get("smo2_context", {})`` keeps a stored ``None``, and the
    drop-point lookup then raised AttributeError — killing the whole figure run, and with
    it the PDF, for every test that had SmO2 and pace but no SmO2 context section."""
    from modules.reporting.figures.smo2_vs_power import generate_smo2_power_chart

    source_df = pd.DataFrame(
        {"time": range(150), "pace": [300.0] * 150, "smo2": [65.0] * 150}
    )
    chart = tmp_path / "smo2_pace.png"

    produced = generate_smo2_power_chart(
        {"time_series": {}, "smo2_context": None}, source_df=source_df, output_path=str(chart)
    )

    assert produced
    assert chart.exists()


# ---------------------------------------------------------------------------
# PACE IN THE TIME SERIES — what the drift heatmap reads back
# ---------------------------------------------------------------------------


def test_pace_is_persisted_under_the_key_the_figures_read(monkeypatch, tmp_path):
    """Pre-fix: nothing mapped a pace column, so time_series had no pace_sec_per_km and
    every regenerated drift heatmap fell back to "Za mało danych"."""
    from modules.reporting.persistence_load import load_ramp_test_report

    path, _, _ = _run_save(
        monkeypatch, tmp_path, test_date="2026-01-15", extra_columns={"pace": 305.0}
    )
    time_series = load_ramp_test_report(path)["time_series"]

    assert time_series["pace_sec_per_km"][0] == pytest.approx(305.0)


def test_speed_columns_are_not_filed_as_pace(monkeypatch, tmp_path):
    """A rename map cannot convert units: m/s under a sec/km key would be a lie."""
    from modules.reporting.persistence_load import load_ramp_test_report

    path, _, _ = _run_save(
        monkeypatch, tmp_path, test_date="2026-01-15", extra_columns={"velocity_smooth": 3.3}
    )

    assert "pace_sec_per_km" not in load_ramp_test_report(path)["time_series"]


def test_a_report_without_pace_still_loads(saved_ramp_report):
    """Old files predate the key and must keep reading exactly as before."""
    from modules.reporting.persistence_load import load_ramp_test_report

    path, _, _ = saved_ramp_report
    loaded = load_ramp_test_report(path)

    assert "pace_sec_per_km" not in loaded["time_series"]
    assert loaded["metadata"]["test_date"] == "2026-01-15"


class _EmptyFigureStub:
    """Stands in for the "not enough data" figure the drift heatmap returns."""

    def to_image(self, **kwargs):
        return b""


@pytest.mark.parametrize(
    "time_series,expect_fallback",
    [
        ({"pace_sec_per_km": [300.0] * 150, "hr_bpm": [150.0] * 150}, False),
        ({"hr_bpm": [150.0] * 150}, True),
    ],
)
def test_drift_heatmap_uses_the_persisted_pace(monkeypatch, time_series, expect_fallback):
    """The round trip has to be useful: the saved key is exactly what drift.py reads."""
    from modules.reporting.figures import drift

    fallbacks = []
    monkeypatch.setattr(
        drift, "create_empty_figure", lambda *a, **k: fallbacks.append(a[0]) or _EmptyFigureStub()
    )

    drift.generate_drift_heatmap({"time_series": time_series}, mode="hr")

    assert bool(fallbacks) is expect_fallback


# ---------------------------------------------------------------------------
# DRIFT CHARTS — the JSON fallback has to filter like the DataFrame branch
# ---------------------------------------------------------------------------


def _drift_data(rows: int = 150, time_column: str = "time"):
    """One run in two shapes: the session DataFrame and the JSON written from it.

    Contains everything the two branches have to agree on — standstills (pace 0, what a
    zero speed becomes), impossible paces, a sensor that returned zeros, and a heart rate
    under the floor the DataFrame branch applies. ``time_column="time_min"`` writes the
    same clock in the other unit the DataFrame branches accept; the saved JSON always
    carries seconds.
    """
    pace: list = []
    hr: list = []
    smo2: list = []
    for i in range(rows):
        if i < 10:
            pace.append(0.0)
            hr.append(150.0)
            smo2.append(65.0)
        elif i < 20:
            pace.append(1500.0)
            hr.append(150.0)
            smo2.append(65.0)
        elif i < 30:
            pace.append(300.0)
            hr.append(0.0)
            smo2.append(0.0)
        elif i < 40:
            pace.append(300.0)
            hr.append(20.0)
            smo2.append(5.0)
        else:
            pace.append(300.0 + i)
            hr.append(150.0)
            smo2.append(65.0)

    times = list(range(rows))
    df = pd.DataFrame({"time": times, "pace": pace, "hr": hr, "smo2": smo2})
    if time_column != "time":
        df[time_column] = [t / 60 for t in times]
        df = df.drop(columns=["time"])
    time_series = {
        "time_sec": times,
        "pace_sec_per_km": pace,
        "hr_bpm": hr,
        "smo2_pct": smo2,
    }
    return df, time_series


def _record_plots(monkeypatch) -> list:
    """Capture the (x, y, colors) triples the chart functions hand to matplotlib.

    The colors are part of what the two branches have to agree on: a scale 60 times
    smaller paints the same points in different shades.
    """
    import matplotlib.axes as maxes

    calls: list = []

    def recorder(name, original):
        def plot(self, x, y, *args, **kwargs):
            colors = kwargs.get("c")
            if isinstance(colors, list):
                colors = list(colors)
            calls.append((name, list(x), list(y), colors))
            return original(self, x, y, *args, **kwargs)

        return plot

    for name in ("scatter", "hexbin"):
        monkeypatch.setattr(maxes.Axes, name, recorder(name, getattr(maxes.Axes, name)))

    return calls


def _run_drift_chart(chart, report_data, source_df, output_path):
    from modules.reporting.figures import drift

    if chart == "hr_scatter":
        return drift.generate_power_hr_scatter(
            report_data, output_path=output_path, source_df=source_df
        )
    if chart == "smo2_scatter":
        return drift.generate_power_smo2_scatter(
            report_data, output_path=output_path, source_df=source_df
        )
    return drift.generate_drift_heatmap(
        report_data, output_path=output_path, source_df=source_df, mode=chart.removeprefix("heatmap_")
    )


@pytest.mark.parametrize("time_column", ["time", "time_min"])
@pytest.mark.parametrize("chart", ["hr_scatter", "smo2_scatter", "heatmap_hr", "heatmap_smo2"])
def test_json_fallback_plots_the_same_map_as_the_dataframe(
    monkeypatch, tmp_path, chart, time_column
):
    """Pre-fix: the JSON path did not filter standstills (pace 0), so a PDF rebuilt from a
    saved report drew a different map than the PDF from the session that produced it. The
    ``time_min`` run covers the second half of the same defect: the colorbar."""
    df, time_series = _drift_data(time_column=time_column)
    report_data = {"time_series": time_series}
    calls = _record_plots(monkeypatch)

    _run_drift_chart(chart, report_data, df, str(tmp_path / f"{chart}_df.png"))
    df_calls = list(calls)

    del calls[:]
    _run_drift_chart(chart, report_data, None, str(tmp_path / f"{chart}_json.png"))
    json_calls = list(calls)

    assert json_calls, "the JSON path must still plot something"
    assert json_calls == df_calls


# ---------------------------------------------------------------------------
# SmO₂ vs PACE — the same map whichever source drew it
# ---------------------------------------------------------------------------


def test_smo2_power_json_path_plots_the_same_points_as_the_dataframe(monkeypatch, tmp_path):
    """Pre-fix: this chart's JSON fallback took the saved pace as it came, so a report
    rebuilt from disk pinned every standstill to 0 min/km while the session's own PDF —
    whose DataFrame branch has always filtered — did not."""
    from modules.reporting.figures import smo2_vs_power

    df, time_series = _drift_data()
    report_data = {"time_series": time_series}
    calls = _record_plots(monkeypatch)

    smo2_vs_power.generate_smo2_power_chart(
        report_data, output_path=str(tmp_path / "df.png"), source_df=df
    )
    df_calls = list(calls)

    del calls[:]
    smo2_vs_power.generate_smo2_power_chart(report_data, output_path=str(tmp_path / "json.png"))
    json_calls = list(calls)

    assert json_calls, "the JSON path must still plot something"
    assert json_calls == df_calls


# ---------------------------------------------------------------------------
# VE PROFILE — the VT line belongs at the threshold, on the trace that was drawn
# ---------------------------------------------------------------------------


def _ramp_ve_chart(monkeypatch, tmp_path, report_data, source_df=None, name="ve.png") -> list:
    """Run the VE chart and return the x of every vertical line it drew."""
    import matplotlib.axes as maxes

    from modules.reporting.figures import ve_profile

    lines: list = []

    def recorder(original):
        def axvline(self, *args, **kwargs):
            lines.append(kwargs.get("x", args[0] if args else None))
            return original(self, *args, **kwargs)

        return axvline

    monkeypatch.setattr(maxes.Axes, "axvline", recorder(maxes.Axes.axvline))

    ve_profile.generate_ve_profile_chart(
        report_data, output_path=str(tmp_path / name), source_df=source_df
    )
    return lines


def _progressive_run(pace_sec: list, threshold_sec: float, start_sec: int = 20) -> dict:
    """A ramp with one VE reading per pace sample and a VT1 threshold to place."""
    times = [start_sec + 20 * i for i in range(len(pace_sec))]
    return {
        "time_series": {
            "time_sec": times,
            "ve_lmin": [30.0 + i for i in range(len(pace_sec))],
            "pace_sec_per_km": pace_sec,
        },
        "thresholds": {"vt1": {"midpoint_pace_sec": threshold_sec}},
        "metadata": {},
    }


def test_vt_line_lands_on_the_threshold_not_on_the_warm_up(monkeypatch, tmp_path):
    """Pre-fix: the comparison ran the wrong way for sec/km, so the first — slowest —
    sample of the warm-up counted as "reaching" the threshold and the line landed at 20 s."""
    pace_sec = [420.0 - 6 * i for i in range(31)]  # 7:00/km down to 4:00/km
    report_data = _progressive_run(pace_sec, 300.0)

    lines = _ramp_ve_chart(monkeypatch, tmp_path, report_data)

    assert lines == [7.0]  # 300 s/km is reached at t = 420 s


def test_vt_line_is_drawn_when_the_threshold_is_met_at_the_start(monkeypatch, tmp_path):
    """A run that begins on the threshold is a crossing at 0 min, which a truthiness
    check on the time — or on the pace — threw away."""
    pace_sec = [300.0 - 5 * i for i in range(31)]
    report_data = _progressive_run(pace_sec, 300.0, start_sec=0)

    lines = _ramp_ve_chart(monkeypatch, tmp_path, report_data)

    assert lines == [0.0]


def test_vt_line_uses_the_same_series_as_the_plotted_trace(monkeypatch, tmp_path):
    """Pre-fix: the threshold was always looked up in the saved JSON, even when the trace
    on the chart came from the session's DataFrame — two different sources for one chart."""
    df = pd.DataFrame(
        {
            "time": [20 * (i + 1) for i in range(31)],
            "ve": [30.0 + i for i in range(31)],
            "pace": [420.0 - 6 * i for i in range(31)],  # crossing at t = 420 s
        }
    )
    report_data = _progressive_run([290.0] * 31, 300.0)  # JSON would say t = 20 s

    lines = _ramp_ve_chart(monkeypatch, tmp_path, report_data, source_df=df, name="ve_df.png")

    assert lines == [7.0]


# ---------------------------------------------------------------------------
# CONTENTS ENTRY — the title lives in one place, and a missing entry is a no-op
# ---------------------------------------------------------------------------


def test_contents_survive_a_list_without_the_metabolic_entry():
    """Pre-fix: ``next()`` without a default raised StopIteration as soon as the entry was
    renamed or taken out of the list."""
    from modules.reporting.pdf.builder import _contents_without_metabolic_page

    titles = [{"title": "1. PODSUMOWANIE WYKONAWCZE", "page": "3", "level": 0}]

    assert _contents_without_metabolic_page(titles) == titles


# ---------------------------------------------------------------------------
# TIME-SERIES LOG — a sensor nobody wears is not a warning
# ---------------------------------------------------------------------------


def test_missing_sensor_is_logged_quietly_and_a_missing_chart_key_is_not(caplog):
    """A missing torque column costs no chart — no figure reads it — so it must not warn
    on every save; a missing heart rate column does cost one."""
    from modules.reporting.persistence_save import _extract_time_series_data

    with caplog.at_level(logging.DEBUG):
        _extract_time_series_data(pd.DataFrame({"time": [0, 1]}))

    levels = {}
    for record in caplog.records:
        for key in ("torque_nm", "hr_bpm"):
            if f"'{key}'" in record.message:
                levels[key] = record.levelname

    assert levels == {"torque_nm": "DEBUG", "hr_bpm": "WARNING"}
