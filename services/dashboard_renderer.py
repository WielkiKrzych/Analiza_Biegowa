"""Connect upload state to the running session analysis."""

import hashlib
import logging
import sqlite3
from typing import Any

import pandas as pd
import streamlit as st

from modules.calculations.pace_utils import format_pace
from modules.db import SessionRecord, SessionStore
from modules.frontend.state import clear_file_selections
from modules.utils import load_data, validate_data_completeness
from services.session_orchestrator import prepare_session_record, process_uploaded_session

logger = logging.getLogger(__name__)


def process_and_cache_session(uploaded_file: Any, threshold_pace: float):
    """Read the current upload, reset its selections on change and analyse it."""
    with st.spinner("Przetwarzanie danych..."):
        try:
            content_hash = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
            if content_hash != st.session_state.get("current_file_hash"):
                clear_file_selections()
                st.session_state["current_file_hash"] = content_hash
            df_raw = load_data(uploaded_file)
            df_plot, resampled, metrics, error = process_uploaded_session(df_raw, threshold_pace)
        except (ValueError, TypeError, KeyError, OSError, pd.errors.ParserError) as exc:
            st.error(f"Błąd wczytywania pliku: {exc}")
            st.stop()
            return None
        if error or df_plot is None or resampled is None or metrics is None:
            st.error(f"Błąd analizy: {error or 'brak danych'}")
            st.stop()
            return None
        return df_plot, resampled, metrics, validate_data_completeness(df_raw)


def auto_save_session(
    uploaded_file: Any,
    df_plot: pd.DataFrame,
    metrics: dict[str, Any],
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


def render_header_and_metrics(metrics: dict[str, Any]) -> None:
    pace = metrics["normalized_pace"]
    columns = st.columns(3)
    columns[0].metric("Tempo normalizowane", format_pace(pace) if pace else "brak")
    columns[1].metric("RSS", f"{metrics['rss']:.0f}")
    columns[2].metric("Dystans", f"{metrics['distance_km']:.2f} km")
