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
        st.sidebar.header("Ustawienia Zawodnika")
        
        params = {}
        
        with st.sidebar.expander("⚙️ Parametry Biegowe", expanded=True):
            params['runner_weight'] = st.number_input(
                "Waga Biegacza [kg]", step=0.5, min_value=30.0, max_value=200.0, 
                key="weight", on_change=self.state.save_settings_callback
            )
            params['runner_height'] = st.number_input(
                "Wzrost [cm]", step=1, min_value=100, max_value=250, 
                key="height", on_change=self.state.save_settings_callback
            )
            params['runner_age'] = st.number_input(
                "Wiek [lata]", step=1, min_value=10, max_value=100, 
                key="age", on_change=self.state.save_settings_callback
            )
            params['is_male'] = st.checkbox(
                "Mężczyzna?", key="gender_m", on_change=self.state.save_settings_callback
            )
            
            st.markdown("---")
            st.markdown("### 🏃 Tempo Progowe")
            params['threshold_pace'] = st.number_input(
                "Tempo Progowe [s/km]", min_value=120, max_value=600, value=300,
                help="5:00 min/km = 300s",
                key="threshold_pace", on_change=self.state.save_settings_callback
            )
            params['d_prime'] = st.number_input(
                "D' (Pojemność Anaerobowa) [m]", min_value=0, max_value=1000, value=200,
                key="d_prime", on_change=self.state.save_settings_callback
            )
            st.divider()

            st.markdown("### 🫁 Wentylacja [L/min]")
            params['vt1_vent'] = st.number_input(
                "VT1 (Próg Tlenowy) [L/min]", min_value=0.0, 
                key="vt1_v", on_change=self.state.save_settings_callback
            )
            params['vt2_vent'] = st.number_input(
                "VT2 (Próg Beztlenowy) [L/min]", min_value=0.0, 
                key="vt2_v", on_change=self.state.save_settings_callback
            )

        st.sidebar.divider()
        st.sidebar.markdown("### ⚡ Parametry Legacy (Kolarstwo)")
        params['cp'] = st.sidebar.number_input(
            "Moc Krytyczna (CP) [W]", min_value=1, value=280,
            key="cp_in", on_change=self.state.save_settings_callback
        )
        params['w_prime'] = st.sidebar.number_input(
            "W' [J]", min_value=0, value=20000,
            key="wp_in", on_change=self.state.save_settings_callback
        )
        uploaded_file = st.sidebar.file_uploader("Wgraj plik (CSV / TXT)", type=['csv', 'txt'])
            
        return uploaded_file, params

    def render_header(self) -> None:
        """Render the main header."""
        st.title(f"{Config.APP_ICON} {Config.APP_TITLE}")

    def render_export_section(self, uploaded_file, data_bundle) -> None:
        """Render the export section in sidebar."""
        # Logic extracted from app.py
        # Passed data_bundle is a dict of whatever is needed for export
        if not uploaded_file:
            return
            
        st.sidebar.markdown("---")
        st.sidebar.header("📄 Export Raportu")
        
        # NOTE: This part requires importing report functions. 
        # To keep layout decoupled, better to pass a callback or specific UI renderer.
        # For now, let's keep it minimal and assume app.py handles the actual button logic 
        # OR we import specifically here.
        pass # Leaving empty to avoid circular imports. Best handled in app.py or dedicated logic.
