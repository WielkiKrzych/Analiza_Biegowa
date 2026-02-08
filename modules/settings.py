import streamlit as st

SETTINGS_FILE = 'user_settings.json'

class SettingsManager:
    def __init__(self, file_path=SETTINGS_FILE):
        self.file_path = file_path
        self.default_settings = {
            # Athlete basic data
            "runner_weight": 75.0,     # kg
            "runner_height": 175,      # cm
            "runner_age": 30,
            "is_male": True,
            
            # Running performance metrics
            "threshold_pace": 300,     # seconds per km (5:00 min/km)
            "threshold_power": 0,      # Watts (optional, for runners with power meter)
            "lthr": 170,               # Lactate Threshold Heart Rate (bpm)
            "max_hr": 185,             # Maximum Heart Rate (bpm)
            "critical_speed": 3.33,    # m/s (equivalent to 5:00 min/km)
            
            # Thresholds from ventilatory markers
            "vt1_vent": 71.0,          # L/min
            "vt2_vent": 109.0,         # L/min
            
            # Running form preferences
            "preferred_cadence": 170,  # SPM (steps per minute)
            "target_stride_length": 0, # 0 = auto-calculate from height
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
