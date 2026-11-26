"""
Frontend State Management.

Centralized state manager to handle Session State with type safety.
"""

import streamlit as st

from modules.config import Config


class StateManager:
    """Manages application state and settings."""

    def init_session_state(self) -> None:
        """Seed defaults once so sidebar input survives reruns."""
        defaults = {
            "weight": Config.DEFAULT_BODY_WEIGHT_KG,
            "height": Config.DEFAULT_RUNNER_HEIGHT_CM,
            "threshold_pace": Config.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
            "vt1_v": 0.0,
            "vt2_v": 0.0,
        }

        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value


def clear_file_selections() -> None:
    """Reset file-specific ranges and widgets when the upload changes."""
    for key in ("df_dfa", "dfa_error", "thb_chart", "hr_start_sec", "hr_end_sec"):
        st.session_state.pop(key, None)
    for channel in ("smo2", "vent", "br", "tv"):
        for suffix in ("start_sec", "end_sec", "manual_start", "manual_end", "chart"):
            st.session_state.pop(f"{channel}_{suffix}", None)
