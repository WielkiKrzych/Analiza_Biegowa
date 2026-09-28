"""Regression tests for the PDF reporting review (package w3).

Guards two defects found in the thermal PDF path:
1. ``builder._build_pdf_story`` called ``build_page_thermal`` with a keyword the
   function does not accept, so the whole PDF story build raised TypeError.
2. ``build_page_thermal`` read flat keys (``core_temp_max``, ``heat_strain_index``,
   ...) that no producer ever writes, so every card printed 0.0 with a reassuring
   "normal" label even when the source file had no core-temperature column.
"""

import pytest
from reportlab.platypus import Paragraph, Spacer, Table

from modules.calculations.thermoregulation import ThermoProfile, format_thermo_for_report
from modules.reporting.pdf.layout import build_page_thermal
from modules.reporting.pdf.styles import create_styles


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
        elif isinstance(el, Spacer):
            continue
    return "\n".join(p for p in parts if p)


def _canonical_thermo() -> dict:
    """Built by the real producer, so the test cannot drift from the schema.

    A hand-written fixture previously used heat_tolerance="Umiarkowana", a value
    `_classify_tolerance` never returns — it masked the fact that the raw English
    token reached the PDF.
    """
    return format_thermo_for_report(
        ThermoProfile(
            max_core_temp=38.94,
            min_core_temp=37.21,
            delta_core_temp=1.73,
            delta_per_10min=0.42,
            peak_hsi=4.6,
            mean_hsi=3.1,
            heat_tolerance="moderate",
            classification_color="#F39C12",
            data_points=900,
            confidence=0.8,
        )
    )


CANONICAL_THERMO = _canonical_thermo()


def test_thermal_page_shows_placeholder_when_no_core_temperature_column():
    """A file without core-temperature data must say so, not print zeros."""
    text = _page_text(build_page_thermal(thermal_data={}, figure_paths={}, styles=create_styles()))

    assert "Brak danych o termoregulacji" in text
    assert "0.0" not in text
    assert "Niski" not in text


def test_thermal_page_renders_measurements_from_canonical_metrics():
    """Values stored by format_thermo_for_report must reach the cards."""
    text = _page_text(
        build_page_thermal(
            thermal_data=CANONICAL_THERMO, figure_paths={}, styles=create_styles()
        )
    )

    assert "38.9" in text  # max_core_temp
    assert "37.2" in text  # min_core_temp
    assert "4.6" in text  # peak_hsi
    assert "0.42" in text  # delta_per_10min
    # The producer stores the token "moderate"; the report must show the Polish label.
    assert "Umiarkowana" in text
    assert "moderate" not in text


def test_thermal_page_marks_missing_metrics_without_crashing():
    """Partial metrics must degrade to 'brak danych' instead of raising."""
    partial = {"metrics": {"max_core_temp": None, "peak_hsi": None}, "classification": {}}
    text = _page_text(build_page_thermal(thermal_data=partial, figure_paths={}, styles=create_styles()))

    assert "brak danych" in text
    assert "Brak danych" in text


def test_build_ramp_pdf_accepts_the_kwargs_the_builder_passes():
    """The story builder must be able to call the thermal page (keyword mismatch
    previously raised TypeError and aborted the whole PDF)."""
    from modules.reporting.pdf.builder import _build_pdf_story, map_ramp_json_to_pdf_data
    from modules.reporting.pdf.styles import PDFConfig

    pdf_data = map_ramp_json_to_pdf_data(
        {"metadata": {}, "metrics": {}, "thermo_analysis": CANONICAL_THERMO}
    )

    story = _build_pdf_story(pdf_data, {}, create_styles(), PDFConfig(), compact_mode=True)

    assert story


@pytest.mark.parametrize("thermo", [{}, CANONICAL_THERMO])
def test_thermal_page_returns_flowables(thermo):
    elements = build_page_thermal(
        thermal_data=thermo, figure_paths={}, styles=create_styles()
    )
    assert elements


# ---------------------------------------------------------------------------
# Limitations page (section 5)
# ---------------------------------------------------------------------------


def test_limitations_page_lists_conditional_caveats():
    """A CONDITIONAL test must print its caveats, not "no limitations".

    Regression: no producer ever wrote pdf_data["limitations"], so the page
    claimed a clean bill of health for every report.
    """
    from modules.reporting.pdf.builder import map_ramp_json_to_pdf_data
    from modules.reporting.pdf.layout import build_page_limitations

    pdf_data = map_ramp_json_to_pdf_data(
        {
            "metadata": {},
            "metrics": {},
            "test_validity": {
                "status": "conditional",
                "issues": ["Rampa za krótka (6:10 < 8:00)"],
            },
            "interpretation": {"warnings": ["Brak danych SmO2"]},
        }
    )

    text = _page_text(
        build_page_limitations(limitations_data=pdf_data["limitations"], styles=create_styles())
    )

    assert "Brak zidentyfikowanych ograniczeń" not in text
    assert "zastrzeżeniami" in text
    assert "Rampa za krótka (6:10 < 8:00)" in text
    assert "Brak danych SmO2" in text


def test_limitations_page_stays_empty_for_a_clean_valid_test():
    """No issues means the "none identified" message is the truth, not a default."""
    from modules.reporting.pdf.builder import map_ramp_json_to_pdf_data
    from modules.reporting.pdf.layout import build_page_limitations

    pdf_data = map_ramp_json_to_pdf_data(
        {"metadata": {}, "metrics": {}, "test_validity": {"status": "valid", "issues": []}}
    )

    text = _page_text(
        build_page_limitations(limitations_data=pdf_data["limitations"], styles=create_styles())
    )

    assert "Brak zidentyfikowanych ograniczeń" in text
