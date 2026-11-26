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
            "age": Config.DEFAULT_RUNNER_AGE_YEARS,
            "gender_m": Config.DEFAULT_IS_MALE,
            "threshold_pace": Config.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
            "lthr": Config.DEFAULT_LTHR_BPM,
            "max_hr": Config.DEFAULT_MAX_HR_BPM,
            "vt1_v": 0.0,
            "vt2_v": 0.0,
        }

        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

        if "report_generation_requested" not in st.session_state:
            st.session_state["report_generation_requested"] = False

    def cleanup_old_data(self) -> None:
        """Clean up old DataFrames from session state."""
        keys_to_Check = ["_prev_df_plot", "_prev_df_resampled", "_prev_file_name", "data_loaded"]
        for key in keys_to_Check:
            if key in st.session_state:
                del st.session_state[key]

    def set_data_loaded(self) -> None:
        st.session_state["data_loaded"] = True

    def is_data_loaded(self) -> bool:
        return st.session_state.get("data_loaded", False)


def clear_file_selections() -> None:
    """Reset file-specific ranges and widgets when the upload changes."""
    for channel in ("smo2", "vent", "br", "tv"):
        for suffix in ("start_sec", "end_sec", "manual_start", "manual_end", "chart"):
            st.session_state.pop(f"{channel}_{suffix}", None)
