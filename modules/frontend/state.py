"""
Frontend State Management.

Centralized state manager to handle Session State with type safety.
"""
import streamlit as st
from modules.settings import SettingsManager

class StateManager:
    """Manages application state and settings."""
    
    def __init__(self):
        self.settings_manager = SettingsManager()
        self._keys_map = {
            "weight": "rider_weight",
            "height": "rider_height", 
            "age": "rider_age",
            "gender_m": "is_male",
            "vt1_w": "vt1_watts",
            "vt2_w": "vt2_watts",
            "vt1_v": "vt1_vent",
            "vt2_v": "vt2_vent",
            "cp_in": "cp",
            "wp_in": "w_prime",
            "crank": "crank_length"
        }

    def init_session_state(self) -> None:
        """Initialize session state from saved settings if needed."""
        saved_settings = self.settings_manager.load_settings()
        
        for ui_key, json_key in self._keys_map.items():
            if ui_key not in st.session_state:
                st.session_state[ui_key] = saved_settings.get(json_key)
        
        if 'report_generation_requested' not in st.session_state:
            st.session_state['report_generation_requested'] = False

    def save_settings_callback(self) -> None:
        """Callback to save current UI values to persistence."""
        current_values = {}
        for ui_key, json_key in self._keys_map.items():
            if ui_key in st.session_state:
                current_values[json_key] = st.session_state[ui_key]
        self.settings_manager.save_settings(current_values)

    def cleanup_old_data(self) -> None:
        """Clean up old DataFrames from session state."""
        keys_to_Check = ['_prev_df_plot', '_prev_df_resampled', '_prev_file_name', 'data_loaded']
        for key in keys_to_Check:
            if key in st.session_state:
                del st.session_state[key]
                
    def set_data_loaded(self) -> None:
        st.session_state['data_loaded'] = True
        
    def is_data_loaded(self) -> bool:
        return st.session_state.get('data_loaded', False)
