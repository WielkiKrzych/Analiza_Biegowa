"""
Persistence loading and git tracking.

Functions for loading saved reports and checking git safety.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Union

from .persistence_constants import CANONICAL_VERSION, METHOD_VERSION

logger = logging.getLogger(__name__)


def _warn_on_version_mismatch(report: Dict, file_path: Union[str, Path]) -> None:
    """Reject a file that is not a report, then warn about version mismatches.

    A version mismatch is only logged — never raised — so older reports stay
    readable.

    Raises:
        ValueError: if the file's top level is not a JSON object — a list or a scalar
            would otherwise fail later on ``AttributeError``, which says nothing to
            the user about what is wrong with the file.
    """
    if not isinstance(report, dict):
        raise ValueError(
            f"Plik {file_path} nie jest raportem Ramp Test: oczekiwano obiektu JSON, "
            f"otrzymano {type(report).__name__}."
        )

    version = report.get("version")
    if version != CANONICAL_VERSION:
        logger.warning(
            f"Report {file_path} declares canonical version {version!r}, but this build "
            f"writes {CANONICAL_VERSION!r}; some fields may be missing or renamed."
        )

    metadata = report.get("metadata") or {}
    method_version = metadata.get("method_version")
    if method_version and method_version != METHOD_VERSION:
        logger.warning(
            f"Report {file_path} was analysed with method version {method_version!r}, "
            f"this build runs {METHOD_VERSION!r}; its numbers are not directly comparable."
        )


def load_ramp_test_report(file_path: Union[str, Path]) -> Dict:
    """
    Load a Ramp Test report from JSON.

    Reports written by an older release stay readable: a version mismatch is
    logged, not raised.

    Args:
        file_path: Path to JSON file

    Returns:
        Dictionary with report data
    """
    with open(file_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    _warn_on_version_mismatch(report, file_path)
    return report


def check_git_tracking(directory: str = "reports/ramp_tests"):
    """
    Check if a directory contains any files tracked by git.
    Display a warning in Streamlit if tracked files are found.

    This is a safeguard against accidental committing of sensitive subject data.
    """
    import streamlit as st

    # Only check in local development environment (could verify env vars but simple check is enough)
    if not os.path.exists(".git"):
        return

    try:
        # Check if any files in the directory are tracked
        # git ls-files returns output if files are tracked
        result = subprocess.run(
            ["git", "ls-files", directory], capture_output=True, text=True, check=False
        )

        if result.returncode == 0 and result.stdout.strip():
            # Tracked files found!
            st.error(
                f"🚨 **SECURITY WARNING**: Folder `{directory}` zawiera pliki śledzone przez Git!\n\n"
                "Dane badanych mogą trafić do repozytorium. "
                "Usuń je z historii gita:\n"
                "```bash\n"
                f"git rm --cached -r {directory}\n"
                "```"
            )

    except (OSError, subprocess.SubprocessError) as e:
        # The privacy check could not run. Staying silent here would tell the user
        # their data is safe when nobody actually looked, so leave a trace — in the
        # log and, because it is subject data, in the interface the user actually sees.
        logger.warning(
            f"Could not check whether '{directory}' is tracked by git ({e}); "
            "the subject-data privacy check did not run."
        )
        st.warning(
            f"⚠️ Nie udało się sprawdzić, czy dane zawodnika w `{directory}` są śledzone "
            f"przez gita ({e}). Kontrola prywatności nie została wykonana — sprawdź to ręcznie."
        )
