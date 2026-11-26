"""The only PDF export uses run data and invalidates stale downloads."""

from contextlib import nullcontext

import pandas as pd
import pytest
import streamlit

from modules.reporting.summary_pdf import generate_summary_pdf, summary_sections
from modules.ui.summary_download import invalidate_summary_pdf, render_summary_download
from services.session_orchestrator import process_uploaded_session


def _run():
    raw = pd.DataFrame({"time": range(60), "pace": 300.0})
    frame, _, metrics, error = process_uploaded_session(raw, threshold_pace=300)
    assert error is None
    return frame, metrics


def test_summary_pdf_renders_missing_sensor_and_model_values_as_missing():
    frame, metrics = _run()
    sections = summary_sections(frame, metrics, runner_weight=72.0, threshold_pace=300.0)
    rows = dict(row for _, group in sections for row in group)
    for label in ("Średnie GAP", "Średnie tętno", "D′", "Tempo przy CS", "Maksymalny HSI z CORE"):
        assert rows[label] == "brak"
    assert rows["Tempo normalizowane (NP)"] == "5:00 min/km"
    assert rows["Masa biegacza"] == "72.0 kg"
    assert len([label for label in rows if label.startswith("Z")]) == 6
    assert not any(
        "ZGODNY" in item or "LT1" in item or "LT2" in item for row in rows.items() for item in row
    )
    pdf = generate_summary_pdf(frame, metrics, runner_weight=72.0, threshold_pace=300.0)
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")


@pytest.mark.parametrize(
    "new_key", [("other_hash", 72, 300), ("hash", 73, 300), ("hash", 72, 310), None]
)
def test_download_disappears_after_input_change(monkeypatch, new_key):
    frame, metrics = _run()
    state = {}
    downloads = []
    buttons = iter([True, False, False])
    monkeypatch.setattr(streamlit, "session_state", state)
    monkeypatch.setattr(streamlit, "expander", lambda *a, **k: nullcontext())
    monkeypatch.setattr(streamlit, "button", lambda *a, **k: next(buttons))
    monkeypatch.setattr(streamlit, "download_button", lambda *a, **k: downloads.append(k["data"]))
    key = ("hash", 72, 300)

    render_summary_download(frame, metrics, key)
    assert state["summary_pdf_key"] == key and len(downloads) == 1
    invalidate_summary_pdf(key)
    render_summary_download(frame, metrics, key)
    assert len(downloads) == 2

    invalidate_summary_pdf(new_key)
    if new_key is not None:
        render_summary_download(frame, metrics, new_key)
    assert len(downloads) == 2
    assert "summary_pdf_bytes" not in state and "summary_pdf_key" not in state
