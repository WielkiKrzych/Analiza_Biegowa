"""Ventilation analysis UI — thin re-export wrapper.

This module provides backward-compatible access to all ventilation UI functions.
Code has been split into focused sub-modules for maintainability.
"""

from modules.ui.vent_br_only import _render_br_only_section  # noqa: F401
from modules.ui.vent_charts import (  # noqa: F401
    _render_br_section,
    _render_tidal_volume_section,
    _render_ve_section,
)
from modules.ui.vent_legacy import _render_legacy_tools  # noqa: F401
from modules.ui.vent_tab import render_vent_tab  # noqa: F401
from modules.ui.vent_utils import _format_time, _parse_time_to_seconds  # noqa: F401

__all__ = [
    "render_vent_tab",
    "_render_br_only_section",
    "_render_ve_section",
    "_render_br_section",
    "_render_tidal_volume_section",
    "_render_legacy_tools",
    "_parse_time_to_seconds",
    "_format_time",
]
