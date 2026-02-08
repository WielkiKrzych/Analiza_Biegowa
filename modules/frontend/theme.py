"""
Frontend Theme Management.

Handles CSS loading and theme configuration.
"""
import streamlit as st
from modules.config import Config

class ThemeManager:
    """Manages application theme and styling."""

    @staticmethod
    def load_css() -> None:
        """Load global CSS from configured file."""
        css_file = Config.CSS_FILE
        try:
            with open(css_file) as f:
                st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Failed to load CSS: {e}")

    @staticmethod
    def set_page_config() -> None:
        """Apply Streamlit page configuration."""
        st.set_page_config(
            page_title=Config.APP_TITLE,
            layout=Config.APP_LAYOUT,
            page_icon=Config.APP_ICON
        )
