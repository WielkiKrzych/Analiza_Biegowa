import logging
import os
import subprocess
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)


@st.cache_data(ttl=300, show_spinner=False)
def _has_tracked_paths(repo: str, directory: str) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--", directory],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args)
    return bool(result.stdout.strip())


def check_git_tracking(directory: str = "reports/ramp_tests") -> None:
    """Warn when a local data directory is tracked or the check fails."""
    repo = os.getcwd()
    if not (Path(repo) / ".git").exists():
        return

    try:
        if _has_tracked_paths(repo, directory):
            st.error(
                f"🚨 **SECURITY WARNING**: Folder `{directory}` zawiera pliki śledzone przez Git!"
            )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning(
            "Could not check whether '%s' is tracked by git (%s); "
            "the subject-data privacy check did not run.",
            directory,
            exc,
        )
        st.warning(
            f"⚠️ Nie udało się sprawdzić, czy dane zawodnika w `{directory}` są śledzone "
            "przez gita. Kontrola prywatności nie została wykonana."
        )
