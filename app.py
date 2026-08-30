import importlib
import logging
import os

import streamlit as st

from modules.domain import SessionType
from modules.frontend.components import UIComponents
from modules.frontend.layout import AppLayout
from modules.frontend.state import StateManager
from modules.frontend.theme import ThemeManager
from modules.ml_logic import MLX_AVAILABLE, MODEL_FILE, predict_only
from modules.notes import TrainingNotes
from modules.reporting.persistence import check_git_tracking
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
        "limiters": ("modules.ui.limiters", "render_limiters_tab"),
        "thresholds": ("modules.ui.threshold_analysis_ui", "render_threshold_analysis_tab"),
        "history": ("modules.ui.trends_history", "render_trends_history_tab"),
        "community": ("modules.ui.community", "render_community_tab"),
        "import": ("modules.ui.history_import_ui", "render_history_import_tab"),
        "heart_rate": ("modules.ui.heart_rate", "render_hr_tab"),
        "summary": ("modules.ui.summary", "render_summary_tab"),
        "drift_maps": ("modules.ui.drift_maps_ui", "render_drift_maps_tab"),
        "training_load": ("modules.ui.training_load_ui", "render_training_load_tab"),
        "banister": ("modules.ui.banister_ui", "render_banister_tab"),
        "durability": ("modules.ui.durability_ui", "render_durability_tab"),
        "tte": ("modules.ui.tte_ui", "render_tte_tab"),
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
        except (ImportError, AttributeError, RuntimeError) as e:
            logger.warning(f"Tab {tab_name} failed: {e}")
            with st.expander(f"⚠️ Błąd w zakładce {tab_name}", expanded=True):
                st.error(f"Nie udało się załadować zakładki: {tab_name}")
                st.caption(f"Szczegóły błędu: {type(e).__name__}: {e}")
                st.caption("Spróbuj przeładować plik lub zmienić parametry.")
            return None


def render_tab_content(tab_name, *args, **kwargs):
    """Facade for TabRegistry."""
    return TabRegistry.render(tab_name, *args, **kwargs)


# --- INIT ---
ThemeManager.set_page_config()
ThemeManager.load_css()

state = StateManager()
state.init_session_state()

# Safety Check: Git Tracking of sensitive data (reports & raw CSVs)
check_git_tracking("reports/ramp_tests")
check_git_tracking("treningi_csv")

layout = AppLayout(state)
uploaded_file, params = layout.render_sidebar()

# Parameters shorthand - RUNNING only
runner_weight = params.get("runner_weight", 75.0)
threshold_pace_input = params.get("threshold_pace", 233)
lthr_input = params.get("lthr", 166)
max_hr_input = params.get("max_hr", 184)
vt1_vent = params.get("vt1_vent", 0)
vt2_vent = params.get("vt2_vent", 0)
runner_age = params.get("runner_age", 30)
is_male = params.get("is_male", True)

layout.render_header()


if runner_weight <= 0 or threshold_pace_input <= 0:
    st.error("Błąd: Waga i tempo progowe muszą być większe od zera.")
    st.stop()

if uploaded_file is not None:
    state.cleanup_old_data()
    training_notes = TrainingNotes()

    # P1-4 (audit v2): processing pipeline + auto-save + header + metrics
    # were 128 lines of inline code in app.py. Now they live in
    # `services/dashboard_renderer.py` so app.py focuses on routing.
    df_plot, df_plot_resampled, metrics = process_and_cache_session(
        uploaded_file, runner_weight=runner_weight, state=state
    )

    # AI Section (Optional/Non-critical) — kept inline because it's short
    # and only relevant for some sessions.
    if MLX_AVAILABLE and os.path.exists(MODEL_FILE):
        try:
            auto_pred = predict_only(df_plot_resampled)
            if auto_pred is not None:
                df_plot_resampled["ai_hr"] = auto_pred
        except (ValueError, TypeError, RuntimeError) as e:
            logger.warning(f"AI prediction failed: {e}")

    # --- RENDER DASHBOARD ---
    np_header = render_header_and_metrics(df_plot, metrics, threshold_pace_input)
    auto_save_session(uploaded_file, df_plot, metrics, np_header)

    # `decoupling_percent`, `drift_z2`, `df_clean_pl` were previously read
    # here from `metrics`. After the refactor they are still available via
    # `metrics` (the dict is returned by `process_and_cache_session`).
    decoupling_percent = metrics.get("_decoupling_percent", 0.0)
    drift_z2 = metrics.get("_drift_z2", 0.0)
    df_clean_pl = metrics.get("_df_clean_pl")
    if df_clean_pl is None or (hasattr(df_clean_pl, "empty") and df_clean_pl.empty):
        df_clean_pl = None  # caller must handle the absence

    # Session Type Badge with Confidence
    session_type = st.session_state.get("session_type")
    ramp_classification = st.session_state.get("ramp_classification")

    if session_type:
        # Build display message based on session type
        if session_type == SessionType.RAMP_TEST and ramp_classification:
            confidence = ramp_classification.confidence
            bg_color = "rgba(46, 204, 113, 0.2)"
            msg = f"Rozpoznano: <b>Ramp Test</b> (confidence: {confidence:.2f})"
        elif session_type == SessionType.RAMP_TEST_CONDITIONAL and ramp_classification:
            confidence = ramp_classification.confidence
            bg_color = "rgba(241, 196, 15, 0.2)"
            msg = f"Rozpoznano: <b>Ramp Test (warunkowo)</b> (confidence: {confidence:.2f})"
        elif session_type == SessionType.TRAINING:
            bg_color = "rgba(52, 152, 219, 0.2)"
            if ramp_classification and not ramp_classification.is_ramp:
                msg = "Sesja treningowa – analiza badawcza pominięta"
            else:
                msg = "Rozpoznano: <b>Sesja treningowa</b>"
        else:
            bg_color = "rgba(149, 165, 166, 0.2)"
            msg = f"Typ sesji: <b>{session_type}</b>"

        st.markdown(
            f"""
        <div style="background: linear-gradient(90deg, {bg_color}, transparent);
                    padding: 10px 15px; border-radius: 8px; margin-bottom: 10px; display: inline-block;">
            <span style="font-size: 1.1em;">{session_type.emoji} {msg}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Sport Type Indicator - Running only
    st.markdown(
        """
        <div style="background: linear-gradient(90deg, rgba(46, 204, 113, 0.2), transparent);
                    padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; display: inline-block;">
            <span style="font-size: 1em;">🏃 Analiza Biegowa</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Data Quality Report
    quality_report = st.session_state.get("data_quality_report")
    if quality_report:
        with st.expander("📋 Raport jakości danych", expanded=False):
            st.write(f"**Typ sportu:** {quality_report.sport_type}")
            st.write(f"**Jakość danych:** {quality_report.quality_score:.0f}%")

            col1, col2 = st.columns(2)
            with col1:
                st.write("**Dostępne metryki:**")
                for m in quality_report.available_metrics[:8]:
                    st.write(f"  ✅ {m}")
                if len(quality_report.available_metrics) > 8:
                    st.write(f"  ... i {len(quality_report.available_metrics) - 8} więcej")

            with col2:
                st.write("**Brakujące metryki:**")
                for m in quality_report.missing_metrics[:5]:
                    st.write(f"  ❌ {m}")

            if quality_report.recommendations:
                st.write("**Rekomendacje:**")
                for rec in quality_report.recommendations:
                    st.write(rec)

    # Layout Tabs
    tab_overview, tab_performance, tab_intelligence, tab_physiology = st.tabs(
        ["📊 Overview", "⚡ Performance", "🧠 Intelligence", "🫀 Physiology"]
    )

    with tab_overview:
        UIComponents.show_breadcrumb("📊 Overview")
        t1, t2 = st.tabs(["📋 Raport z KPI", "📊 Podsumowanie"])
        with t1:
            render_tab_content(
                "report",
                df_plot,
                df_plot_resampled,
                metrics,
                runner_weight,
                0,
                decoupling_percent,
                drift_z2,
                vt1_vent,
                vt2_vent,
            )
        with t2:
            render_tab_content(
                "summary",
                df_plot,
                df_plot_resampled,
                metrics,
                training_notes,
                uploaded_file.name,
                0,
                0,
                runner_weight,
                threshold_pace_input,
                threshold_pace_input,
                0,
                0,
            )

    with tab_performance:
        UIComponents.show_breadcrumb("⚡ Performance")
        t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(
            [
                "🏃 Running",
                "🦶 Biomechanika",
                "📐 Model",
                "❤️ HR",
                "🧬 Hematology",
                "📈 Drift Maps",
                "🛡️ Wytrzymałość",
                "⏱️ TTE",
            ]
        )
        with t1:
            render_tab_content(
                "running",
                df_plot,
                threshold_pace_input,
                runner_weight,
            )
        with t2:
            render_tab_content("biomech", df_plot, df_plot_resampled)
        with t3:
            render_tab_content("model", df_plot, 0, 0)
        with t4:
            render_tab_content("heart_rate", df_plot)
        with t5:
            render_tab_content("hemo", df_plot)
        with t6:
            render_tab_content("drift_maps", df_plot)
        with t7:
            render_tab_content("durability", df_plot, df_plot_resampled, metrics)
        with t8:
            render_tab_content("tte", df_plot, 0.0, threshold_pace_input, uploaded_file.name)

    with tab_intelligence:
        UIComponents.show_breadcrumb("🧠 Intelligence")
        t1, t2, t3, t4 = st.tabs(
            ["🍎 Nutrition", "🚧 Limiters", "📊 Obciążenie (PMC)", "🎯 Banister"]
        )
        with t1:
            render_tab_content("nutrition", df_plot, 0, threshold_pace_input, threshold_pace_input)
        with t2:
            render_tab_content("limiters", df_plot, 0, vt2_vent)
        with t3:
            render_tab_content("training_load")
        with t4:
            render_tab_content("banister")

    with tab_physiology:
        UIComponents.show_breadcrumb("🫀 Physiology")
        t1, t2, t3, t4 = st.tabs(
            [
                "💓 HRV",
                "🩸 SmO2",
                "🫁 Ventilation",
                "🌡️ Thermal",
            ]
        )
        with t1:
            render_tab_content("hrv", df_clean_pl)
        with t2:
            render_tab_content("smo2", df_plot, training_notes, uploaded_file.name)
        max_hr = int(208 - 0.7 * runner_age) if runner_age else 185
        with t3:
            render_tab_content("vent", df_plot, training_notes, uploaded_file.name)
        with t4:
            render_tab_content("thermal", df_plot)

else:
    st.sidebar.info("Wgraj plik.")
