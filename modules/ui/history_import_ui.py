"""
History Import UI.

UI for importing historical training files from 'treningi_csv' folder.
"""
import streamlit as st

from modules.history_import import (
    import_training_folder, 
    get_available_files, 
    TRAINING_FOLDER
)
from modules.db import SessionStore


def render_history_import_tab(cp: float = 280):
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
    
    # Check available files
    available = get_available_files()
    
    if not available:
        st.warning("Brak plików CSV w folderze 'treningi_csv'.")
        return
    
    # Display available files
    st.subheader(f"📋 Dostępne pliki ({len(available)})")
    
    with st.expander("Pokaż listę plików", expanded=False):
        for f in available[:20]:  # Show first 20
            size_kb = f['size'] / 1024
            st.markdown(f"- `{f['date']}` - {f['name']} ({size_kb:.0f} KB)")
        
        if len(available) > 20:
            st.caption(f"...i {len(available) - 20} więcej")
    
    # Import settings
    st.divider()
    st.subheader("⚙️ Ustawienia importu")
    
    col1, col2 = st.columns(2)
    
    with col1:
        cp_import = st.number_input(
            "CP/FTP dla obliczeń TSS [W]",
            min_value=100,
            max_value=500,
            value=int(cp),
            help="Moc krytyczna używana do obliczania TSS historycznych treningów"
        )
    
    with col2:
        st.metric("Pliki do importu", len(available))
    
    # Import button
    st.divider()
    
    if st.button("🚀 Importuj wszystkie pliki", type="primary", use_container_width=True):
        with st.spinner("Importowanie..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def progress_callback(current, total, message):
                progress_bar.progress(current / total)
                status_text.text(f"[{current}/{total}] {message}")
            
            success, fail, messages = import_training_folder(
                cp=cp_import,
                progress_callback=progress_callback
            )
            
            progress_bar.empty()
            status_text.empty()
            
            # Show results
            if success > 0:
                st.success(f"✅ Zaimportowano **{success}** treningów!")
            
            if fail > 0:
                st.warning(f"⚠️ Nieudane: **{fail}** plików")
            
            # Show details
            with st.expander("Szczegóły importu"):
                for msg in messages:
                    if msg.startswith("✅"):
                        st.markdown(f"<span style='color: green'>{msg}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span style='color: red'>{msg}</span>", unsafe_allow_html=True)
            
            # Refresh count
            new_count = store.get_session_count()
            st.info(f"**Sesje w bazie po imporcie:** {new_count}")
    
    # Manual file selection
    st.divider()
    st.subheader("📁 Import wybranych plików")
    
    selected = st.multiselect(
        "Wybierz pliki do importu",
        options=[f['name'] for f in available],
        default=[]
    )
    
    if selected and st.button("Importuj wybrane"):
        from modules.history_import import import_single_file
        
        with st.spinner("Importowanie wybranych..."):
            for filename in selected:
                filepath = TRAINING_FOLDER / filename
                success, msg = import_single_file(filepath, cp_import)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
