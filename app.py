import importlib
import logging

import streamlit as st

from modules.frontend.git_tracking import check_git_tracking
from modules.frontend.layout import AppLayout
from modules.frontend.state import StateManager
from modules.frontend.theme import ThemeManager
from modules.notes import TrainingNotes
from services.dashboard_renderer import (
    auto_save_session,
    process_and_cache_session,
    render_header_and_metrics,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


# --- TAB REGISTRY (OCP) ---
class TabRegistry:
    """Registry for UI tabs to support Open/Closed Principle."""

    # `thresholds`, `history`, `import` and `community` were deregistered: this
    # registry listed them, but no `render_tab_content(...)` call ever reached
    # them. Their modules stay on disk; see docs/DEAD_CODE_INVENTORY.md.
    _tabs = {
        "report": ("modules.ui.report", "render_report_tab"),
        "running": ("modules.ui.running", "render_running_tab"),
        "biomech": ("modules.ui.biomech", "render_biomech_tab"),
        "model": ("modules.ui.model", "render_model_tab"),
        "hrv": ("modules.ui.hrv", "render_hrv_tab"),
        "smo2": ("modules.ui.smo2", "render_smo2_tab"),
        "hemo": ("modules.ui.hemo", "render_hemo_tab"),
        "vent": ("modules.ui.vent", "render_vent_tab"),
        "thermal": ("modules.ui.thermal", "render_thermal_tab"),
        "nutrition": ("modules.ui.nutrition", "render_nutrition_tab"),
        "heart_rate": ("modules.ui.heart_rate", "render_hr_tab"),
        "summary": ("modules.ui.summary", "render_summary_tab"),
        "drift_maps": ("modules.ui.drift_maps_ui", "render_drift_maps_tab"),
        "tte": ("modules.ui.tte_ui", "render_tte_tab"),
        "aerobic_efficiency": ("modules.ui.aerobic_efficiency", "render_aerobic_efficiency_tab"),
    }

    @classmethod
    def render(cls, tab_name: str, *args, **kwargs):
        """Dynamic dispatcher for tab rendering (Lazy loading).

        Includes error boundary - tabs fail gracefully without crashing app.
        """
        logger = logging.getLogger(__name__)

        if tab_name not in cls._tabs:
            st.error(f"Unknown tab: {tab_name}")
            return

        module_path, func_name = cls._tabs[tab_name]
        try:
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            return func(*args, **kwargs)
        except (
            ImportError,
            AttributeError,
            RuntimeError,
            # Data-shape errors raised inside a tab (missing column, wrong
            # dtype, short frame) used to escape this boundary and take the
            # whole page down instead of one tab. Still an explicit tuple —
            # not `except Exception` — so genuine bug types keep surfacing.
            ValueError,
            KeyError,
            TypeError,
            IndexError,
        ) as e:
            # exc_info: the boundary now also catches TypeError/KeyError/IndexError,
            # which are usually real bugs — one log line without a traceback would
            # make them untraceable.
            logger.warning(f"Tab {tab_name} failed: {e}", exc_info=True)
            with st.expander(f"⚠️ Błąd w zakładce {tab_name}", expanded=True):
                st.error(f"Nie udało się załadować zakładki: {tab_name}")
                st.caption(f"Szczegóły błędu: {type(e).__name__}: {e}")
                st.caption("Spróbuj przeładować plik lub zmienić parametry.")
            return None


TAB_GROUPS = {
    "📊 Overview": {"report": "Raport z KPI", "summary": "Podsumowanie"},
    "⚡ Performance": {
        "running": "Running",
        "biomech": "Biomechanika",
        "model": "CS i D′",
        "heart_rate": "HR",
        "drift_maps": "Drift Maps",
        "tte": "TTE",
    },
    "🧠 Intelligence": {
        "nutrition": "Żywienie",
    },
    "🫀 Physiology": {
        "hrv": "HRV",
        "smo2": "SmO₂",
        "vent": "Ventilation",
        "thermal": "Thermal",
        "hemo": "Hemodynamika",
        "aerobic_efficiency": "Efektywność tlenowa",
    },
}


def select_tab() -> str:
    group = st.radio("Grupa analiz", list(TAB_GROUPS), key="nav_group", horizontal=True)
    if group is None:
        group = next(iter(TAB_GROUPS))
    group_tabs = TAB_GROUPS[group]
    options = list(group_tabs)
    state_key = f"selected_tab_{group}"
    previous = st.session_state.get(state_key)
    index = options.index(previous) if previous in group_tabs else 0
    selected = (
        st.radio(
            "Analiza",
            options,
            index=index,
            format_func=group_tabs.__getitem__,
            key=f"nav_tab_{group}",
            horizontal=True,
        )
        or options[0]
    )
    st.session_state[state_key] = selected
    return selected


def render_data_quality(quality) -> None:
    with st.expander("Dostępne sygnały"):
        st.write(", ".join(quality.available_metrics))
        if quality.missing_metrics:
            st.caption("Brak: " + ", ".join(quality.missing_metrics))


def main() -> None:
    # --- INIT ---
    ThemeManager.set_page_config()
    ThemeManager.load_css()

    state = StateManager()
    state.init_session_state()

    # Safety Check: Git Tracking of sensitive data (reports & raw CSVs)
    check_git_tracking("reports/ramp_tests")
    check_git_tracking("treningi_csv")

    layout = AppLayout()
    uploaded_file, params = layout.render_sidebar()

    # Parameters shorthand - RUNNING only
    runner_weight = params.get("runner_weight", 75.0)
    threshold_pace_input = params.get("threshold_pace", 233)
    vt1_vent = params.get("vt1_vent", 0)
    vt2_vent = params.get("vt2_vent", 0)

    layout.render_header()

    if runner_weight <= 0 or threshold_pace_input <= 0:
        st.error("Błąd: Waga i tempo progowe muszą być większe od zera.")
        st.stop()

    if uploaded_file is None:
        st.sidebar.info("Wgraj plik.")
        return

    result = process_and_cache_session(uploaded_file, threshold_pace_input)
    if result is None:
        return
    df_plot, df_plot_resampled, metrics, quality = result
    render_header_and_metrics(metrics)
    render_data_quality(quality)
    auto_save_session(uploaded_file, df_plot, metrics, metrics["normalized_pace"] or 0.0)

    training_notes = TrainingNotes()
    selected = select_tab()
    args = {
        "report": (df_plot_resampled, metrics, vt1_vent, vt2_vent),
        "summary": (df_plot_resampled, metrics),
        "running": (df_plot, threshold_pace_input, runner_weight),
        "biomech": (df_plot, df_plot_resampled),
        "model": (df_plot,),
        "heart_rate": (df_plot,),
        "hemo": (df_plot,),
        "drift_maps": (df_plot,),
        "tte": (df_plot, threshold_pace_input),
        "nutrition": (df_plot, threshold_pace_input, runner_weight),
        "hrv": (df_plot,),
        "smo2": (df_plot, training_notes, uploaded_file.name),
        "vent": (df_plot, training_notes, uploaded_file.name),
        "thermal": (df_plot,),
        "aerobic_efficiency": (df_plot,),
    }
    TabRegistry.render(selected, *args[selected])


if __name__ == "__main__":
    main()
