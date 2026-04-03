"""
Drift Analysis Scatter Charts Generator.

Generates:
1. Pace vs HR Scatter (Decoupling Map)
2. Pace vs SmO2 Scatter (Muscle Oxygen Map)
3. Pace vs HR/SmO2 Heatmaps
"""

from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd

from .common import apply_common_style, create_empty_figure, get_color, save_figure


def _find_column(df: pd.DataFrame, aliases: list) -> Optional[str]:
    """Find first existing column from aliases."""
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None


def _format_pace_min_km(pace_sec_per_km: float) -> str:
    """Convert pace from sec/km to min:sec/km format for display."""
    if pd.isna(pace_sec_per_km) or pace_sec_per_km <= 0:
        return "--:--"
    minutes = int(pace_sec_per_km // 60)
    seconds = int(pace_sec_per_km % 60)
    return f"{minutes}:{seconds:02d}"


def _sec_to_min(pace_sec: float) -> float:
    """Convert pace from sec/km to min/km for axis display."""
    return pace_sec / 60.0 if pace_sec and pace_sec > 0 else 0


def generate_power_hr_scatter(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None,
) -> bytes:
    """Generate Pace vs Heart Rate scatter plot with time coloring."""
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

    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})

    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        hr_col = _find_column(df, ["heartrate", "heartrate_smooth", "hr", "heart_rate"])
        pace_col = _find_column(df, ["pace", "pace_smooth", "pace_sec_per_km", "tempo"])
        time_col = _find_column(df, ["time_min", "time", "seconds"])

        if hr_col and pace_col:
            # Filter valid data (pace > 0, hr > 30)
            mask = (
                (df[pace_col] > 0) & (df[pace_col] < 1200) & (df[hr_col] > 30)
            )  # pace < 20 min/km
            df_clean = df[mask].copy()
            # Convert pace to min/km for display
            pace_data = [_sec_to_min(p) for p in df_clean[pace_col].tolist()]
            hr_data = df_clean[hr_col].tolist()
            c_vals = df_clean[time_col].tolist() if time_col else None
        else:
            pace_data, hr_data, c_vals = [], [], None
    else:
        # Fallback to JSON time_series
        pace_sec = time_series.get("pace_sec_per_km", time_series.get("pace", []))
        pace_data = [_sec_to_min(p) for p in pace_sec] if pace_sec else []
        hr_data = time_series.get("hr_bpm", [])
        c_vals = time_series.get("time_sec", [])

    if not hr_data or not pace_data:
        empty_result = create_empty_figure(
            "Brak danych Tempo/HR", "Tempo vs HR", output_path, **cfg
        )
        return empty_result if output_path else empty_result.to_image(format="png")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Scatter with time coloring
    if c_vals and len(c_vals) == len(pace_data):
        sc = ax.scatter(pace_data, hr_data, c=c_vals, cmap="viridis", alpha=0.5, s=20)
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label("Czas")
    else:
        ax.scatter(pace_data, hr_data, c=get_color("pace"), alpha=0.5, s=20)

    ax.set_xlabel("Tempo [min/km]", fontsize=font_size)
    ax.set_ylabel("HR [bpm]", fontsize=font_size)
    ax.set_title("Relacja: Tempo vs Tętno (Decoupling)", fontsize=title_size, fontweight="bold")

    # Invert X-axis (lower pace = faster, so show right-to-left)
    ax.invert_xaxis()

    apply_common_style(fig, ax, **cfg)
    plt.tight_layout()

    return save_figure(fig, output_path, **cfg)


def generate_power_smo2_scatter(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None,
) -> bytes:
    """Generate Pace vs SmO2 scatter plot with time coloring."""
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

    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})

    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        smo2_col = _find_column(df, ["smo2", "smo2_smooth", "muscle_oxygen", "smo2_pct"])
        pace_col = _find_column(df, ["pace", "pace_smooth", "pace_sec_per_km", "tempo"])
        time_col = _find_column(df, ["time_min", "time", "seconds"])

        if smo2_col and pace_col:
            # Filter valid data
            mask = (df[pace_col] > 0) & (df[pace_col] < 1200) & (df[smo2_col] > 0)
            df_clean = df[mask].copy()
            # Convert pace to min/km for display
            pace_data = [_sec_to_min(p) for p in df_clean[pace_col].tolist()]
            smo2_data = df_clean[smo2_col].tolist()
            c_vals = df_clean[time_col].tolist() if time_col else None
        else:
            pace_data, smo2_data, c_vals = [], [], None
    else:
        # Fallback to JSON time_series
        pace_sec = time_series.get("pace_sec_per_km", time_series.get("pace", []))
        pace_data = [_sec_to_min(p) for p in pace_sec] if pace_sec else []
        smo2_data = time_series.get("smo2_pct", [])
        c_vals = time_series.get("time_sec", [])

    if not pace_data or not smo2_data:
        empty_result = create_empty_figure(
            "Brak danych Tempo/SmO2", "Tempo vs SmO2", output_path, **cfg
        )
        return empty_result if output_path else empty_result.to_image(format="png")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Scatter with time coloring
    if c_vals and len(c_vals) == len(pace_data):
        sc = ax.scatter(pace_data, smo2_data, c=c_vals, cmap="inferno", alpha=0.5, s=20)
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label("Czas")
    else:
        ax.scatter(pace_data, smo2_data, c=get_color("smo2"), alpha=0.5, s=20)

    ax.set_xlabel("Tempo [min/km]", fontsize=font_size)
    ax.set_ylabel("SmO₂ [%]", fontsize=font_size)
    ax.set_title("Relacja: Tempo vs Saturacja Mięśniowa", fontsize=title_size, fontweight="bold")

    # Invert X-axis (lower pace = faster)
    ax.invert_xaxis()

    apply_common_style(fig, ax, **cfg)
    plt.tight_layout()

    return save_figure(fig, output_path, **cfg)


def generate_drift_heatmap(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None,
    mode: str = "hr",  # "hr" or "smo2"
) -> bytes:
    """Generate Decoupling Heatmap (Density map of Pace vs Physiological signal)."""
    if hasattr(config, "__dict__"):
        cfg = config.__dict__
    elif isinstance(config, dict):
        cfg = config
    else:
        cfg = {}

    figsize = cfg.get("figsize", (10, 6))
    dpi = cfg.get("dpi", 150)

    # Extract data from source_df or fallback
    time_series = report_data.get("time_series", {})

    if source_df is not None and not source_df.empty:
        df = source_df.copy()
        df.columns = df.columns.str.lower().str.strip()
        pace_col = _find_column(df, ["pace", "pace_smooth", "pace_sec_per_km", "tempo"])

        if mode == "hr":
            target_col = _find_column(df, ["heartrate", "hr", "heartrate_smooth"])
        else:
            target_col = _find_column(df, ["smo2", "smo2_smooth", "muscle_oxygen", "smo2_pct"])

        if pace_col and target_col:
            mask = (df[pace_col] > 0) & (df[pace_col] < 1200) & (df[target_col] > 0)
            df_clean = df[mask].copy()
            # Convert pace to min/km for display
            pace_data = [_sec_to_min(p) for p in df_clean[pace_col].tolist()]
            target_data = df_clean[target_col].tolist()
        else:
            pace_data, target_data = [], []
    else:
        # Fallback to JSON time_series
        pace_sec = time_series.get("pace_sec_per_km", time_series.get("pace", []))
        pace_data = [_sec_to_min(p) for p in pace_sec] if pace_sec else []
        if mode == "hr":
            target_data = time_series.get("hr_bpm", [])
        else:
            target_data = time_series.get("smo2_pct", [])

    if mode == "hr":
        cmap = "magma"
        label = "HR [bpm]"
        title = "Mapa Dryfu: Tempo vs Tętno"
    else:
        cmap = "viridis"
        label = "SmO2 [%]"
        title = "Mapa Oksydacji: Tempo vs Saturacja"

    if not pace_data or not target_data or len(pace_data) < 100:
        empty_result = create_empty_figure(
            f"Za mało danych dla mapy gęstości {mode.upper()}", "Mapa Dryfu", output_path, **cfg
        )
        return empty_result if output_path else empty_result.to_image(format="png")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Hexbin for heatmap effect
    hb = ax.hexbin(pace_data, target_data, gridsize=30, cmap=cmap, mincnt=1, marginals=False)
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("Gęstość (liczba próbek)")

    ax.set_xlabel("Tempo [min/km]")
    ax.set_ylabel(label)
    ax.set_title(title, fontweight="bold", pad=15)

    # Invert X-axis (lower pace = faster)
    ax.invert_xaxis()

    apply_common_style(fig, ax, **cfg)
    plt.tight_layout()

    return save_figure(fig, output_path, **cfg)
