"""
Ramp Profile Chart Generator.

Generates power profile over time with VT1/VT2 range bands.
Input: Canonical JSON report
Output: PNG file

Chart shows:
- Power trace over time
- VT1 and VT2 as HORIZONTAL RANGE BANDS (semi-transparent)
- No vertical "magic lines"
- Footer with test_id and method version
"""

from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from .common import apply_common_style, create_empty_figure, get_color, save_figure


def _normalize_config(config: Optional[Any]) -> Dict[str, Any]:
    """Extract config dict from object, dict, or None."""
    if hasattr(config, "__dict__"):
        return config.__dict__
    if isinstance(config, dict):
        return config
    return {}


def _extract_first_matching_col(
    df: Any,
    candidates: List[str],
) -> Optional[str]:
    """Return the first column name from candidates that exists in df."""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _extract_timeseries_from_df(
    source_df: Any,
) -> Tuple[List[float], List[float], List[float]]:
    """Extract time, power, and HR data from a source DataFrame."""
    df = source_df.copy()
    df.columns = df.columns.str.lower().str.strip()

    time_col = _extract_first_matching_col(df, ["time", "seconds"])
    if time_col:
        time_data = df[time_col].tolist()
    else:
        time_data = list(range(len(df)))

    power_col = _extract_first_matching_col(
        df, ["watts", "power", "watts_smooth", "watts_smooth_5s"]
    )
    power_data = df[power_col].fillna(0).tolist() if power_col else []

    hr_col = _extract_first_matching_col(
        df, ["hr", "heart_rate", "heartrate", "bpm", "heart_rate_bpm"]
    )
    hr_data = df[hr_col].fillna(0).tolist() if hr_col else []

    return time_data, power_data, hr_data


def _extract_timeseries_from_json(
    report_data: Dict[str, Any],
) -> Tuple[List[float], List[float], List[float]]:
    """Extract time, power, and HR data from JSON report_data."""
    time_series = report_data.get("time_series", {})
    return (
        time_series.get("time_sec", []),
        time_series.get("power_watts", []),
        time_series.get("hr_bpm", []),
    )


def _get_threshold_watts(
    report_data: Dict[str, Any],
    cfg: Dict[str, Any],
) -> Tuple[float, float]:
    """Get VT1/VT2 watt values with manual overrides applied."""
    thresholds = report_data.get("thresholds", {})
    vt1_data = thresholds.get("vt1", {})
    vt2_data = thresholds.get("vt2", {})

    vt1_watts = vt1_data.get("midpoint_watts", 0) if isinstance(vt1_data, dict) else 0
    vt2_watts = vt2_data.get("midpoint_watts", 0) if isinstance(vt2_data, dict) else 0

    manual_overrides = cfg.get("manual_overrides", {})
    if manual_overrides.get("manual_vt1_watts") and manual_overrides["manual_vt1_watts"] > 0:
        vt1_watts = float(manual_overrides["manual_vt1_watts"])
    if manual_overrides.get("manual_vt2_watts") and manual_overrides["manual_vt2_watts"] > 0:
        vt2_watts = float(manual_overrides["manual_vt2_watts"])

    return vt1_watts, vt2_watts


def _plot_hr_trace(
    ax: plt.Axes,
    time_min: List[float],
    hr_data: List[float],
    font_size: int,
) -> Optional[plt.Axes]:
    """Plot HR trace on secondary axis if data is available."""
    if not hr_data:
        return None
    ax2 = ax.twinx()
    (l2,) = ax2.plot(
        time_min,
        hr_data,
        color=get_color("hr"),
        linestyle="-",
        label="HR",
        alpha=0.9,
        linewidth=2.5,
        zorder=10,
    )
    ax2.set_ylabel("HR [bpm]", color=get_color("hr"), fontsize=font_size)
    ax2.tick_params(axis="y", labelcolor=get_color("hr"))
    ax2.spines["right"].set_color(get_color("hr"))
    return ax2


def _plot_vt_band(
    ax: plt.Axes,
    vt_watts: float,
    label_prefix: str,
) -> None:
    """Plot a VT horizontal band with center line if watts > 0."""
    if not vt_watts:
        return
    color_key = label_prefix.lower()
    vt_range = (vt_watts * 0.95, vt_watts * 1.05)
    ax.axhspan(
        vt_range[0],
        vt_range[1],
        alpha=0.25,
        color=get_color(color_key),
        zorder=1,
        label=f"{label_prefix}: {int(vt_watts)} W",
    )
    ax.axhline(
        y=vt_watts, color=get_color(color_key), linewidth=1, linestyle=":", alpha=0.7, zorder=2
    )


def generate_ramp_profile_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[Any] = None,
) -> bytes:
    """Generate ramp profile chart with VT1/VT2 as horizontal range bands."""
    cfg = _normalize_config(config)

    figsize = cfg.get("figsize", (10, 6))
    dpi = cfg.get("dpi", 150)
    font_size = cfg.get("font_size", 10)
    title_size = cfg.get("title_size", 14)
    method_version = cfg.get("method_version", "1.0.0")

    if source_df is not None and len(source_df) > 0:
        time_data, power_data, hr_data = _extract_timeseries_from_df(source_df)
    else:
        time_data, power_data, hr_data = _extract_timeseries_from_json(report_data)

    if not time_data or not power_data:
        return create_empty_figure("Brak danych mocy", "Profil Ramp Test", output_path, **cfg)

    vt1_watts, vt2_watts = _get_threshold_watts(report_data, cfg)

    time_min = [t / 60 for t in time_data]
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(time_min, power_data, color=get_color("power"), linewidth=1.5, label="Moc", zorder=3)
    ax.fill_between(time_min, power_data, alpha=0.15, color=get_color("power"), zorder=2)

    _plot_hr_trace(ax, time_min, hr_data, font_size)
    _plot_vt_band(ax, vt1_watts, "VT1")
    _plot_vt_band(ax, vt2_watts, "VT2")

    time_max = max(time_min)
    tick_step = 5
    tick_vals = np.arange(0, time_max + tick_step, tick_step)
    tick_labels = [f"{int(m // 60):02d}:{int(m % 60):02d}:00" for m in tick_vals]
    ax.set_xticks(tick_vals)
    ax.set_xticklabels(tick_labels)

    ax.set_xlabel("Czas [hh:mm:ss]", fontsize=font_size, fontweight="medium")
    ax.set_ylabel("Moc [W]", fontsize=font_size, fontweight="medium")

    metadata = report_data.get("metadata", {})
    test_date = metadata.get("test_date", "")
    ax.set_title(f"Profil Ramp Test – {test_date}", fontsize=title_size, fontweight="bold", pad=15)

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles, labels, loc="upper left", fontsize=font_size - 1, framealpha=0.9, edgecolor="none"
    )

    apply_common_style(fig, ax, **cfg)

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
    fig.text(
        0.99,
        0.01,
        f"v{method_version}",
        ha="right",
        va="bottom",
        fontsize=8,
        color=get_color("secondary"),
        style="italic",
    )

    plt.tight_layout()
    return save_figure(fig, output_path, **cfg)
