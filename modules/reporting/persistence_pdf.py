"""
Persistence PDF generation and index management.

Handles PDF auto-generation after save, manual PDF regeneration,
and CSV index read/write operations.
"""

import csv
import logging
from pathlib import Path
from typing import Dict, Optional, Union

import streamlit as st

from .persistence_constants import INDEX_COLUMNS
from .persistence_load import load_ramp_test_report

logger = logging.getLogger(__name__)


def _auto_generate_pdf(
    json_path: str,
    report_data: Dict,
    is_conditional: bool = False,
    source_df=None,
    manual_overrides=None,
) -> Optional[str]:
    """
    Auto-generate PDF from JSON report.

    Called automatically after save_ramp_test_report.
    PDF is saved next to JSON with same basename.

    Args:
        json_path: Absolute path to saved JSON
        report_data: The report data dictionary
        is_conditional: If True, PDF will include conditional warning
        source_df: Optional DataFrame with raw data for chart generation
        manual_overrides: Dict of manual threshold values (VT1/VT2/SmO2/CP) from session_state

    Returns:
        PDF path if successful, None otherwise
    """
    # --- HARD TRIGGER CHECK ---
    if not st.session_state.get("report_generation_requested", False):
        logger.info("[PDF GATING] PDF generation NOT requested (Hard Trigger). Aborting.")
        return None

    import tempfile

    from .figures import generate_all_ramp_figures
    from .pdf import PDFConfig, generate_ramp_pdf

    json_path = Path(json_path)
    pdf_path = json_path.with_suffix(".pdf")

    # Generate figures in temp directory
    temp_dir = tempfile.mkdtemp()
    method_version = report_data.get("metadata", {}).get("method_version", "1.0.0")
    fig_config = {"method_version": method_version}

    # Pass source_df for chart generation
    # If source_df is missing (regeneration from index), charts will try to use report_data['time_series']
    figure_paths = generate_all_ramp_figures(report_data, temp_dir, fig_config, source_df=source_df)

    # Configure PDF with conditional flag
    pdf_config = PDFConfig(is_conditional=is_conditional)

    # Generate PDF with manual overrides
    generate_ramp_pdf(
        report_data, figure_paths, str(pdf_path), pdf_config, manual_overrides=manual_overrides
    )

    # Generate DOCX (optional)
    try:
        from .docx_builder import build_ramp_docx

        docx_path = pdf_path.with_suffix(".docx")
        build_ramp_docx(report_data, figure_paths, str(docx_path))
        logger.info(f"Ramp Test DOCX generated: {docx_path}")
    except (ImportError, OSError, ValueError) as e:
        logger.error(f"DOCX generation failed: {e}")

    logger.info(f"Ramp Test PDF generated: {pdf_path}")

    # --- RESET HARD TRIGGER ---
    st.session_state["report_generation_requested"] = False

    return str(pdf_path.absolute())


def _update_index(
    base_dir: str,
    metadata: Dict,
    file_path: str,
    pdf_path: Optional[str] = None,
    source_file: Optional[str] = None,
):
    """
    Update CSV index with new test record.

    Columns: session_id, test_date, athlete_id, method_version, json_path, pdf_path, source_file
    """
    index_path = Path(base_dir) / "index.csv"
    file_exists = index_path.exists()

    row = {
        "session_id": metadata.get("session_id", ""),
        "test_date": metadata.get("test_date", ""),
        "athlete_id": metadata.get("athlete_id") or "anonymous",
        "method_version": metadata.get("method_version", ""),
        "json_path": file_path,
        "pdf_path": pdf_path or "",
        "source_file": source_file or "",
    }

    # Validation: Ensure all columns are present and no empty critical fields
    if len(row) != len(INDEX_COLUMNS):
        logger.error(
            f"Invalid record length for index. Expected {len(INDEX_COLUMNS)}, got {len(row)}."
        )
        return

    if not row["session_id"] or not row["json_path"]:
        logger.error("Missing critical data for index (session_id or json_path). Record not saved.")
        return

    try:
        with open(index_path, "a", newline="", encoding="utf-8") as f:
            # quote_all ensures paths (and other strings) are in quotes as requested
            writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS, quoting=csv.QUOTE_ALL)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        logger.info(f"Ramp Test indexed: {row['session_id']}")
    except (OSError, csv.Error) as e:
        logger.error(f" Failed to write to index at {index_path}: {e}")


def update_index_pdf_path(base_dir: str, session_id: str, pdf_path: str):
    """
    Update existing index row with PDF path.

    PDF can be regenerated, so this updates an existing row.
    JSON is never modified (immutable).

    Args:
        base_dir: Base directory containing index.csv
        session_id: Session ID to update
        pdf_path: Path to generated PDF
    """
    index_path = Path(base_dir) / "index.csv"

    if not index_path.exists():
        logger.warning(f" Index not found at {index_path}")
        return

    # Read all rows
    rows = []

    with open(index_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("session_id") == session_id:
                row["pdf_path"] = pdf_path

            # Basic validation for existing row
            if all(k in row for k in INDEX_COLUMNS):
                rows.append(row)
            else:
                logger.warning(f" Skipping malformed index row for session {row.get('session_id')}")

    # Write back with updated row
    try:
        with open(index_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"Updated PDF path for session {session_id}")
    except (OSError, csv.Error) as e:
        logger.error(f" Failed to update index at {index_path}: {e}")


def generate_and_save_pdf(
    json_path: Union[str, Path],
    output_base_dir: str = "reports/ramp_tests",
    is_conditional: bool = False,
    manual_overrides: Optional[Dict] = None,
) -> Optional[str]:
    """
    Generate PDF from existing JSON report and save alongside it.

    - PDF is saved next to the JSON with .pdf extension
    - PDF can be regenerated (overwritten)
    - JSON is NEVER modified (immutable)
    - Index is updated with PDF path

    Args:
        json_path: Path to the canonical JSON report
        output_base_dir: Base directory for index update
        is_conditional: Whether to include conditional warning
        manual_overrides: Dict of manual threshold values from session_state to override saved values

    Returns:
        Path to generated PDF or None on failure
    """
    import tempfile

    from .figures import generate_all_ramp_figures
    from .pdf import PDFConfig, generate_ramp_pdf

    json_path = Path(json_path)

    if not json_path.exists():
        logger.error(f" JSON report not found: {json_path}")
        return None

    # Load JSON report
    report_data = load_ramp_test_report(json_path)

    # Generate figure paths
    # NOTE: Charts will show "Brak danych" since source_df is not available
    # during regeneration from JSON. Full charts are only generated during
    # initial save when DataFrame is available.
    temp_dir = tempfile.mkdtemp()
    fig_config = {"method_version": report_data.get("metadata", {}).get("method_version", "1.0.0")}
    figure_paths = generate_all_ramp_figures(
        report_data, temp_dir, fig_config, source_df=None, manual_overrides=manual_overrides
    )

    # Generate PDF path (same name as JSON but .pdf)
    pdf_path = json_path.with_suffix(".pdf")

    # Configure PDF
    pdf_config = PDFConfig(is_conditional=is_conditional)

    # Generate PDF (can overwrite existing) - with manual overrides if provided
    generate_ramp_pdf(
        report_data, figure_paths, str(pdf_path), pdf_config, manual_overrides=manual_overrides
    )

    # Generate DOCX (optional)
    try:
        from .docx_builder import build_ramp_docx

        docx_path = pdf_path.with_suffix(".docx")
        build_ramp_docx(report_data, figure_paths, str(docx_path))
        logger.info(f"DOCX generated: {docx_path}")
    except (ImportError, OSError, ValueError) as e:
        logger.info(f"DOCX failure: {e}")

    # Update index with PDF path
    session_id = report_data.get("metadata", {}).get("session_id", "")
    if session_id:
        update_index_pdf_path(output_base_dir, session_id, str(pdf_path.absolute()))

    logger.info(f"PDF generated: {pdf_path}")

    return str(pdf_path.absolute())


def generate_ramp_test_pdf(
    session_id: str,
    output_base_dir: str = "reports/ramp_tests",
    manual_overrides: Optional[Dict] = None,
) -> Optional[str]:
    """
    Ręczne generowanie raportu PDF na podstawie session_id.

    1. Znajduje json_path w index.csv
    2. Wczytuje JSON
    3. Generuje PDF (z opcjonalnymi wartościami manualnymi) i aktualizuje index

    Args:
        session_id: ID sesji raportu
        output_base_dir: Bazowy katalog raportów
        manual_overrides: Słownik z ręcznymi wartościami progowymi

    Returns:
        Ścieżka do wygenerowanego PDF lub None
    """
    import csv

    index_path = Path(output_base_dir) / "index.csv"

    if not index_path.exists():
        logger.error(f" Index not found at {index_path}")
        return None

    json_path = None

    with open(index_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("session_id") == session_id:
                json_path = row.get("json_path")
                break

    if not json_path:
        logger.error(f" JSON path not found in index for session {session_id}")
        return None

    # Re-use existing logic for generation - NOW with manual_overrides
    pdf_path_str = generate_and_save_pdf(
        json_path, output_base_dir, manual_overrides=manual_overrides
    )

    if pdf_path_str:
        logger.info(f"PDF saved to: {pdf_path_str}")
        logger.info(f"index.csv updated for session_id: {session_id}")
        return pdf_path_str

    return None
