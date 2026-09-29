"""
Frontend Theme Management.

Handles CSS loading and theme configuration.
"""

import os

import streamlit as st

from modules.config import Config


@st.cache_data(show_spinner=False)
def _read_css_file(css_path: str, mtime_ns: int, size: int) -> str:
    """Read CSS file contents. Cached per path so re-runs don't re-read
    the 12 KB file on every interaction.

    The cached value is the file's *contents*, so the key has to carry the
    file's identity too. `mtime_ns` and `size` are taken from the caller's
    `stat()` and are not used in the body — they exist purely so that editing
    `style.css` misses the cache. With a path-only key and no TTL the first
    read of a session was also the last one, and a CSS edit stayed invisible
    until the Streamlit process was restarted.
    """
    with open(css_path) as f:
        return f.read()


class ThemeManager:
    """Manages application theme and styling."""

    @staticmethod
    def load_css() -> None:
        """Load global CSS from configured file.

        P2-7 (audit v2): the previous version read `style.css` (12.2 KB)
        from disk on every Streamlit re-run. Now wrapped in
        `@st.cache_data` so the file is read once per path; the markdown
        injection still runs every time (Streamlit needs the `<style>`
        tag on every re-render).
        """
        css_file = Config.CSS_FILE
        try:
            css_stat = os.stat(css_file)
            css = _read_css_file(css_file, css_stat.st_mtime_ns, css_stat.st_size)
        except (FileNotFoundError, OSError, UnicodeDecodeError) as e:
            st.error(f"Failed to load CSS: {e}")
            return
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    @staticmethod
    def set_page_config() -> None:
        """Apply Streamlit page configuration."""
        st.set_page_config(
            page_title=Config.APP_TITLE, layout=Config.APP_LAYOUT, page_icon=Config.APP_ICON
        )
