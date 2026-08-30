"""
Dashboard Renderer Service.

P1-4 (audit v2): the original `app.py` mixed routing, header rendering,
metrics, auto-save, and the processing pipeline in a single 435-line file.
This module owns the per-session dashboard rendering so `app.py` can
focus on routing and top-level layout.

The functions here are thin wrappers around the existing services
(`session_orchestrator`, `session_store`, `layout`); they exist to give
`app.py` a clean entry point and to make each phase independently testable
and importable.

The functions DO NOT initialize Streamlit (no `st.set_page_config`), they
only render into the current Streamlit session.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from modules.calculations.dual_mode import (
    calculate_normalized_pace,
    calculate_running_stress_score,
)
from modules.calculations.pace_utils import format_pace
from modules.db import SessionRecord, SessionStore
from modules.domain import classify_session_type
from modules.frontend.components import UIComponents
from modules.utils import load_data, validate_data_completeness
from services import prepare_session_record, prepare_sticky_header_data
from services.session_orchestrator import process_uploaded_session

logger = logging.getLogger(__name__)


def process_and_cache_session(
    uploaded_file: Any,
    runner_weight: float,
    state: Any,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
    """Load, classify, validate and process the uploaded file.

    Results are cached in `st.session_state` so the same file isn't
    re-processed on every Streamlit re-run. The cache key is the MD5 of
    the file content (not the filename), so a re-upload of the same
    content is also cached.

    Returns:
        (df_plot, df_plot_resampled, metrics) or (None, None, None) on error.

    Raises:
        st.stop() is called by Streamlit on validation error — this
        function therefore never returns None silently for user-facing
        validation errors.
    """
    with st.spinner("Przetwarzanie danych..."):
        try:
            df_raw = load_data(uploaded_file)

            # --- SESSION TYPE CLASSIFICATION (must run first) ---
            uploaded_file.seek(0)
            file_content = uploaded_file.read()
            uploaded_file.seek(0)
            current_file_hash = hashlib.md5(file_content).hexdigest()
            cached_hash = st.session_state.get("current_file_hash")

            if cached_hash != current_file_hash:
                session_type = classify_session_type(df_raw, uploaded_file.name)
                st.session_state["session_type"] = session_type
                st.session_state["current_file_hash"] = current_file_hash
                ramp_classification = None
                if "watts" in df_raw.columns or "power" in df_raw.columns:
                    power_col = "watts" if "watts" in df_raw.columns else "power"
                    power = df_raw[power_col].dropna()
                    if len(power) >= 300:
                        from modules.domain import classify_ramp_test

                        ramp_classification = classify_ramp_test(power)
                        st.session_state["ramp_classification"] = ramp_classification
            # else: reuse cached session_type / ramp_classification from session_state

            # --- DATA QUALITY VALIDATION ---
            quality_report = validate_data_completeness(df_raw)
            st.session_state["data_quality_report"] = quality_report
            st.session_state["sport_type"] = quality_report.sport_type

            # --- PROCESSING PIPELINE (SRP/DIP) ---
            df_plot, df_plot_resampled, metrics, error_msg = process_uploaded_session(
                df_raw, rider_weight=runner_weight, vt1_watts=0, vt2_watts=0
            )

            if error_msg:
                st.error(f"Błąd analizy: {error_msg}")
                st.stop()

            if metrics.get("power_is_estimated"):
                st.info(
                    "🏃 **Tryb biegowy (tempo + HR):** brak miernika mocy, więc intensywność "
                    "liczona jest z **tempa/GAP** (moc w watach w zakładkach to wartość *szacowana* "
                    "z tempa, nie pomiar). Analizy progów, obciążenia i limiterów bazują na "
                    "Twoim tempie i tętnie."
                )

            state.set_data_loaded()
            return df_plot, df_plot_resampled, metrics

        except (ValueError, TypeError, KeyError, OSError) as e:
            st.error(f"Błąd wczytywania pliku: {e}")
            st.stop()
            return None, None, None  # unreachable, keeps type-checker happy


def auto_save_session(
    uploaded_file: Any,
    df_plot: pd.DataFrame,
    metrics: Dict[str, Any],
    np_header: float,
) -> None:
    """Persist the current session to the SQLite store.

    Failures (e.g. disk full, lock contention) are logged but do NOT block
    rendering — auto-save is a nice-to-have, not a contract.
    """
    try:
        session_data = prepare_session_record(
            uploaded_file.name,
            df_plot,
            metrics,
            np_header,
            if_header=0.0,
            tss_header=0.0,
        )
        SessionStore().add_session(SessionRecord(**session_data))
    except (sqlite3.Error, ValueError, KeyError) as exc:  # noqa: BLE001
        logger.warning("Auto-save failed: %s", exc)


def render_header_and_metrics(
    df_plot: pd.DataFrame,
    metrics: Dict[str, Any],
    threshold_pace_input: float,
) -> float:
    """Render the sticky header (auto-save + UI) and the 3-metric bar (NP/RSS/Distance).

    Returns the calculated Normalized Pace so the caller can reuse it.
    """
    # --- Auto-save (P1-4: was inline; now in its own function above) ---
    np_header = calculate_normalized_pace(df_plot)
    # We can't auto_save here without the uploaded_file handle — the caller
    # is expected to call auto_save_session() separately.

    # --- Sticky Header ---
    header_data = prepare_sticky_header_data(df_plot, metrics)
    UIComponents.render_sticky_header(header_data)

    # --- Running metrics (RSS, IF, distance) ---
    if "time" in df_plot.columns:
        duration_sec = float(df_plot["time"].max() - df_plot["time"].min())
    else:
        duration_sec = len(df_plot)  # Fallback assumption of 1Hz

    rss_header = calculate_running_stress_score(df_plot, threshold_pace_input, duration_sec)
    intensity_factor = threshold_pace_input / np_header if np_header > 0 else 0

    if "distance" in df_plot.columns and df_plot["distance"].max() > 0:
        distance_km = float(df_plot["distance"].max()) / 1000.0
    elif "pace" in df_plot.columns:
        pace_valid = df_plot["pace"].replace(0, np.nan).dropna()
        if len(pace_valid) > 0:
            speed_ms = 1000.0 / pace_valid
            distance_m = speed_ms.sum()
            distance_km = distance_m / 1000.0
        else:
            distance_km = 0
    else:
        distance_km = 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Tempo Normalizowane", format_pace(np_header))
    m2.metric("RSS", f"{rss_header:.0f}", help=f"IF: {intensity_factor:.2f}")
    m3.metric("Dystans", f"{distance_km:.2f} km")

    return np_header


