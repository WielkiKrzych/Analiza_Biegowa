"""Ventilation interactive chart sections — VE, BR, and Tidal Volume."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from modules.ui.vent_utils import _format_time, _parse_time_to_seconds


def _render_ve_section(target_df, startsec, endsec, interval_data, slope_ve, intercept_ve):
    """Render VE chart with interactive selection."""
    fig_vent = go.Figure()

    fig_vent.add_trace(
        go.Scatter(
            x=target_df["time"],
            y=target_df["ve_smooth"],
            customdata=target_df["time_str"],
            mode="lines",
            name="VE (L/min)",
            line=dict(color="#ffa15a", width=2),
            hovertemplate="<b>Czas:</b> %{customdata}<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
        )
    )

    if "pace_smooth" in target_df.columns:
        pace_min_display = target_df["pace_smooth"] / 60.0
        pace_formatted = pace_min_display.apply(
            lambda x: f"{int(x):d}:{int((x % 1) * 60):02d}" if x > 0 else "--:--"
        )
        fig_vent.add_trace(
            go.Scatter(
                x=target_df["time"],
                y=pace_min_display,
                customdata=np.stack([target_df["time_str"], pace_formatted], axis=-1),
                mode="lines",
                name="Tempo",
                line=dict(color="#00BCD4", width=1),
                yaxis="y2",
                opacity=0.3,
                hovertemplate="<b>Czas:</b> %{customdata[0]}<br><b>Tempo:</b> %{customdata[1]} min/km<extra></extra>",
            )
        )

    fig_vent.add_vrect(
        x0=startsec,
        x1=endsec,
        fillcolor="orange",
        opacity=0.1,
        layer="below",
        line_width=0,
        annotation_text="MANUAL",
        annotation_position="top left",
    )

    if len(interval_data) > 1:
        trend_line = intercept_ve + slope_ve * interval_data["time"]
        fig_vent.add_trace(
            go.Scatter(
                x=interval_data["time"],
                y=trend_line,
                mode="lines",
                name="Trend VE (Man)",
                line=dict(color="white", width=2, dash="dash"),
                hovertemplate="<b>Trend:</b> %{y:.2f} L/min<extra></extra>",
            )
        )

    fig_vent.update_layout(
        title="Dynamika Wentylacji vs Tempo",
        xaxis_title="Czas",
        yaxis=dict(title=dict(text="Wentylacja (L/min)", font=dict(color="#ffa15a"))),
        yaxis2=dict(
            title=dict(text="Tempo (min/km)", font=dict(color="#00BCD4")),
            overlaying="y",
            side="right",
            showgrid=False,
            autorange="reversed",
        ),
        legend=dict(x=0.01, y=0.99),
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
    )

    selected = st.plotly_chart(
        fig_vent,
        use_container_width=True,
        key="vent_chart",
        on_select="rerun",
        selection_mode="box",
    )

    if selected and "selection" in selected and "box" in selected["selection"]:
        box_data = selected["selection"]["box"]
        if box_data and len(box_data) > 0:
            x_range = box_data[0].get("x", [])
            if len(x_range) == 2:
                new_start = min(x_range)
                new_end = max(x_range)
                if (
                    new_start != st.session_state.vent_start_sec
                    or new_end != st.session_state.vent_end_sec
                ):
                    st.session_state.vent_start_sec = new_start
                    st.session_state.vent_end_sec = new_end
                    st.rerun()


def _compute_br_trend(
    interval_data: "pd.DataFrame",
) -> tuple[float, float, str]:
    """Compute linear regression trend for BR interval."""
    if len(interval_data) > 1:
        slope, intercept, _, _, _ = stats.linregress(
            interval_data["time"], interval_data["tymebreathrate"]
        )
        trend_desc = f"{slope:.4f} /s"
        return slope, intercept, trend_desc
    return 0.0, 0.0, "N/A"


def _render_br_manual_input() -> None:
    """Render manual time-range input expander for BR section."""
    with st.expander("🔧 Ręczne wprowadzenie zakresu czasowego BR", expanded=False):
        col_br_1, col_br_2 = st.columns(2)
        with col_br_1:
            manual_br_start = st.text_input(
                "Start Interwału (hh:mm:ss)", value="00:10:00", key="br_manual_start"
            )
        with col_br_2:
            manual_br_end = st.text_input(
                "Koniec Interwału (hh:mm:ss)", value="00:20:00", key="br_manual_end"
            )

        if st.button("Zastosuj ręczny zakres", key="btn_br_manual"):
            br_start = _parse_time_to_seconds(manual_br_start)
            br_end = _parse_time_to_seconds(manual_br_end)
            if br_start is not None and br_end is not None:
                st.session_state.br_start_sec = br_start
                st.session_state.br_end_sec = br_end
                st.success(f"✅ Zaktualizowano zakres BR: {manual_br_start} - {manual_br_end}")


def _render_br_metrics(
    interval_data: "pd.DataFrame",
    startsec: float,
    endsec: float,
    slope_br: float,
    trend_br_desc: str,
) -> None:
    """Render BR metric cards."""
    duration_sec = int(endsec - startsec)
    avg_br = interval_data["tymebreathrate"].mean()
    min_br = interval_data["tymebreathrate"].min()
    max_br = interval_data["tymebreathrate"].max()
    avg_pace_br = interval_data["pace"].mean() if "pace" in interval_data.columns else 0
    avg_pace_br_min = avg_pace_br / 60.0 if avg_pace_br > 0 else 0

    st.markdown(
        f"##### METRYKI BR: {_format_time(startsec)} - {_format_time(endsec)} ({duration_sec}s)"
    )
    br_m1, br_m2, br_m3, br_m4, br_m5 = st.columns(5)
    br_m1.metric("Śr. BR", f"{avg_br:.1f} /min")
    br_m2.metric("Min BR", f"{min_br:.1f} /min")
    br_m3.metric("Max BR", f"{max_br:.1f} /min")
    br_m4.metric("Śr. Tempo", f"{avg_pace_br_min:.2f} min/km")
    trend_color_br = "inverse" if slope_br > 0.01 else "normal"
    br_m5.metric("Trend BR (Slope)", trend_br_desc, delta=trend_br_desc, delta_color=trend_color_br)


def _build_br_figure(
    target_df: "pd.DataFrame",
    interval_data: "pd.DataFrame",
    startsec: float,
    endsec: float,
    slope_br: float,
    intercept_br: float,
) -> go.Figure:
    """Build the BR chart figure with traces and layout."""
    fig_br = go.Figure()

    fig_br.add_trace(
        go.Scatter(
            x=target_df["time"],
            y=target_df["rr_smooth"],
            customdata=target_df["time_str"],
            mode="lines",
            name="BR (/min)",
            line=dict(color="#00cc96", width=2),
            hovertemplate="<b>Czas:</b> %{customdata}<br><b>BR:</b> %{y:.1f} /min<extra></extra>",
        )
    )

    if "pace_smooth" in target_df.columns:
        pace_min_br = target_df["pace_smooth"] / 60.0
        pace_br_formatted = pace_min_br.apply(
            lambda x: f"{int(x):d}:{int((x % 1) * 60):02d}" if x > 0 else "--:--"
        )
        fig_br.add_trace(
            go.Scatter(
                x=target_df["time"],
                y=pace_min_br,
                customdata=np.stack([target_df["time_str"], pace_br_formatted], axis=-1),
                mode="lines",
                name="Tempo",
                line=dict(color="#00BCD4", width=1),
                yaxis="y2",
                opacity=0.3,
                hovertemplate="<b>Czas:</b> %{customdata[0]}<br><b>Tempo:</b> %{customdata[1]} min/km<extra></extra>",
            )
        )

    fig_br.add_vrect(
        x0=startsec,
        x1=endsec,
        fillcolor="green",
        opacity=0.1,
        layer="below",
        line_width=0,
        annotation_text="BR",
        annotation_position="top left",
    )

    if len(interval_data) > 1:
        trend_line_br = intercept_br + slope_br * interval_data["time"]
        fig_br.add_trace(
            go.Scatter(
                x=interval_data["time"],
                y=trend_line_br,
                mode="lines",
                name="Trend BR",
                line=dict(color="white", width=2, dash="dash"),
                hovertemplate="<b>Trend:</b> %{y:.2f} /min<extra></extra>",
            )
        )

    fig_br.update_layout(
        title="Dynamika Częstości Oddechów vs Tempo",
        xaxis_title="Czas",
        yaxis=dict(title=dict(text="BR (/min)", font=dict(color="#00cc96"))),
        yaxis2=dict(
            title=dict(text="Tempo (min/km)", font=dict(color="#00BCD4")),
            overlaying="y",
            side="right",
            showgrid=False,
            autorange="reversed",
        ),
        legend=dict(x=0.01, y=0.99),
        height=450,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
    )
    return fig_br


def _handle_box_selection(
    selected: dict | None,
    start_key: str,
    end_key: str,
) -> None:
    """Update session state from a plotly box selection, if changed."""
    if not selected or "selection" not in selected or "box" not in selected["selection"]:
        return
    box_data = selected["selection"]["box"]
    if not box_data or len(box_data) == 0:
        return
    x_range = box_data[0].get("x", [])
    if len(x_range) != 2:
        return
    new_start = min(x_range)
    new_end = max(x_range)
    if new_start != st.session_state[start_key] or new_end != st.session_state[end_key]:
        st.session_state[start_key] = new_start
        st.session_state[end_key] = new_end
        st.rerun()


def _render_br_section(target_df):
    """Render BR (Breath Rate) interactive chart section."""
    if "tymebreathrate" not in target_df.columns:
        st.warning("Brak danych Breath Rate (tymebreathrate) w pliku.")
        return

    st.subheader("🫁 Częstość Oddechów (Breath Rate)")
    st.info(
        "💡 **ANALIZA BR:** Zaznacz obszar na wykresie (kliknij i przeciągnij), aby sprawdzić statystyki i trend."
    )

    _render_br_manual_input()

    br_startsec = st.session_state.br_start_sec
    br_endsec = st.session_state.br_end_sec
    br_mask = (target_df["time"] >= br_startsec) & (target_df["time"] <= br_endsec)
    br_interval_data = target_df.loc[br_mask]

    if br_interval_data.empty or br_endsec <= br_startsec:
        return

    slope_br, intercept_br, trend_br_desc = _compute_br_trend(br_interval_data)

    _render_br_metrics(br_interval_data, br_startsec, br_endsec, slope_br, trend_br_desc)

    fig_br = _build_br_figure(
        target_df, br_interval_data, br_startsec, br_endsec, slope_br, intercept_br
    )

    selected_br = st.plotly_chart(
        fig_br,
        use_container_width=True,
        key="br_chart",
        on_select="rerun",
        selection_mode="box",
    )

    _handle_box_selection(selected_br, "br_start_sec", "br_end_sec")


def _compute_tv_stats(
    interval_data: "pd.DataFrame",
) -> tuple[float, float, float, float, float, str, "pd.DataFrame"]:
    """Compute tidal volume statistics and trend.

    Returns (avg_tv, min_tv, max_tv, slope, intercept, trend_desc, tv_valid).
    """
    tv_clean = (
        interval_data["tidal_volume"].replace([float("inf"), float("-inf")], float("nan")).dropna()
    )
    if len(tv_clean) > 0:
        avg_tv = tv_clean.mean()
        min_tv = tv_clean.min()
        max_tv = tv_clean.max()
    else:
        avg_tv = min_tv = max_tv = 0.0

    tv_valid = interval_data[["time", "tidal_volume"]].dropna()
    tv_valid = tv_valid[~tv_valid["tidal_volume"].isin([float("inf"), float("-inf")])]

    if len(tv_valid) > 1:
        slope, intercept, _, _, _ = stats.linregress(tv_valid["time"], tv_valid["tidal_volume"])
        trend_desc = f"{slope:.5f} L/s"
    else:
        slope = 0.0
        intercept = 0.0
        trend_desc = "N/A"

    return avg_tv, min_tv, max_tv, slope, intercept, trend_desc, tv_valid


def _render_tv_metrics(
    interval_data: "pd.DataFrame",
    startsec: float,
    endsec: float,
    avg_tv: float,
    min_tv: float,
    max_tv: float,
    slope_tv: float,
    trend_tv_desc: str,
) -> None:
    """Render tidal volume metric cards."""
    duration_sec = int(endsec - startsec)
    avg_pace_tv = interval_data["pace"].mean() if "pace" in interval_data.columns else 0
    avg_pace_tv_min = avg_pace_tv / 60.0 if avg_pace_tv > 0 else 0

    st.markdown(
        f"##### METRYKI VT: {_format_time(startsec)} - {_format_time(endsec)} ({duration_sec}s)"
    )
    tv_m1, tv_m2, tv_m3, tv_m4, tv_m5 = st.columns(5)
    tv_m1.metric("Śr. VT", f"{avg_tv:.2f} L")
    tv_m2.metric("Min VT", f"{min_tv:.2f} L")
    tv_m3.metric("Max VT", f"{max_tv:.2f} L")
    tv_m4.metric("Śr. Tempo", f"{avg_pace_tv_min:.2f} min/km")
    trend_color_tv = "inverse" if slope_tv < -0.0001 else "normal"
    tv_m5.metric("Trend VT (Slope)", trend_tv_desc, delta=trend_tv_desc, delta_color=trend_color_tv)


def _build_tv_figure(
    target_df: "pd.DataFrame",
    tv_valid: "pd.DataFrame",
    startsec: float,
    endsec: float,
    slope_tv: float,
    intercept_tv: float,
) -> go.Figure:
    """Build the Tidal Volume chart figure with traces and layout."""
    fig_tv = go.Figure()

    fig_tv.add_trace(
        go.Scatter(
            x=target_df["time"],
            y=target_df["tv_smooth"],
            customdata=target_df["time_str"],
            mode="lines",
            name="VT (L)",
            line=dict(color="#ab63fa", width=2),
            hovertemplate="<b>Czas:</b> %{customdata}<br><b>VT:</b> %{y:.2f} L<extra></extra>",
        )
    )

    if "pace_smooth" in target_df.columns:
        pace_min_tv = target_df["pace_smooth"] / 60.0
        pace_tv_formatted = pace_min_tv.apply(
            lambda x: f"{int(x):d}:{int((x % 1) * 60):02d}" if x > 0 else "--:--"
        )
        fig_tv.add_trace(
            go.Scatter(
                x=target_df["time"],
                y=pace_min_tv,
                customdata=np.stack([target_df["time_str"], pace_tv_formatted], axis=-1),
                mode="lines",
                name="Tempo",
                line=dict(color="#00BCD4", width=1),
                yaxis="y2",
                opacity=0.3,
                hovertemplate="<b>Czas:</b> %{customdata[0]}<br><b>Tempo:</b> %{customdata[1]} min/km<extra></extra>",
            )
        )

    fig_tv.add_vrect(
        x0=startsec,
        x1=endsec,
        fillcolor="purple",
        opacity=0.1,
        layer="below",
        line_width=0,
        annotation_text="VT",
        annotation_position="top left",
    )

    if len(tv_valid) > 1:
        trend_line_tv = intercept_tv + slope_tv * tv_valid["time"]
        fig_tv.add_trace(
            go.Scatter(
                x=tv_valid["time"],
                y=trend_line_tv,
                mode="lines",
                name="Trend VT",
                line=dict(color="white", width=2, dash="dash"),
                hovertemplate="<b>Trend:</b> %{y:.3f} L<extra></extra>",
            )
        )

    fig_tv.update_layout(
        title="Dynamika Objętości Oddechowej vs Tempo",
        xaxis_title="Czas",
        yaxis=dict(title=dict(text="VT (L)", font=dict(color="#ab63fa"))),
        yaxis2=dict(
            title=dict(text="Tempo (min/km)", font=dict(color="#00BCD4")),
            overlaying="y",
            side="right",
            showgrid=False,
            autorange="reversed",
        ),
        legend=dict(x=0.01, y=0.99),
        height=450,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
    )
    return fig_tv


def _render_tidal_volume_section(target_df):
    """Render Tidal Volume interactive chart section."""
    if "tidal_volume" not in target_df.columns:
        st.warning(
            "Brak danych do obliczenia Tidal Volume (wymagane: tymeventilation i tymebreathrate)."
        )
        return

    st.subheader("💨 Objętość Oddechowa (Tidal Volume)")
    st.info(
        "💡 **ANALIZA VT:** Zaznacz obszar na wykresie (kliknij i przeciągnij), aby sprawdzić statystyki i trend. VT = VE / BR."
    )

    with st.expander("🔧 Ręczne wprowadzenie zakresu czasowego VT", expanded=False):
        col_tv_1, col_tv_2 = st.columns(2)
        with col_tv_1:
            manual_tv_start = st.text_input(
                "Start Interwału (hh:mm:ss)", value="00:10:00", key="tv_manual_start"
            )
        with col_tv_2:
            manual_tv_end = st.text_input(
                "Koniec Interwału (hh:mm:ss)", value="00:20:00", key="tv_manual_end"
            )

        if st.button("Zastosuj ręczny zakres", key="btn_tv_manual"):
            tv_start = _parse_time_to_seconds(manual_tv_start)
            tv_end = _parse_time_to_seconds(manual_tv_end)
            if tv_start is not None and tv_end is not None:
                st.session_state.tv_start_sec = tv_start
                st.session_state.tv_end_sec = tv_end
                st.success(f"✅ Zaktualizowano zakres VT: {manual_tv_start} - {manual_tv_end}")

    tv_startsec = st.session_state.tv_start_sec
    tv_endsec = st.session_state.tv_end_sec
    tv_mask = (target_df["time"] >= tv_startsec) & (target_df["time"] <= tv_endsec)
    tv_interval_data = target_df.loc[tv_mask]

    if tv_interval_data.empty or tv_endsec <= tv_startsec:
        return

    avg_tv, min_tv, max_tv, slope_tv, intercept_tv, trend_tv_desc, tv_valid = _compute_tv_stats(
        tv_interval_data
    )

    _render_tv_metrics(
        tv_interval_data, tv_startsec, tv_endsec, avg_tv, min_tv, max_tv, slope_tv, trend_tv_desc
    )

    fig_tv = _build_tv_figure(target_df, tv_valid, tv_startsec, tv_endsec, slope_tv, intercept_tv)

    selected_tv = st.plotly_chart(
        fig_tv,
        use_container_width=True,
        key="tv_chart",
        on_select="rerun",
        selection_mode="box",
    )

    _handle_box_selection(selected_tv, "tv_start_sec", "tv_end_sec")
