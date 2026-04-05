import html
from typing import List

import streamlit as st

from modules.db import SessionStore
from modules.history_import import TRAINING_FOLDER, get_available_files, import_training_folder


def _render_import_results(
    success: int, fail: int, messages: List[str], store: SessionStore
) -> None:
    """Display batch import results and refresh session count."""
    if success > 0:
        st.success(f"✅ Zaimportowano **{success}** treningów!")

    if fail > 0:
        st.warning(f"⚠️ Nieudane: **{fail}** plików")

    with st.expander("Szczegóły importu"):
        for msg in messages:
            safe_msg = html.escape(msg)
            color = "green" if msg.startswith("✅") else "red"
            st.markdown(f"<span style='color: {color}'>{safe_msg}</span>", unsafe_allow_html=True)

    new_count = store.get_session_count()
    st.info(f"**Sesje w bazie po imporcie:** {new_count}")


def _render_manual_file_import(selected: List[str], cp_import: int) -> None:
    """Import individually selected files one by one."""
    from modules.history_import import import_single_file

    with st.spinner("Importowanie wybranych..."):
        for filename in selected:
            filepath = TRAINING_FOLDER / filename
            ok, msg = import_single_file(filepath, cp_import)
            if ok:
                st.success(msg)
            else:
                st.error(msg)


def _run_batch_import(cp_import: int, store: SessionStore) -> None:
    """Execute batch import of all training files with progress."""
    progress_bar = st.progress(0)
    status_text = st.empty()

    def progress_callback(current: int, total: int, message: str) -> None:
        progress_bar.progress(current / total)
        status_text.text(f"[{current}/{total}] {message}")

    success, fail, messages = import_training_folder(
        cp=cp_import, progress_callback=progress_callback
    )

    progress_bar.empty()
    status_text.empty()

    _render_import_results(success, fail, messages, store)


def render_history_import_tab(cp: float = 280) -> None:
    """Render the history import UI tab.

    Args:
        cp: Critical Power for TSS calculations
    """
    st.header("📂 Import Historycznych Treningów")

    store = SessionStore()
    current_count = store.get_session_count()

    st.info(f"""
    **Folder źródłowy:** `{TRAINING_FOLDER}`

    **Aktualne sesje w bazie:** {current_count}
    """)

    available = get_available_files()

    if not available:
        st.warning("Brak plików CSV w folderze 'treningi_csv'.")
        return

    st.subheader(f"📋 Dostępne pliki ({len(available)})")

    with st.expander("Pokaż listę plików", expanded=False):
        for f in available[:20]:
            size_kb = f["size"] / 1024
            st.markdown(f"- `{f['date']}` - {f['name']} ({size_kb:.0f} KB)")

        if len(available) > 20:
            st.caption(f"...i {len(available) - 20} więcej")

    st.divider()
    st.subheader("⚙️ Ustawienia importu")

    col1, col2 = st.columns(2)

    with col1:
        cp_import = st.number_input(
            "CP/FTP dla obliczeń TSS [W]",
            min_value=100,
            max_value=500,
            value=int(cp),
            help="Moc krytyczna używana do obliczania TSS historycznych treningów",
        )

    with col2:
        st.metric("Pliki do importu", len(available))

    st.divider()

    if st.button("🚀 Importuj wszystkie pliki", type="primary", use_container_width=True):
        with st.spinner("Importowanie..."):
            _run_batch_import(cp_import, store)

    st.divider()
    st.subheader("📁 Import wybranych plików")

    selected = st.multiselect(
        "Wybierz pliki do importu", options=[f["name"] for f in available], default=[]
    )

    if selected and st.button("Importuj wybrane"):
        _render_manual_file_import(selected, cp_import)
