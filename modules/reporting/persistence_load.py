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

logger = logging.getLogger(__name__)


def load_ramp_test_report(file_path: Union[str, Path]) -> Dict:
    """
    Load a Ramp Test report from JSON.

    Args:
        file_path: Path to JSON file

    Returns:
        Dictionary with report data
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


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

    except Exception:
        # Git command failed or not available - ignore
        pass
