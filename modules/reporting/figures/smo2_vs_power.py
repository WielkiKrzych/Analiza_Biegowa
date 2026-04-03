"""
SmO₂ vs Pace Chart Generator.

Generates SmO₂ saturation vs pace scatter with LT1/LT2 range bands.
Input: Canonical JSON report
Output: PNG file

Chart shows:
- Raw scatter of SmO₂ vs Pace (NO smoothing/interpolation)
- LT1/LT2 as HORIZONTAL RANGE BANDS if available
- Annotation about SmO₂ being a local signal
- Footer with test_id and method version
"""

from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd

from .common import apply_common_style, create_empty_figure, get_color, save_figure


def _sec_to_min(pace_sec: float) -> float:
    """Convert pace from sec/km to min/km for axis display."""
    return pace_sec / 60.0 if pace_sec and pace_sec > 0 else 0


def generate_smo2_power_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional["pd.DataFrame"] = None,
) -> bytes:
    """Generate SmO₂ vs Pace chart with LT1/LT2 range bands."""
    # Handle config as dict if passed, or use defaults
    if hasattr(config, "__dict__"):
        cfg = config.__dict__
    elif isinstance(config, dict):
        cfg = config
    else:
        cfg = {}

    figsize = cfg.get("figsize", (10, 6))
    dpi = cfg.get("dpi", 150)
    font_size = cfg.get("font_size", 10)
    title_size = cfg.get("title_size", 14)
    method_version = cfg.get("method_version", "1.0.0")

    # Extract data
    time_series = report_data.get("time_series", {})
    report_data.get("thresholds", {})
    metadata = report_data.get("metadata", {})
    smo2_context = report_data.get("smo2_context", {})

    # Try to get data from source_df first
    if source_df is not None and len(source_df) > 0:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()

        # Get pace data (instead of power)
        pace_col = next(
            (c for c in ["pace", "pace_smooth", "pace_sec_per_km", "tempo"] if c in df.columns),
            None,
        )

        # Get smo2 data
        smo2_col = next(
            (c for c in ["smo2", "smo2_pct", "muscle_oxygen", "smo2_smooth"] if c in df.columns),
            None,
        )

        if pace_col and smo2_col:
            # Filter out NaN values and convert pace to min/km
            mask = (
                ~(df[pace_col].isna() | df[smo2_col].isna())
                & (df[pace_col] > 0)
                & (df[pace_col] < 1200)
            )
            pace_sec_data = df.loc[mask, pace_col].tolist()
            smo2_data = df.loc[mask, smo2_col].tolist()
            # Convert pace to min/km for display
            pace_data = [_sec_to_min(p) for p in pace_sec_data]
        else:
            pace_data, smo2_data = [], []
    else:
        # Fallback to time_series from JSON
        pace_sec = time_series.get("pace_sec_per_km", time_series.get("pace", []))
        pace_data = [_sec_to_min(p) for p in pace_sec] if pace_sec else []
        smo2_data = time_series.get("smo2_pct", [])

    # Handle missing data
    if not pace_data or not smo2_data:
        empty_result = create_empty_figure("Brak danych SmO₂", "SmO₂ vs Tempo", output_path, **cfg)
        return empty_result if output_path else empty_result.to_image(format="png")

    # Get SmO2 drop point from smo2_context (convert watts to pace if available)
    drop_point = smo2_context.get("drop_point", {})
    # Try to get pace-based threshold, fallback to converting watts
    lt1_pace_sec = drop_point.get("midpoint_pace_sec", 0)
    if not lt1_pace_sec and drop_point.get("midpoint_watts", 0):
        # If only watts available, we'd need conversion - for now use placeholder
        lt1_pace_sec = 0

    # MANUAL OVERRIDE: Check config for manual SmO2 LT1 (priority over saved)
    manual_overrides = cfg.get("manual_overrides", {})
    if manual_overrides.get("smo2_lt1_pace") and manual_overrides["smo2_lt1_pace"] > 0:
        lt1_pace_sec = float(manual_overrides["smo2_lt1_pace"])

    # Define LT ranges in min/km (±5% for visual band width)
    if lt1_pace_sec:
        lt1_pace_min = _sec_to_min(lt1_pace_sec)
        lt1_range = (lt1_pace_min * 0.95, lt1_pace_min * 1.05)
    else:
        lt1_range = None

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Raw scatter plot SmO2 vs Pace (NO SMOOTHING)
    ax.scatter(
        pace_data,
        smo2_data,
        c=get_color("smo2"),
        alpha=0.4,
        s=12,
        label="SmO₂",
        zorder=3,
        edgecolors="none",
    )

    # LT1 vertical range band (semi-transparent) - SmO2 drop point
    if lt1_range:
        ax.axvspan(
            lt1_range[0],
            lt1_range[1],
            alpha=0.2,
            color=get_color("vt1"),
            zorder=1,
            label=f"SmO₂ Drop: {_sec_to_min(lt1_pace_sec):.2f} min/km",
        )

    # Axis labels
    ax.set_xlabel("Tempo [min/km]", fontsize=font_size, fontweight="medium")
    ax.set_ylabel("SmO₂ [%]", fontsize=font_size, fontweight="medium")

    # Title
    ax.set_title("SmO₂ vs Tempo", fontsize=title_size, fontweight="bold", pad=15)

    # Invert X-axis (lower pace = faster)
    ax.invert_xaxis()

    # Legend
    ax.legend(loc="upper right", fontsize=font_size - 1, framealpha=0.9, edgecolor="none")

    # Apply common styling
    apply_common_style(fig, ax, **cfg)

    # Important annotation about SmO₂ interpretation
    ax.text(
        0.5,
        -0.12,
        "ℹ️ SmO₂ jest sygnałem lokalnym – interpretować kontekstowo",
        ha="center",
        va="top",
        fontsize=9,
        style="italic",
        color=get_color("secondary"),
        transform=ax.transAxes,
    )

    # Footer with test_id and method version
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
