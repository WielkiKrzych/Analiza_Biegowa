"""
VE Profile Chart Generator.

Generates ventilation (VE) profile over time with VT1/VT2 thresholds.
Input: Canonical JSON report + Source DataFrame
Output: PNG file

Chart shows:
- Ventilation (VE) on Left Y-Axis
- Pace (min/km) on Right Y-Axis (background)
- VT1 and VT2 vertical lines
- Footer with test_id and method version
"""

from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import create_empty_figure, get_color, save_figure


def _sec_to_min(pace_sec: float) -> float:
    """Convert pace from sec/km to min/km for axis display."""
    return pace_sec / 60.0 if pace_sec and pace_sec > 0 else 0


def _normalize_config(config: Optional[Any]) -> Dict[str, Any]:
    """Extract config dict from object, dict, or None."""
    if hasattr(config, "__dict__"):
        return config.__dict__
    if isinstance(config, dict):
        return config
    return {}


def _find_first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Return the first matching column name from candidates."""
    return next((c for c in candidates if c in df.columns), None)


def _extract_ve_from_df(
    source_df: pd.DataFrame,
) -> Tuple[List[float], List[float], List[float]]:
    """Extract time, VE, and pace data from a source DataFrame."""
    df = source_df.copy()
    df.columns = df.columns.str.lower().str.strip()

    ve_col = _find_first_col(df, ["tymeventilation", "ve", "ventilation", "ve_smooth"])
    pace_col = _find_first_col(df, ["pace", "pace_smooth", "pace_sec_per_km", "tempo"])
    time_col = _find_first_col(df, ["time", "seconds"])

    if not ve_col or not time_col:
        return [], [], []

    time_data = df[time_col].tolist()
    ve_data = df[ve_col].fillna(0).tolist()
    pace_sec_data = df[pace_col].fillna(0).tolist() if pace_col else []
    pace_data = [_sec_to_min(p) for p in pace_sec_data] if pace_col else []
    return time_data, ve_data, pace_data


def _extract_ve_from_json(
    time_series: Dict[str, Any],
) -> Tuple[List[float], List[float], List[float]]:
    """Extract time, VE, and pace data from JSON time_series."""
    time_data = time_series.get("time_sec", [])
    ve_data = time_series.get("ve_lmin", [])
    pace_sec = time_series.get("pace_sec_per_km", time_series.get("pace", []))
    pace_data = [_sec_to_min(p) for p in pace_sec] if pace_sec else []
    return time_data, ve_data, pace_data


def _find_vt_time(
    time_data: List[float],
    time_series: Dict[str, Any],
    vt_pace_sec: float,
) -> Optional[float]:
    """Find the first time point where pace reaches the VT threshold."""
    if not vt_pace_sec:
        return None
    pace_sec_list = time_series.get("pace_sec_per_km", time_series.get("pace", []))
    for t, p_sec in zip(time_data, pace_sec_list, strict=False):
        if p_sec >= vt_pace_sec:
            return t
    return None


def _plot_pace_background(
    ax2: plt.Axes,
    time_min: List[float],
    pace_data: List[float],
    font_size: int,
) -> None:
    """Plot pace trace on secondary axis with inverted Y."""
    if not pace_data:
        return
    ax2.plot(time_min, pace_data, color=get_color("pace"), alpha=0.3, linewidth=1, label="Tempo")
    ax2.fill_between(time_min, pace_data, color=get_color("pace"), alpha=0.05)
    ax2.set_ylabel("Tempo [min/km]", color=get_color("pace"), fontsize=font_size)
    ax2.tick_params(axis="y", labelcolor=get_color("pace"))
    ax2.invert_yaxis()


def _plot_vt_line(
    ax: plt.Axes,
    vt_time_min: Optional[float],
    vt_pace_min: Optional[float],
    ve_max: float,
    label: str,
) -> None:
    """Plot a vertical VT line with label annotation."""
    if not vt_time_min or not vt_pace_min:
        return
    color_key = label.lower()
    ax.axvline(
        x=vt_time_min,
        color=get_color(color_key),
        linestyle="--",
        alpha=0.9,
        linewidth=1.5,
        label=f"{label}: {vt_pace_min:.2f} min/km",
    )
    ax.text(
        vt_time_min,
        ve_max * 0.95,
        f"{label}\n{vt_pace_min:.2f}",
        color=get_color(color_key),
        ha="center",
        va="top",
        fontweight="bold",
        bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"),
    )


def generate_ve_profile_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None,
) -> bytes:
    """Generate VE profile chart with Pace overlay."""
    cfg = _normalize_config(config)

    figsize = cfg.get("figsize", (10, 6))
    dpi = cfg.get("dpi", 150)
    font_size = cfg.get("font_size", 10)
    title_size = cfg.get("title_size", 14)

    time_series = report_data.get("time_series", {})

    if source_df is not None and not source_df.empty:
        time_data, ve_data, pace_data = _extract_ve_from_df(source_df)
    else:
        time_data, ve_data, pace_data = _extract_ve_from_json(time_series)

    if not time_data or not ve_data:
        empty_result = create_empty_figure(
            "Brak danych wentylacji", "Dynamika Wentylacji", output_path, **cfg
        )
        return empty_result if output_path else empty_result.to_image(format="png")

    thresholds = report_data.get("thresholds", {})
    vt1_data = thresholds.get("vt1", {})
    vt2_data = thresholds.get("vt2", {})
    vt1_pace_sec = vt1_data.get("midpoint_pace_sec", 0)
    vt2_pace_sec = vt2_data.get("midpoint_pace_sec", 0)

    vt1_time = _find_vt_time(time_data, time_series, vt1_pace_sec)
    vt2_time = _find_vt_time(time_data, time_series, vt2_pace_sec)
    vt1_pace_min = _sec_to_min(vt1_pace_sec) if vt1_pace_sec else None
    vt2_pace_min = _sec_to_min(vt2_pace_sec) if vt2_pace_sec else None

    time_min = [t / 60 for t in time_data]
    vt1_time_min = vt1_time / 60 if vt1_time else None
    vt2_time_min = vt2_time / 60 if vt2_time else None

    fig, ax1 = plt.subplots(figsize=figsize, dpi=dpi)
    ax2 = ax1.twinx()

    _plot_pace_background(ax2, time_min, pace_data, font_size)
    ax1.plot(time_min, ve_data, color=get_color("ve"), linewidth=2, label="VE (Wentylacja)")

    time_max = max(time_min)
    tick_step = 5
    tick_vals = np.arange(0, time_max + tick_step, tick_step)
    tick_labels = [f"{int(m // 60):02d}:{int(m % 60):02d}:00" for m in tick_vals]
    ax1.set_xticks(tick_vals)
    ax1.set_xticklabels(tick_labels)

    ax1.set_xlabel("Czas [hh:mm:ss]", fontsize=font_size)
    ax1.set_ylabel("VE [L/min]", color=get_color("ve"), fontsize=font_size, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=get_color("ve"))

    _plot_vt_line(ax1, vt1_time_min, vt1_pace_min, max(ve_data), "VT1")
    _plot_vt_line(ax1, vt2_time_min, vt2_pace_min, max(ve_data), "VT2")

    metadata = report_data.get("metadata", {})
    test_date = metadata.get("test_date", "")
    ax1.set_title(
        f"Dynamika Wentylacji (VE) – {test_date}", fontsize=title_size, fontweight="bold", pad=15
    )

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=font_size - 1)

    ax1.grid(True, alpha=0.3, linestyle=":")
    ax1.spines["top"].set_visible(False)
    ax2.spines["top"].set_visible(False)

    session_id = metadata.get("session_id", "unknown")[:8]
    fig.text(
        0.01,
        0.01,
        f"ID: {session_id}",
        ha="left",
        va="bottom",
        fontsize=8,
        color=get_color("secondary"),
        style="italic",
    )

    plt.tight_layout()
    return save_figure(fig, output_path, **cfg)
