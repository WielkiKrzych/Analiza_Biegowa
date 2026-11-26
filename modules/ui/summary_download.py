"""Show the export only while its input file and settings match."""

from typing import Any

import pandas as pd
import streamlit as st

from modules.reporting.summary_pdf import generate_summary_pdf

SummaryPDFKey = tuple[str, float, float]


def invalidate_summary_pdf(key: SummaryPDFKey | None) -> None:
    if key is None or st.session_state.get("summary_pdf_key") != key:
        st.session_state.pop("summary_pdf_key", None)
        st.session_state.pop("summary_pdf_bytes", None)


def render_summary_download(df: pd.DataFrame, metrics: dict[str, Any], key: SummaryPDFKey) -> None:
    with st.expander("Raport PDF"):
        if st.button("Przygotuj PDF", key="prepare_summary_pdf"):
            _, weight, pace = key
            pdf = generate_summary_pdf(df, metrics, weight, pace)
            st.session_state["summary_pdf_bytes"] = pdf
            st.session_state["summary_pdf_key"] = key
        if st.session_state.get("summary_pdf_key") == key:
            st.download_button(
                "Pobierz podsumowanie PDF",
                data=st.session_state["summary_pdf_bytes"],
                file_name="podsumowanie-biegu.pdf",
                mime="application/pdf",
                key="download_summary_pdf",
            )
