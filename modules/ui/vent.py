"""Ventilation analysis UI — thin re-export wrapper.

This module provides backward-compatible access to all ventilation UI functions.
Code has been split into focused sub-modules for maintainability.
"""

from modules.ui.vent_tab import render_vent_tab  # noqa: F401

# Only the tab entry point is reachable through this module: `app.py` looks it
# up by name via `importlib`. The other helpers that used to be re-exported here
# had no caller — `vent_tab` and `vent_charts` import them straight from
# `vent_br_only` / `vent_charts` / `vent_legacy` / `vent_utils`.
__all__ = ["render_vent_tab"]
