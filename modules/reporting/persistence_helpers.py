"""
Persistence helpers — utilities for saving ramp test reports.

Includes NumpyEncoder for JSON serialization, limiter interpretation,
and source file deduplication checks.
"""

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def _get_limiter_interpretation(limiting_factor: str) -> dict:
    """Get interpretation text for limiting factor."""
    interpretations = {
        "Serce": {
            "title": "Ograniczenie Centralne (Serce)",
            "description": "Twoje serce pracuje na maksymalnych obrotach, ale mięśnie mogłyby więcej.",
            "suggestions": [
                "Więcej treningu Z2 (podniesienie SV - objętości wyrzutowej)",
                "Interwały 4×8 min @ 88-94% HRmax",
                "Rozważ pracę nad VO₂max (Hill Repeats)",
            ],
        },
        "Płuca": {
            "title": "Ograniczenie Oddechowe (Płuca)",
            "description": "Wentylacja jest na limicie.",
            "suggestions": [
                "Ćwiczenia oddechowe (pranayama, Wim Hof)",
                "Trening na wysokości (lub maska hipoksyjna)",
                "Sprawdź technikę oddychania podczas wysiłku",
            ],
        },
        "Mięśnie": {
            "title": "Ograniczenie Peryferyjne (Mięśnie)",
            "description": "Mięśnie zużywają cały dostarczany tlen.",
            "suggestions": [
                "Więcej pracy siłowej (squat, deadlift)",
                "Interwały 'over-under' (93-97% / 103-107% FTP)",
                "Sprawdź pozycję na rowerze (okluzja mechaniczna?)",
            ],
        },
    }
    return interpretations.get(limiting_factor, interpretations["Serce"])


def _check_source_file_exists(base_dir: str, source_file: str) -> bool:
    """
    Check if a source file has already been saved in the index.

    Used for deduplication - prevents saving multiple reports for the same CSV file.

    Args:
        base_dir: Base directory containing index.csv
        source_file: Filename to check (e.g., 'ramp_test_2026-01-03.csv')

    Returns:
        True if source_file already exists in index, False otherwise
    """
    import csv

    index_path = Path(base_dir) / "index.csv"

    if not index_path.exists():
        return False

    try:
        with open(index_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_source = row.get("source_file", "")
                if existing_source and existing_source == source_file:
                    return True
    except (OSError, csv.Error) as e:
        logger.warning(f"Failed to check deduplication: {e}")
        return False

    return False


class NumpyEncoder(json.JSONEncoder):
    """Custom encoder for NumPy data types."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)

        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)
