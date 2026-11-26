"""
Frontend Layout Manager.

Handles the main application shell, sidebar, and high-level routing.
"""

from typing import Any, Tuple

import streamlit as st

from modules.config import Config


class AppLayout:
    """Main application layout and shell."""

    def render_sidebar(self) -> Tuple[Any, dict]:
        """Render the application sidebar.

        Returns:
            Tuple of (uploaded_file, user_params_dict)
        """
        st.sidebar.header("Ustawienia Biegacza")

        params = {}

        with st.sidebar.expander("⚙️ Parametry Podstawowe", expanded=True):
            params["runner_weight"] = st.number_input(
                "Waga [kg]",
                step=0.5,
                min_value=30.0,
                max_value=200.0,
                key="weight",
            )
            params["runner_height"] = st.number_input(
                "Wzrost [cm]",
                step=1,
                min_value=100,
                max_value=250,
                key="height",
            )
        with st.sidebar.expander("🏃 Parametry Progowe", expanded=True):
            params["threshold_pace"] = st.number_input(
                "Tempo Progowe [s/km]",
                min_value=120,
                max_value=600,
                help="Np. 3:53 min/km = 233s",
                key="threshold_pace",
            )
        with st.sidebar.expander("🫁 Wentylacja", expanded=False):
            params["vt1_vent"] = st.number_input(
                "VT1 [L/min]",
                min_value=0.0,
                key="vt1_v",
            )
            params["vt2_vent"] = st.number_input(
                "VT2 [L/min]",
                min_value=0.0,
                key="vt2_v",
            )

        uploaded_file = st.sidebar.file_uploader("Wgraj plik (CSV / TXT)", type=["csv", "txt"])

        return uploaded_file, params

    def render_header(self) -> None:
        """Render the main header."""
        st.title(f"{Config.APP_ICON} {Config.APP_TITLE}")
