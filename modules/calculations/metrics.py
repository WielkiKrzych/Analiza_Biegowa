"""
SRP: Moduł odpowiedzialny za podstawowe metryki treningowe.
"""

from typing import Union, Any, Tuple
import numpy as np
import pandas as pd

from .common import (
    ensure_pandas,
    MIN_SAMPLES_ACTIVE,
    MIN_SAMPLES_Z2_DRIFT,
    MIN_WATTS_DECOUPLING,
    MIN_HR_DECOUPLING,
)


def calculate_metrics(df_pl, cp_val: float) -> dict:
    """Calculate basic training metrics.

    Args:
        df_pl: DataFrame with training data
        cp_val: Critical Power [W]

    Returns:
        Dictionary with metrics
    """
    is_empty = df_pl.empty
    cols = df_pl.columns

    avg_watts = df_pl["watts"].mean() if "watts" in cols and not is_empty else 0.0
    avg_hr = df_pl["heartrate"].mean() if "heartrate" in cols and not is_empty else 0.0
    avg_cadence = df_pl["cadence"].mean() if "cadence" in cols and not is_empty else 0.0
    avg_vent = (
        df_pl["tymeventilation"].mean() if "tymeventilation" in cols and not is_empty else 0.0
    )
    avg_rr = df_pl["tymebreathrate"].mean() if "tymebreathrate" in cols and not is_empty else 0.0

    # Handle NaN from mean() if columns exist but are all NaN
    avg_watts = 0.0 if pd.isna(avg_watts) else float(avg_watts)
    avg_hr = 0.0 if pd.isna(avg_hr) else float(avg_hr)
    avg_cadence = 0.0 if pd.isna(avg_cadence) else float(avg_cadence)
    avg_vent = 0.0 if pd.isna(avg_vent) else float(avg_vent)
    avg_rr = 0.0 if pd.isna(avg_rr) else float(avg_rr)
    power_hr = (avg_watts / avg_hr) if avg_hr > 0 else 0
    np_est = avg_watts * 1.05
    ef_factor = (np_est / avg_hr) if avg_hr > 0 else 0
    work_above_cp_kj = 0.0

    if "watts" in cols:
        try:
            if hasattr(df_pl, "select"):
                t = df_pl["time"].to_numpy().astype(float)
                w = df_pl["watts"].to_numpy().astype(float)
            else:
                t = df_pl["time"].values.astype(float)
                w = df_pl["watts"].values.astype(float)
            dt = np.diff(t, prepend=t[0])
            if len(dt) > 1:
                dt[0] = dt[1] if dt[1] > 0 else np.median(dt[1:]) if len(dt) > 2 else 1.0
            else:
                dt = np.ones_like(w)
            excess = np.maximum(w - cp_val, 0.0)
            energy_j = np.sum(excess * dt)
            work_above_cp_kj = energy_j / 1000.0
        except Exception:
            df_above_cp = (
                df_pl[df_pl["watts"] > cp_val] if "watts" in df_pl.columns else pd.DataFrame()
            )
            work_above_cp_kj = (df_above_cp["watts"].sum() / 1000) if len(df_above_cp) > 0 else 0.0

    return {
        "avg_watts": avg_watts,
        "avg_hr": avg_hr,
        "avg_cadence": avg_cadence,
        "avg_vent": avg_vent,
        "avg_rr": avg_rr,
        "power_hr": power_hr,
        "ef_factor": ef_factor,
        "work_above_cp_kj": work_above_cp_kj,
    }


def calculate_advanced_kpi(df_pl: Union[pd.DataFrame, Any]) -> Tuple[float, float]:
    """Calculate decoupling percentage and efficiency factor.

    Decoupling indicates cardiac drift - difference in efficiency
    between first and second half of workout.

    Args:
        df_pl: DataFrame with smoothed power and HR

    Returns:
        Tuple of (decoupling %, efficiency factor)
    """
    df = ensure_pandas(df_pl)
    if "watts_smooth" not in df.columns or "heartrate_smooth" not in df.columns:
        return 0.0, 0.0
    df_active = df[
        (df["watts_smooth"] > MIN_WATTS_DECOUPLING) & (df["heartrate_smooth"] > MIN_HR_DECOUPLING)
    ]
    if len(df_active) < MIN_SAMPLES_ACTIVE:
        return 0.0, 0.0
    mid = len(df_active) // 2
    p1, p2 = df_active.iloc[:mid], df_active.iloc[mid:]
    hr1 = p1["heartrate_smooth"].mean()
    hr2 = p2["heartrate_smooth"].mean()
    if hr1 == 0 or hr2 == 0:
        return 0.0, 0.0
    ef1 = p1["watts_smooth"].mean() / hr1
    ef2 = p2["watts_smooth"].mean() / hr2
    if ef1 == 0:
        return 0.0, 0.0
    return ((ef1 - ef2) / ef1) * 100, (
        df_active["watts_smooth"] / df_active["heartrate_smooth"]
    ).mean()


def calculate_z2_drift(df_pl: Union[pd.DataFrame, Any], cp: float) -> float:
    """Calculate cardiac drift in Zone 2.

    Args:
        df_pl: DataFrame with training data
        cp: Critical Power [W]

    Returns:
        Drift percentage
    """
    df = ensure_pandas(df_pl)
    if "watts_smooth" not in df.columns or "heartrate_smooth" not in df.columns:
        return 0.0
    # Z2 is 55-75% of CP
    df_z2 = df[
        (df["watts_smooth"] >= 0.55 * cp)
        & (df["watts_smooth"] <= 0.75 * cp)
        & (df["heartrate_smooth"] > 60)
    ]
    if len(df_z2) < MIN_SAMPLES_Z2_DRIFT:
        return 0.0
    mid = len(df_z2) // 2
    p1, p2 = df_z2.iloc[:mid], df_z2.iloc[mid:]
    hr1 = p1["heartrate_smooth"].mean()
    hr2 = p2["heartrate_smooth"].mean()
    if hr1 == 0 or hr2 == 0:
        return 0.0
    ef1 = p1["watts_smooth"].mean() / hr1
    ef2 = p2["watts_smooth"].mean() / hr2
    return ((ef1 - ef2) / ef1) * 100 if ef1 != 0 else 0.0


def calculate_vo2max(mmp_5m, rider_weight: float) -> float:
    """Estimate VO2max from 5-minute max power.

    Uses Sitko et al. 2021 formula: VO2max = 16.61 + 8.87 × 5' max power (W/kg)

    Args:
        mmp_5m: 5-minute maximum power [W]
        rider_weight: Athlete weight [kg]

    Returns:
        Estimated VO2max [ml/kg/min]
    """
    if mmp_5m is None or pd.isna(mmp_5m) or rider_weight <= 0:
        return 0.0
    power_per_kg = mmp_5m / rider_weight
    return 16.61 + 8.87 * power_per_kg


def calculate_trend(x, y):
    """Calculate linear trend line.

    Args:
        x: X values (usually time)
        y: Y values (metric to trend)

    Returns:
        Array of trend values or None
    """
    try:
        idx = np.isfinite(x) & np.isfinite(y)
        if np.sum(idx) < 2:
            return None
        z = np.polyfit(x[idx], y[idx], 1)
        p = np.poly1d(z)
        return p(x)
    except (ValueError, TypeError, np.linalg.LinAlgError):
        return None
