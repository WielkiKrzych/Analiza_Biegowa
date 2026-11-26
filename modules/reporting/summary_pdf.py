"""Build the single running-session PDF from the same values used on screen."""

from functools import lru_cache
from io import BytesIO
from math import isfinite
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from modules.calculations.pace import fit_critical_speed_from_pdc
from modules.calculations.pace_utils import format_pace


def _pace(value: float | None) -> str:
    return f"{format_pace(value)} min/km" if value and isfinite(value) else "brak"


def _number(value: float | None, pattern: str) -> str:
    return pattern.format(value) if value is not None and isfinite(value) else "brak"


def summary_sections(
    df: pd.DataFrame, metrics: dict[str, Any], runner_weight: float, threshold_pace: float
) -> list[tuple[str, list[tuple[str, str]]]]:
    fit = fit_critical_speed_from_pdc(df)
    valid_fit = fit["is_valid"]
    hsi = metrics.get("heat_strain")
    return [
        (
            "Tempo i obciążenie",
            [
                ("Czas sesji", _number(metrics.get("duration_sec"), "{:.0f} s")),
                ("Dystans", _number(metrics.get("distance_km"), "{:.2f} km")),
                ("Średnie tempo w ruchu", _pace(metrics.get("avg_pace"))),
                ("Średnie GAP", _pace(metrics.get("avg_gap"))),
                ("Tempo normalizowane (NP)", _pace(metrics.get("normalized_pace"))),
                ("Running Stress Score (RSS)", _number(metrics.get("rss"), "{:.1f} pkt")),
                ("Tempo progowe", _pace(threshold_pace)),
                ("Masa biegacza", _number(runner_weight, "{:.1f} kg")),
            ],
        ),
        (
            "Pomiary w trakcie biegu",
            [
                ("Średnie tętno", _number(metrics.get("avg_hr"), "{:.0f} bpm")),
                ("Maksymalne tętno", _number(metrics.get("max_hr"), "{:.0f} bpm")),
                ("Średnia kadencja", _number(metrics.get("avg_cadence"), "{:.0f} spm")),
                ("Średnia wentylacja", _number(metrics.get("avg_vent"), "{:.1f} L/min")),
                ("Średnia częstość oddechów", _number(metrics.get("avg_rr"), "{:.1f} /min")),
                ("Średnie SmO₂", _number(metrics.get("avg_smo2"), "{:.1f}%")),
                ("Średnia temperatura centralna", _number(metrics.get("avg_core"), "{:.2f} °C")),
                ("Maksymalny HSI z CORE", _number(hsi["peak"] if hsi else None, "{:.1f}")),
            ],
        ),
        (
            "Model prędkości krytycznej",
            [
                ("Tempo przy CS", _pace(fit["cs_pace_s_km"] if valid_fit else None)),
                ("D′", _number(fit["d_prime_m"] if valid_fit else None, "{:.0f} m")),
                ("R² modelu", _number(fit["r_squared"] if valid_fit else None, "{:.3f}")),
            ],
        ),
        (
            "Strefy tempa",
            [
                (label, f"{seconds // 60}:{seconds % 60:02d}")
                for label, seconds in metrics.get("pace_zones", {}).items()
            ],
        ),
    ]


@lru_cache(maxsize=1)
def _font() -> str:
    name = "DejaVu Sans Running"
    registerFont(TTFont(name, str(Path(__file__).with_name("DejaVuSans.ttf"))))
    return name


def generate_summary_pdf(
    df: pd.DataFrame, metrics: dict[str, Any], runner_weight: float, threshold_pace: float
) -> bytes:
    stream = BytesIO()
    width, height = A4
    pdf = Canvas(stream, pagesize=A4)
    pdf.setTitle("Podsumowanie biegu")
    font = _font()

    pdf.setFillColor(HexColor("#102d3b"))
    pdf.rect(0, height - 102, width, 102, stroke=0, fill=1)
    pdf.setFillColor(HexColor("#b5ded7"))
    pdf.setFont(font, 9)
    pdf.drawString(46, height - 44, "ANALIZA BIEGOWA")
    pdf.setFillColor(HexColor("#ffffff"))
    pdf.setFont(font, 23)
    pdf.drawString(46, height - 76, "Podsumowanie biegu")

    y = height - 131
    for title, rows in summary_sections(df, metrics, runner_weight, threshold_pace):
        pdf.setFillColor(HexColor("#166052"))
        pdf.setFont(font, 12)
        pdf.drawString(46, y, title)
        pdf.setFont(font, 9)
        for label, value in rows:
            y -= 17
            pdf.setStrokeColor(HexColor("#e3ebed"))
            pdf.line(46, y - 5, width - 46, y - 5)
            pdf.setFillColor(HexColor("#203642"))
            pdf.drawString(46, y, label)
            pdf.drawRightString(width - 46, y, value)
        y -= 29

    pdf.setFillColor(HexColor("#526771"))
    pdf.setFont(font, 8)
    pdf.drawString(46, 42, "Czas stref podano w min:s. W strefie Z1 uwzględniono postoje.")
    pdf.showPage()
    pdf.save()
    return stream.getvalue()
