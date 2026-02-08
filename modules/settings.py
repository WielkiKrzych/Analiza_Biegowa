import streamlit as st

SETTINGS_FILE = 'user_settings.json'

class SettingsManager:
    def __init__(self, file_path=SETTINGS_FILE):
        self.file_path = file_path
        self.default_settings = {
            "runner_weight": 95.0,
            "runner_height": 180,
            "runner_age": 30,
            "is_male": True,
            "threshold_pace": 230,
            "threshold_power": 0,
            "lthr": 170,
            "max_hr": 185,
            "critical_speed": 4.35,
            "vt1_vent": 71.0,
            "vt2_vent": 109.0,
            "preferred_cadence": 170,
            "target_stride_length": 0,
        }

    def load_settings(self):
        """Returns hardcoded default settings, ignoring any saved file to enforce user preferences."""
        # Always return defaults to ensure consistent startup state as requested
        return self.default_settings

    def save_settings(self, settings_dict):
        """Settings persistence is disabled to enforce hardcoded defaults."""
        # Intentionally do nothing
        return True

    def get_ui_values(self):
        """Pomocnik do pobierania wartości do UI (Session State lub Load)."""
        # Jeśli settings są już w session_state, użyj ich. Jak nie, wczytaj z pliku.
        if 'user_settings' not in st.session_state:
            st.session_state['user_settings'] = self.load_settings()
        return st.session_state['user_settings']

    def update_from_ui(self, key, value):
        """Callback do aktualizacji konkretnego ustawienia."""
        if 'user_settings' not in st.session_state:
             st.session_state['user_settings'] = self.load_settings()
        
        st.session_state['user_settings'][key] = value
        # Save is disabled, but we update session state
        # self.save_settings(st.session_state['user_settings'])
