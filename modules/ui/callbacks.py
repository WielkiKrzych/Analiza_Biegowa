"""
SOLID: Implementacja Streamlit-specyficznych callbacków dla logiki ML.

Ten moduł zawiera konkretne implementacje abstrakcyjnych callbacków
z ml_logic.py dla interfejsu Streamlit.
"""
import streamlit as st
from modules.ml_logic import TrainingCallback


class StreamlitCallback(TrainingCallback):
    """Callback dla Streamlit UI - wyświetla pasek postępu i statusy.
    
    Implementuje wzorzec Dependency Inversion - warstwa UI zależy od 
    abstrakcji z warstwy logiki biznesowej, a nie odwrotnie.
    """
    
    def __init__(self):
        self._status_container = st.empty()
        self._progress_bar = st.progress(0)
    
    def on_status(self, message: str) -> None:
        """Wyświetla wiadomość statusu w UI Streamlit."""
        self._status_container.info(message)
    
    def on_progress(self, current: int, total: int) -> None:
        """Aktualizuje pasek postępu Streamlit."""
        if total > 0:
            self._progress_bar.progress(min(current / total, 1.0))
        else:
            self._progress_bar.progress(0)
    
    def on_error(self, error: Exception) -> None:
        """Wyświetla błąd w sidebar Streamlit."""
        st.sidebar.error(f"⚠️ Błąd AI: {error}")
    
    def on_complete(self) -> None:
        """Czyści elementy UI po zakończeniu treningu."""
        self._progress_bar.empty()
        self._status_container.empty()
