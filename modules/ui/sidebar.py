"""
Sidebar UI Module.

Extracts sidebar configuration from app.py for better separation of concerns.
"""

import streamlit as st
from dataclasses import dataclass
from typing import Optional, Tuple
from modules.settings import SettingsManager


@dataclass
class RiderSettings:
    """Container for rider physical parameters."""

    weight: float
    height: int
    age: int
    is_male: bool
    vt1_watts: int
    vt2_watts: int
    vt1_vent: float
    vt2_vent: float
    cp: int
    w_prime: int
    crank_length: float


def init_session_state(settings_manager: SettingsManager) -> None:
    """Initialize session state from saved settings.

    Args:
        settings_manager: SettingsManager instance
    """
    saved_settings = settings_manager.load_settings()

    # Mapping UI keys to JSON keys
    keys_map = {
        "weight": "rider_weight",
        "height": "rider_height",
        "age": "rider_age",
        "gender_m": "is_male",
        "vt1_w": "vt1_watts",
        "vt2_w": "vt2_watts",
        "vt1_v": "vt1_vent",
        "vt2_v": "vt2_vent",
        "cp_in": "cp",
        "wp_in": "w_prime",
        "crank": "crank_length",
    }

    for ui_key, json_key in keys_map.items():
        if ui_key not in st.session_state:
            st.session_state[ui_key] = saved_settings.get(json_key)


def _create_save_callback(settings_manager: SettingsManager):
    """Create callback function for saving settings."""
    keys_map = {
        "weight": "rider_weight",
        "height": "rider_height",
        "age": "rider_age",
        "gender_m": "is_male",
        "vt1_w": "vt1_watts",
        "vt2_w": "vt2_watts",
        "vt1_v": "vt1_vent",
        "vt2_v": "vt2_vent",
        "cp_in": "cp",
        "wp_in": "w_prime",
        "crank": "crank_length",
    }

    def save_settings_callback():
        """Save current UI values to JSON file."""
        current_values = {}
        for ui_key, json_key in keys_map.items():
            if ui_key in st.session_state:
                current_values[json_key] = st.session_state[ui_key]
        settings_manager.save_settings(current_values)

    return save_settings_callback


def render_sidebar(settings_manager: SettingsManager) -> Tuple[RiderSettings, Optional[object]]:
    """Render the sidebar with all rider settings.

    Args:
        settings_manager: SettingsManager instance

    Returns:
        Tuple of (RiderSettings, uploaded_file)
    """
    save_callback = _create_save_callback(settings_manager)

    st.sidebar.header("Ustawienia Zawodnika")

    with st.sidebar.expander("⚙️ Parametry Fizyczne", expanded=True):
        rider_weight = st.number_input(
            "Waga Zawodnika [kg]",
            step=0.5,
            min_value=30.0,
            max_value=200.0,
            key="weight",
            on_change=save_callback,
        )
        rider_height = st.number_input(
            "Wzrost [cm]",
            step=1,
            min_value=100,
            max_value=250,
            key="height",
            on_change=save_callback,
        )
        rider_age = st.number_input(
            "Wiek [lata]", step=1, min_value=10, max_value=100, key="age", on_change=save_callback
        )
        is_male = st.checkbox("Mężczyzna?", key="gender_m", on_change=save_callback)

        st.markdown("---")
        vt1_watts = st.number_input(
            "VT1 (Próg Tlenowy) [W]", min_value=0, key="vt1_w", on_change=save_callback
        )
        vt2_watts = st.number_input(
            "VT2 (Próg Beztlenowy/FTP) [W]", min_value=0, key="vt2_w", on_change=save_callback
        )

        st.divider()
        st.markdown("### 🫁 Wentylacja [L/min]")
        vt1_vent = st.number_input(
            "VT1 (Próg Tlenowy) [L/min]", min_value=0.0, key="vt1_v", on_change=save_callback
        )
        vt2_vent = st.number_input(
            "VT2 (Próg Beztlenowy) [L/min]", min_value=0.0, key="vt2_v", on_change=save_callback
        )

    st.sidebar.divider()
    cp_input = st.sidebar.number_input(
        "Moc Krytyczna (CP) [W]", min_value=1, key="cp_in", on_change=save_callback
    )
    w_prime_input = st.sidebar.number_input(
        "W' (W Prime) [J]", min_value=0, key="wp_in", on_change=save_callback
    )
    st.sidebar.divider()
    crank_length = st.sidebar.number_input(
        "Długość korby [mm]", key="crank", on_change=save_callback
    )

    # File upload
    uploaded_file = st.sidebar.file_uploader("Wgraj plik (CSV / TXT)", type=["csv", "txt"])

    settings = RiderSettings(
        weight=rider_weight,
        height=rider_height,
        age=rider_age,
        is_male=is_male,
        vt1_watts=vt1_watts,
        vt2_watts=vt2_watts,
        vt1_vent=vt1_vent,
        vt2_vent=vt2_vent,
        cp=cp_input,
        w_prime=w_prime_input,
        crank_length=crank_length,
    )

    return settings, uploaded_file


def render_export_section(
    data_loaded: bool,
    uploaded_file: Optional[object],
    generate_docx_fn,
    export_png_fn,
    export_summary_pdf_fn,
    export_args: dict,
) -> None:
    """Render export buttons in sidebar.

    Args:
        data_loaded: Whether data is loaded
        uploaded_file: Uploaded file object
        generate_docx_fn: Function to generate DOCX report
        export_png_fn: Function to export PNG charts
        export_summary_pdf_fn: Function to export Summary page to PDF
        export_args: Arguments for export functions
    """
    from io import BytesIO

    st.sidebar.markdown("---")
    st.sidebar.header("📄 Export Raportu")

    if data_loaded and uploaded_file is not None:
        col_docx, col_png = st.sidebar.columns(2)

        with col_docx:
            if st.session_state.get("report_generation_requested", False):
                try:
                    docx_doc = generate_docx_fn(**export_args["docx"])
                    if docx_doc:
                        docx_buffer = BytesIO()
                        docx_doc.save(docx_buffer)
                        docx_buffer.seek(0)

                        st.sidebar.download_button(
                            label="📥 Pobierz Raport DOCX",
                            data=docx_buffer.getvalue(),
                            file_name=f"Raport_{uploaded_file.name.split('.')[0]}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )
                except Exception as e:
                    st.sidebar.error(f"Błąd DOCX: {e}")
            else:
                st.sidebar.info("📄 Raport DOCX: Kliknij 'GENERUJ RAPORT', aby przygotować plik.")

        with col_png:
            if st.session_state.get("report_generation_requested", False):
                try:
                    png_zip = export_png_fn(**export_args["png"])
                    if png_zip:
                        st.sidebar.download_button(
                            label="📸 Pobierz Wykresy PNG (ZIP)",
                            data=png_zip,
                            file_name=f"Wykresy_{uploaded_file.name.split('.')[0]}.zip",
                            mime="application/zip",
                            use_container_width=True,
                        )
                except Exception as e:
                    st.sidebar.error(f"Błąd PNG: {e}")
            else:
                st.sidebar.info("📸 Wykresy PNG: Kliknij 'GENERUJ RAPORT', aby przygotować paczkę.")

        # Export Summary PDF button
        st.sidebar.markdown("---")
        if st.session_state.get("report_generation_requested", False):
            try:
                summary_pdf = export_summary_pdf_fn(**export_args.get("summary_pdf", {}))
                if summary_pdf:
                    st.sidebar.download_button(
                        label="📄 Pobierz Podsumowanie (PDF)",
                        data=summary_pdf,
                        file_name=f"Podsumowanie_{uploaded_file.name.split('.')[0]}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            except Exception as e:
                st.sidebar.error(f"Błąd PDF Podsumowania: {e}")
        else:
            st.sidebar.info("📄 PDF Podsumowania: Kliknij 'GENERUJ RAPORT', aby przygotować plik.")
    else:
        st.sidebar.info("Wgraj plik aby pobrać raport.")
