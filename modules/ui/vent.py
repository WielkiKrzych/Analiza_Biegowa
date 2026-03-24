import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy import stats
from modules.calculations.quality import check_signal_quality


def _parse_time_to_seconds(t_str):
    """Parse time string (hh:mm:ss or mm:ss) to seconds."""
    try:
        parts = list(map(int, t_str.split(":")))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 1:
            return parts[0]
    except (ValueError, AttributeError):
        return None
    return None


def _format_time(s):
    """Format seconds to hh:mm:ss or mm:ss string."""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _render_br_only_section(target_df):
    """Render BR-only analysis when VE data is absent but BR exists.

    Returns True if this section was rendered (caller should return early).
    Returns False if caller should continue with full VE analysis.
    """
    has_ve = "tymeventilation" in target_df.columns
    has_br = "tymebreathrate" in target_df.columns

    if has_ve or not has_br:
        return False

    from modules.calculations.br_analysis import (
        classify_br_zone,
        calculate_br_zones_time,
        detect_vt_from_br,
    )

    target_df = target_df.copy()
    br_series = target_df["tymebreathrate"].dropna()

    st.subheader("🫁 Analiza Częstości Oddechów (BR)")
    st.caption(
        "Dane z zegarka (Garmin/COROS). Brak pełnej wentylacji (VE) — analiza oparta wyłącznie na BR."
    )

    if len(br_series) > 60:
        col_b1, col_b2, col_b3 = st.columns(3)
        col_b1.metric("Śr. BR", f"{br_series.mean():.0f} oddechów/min")
        col_b2.metric("Max BR", f"{br_series.max():.0f} oddechów/min")
        col_b3.metric("Min BR", f"{br_series.min():.0f} oddechów/min")

        # BR zones
        zones_time = calculate_br_zones_time(br_series)
        total_sec = sum(zones_time.values())
        if total_sec > 0:
            import plotly.graph_objects as go_br

            zone_names = list(zones_time.keys())
            zone_pcts = [zones_time[z] / total_sec * 100 for z in zone_names]
            zone_colors = ["#2ecc71", "#3498db", "#f1c40f", "#e67e22", "#e74c3c"]

            fig_brz = go.Figure(
                data=[
                    go.Bar(
                        x=zone_pcts,
                        y=zone_names,
                        orientation="h",
                        marker_color=zone_colors[: len(zone_names)],
                        text=[f"{p:.0f}%" for p in zone_pcts],
                        textposition="auto",
                    )
                ]
            )
            fig_brz.update_layout(
                template="plotly_dark",
                title="Czas w strefach BR (npj Digital Medicine 2024)",
                xaxis_title="% czasu",
                height=250,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_brz, use_container_width=True)

        # VT detection from BR
        vt_result = detect_vt_from_br(br_series)
        if vt_result.get("vt1_index") is not None:
            col_vt1, col_vt2 = st.columns(2)
            vt1_time = vt_result["vt1_index"]
            col_vt1.metric(
                "VT1 (z BR)",
                f"{vt1_time // 60}:{vt1_time % 60:02d}",
                help="Próg wentylacyjny 1 wykryty z punktu załamania BR",
            )
            if vt_result.get("vt2_index") is not None:
                vt2_time = vt_result["vt2_index"]
                col_vt2.metric(
                    "VT2 (z BR)",
                    f"{vt2_time // 60}:{vt2_time % 60:02d}",
                    help="Próg wentylacyjny 2 wykryty z drugiego punktu załamania BR",
                )
            else:
                col_vt2.metric("VT2 (z BR)", "Nie wykryto")

        # BR time series chart
        if "time" in target_df.columns:
            br_smooth = br_series.rolling(window=15, center=True, min_periods=1).median()
            time_min = target_df["time"].iloc[: len(br_smooth)] / 60.0

            fig_br_ts = go.Figure()
            fig_br_ts.add_trace(
                go.Scatter(
                    x=time_min,
                    y=br_smooth.values,
                    name="BR (oddechów/min)",
                    line=dict(color="#3498db", width=2),
                )
            )
            fig_br_ts.update_layout(
                template="plotly_dark",
                title="Częstość oddechów w czasie",
                xaxis_title="Czas [min]",
                yaxis_title="BR [oddechów/min]",
                height=350,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_br_ts, use_container_width=True)
    else:
        st.info("Za mało danych BR do analizy (min. 60 próbek).")

    return True


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


def _render_br_section(target_df):
    """Render BR (Breath Rate) interactive chart section."""
    if "tymebreathrate" not in target_df.columns:
        st.warning("Brak danych Breath Rate (tymebreathrate) w pliku.")
        return

    st.subheader("🫁 Częstość Oddechów (Breath Rate)")
    st.info(
        "💡 **ANALIZA BR:** Zaznacz obszar na wykresie (kliknij i przeciągnij), aby sprawdzić statystyki i trend."
    )

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

    br_startsec = st.session_state.br_start_sec
    br_endsec = st.session_state.br_end_sec
    br_mask = (target_df["time"] >= br_startsec) & (target_df["time"] <= br_endsec)
    br_interval_data = target_df.loc[br_mask]

    if br_interval_data.empty or br_endsec <= br_startsec:
        return

    br_duration_sec = int(br_endsec - br_startsec)

    avg_br = br_interval_data["tymebreathrate"].mean()
    min_br = br_interval_data["tymebreathrate"].min()
    max_br = br_interval_data["tymebreathrate"].max()
    avg_pace_br = br_interval_data["pace"].mean() if "pace" in br_interval_data.columns else 0
    avg_pace_br_min = avg_pace_br / 60.0 if avg_pace_br > 0 else 0

    if len(br_interval_data) > 1:
        slope_br, intercept_br, _, _, _ = stats.linregress(
            br_interval_data["time"], br_interval_data["tymebreathrate"]
        )
        trend_br_desc = f"{slope_br:.4f} /s"
    else:
        slope_br = 0
        intercept_br = 0
        trend_br_desc = "N/A"

    st.markdown(
        f"##### METRYKI BR: {_format_time(br_startsec)} - {_format_time(br_endsec)} ({br_duration_sec}s)"
    )
    br_m1, br_m2, br_m3, br_m4, br_m5 = st.columns(5)
    br_m1.metric("Śr. BR", f"{avg_br:.1f} /min")
    br_m2.metric("Min BR", f"{min_br:.1f} /min")
    br_m3.metric("Max BR", f"{max_br:.1f} /min")
    br_m4.metric("Śr. Tempo", f"{avg_pace_br_min:.2f} min/km")
    trend_color_br = "inverse" if slope_br > 0.01 else "normal"
    br_m5.metric("Trend BR (Slope)", trend_br_desc, delta=trend_br_desc, delta_color=trend_color_br)

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
        x0=br_startsec,
        x1=br_endsec,
        fillcolor="green",
        opacity=0.1,
        layer="below",
        line_width=0,
        annotation_text="BR",
        annotation_position="top left",
    )

    if len(br_interval_data) > 1:
        trend_line_br = intercept_br + slope_br * br_interval_data["time"]
        fig_br.add_trace(
            go.Scatter(
                x=br_interval_data["time"],
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

    selected_br = st.plotly_chart(
        fig_br,
        use_container_width=True,
        key="br_chart",
        on_select="rerun",
        selection_mode="box",
    )

    if selected_br and "selection" in selected_br and "box" in selected_br["selection"]:
        box_data_br = selected_br["selection"]["box"]
        if box_data_br and len(box_data_br) > 0:
            x_range_br = box_data_br[0].get("x", [])
            if len(x_range_br) == 2:
                new_br_start = min(x_range_br)
                new_br_end = max(x_range_br)
                if (
                    new_br_start != st.session_state.br_start_sec
                    or new_br_end != st.session_state.br_end_sec
                ):
                    st.session_state.br_start_sec = new_br_start
                    st.session_state.br_end_sec = new_br_end
                    st.rerun()


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

    tv_duration_sec = int(tv_endsec - tv_startsec)

    tv_clean = (
        tv_interval_data["tidal_volume"]
        .replace([float("inf"), float("-inf")], float("nan"))
        .dropna()
    )
    if len(tv_clean) > 0:
        avg_tv = tv_clean.mean()
        min_tv = tv_clean.min()
        max_tv = tv_clean.max()
    else:
        avg_tv = min_tv = max_tv = 0
    avg_pace_tv = tv_interval_data["pace"].mean() if "pace" in tv_interval_data.columns else 0
    avg_pace_tv_min = avg_pace_tv / 60.0 if avg_pace_tv > 0 else 0

    tv_valid = tv_interval_data[["time", "tidal_volume"]].dropna()
    tv_valid = tv_valid[~tv_valid["tidal_volume"].isin([float("inf"), float("-inf")])]
    if len(tv_valid) > 1:
        slope_tv, intercept_tv, _, _, _ = stats.linregress(
            tv_valid["time"], tv_valid["tidal_volume"]
        )
        trend_tv_desc = f"{slope_tv:.5f} L/s"
    else:
        slope_tv = 0
        intercept_tv = 0
        trend_tv_desc = "N/A"

    st.markdown(
        f"##### METRYKI VT: {_format_time(tv_startsec)} - {_format_time(tv_endsec)} ({tv_duration_sec}s)"
    )
    tv_m1, tv_m2, tv_m3, tv_m4, tv_m5 = st.columns(5)
    tv_m1.metric("Śr. VT", f"{avg_tv:.2f} L")
    tv_m2.metric("Min VT", f"{min_tv:.2f} L")
    tv_m3.metric("Max VT", f"{max_tv:.2f} L")
    tv_m4.metric("Śr. Tempo", f"{avg_pace_tv_min:.2f} min/km")
    trend_color_tv = "inverse" if slope_tv < -0.0001 else "normal"
    tv_m5.metric("Trend VT (Slope)", trend_tv_desc, delta=trend_tv_desc, delta_color=trend_color_tv)

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
        x0=tv_startsec,
        x1=tv_endsec,
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

    selected_tv = st.plotly_chart(
        fig_tv,
        use_container_width=True,
        key="tv_chart",
        on_select="rerun",
        selection_mode="box",
    )

    if selected_tv and "selection" in selected_tv and "box" in selected_tv["selection"]:
        box_data_tv = selected_tv["selection"]["box"]
        if box_data_tv and len(box_data_tv) > 0:
            x_range_tv = box_data_tv[0].get("x", [])
            if len(x_range_tv) == 2:
                new_tv_start = min(x_range_tv)
                new_tv_end = max(x_range_tv)
                if (
                    new_tv_start != st.session_state.tv_start_sec
                    or new_tv_end != st.session_state.tv_end_sec
                ):
                    st.session_state.tv_start_sec = new_tv_start
                    st.session_state.tv_end_sec = new_tv_end
                    st.rerun()


def _render_legacy_tools(interval_data):
    """Render legacy raw data analysis tools."""
    with st.expander("🔧 Szczegółowa Analiza (Surowe Dane)", expanded=False):
        st.markdown("### Surowe Dane i Korelacje")

        if "watts" in interval_data.columns:
            interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                "%H:%M:%S"
            )

            fig_scatter = go.Figure()
            fig_scatter.add_trace(
                go.Scatter(
                    x=interval_data["watts"],
                    y=interval_data["tymeventilation"],
                    customdata=interval_time_str,
                    mode="markers",
                    marker=dict(
                        size=6,
                        color=interval_data["time"],
                        colorscale="Viridis",
                        showscale=True,
                        colorbar=dict(title="Czas (s)"),
                    ),
                    name="VE vs Power",
                    hovertemplate="<b>Czas:</b> %{customdata}<br><b>Moc:</b> %{x:.0f} W<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
                )
            )
            fig_scatter.update_layout(
                title="Korelacja: VE vs Moc",
                xaxis_title="Moc [W]",
                yaxis_title="VE (L/min)",
                height=400,
                hovermode="closest",
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        if "tymebreathrate" in interval_data.columns:
            st.subheader("Częstość Oddechów (Breathing Rate)")

            interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime(
                "%H:%M:%S"
            )

            fig_br = go.Figure()
            fig_br.add_trace(
                go.Scatter(
                    x=interval_data["time"],
                    y=interval_data["tymebreathrate"],
                    customdata=interval_time_str,
                    mode="lines",
                    name="BR",
                    line=dict(color="#00cc96", width=2),
                    hovertemplate="<b>Czas:</b> %{customdata}<br><b>BR:</b> %{y:.1f} /min<extra></extra>",
                )
            )
            fig_br.update_layout(
                title="Breathing Rate",
                xaxis_title="Czas",
                yaxis_title="BR (/min)",
                height=300,
                hovermode="x unified",
            )
            st.plotly_chart(fig_br, use_container_width=True)

        st.subheader("Wentylacja Minutowa (VE)")

        interval_time_str = pd.to_datetime(interval_data["time"], unit="s").dt.strftime("%H:%M:%S")

        fig_ve = go.Figure()
        fig_ve.add_trace(
            go.Scatter(
                x=interval_data["time"],
                y=interval_data["tymeventilation"],
                customdata=interval_time_str,
                mode="lines",
                name="VE",
                line=dict(color="#ffa15a", width=2),
                hovertemplate="<b>Czas:</b> %{customdata}<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
            )
        )
        fig_ve.update_layout(
            title="Minute Ventilation (VE)",
            xaxis_title="Czas",
            yaxis_title="VE (L/min)",
            height=300,
            hovermode="x unified",
        )
        st.plotly_chart(fig_ve, use_container_width=True)


def render_vent_tab(target_df, training_notes, uploaded_file_name):
    """Analiza wentylacji dla dowolnego treningu - struktura jak SmO2."""
    st.header("Analiza Wentylacji (VE & Breathing Rate)")
    st.markdown(
        "Analiza dynamiki oddechu dla dowolnego treningu. Szukaj anomalii w wentylacji i częstości oddechów."
    )

    # 1. Przygotowanie danych
    if target_df is None or target_df.empty:
        st.error("Brak danych. Najpierw wgraj plik w sidebar.")
        return

    if "time" not in target_df.columns:
        st.error("Brak kolumny 'time' w danych!")
        return

    has_ve = "tymeventilation" in target_df.columns
    has_br = "tymebreathrate" in target_df.columns

    if not has_ve and not has_br:
        st.info(
            """
        ℹ️ **Brak danych wentylacji (VE) i częstości oddechów (BR)**

        Aby uzyskać analizę wentylacyjną, potrzebujesz czujnika wentylacji
        (np. VO2 Master, Cosmed) lub zegarka z pomiarem BR (Garmin, COROS).

        **Twoje dane zawierają:**
        """
            + ", ".join(
                [
                    f"`{col}`"
                    for col in target_df.columns
                    if col in ["watts", "heartrate", "smo2", "cadence", "core_temperature"]
                ]
            )
            + """

        💡 **Analiza fizjologii mięśniowej jest dostępna w zakładce 🩸 SmO2**
        """
        )
        return

    if _render_br_only_section(target_df):
        return

    # Work on a copy to avoid mutating the caller's DataFrame
    target_df = target_df.copy()
    # FIX: Use 15s median (more robust to outliers than 5s mean)
    if "pace_smooth" not in target_df.columns and "pace" in target_df.columns:
        target_df["pace_smooth"] = target_df["pace"].rolling(window=15, center=True).median()
    if "ve_smooth" not in target_df.columns:
        target_df["ve_smooth"] = (
            target_df["tymeventilation"].rolling(window=15, center=True).median()
        )
    if "tymebreathrate" in target_df.columns and "rr_smooth" not in target_df.columns:
        target_df["rr_smooth"] = (
            target_df["tymebreathrate"].rolling(window=15, center=True).median()
        )
    # Tidal Volume = VE / BR (objętość oddechowa)
    if "tymebreathrate" in target_df.columns and "tymeventilation" in target_df.columns:
        # Avoid division by zero
        target_df["tidal_volume"] = target_df["tymeventilation"] / target_df[
            "tymebreathrate"
        ].replace(0, float("nan"))
        target_df["tv_smooth"] = target_df["tidal_volume"].rolling(window=10, center=True).mean()

    target_df["time_str"] = pd.to_datetime(target_df["time"], unit="s").dt.strftime("%H:%M:%S")

    # Check Quality
    qual_res = check_signal_quality(target_df["tymeventilation"], "VE", (0, 300))
    if not qual_res["is_valid"]:
        st.warning(f"⚠️ **Niska Jakość Sygnału VE (Score: {qual_res['score']})**")
        for issue in qual_res["issues"]:
            st.caption(f"❌ {issue}")

    # Inicjalizacja session_state
    if "vent_start_sec" not in st.session_state:
        st.session_state.vent_start_sec = 600
    if "vent_end_sec" not in st.session_state:
        st.session_state.vent_end_sec = 1200
    # BR chart range
    if "br_start_sec" not in st.session_state:
        st.session_state.br_start_sec = 600
    if "br_end_sec" not in st.session_state:
        st.session_state.br_end_sec = 1200
    # Tidal Volume chart range
    if "tv_start_sec" not in st.session_state:
        st.session_state.tv_start_sec = 600
    if "tv_end_sec" not in st.session_state:
        st.session_state.tv_end_sec = 1200

    # ===== NOTATKI VENTILATION =====
    with st.expander("📝 Dodaj Notatkę do tej Analizy", expanded=False):
        note_col1, note_col2 = st.columns([1, 2])
        with note_col1:
            note_time = st.number_input(
                "Czas (min)",
                min_value=0.0,
                max_value=float(len(target_df) / 60) if len(target_df) > 0 else 60.0,
                value=float(len(target_df) / 120) if len(target_df) > 0 else 15.0,
                step=0.5,
                key="vent_note_time",
            )
        with note_col2:
            note_text = st.text_input(
                "Notatka",
                key="vent_note_text",
                placeholder="Np. 'VE jump', 'Spłycenie oddechu', 'Hiperwentylacja'",
            )

        if st.button("➕ Dodaj Notatkę", key="vent_add_note"):
            if note_text:
                training_notes.add_note(uploaded_file_name, note_time, "ventilation", note_text)
                st.success(f"✅ Notatka: {note_text} @ {note_time:.1f} min")
            else:
                st.warning("Wpisz tekst notatki!")

    # Wyświetl istniejące notatki
    existing_notes = training_notes.get_notes_for_metric(uploaded_file_name, "ventilation")
    if existing_notes:
        st.subheader("📋 Notatki Wentylacji")
        for idx, note in enumerate(existing_notes):
            col_note, col_del = st.columns([4, 1])
            with col_note:
                st.info(f"⏱️ **{note['time_minute']:.1f} min** | {note['text']}")
            with col_del:
                if st.button("🗑️", key=f"del_vent_note_{idx}"):
                    training_notes.delete_note(uploaded_file_name, idx)
                    st.rerun()

    st.markdown("---")

    st.info(
        "💡 **ANALIZA MANUALNA:** Zaznacz obszar na wykresie poniżej (kliknij i przeciągnij), aby sprawdzić nachylenie lokalne."
    )

    with st.expander("🔧 Ręczne wprowadzenie zakresu czasowego (opcjonalne)", expanded=False):
        col_inp_1, col_inp_2 = st.columns(2)
        with col_inp_1:
            manual_start = st.text_input(
                "Start Interwału (hh:mm:ss)", value="00:10:00", key="vent_manual_start"
            )
        with col_inp_2:
            manual_end = st.text_input(
                "Koniec Interwału (hh:mm:ss)", value="00:20:00", key="vent_manual_end"
            )

        if st.button("Zastosuj ręczny zakres", key="btn_vent_manual"):
            manual_start_sec = _parse_time_to_seconds(manual_start)
            manual_end_sec = _parse_time_to_seconds(manual_end)
            if manual_start_sec is not None and manual_end_sec is not None:
                st.session_state.vent_start_sec = manual_start_sec
                st.session_state.vent_end_sec = manual_end_sec
                st.success(f"✅ Zaktualizowano zakres: {manual_start} - {manual_end}")

    startsec = st.session_state.vent_start_sec
    endsec = st.session_state.vent_end_sec

    # Wycinanie danych
    mask = (target_df["time"] >= startsec) & (target_df["time"] <= endsec)
    interval_data = target_df.loc[mask]

    if not interval_data.empty and endsec > startsec:
        duration_sec = int(endsec - startsec)

        # Obliczenia
        avg_pace = interval_data["pace"].mean() if "pace" in interval_data.columns else 0
        avg_pace_min = avg_pace / 60.0 if avg_pace > 0 else 0
        avg_ve = interval_data["tymeventilation"].mean()
        avg_rr = (
            interval_data["tymebreathrate"].mean()
            if "tymebreathrate" in interval_data.columns
            else 0
        )

        # Trend (Slope) dla VE
        if len(interval_data) > 1:
            slope_ve, intercept_ve, _, _, _ = stats.linregress(
                interval_data["time"], interval_data["tymeventilation"]
            )
            trend_desc = f"{slope_ve:.4f} (L/min)/s"
        else:
            slope_ve = 0
            intercept_ve = 0
            trend_desc = "N/A"

        st.subheader(
            f"METRYKI MANUALNE: {_format_time(startsec)} - {_format_time(endsec)} ({duration_sec}s)"
        )

        m1, m2, m3, m4 = st.columns(4)
        pace_str = (
            f"{int(avg_pace_min):02d}:{int((avg_pace_min % 1) * 60):02d}"
            if avg_pace > 0
            else "--:--"
        )
        m1.metric("Śr. Tempo", pace_str)
        m2.metric("Śr. VE", f"{avg_ve:.1f} L/min")
        m3.metric("Śr. BR", f"{avg_rr:.1f} /min")

        trend_color = "inverse" if slope_ve > 0.05 else "normal"
        m4.metric("Trend VE (Slope)", trend_desc, delta=trend_desc, delta_color=trend_color)

        _render_ve_section(target_df, startsec, endsec, interval_data, slope_ve, intercept_ve)

        st.markdown("---")
        _render_br_section(target_df)

        st.markdown("---")
        _render_tidal_volume_section(target_df)

        st.markdown("---")
        _render_legacy_tools(interval_data)

    else:
        st.warning("Brak danych w wybranym zakresie.")

    # ===== TEORIA =====
    with st.expander("🫁 TEORIA: Interpretacja Wentylacji", expanded=False):
        st.markdown("""
        ## Co oznacza Wentylacja (VE)?
        
        **VE (Minute Ventilation)** to objętość powietrza wdychanego/wydychanego na minutę.
        Mierzona przez sensory oddechowe np. **CORE, Tyme Wear, Garmin HRM-Pro (estymacja)**.
        
        | Parametr | Opis | Jednostka |
        |----------|------|-----------|
        | **VE** | Wentylacja minutowa | L/min |
        | **BR / RR** | Częstość oddechów | oddechy/min |
        | **VT** | Objętość oddechowa (VE/BR) | L |
        
        ---
        
        ## Strefy VE i ich znaczenie
        
        | VE (L/min) | Interpretacja | Typ wysiłku |
        |------------|---------------|-------------|
        | **20-40** | Spokojny oddech | Recovery, rozgrzewka |
        | **40-80** | Umiarkowany wysiłek | Tempo, Sweet Spot |
        | **80-120** | Intensywny wysiłek | Threshold, VO2max |
        | **> 120** | Maksymalny wysiłek | Sprint, test wyczerpania |
        
        ---
        
        ## Trend VE (Slope) - Co oznacza nachylenie?
        
        | Trend | Wartość | Interpretacja |
        |-------|---------|---------------|
        | 🟢 **Stabilny** | ~ 0 | Steady state, VE odpowiada obciążeniu |
        | 🟡 **Łagodny wzrost** | 0.01-0.05 | Normalna adaptacja do wysiłku |
        | 🔴 **Gwałtowny wzrost** | > 0.05 | Możliwy próg wentylacyjny (VT1/VT2) |
        
        ---
        
        ## BR (Breathing Rate) - Częstość oddechów
        
        **BR** odzwierciedla strategię oddechową:
        
        - **⬆️ Wzrost BR przy stałej VE**: Płytszy oddech, możliwe zmęczenie przepony
        - **⬇️ Spadek BR przy stałej VE**: Głębszy oddech, lepsza efektywność
        - **➡️ Stabilny BR**: Optymalna strategia oddechowa
        
        ### Praktyczny przykład:
        - **VE=100, BR=30**: Objętość oddechowa = 3.3L (głęboki oddech)
        - **VE=100, BR=50**: Objętość oddechowa = 2.0L (płytki oddech - nieefektywne!)
        
        ---
        
        ## Zastosowania Treningowe VE
        
        ### 1️⃣ Detekcja Progów (VT1, VT2)
        - **VT1 (Próg tlenowy)**: Pierwszy nieliniowy skok VE względem mocy
        - **VT2 (Próg beztlenowy)**: Drugi, gwałtowniejszy skok VE
        - 🔗 Użyj zakładki **"Ventilation - Progi"** do automatycznej detekcji
        
        ### 2️⃣ Kontrola Intensywności
        - Jeśli VE rośnie szybciej niż moc → zbliżasz się do progu
        - Stabilna VE przy stałej mocy → jesteś w strefie tlenowej
        
        ### 3️⃣ Efektywność Oddechowa
        - Optymalna częstość BR: 20-40 oddechów/min
        - Powyżej 50/min: możliwe zmęczenie, stres, lub panika
        
        ### 4️⃣ Detekcja Zmęczenia
        - **BR rośnie przy spadku VE**: Zmęczenie przepony
        - **VE fluktuuje chaotycznie**: Możliwe odwodnienie lub hipoglikemia
        
        ---
        
        ## Korelacja VE vs Moc
        
        Wykres scatter pokazuje zależność między mocą a wentylacją:
        
        - **Liniowa zależność**: Normalna odpowiedź fizjologiczna
        - **Punkt załamania**: Próg wentylacyjny (VT)
        - **Stroma krzywa**: Niska wydolność, szybkie zadyszenie
        
        ### Kolor punktów (czas):
        - **Wczesne punkty (ciemne)**: Początek treningu
        - **Późne punkty (jasne)**: Koniec treningu, kumulacja zmęczenia
        
        ---
        
        ## Limitacje Pomiaru VE
        
        ⚠️ **Czynniki wpływające na dokładność:**
        - Pozycja sensora na klatce piersiowej
        - Oddychanie ustami vs nosem
        - Warunki atmosferyczne (wysokość, wilgotność)
        - Intensywność mowy podczas jazdy
        
        💡 **Wskazówka**: Dla dokładnej detekcji progów wykonaj Test Stopniowany (Ramp Test)!
        """)
