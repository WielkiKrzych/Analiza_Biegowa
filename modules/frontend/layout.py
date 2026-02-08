"""
Frontend Layout Manager.

Handles the main application shell, sidebar, and high-level routing.
"""
import streamlit as st
from typing import Tuple, Any

from modules.config import Config
from .state import StateManager

class AppLayout:
    """Main application layout and shell."""

    def __init__(self, state_manager: StateManager):
        self.state = state_manager

    def render_sidebar(self) -> Tuple[Any, dict]:
        """Render the application sidebar.
        
        Returns:
            Tuple of (uploaded_file, user_params_dict)
        """
        st.sidebar.header("Ustawienia Biegacza")
        
        params = {}
        
        with st.sidebar.expander("⚙️ Parametry Podstawowe", expanded=True):
            params['runner_weight'] = st.number_input(
                "Waga [kg]", step=0.5, min_value=30.0, max_value=200.0, value=95.0,
                key="weight", on_change=self.state.save_settings_callback
            )
            params['runner_height'] = st.number_input(
                "Wzrost [cm]", step=1, min_value=100, max_value=250, value=180,
                key="height", on_change=self.state.save_settings_callback
            )
            params['runner_age'] = st.number_input(
                "Wiek [lata]", step=1, min_value=10, max_value=100, value=30,
                key="age", on_change=self.state.save_settings_callback
            )
            params['is_male'] = st.checkbox(
                "Mężczyzna?", value=True, key="gender_m", on_change=self.state.save_settings_callback
            )
        
        with st.sidebar.expander("🏃 Parametry Progowe", expanded=True):
            params['threshold_pace'] = st.number_input(
                "Tempo Progowe [s/km]", min_value=120, max_value=600, value=230,
                help="3:50 min/km = 230s",
                key="threshold_pace", on_change=self.state.save_settings_callback
            )
            params['lthr'] = st.number_input(
                "LTHR (Tętno Progowe) [bpm]", min_value=100, max_value=200, value=170,
                key="lthr", on_change=self.state.save_settings_callback
            )
            params['threshold_power'] = st.number_input(
                "Threshold Power [W]", min_value=0, max_value=500, value=0,
                help="Dla biegaczy z czujnikiem mocy (opcjonalnie)",
                key="threshold_power", on_change=self.state.save_settings_callback
            )
            params['max_hr'] = st.number_input(
                "MaxHR [bpm]", min_value=120, max_value=220, value=185,
                key="max_hr", on_change=self.state.save_settings_callback
            )
        
        with st.sidebar.expander("🫁 Wentylacja", expanded=False):
            params['vt1_vent'] = st.number_input(
                "VT1 [L/min]", min_value=0.0, value=0.0,
                key="vt1_v", on_change=self.state.save_settings_callback
            )
            params['vt2_vent'] = st.number_input(
                "VT2 [L/min]", min_value=0.0, value=0.0,
                key="vt2_v", on_change=self.state.save_settings_callback
            )

        uploaded_file = st.sidebar.file_uploader("Wgraj plik (CSV / TXT)", type=['csv', 'txt'])
            
        return uploaded_file, params

    def render_header(self) -> None:
        """Render the main header."""
        st.title(f"{Config.APP_ICON} {Config.APP_TITLE}")

    def render_export_section(self, uploaded_file, data_bundle) -> None:
        """Render the export section in sidebar."""
        if not uploaded_file:
            return
            
        st.sidebar.markdown("---")
        st.sidebar.header("📄 Export Raportu")
        pass
