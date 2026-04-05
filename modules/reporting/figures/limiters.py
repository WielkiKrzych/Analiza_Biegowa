"""
Limiters Analysis Chart Generator.

Generates:
1. Metabolic Profile Radar Chart (5min Peak Window)
   - Dimensions: Heart, Lungs, Muscles, Power
"""

from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import create_empty_figure, save_figure


def _find_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    """Find first existing column from aliases."""
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None


def _resolve_config(config: Optional[Any]) -> Dict[str, Any]:
    if hasattr(config, "__dict__"):
        return config.__dict__
    if isinstance(config, dict):
        return config
    return {}


def _build_source_df(
    report_data: Dict[str, Any],
    source_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    if source_df is not None and not source_df.empty:
        return source_df

    time_series = report_data.get("time_series", {})
    if not time_series or not time_series.get("power_watts"):
        return None

    return pd.DataFrame(
        {
            "watts": time_series.get("power_watts", []),
            "heartrate": time_series.get("hr_bpm", []),
            "smo2": time_series.get("smo2_pct", []),
            "tymeventilation": time_series.get("ve_lmin", time_series.get("ve_lpm", [])),
        }
    )


def _extract_vt2_ve(report_data: Dict[str, Any]) -> float:
    try:
        thresholds = report_data.get("thresholds", {})
        vt2 = thresholds.get("vt2_result", thresholds.get("vt2", {}))
        return float(vt2.get("ve", 0))
    except (KeyError, TypeError, ValueError):
        return 0.0


def _compute_heart_metric(
    df: pd.DataFrame,
    df_peak: pd.DataFrame,
    report_data: Dict[str, Any],
) -> float:
    hr_col = _find_column(df, ["heartrate", "hr"])
    max_hr = report_data.get("metadata", {}).get("max_hr") or 190.0

    if hr_col and max_hr:
        peak_hr_avg = df_peak[hr_col].mean()
        return min(100.0, peak_hr_avg / max_hr * 100)
    return 0.0


def _compute_lungs_metric(
    df: pd.DataFrame,
    df_peak: pd.DataFrame,
    report_data: Dict[str, Any],
) -> float:
    ve_col = _find_column(df, ["tymeventilation", "ve", "ventilation"])
    if not ve_col:
        return 0.0

    vt2_ve = _extract_vt2_ve(report_data)
    ve_max_user = vt2_ve * 1.1 if vt2_ve > 0 else df[ve_col].max()
    peak_ve_avg = df_peak[ve_col].mean()

    if ve_max_user > 0:
        return min(100.0, peak_ve_avg / ve_max_user * 100)
    return 0.0


def _compute_radar_metrics(
    df: pd.DataFrame,
    df_peak: pd.DataFrame,
    pwr_col: str,
    report_data: Dict[str, Any],
) -> Tuple[float, float, float, float]:
    pct_hr = _compute_heart_metric(df, df_peak, report_data)
    pct_ve = _compute_lungs_metric(df, df_peak, report_data)

    smo2_col = _find_column(df, ["smo2", "SmO2"])
    pct_smo2 = min(100.0, 100 - df_peak[smo2_col].mean()) if smo2_col else 0.0

    cp_watts = report_data.get("cp_model", {}).get("cp_watts", 0)
    peak_w_avg = df_peak[pwr_col].mean()
    pct_power = min(120.0, peak_w_avg / cp_watts * 100) if cp_watts and cp_watts > 0 else 0.0

    return pct_hr, pct_ve, pct_smo2, pct_power


def generate_radar_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None,
) -> bytes:
    """Generate Metabolic Profile Radar Chart (5min Peak Window)."""
    cfg = _resolve_config(config)

    figsize = cfg.get("figsize", (10, 6))
    dpi = cfg.get("dpi", 150)
    font_size = cfg.get("font_size", 10)

    source_df = _build_source_df(report_data, source_df)
    if source_df is None:
        return create_empty_figure(
            "Brak danych źródłowych", "Profil Metaboliczny", output_path, **cfg
        )

    df = source_df.copy()
    pwr_col = _find_column(df, ["watts", "watts_smooth", "power", "Power"])
    if not pwr_col:
        return create_empty_figure("Brak danych Mocy", "Profil Metaboliczny", output_path, **cfg)

    # Rolling 5min (300s)
    window_sec = 300
    df["rolling_watts"] = df[pwr_col].rolling(window=window_sec, min_periods=window_sec).mean()
    if df["rolling_watts"].isna().all():
        return create_empty_figure(
            "Za krótki trening (<5min)", "Profil Metaboliczny", output_path, **cfg
        )

    peak_idx = df["rolling_watts"].idxmax()
    start_idx = max(0, peak_idx - window_sec + 1)
    df_peak = df.iloc[start_idx : peak_idx + 1]

    pct_hr, pct_ve, pct_smo2, pct_power = _compute_radar_metrics(df, df_peak, pwr_col, report_data)

    # --- Plotting ---
    categories = ["Serce\n(% HRmax)", "Płuca\n(% VEmax)", "Mięśnie\n(% Desat)", "Moc\n(% CP)"]
    values = [pct_hr, pct_ve, pct_smo2, pct_power]
    values_closed = values + [values[0]]
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += [angles[0]]

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw=dict(polar=True))
    ax.plot(angles, values_closed, color="#00cc96", linewidth=2)
    ax.fill(angles, values_closed, color="#00cc96", alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=font_size)
    ax.set_ylim(0, 100)
    plt.yticks([20, 40, 60, 80, 100], color="grey", size=8)
    plt.tight_layout()
    return save_figure(fig, output_path, **cfg)


def _extract_mmp_values(
    report_data: Dict[str, Any],
    source_df: Optional[pd.DataFrame],
) -> Tuple[float, float]:
    """Extract MMP 5min and 20min with cascading fallbacks."""
    mmp_5min: float = report_data.get("metrics", {}).get("mmp_5min", 0)
    mmp_20min: float = report_data.get("metrics", {}).get("mmp_20min", 0)

    # Fallback 1: calculate from source_df
    if (not mmp_5min or not mmp_20min) and source_df is not None and not source_df.empty:
        df = source_df.copy()
        pwr_col = _find_column(df, ["watts", "power"])
        if pwr_col:
            mmp_5min = df[pwr_col].rolling(300, min_periods=60).mean().max()
            mmp_20min = df[pwr_col].rolling(1200, min_periods=300).mean().max()

    # Fallback 2: try time_series from report_data
    if not mmp_5min or not mmp_20min:
        time_series = report_data.get("time_series", {})
        power_watts = time_series.get("power_watts", [])
        if power_watts and len(power_watts) > 300:
            power_series = pd.Series(power_watts)
            mmp_5min = power_series.rolling(300, min_periods=60).mean().max()
            if len(power_watts) > 1200:
                mmp_20min = power_series.rolling(1200, min_periods=300).mean().max()
            elif len(power_watts) > 600:
                mmp_20min = power_series.rolling(600, min_periods=300).mean().max()

    return mmp_5min, mmp_20min


def _classify_metabolic_profile(
    ratio: float,
) -> Tuple[str, str, str, float]:
    """Classify metabolic profile from 5min/20min power ratio.

    Returns (profile, description, color, marker_position).
    """
    if ratio > 1.08:
        return "Sprinter / Puncheur", "Wysoki VLaMax (>0.5 mmol/L/s)", "#ff6b6b", 0.8
    if ratio < 0.95:
        return "Climber / TT Specialist", "Niski VLaMax (<0.4 mmol/L/s)", "#4ecdc4", 0.2
    return "All-Rounder", "Zbalansowany VLaMax (0.4-0.5 mmol/L/s)", "#ffd93d", 0.5


def generate_vlamax_balance_chart(
    report_data: Dict[str, Any],
    config: Optional[Any] = None,
    output_path: Optional[str] = None,
    source_df: Optional[pd.DataFrame] = None,
) -> bytes:
    """Generate VO2max vs VLaMax Balance Schema (Metabolic Profiling)."""
    cfg = _resolve_config(config)
    figsize = cfg.get("figsize", (10, 4))

    mmp_5min, mmp_20min = _extract_mmp_values(report_data, source_df)

    if not mmp_20min or mmp_20min == 0 or pd.isna(mmp_20min):
        return create_empty_figure(
            "Brak danych (MMP 20 min)", "Profil Metaboliczny", output_path, **cfg
        )

    ratio = mmp_5min / mmp_20min
    profile, desc, color, marker_pos = _classify_metabolic_profile(ratio)

    # Plotting Schema
    fig, ax = plt.subplots(figsize=figsize)

    ax.axhline(0, color="grey", linewidth=2, zorder=1)
    ax.plot([0, 0.35], [0, 0], color="#4ecdc4", linewidth=8, alpha=0.3, label="Time Trial / Diesel")
    ax.plot([0.35, 0.65], [0, 0], color="#ffd93d", linewidth=8, alpha=0.3, label="All-Rounder")
    ax.plot(
        [0.65, 1.0], [0, 0], color="#ff6b6b", linewidth=8, alpha=0.3, label="Sprinter / Puncheur"
    )

    ax.scatter(
        [marker_pos],
        [0],
        color=color,
        s=200,
        edgecolor="white",
        zorder=5,
        label=f"Twój Profil: {profile}",
    )

    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-1, 1)
    ax.axis("off")

    ax.text(
        marker_pos,
        0.15,
        f"{profile}",
        ha="center",
        va="bottom",
        fontweight="bold",
        fontsize=12,
        color=color,
    )
    ax.text(marker_pos, -0.4, desc, ha="center", va="top", fontsize=10, style="italic")
    ax.text(
        0,
        -0.15,
        "DOMINACJA TLENOWA\n(Niski VLaMax)",
        ha="center",
        va="top",
        fontsize=8,
        color="#4ecdc4",
    )
    ax.text(
        1.0,
        -0.15,
        "DOMINACJA BEZTLENOWA\n(Wysoki VLaMax)",
        ha="center",
        va="top",
        fontsize=8,
        color="#ff6b6b",
    )

    ax.set_title(
        f"Balans Metaboliczny: VO2max vs VLaMax (Ratio: {ratio:.2f})", pad=10, fontweight="bold"
    )

    return save_figure(fig, output_path, **cfg)
