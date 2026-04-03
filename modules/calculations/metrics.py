"""
SRP: Moduł odpowiedzialny za podstawowe metryki treningowe.
"""

from typing import Any, Dict, Tuple, Union

import numpy as np
import pandas as pd

from .common import (
    MIN_HR_DECOUPLING,
    MIN_SAMPLES_ACTIVE,
    MIN_SAMPLES_Z2_DRIFT,
    MIN_WATTS_DECOUPLING,
    ensure_pandas,
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
        except (ValueError, TypeError, KeyError):
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


def calculate_pace_hr_decoupling(
    df_pl: Union[pd.DataFrame, Any], pace_col: str = "pace", hr_col: str = "heartrate"
) -> Tuple[float, float]:
    """Calculate Pace:HR Decoupling (Efficiency Factor for running).

    This is the RUNNING version of power-based decoupling.
    Critical for assessing aerobic fitness (Joe Friel methodology).

    EF = Speed / HR (higher = more efficient)
    Decoupling = (EF_first_half - EF_second_half) / EF_first_half * 100

    Target: <5% = good aerobic adaptation, >5% = needs more base training

    Args:
        df_pl: DataFrame with pace and heart rate columns
        pace_col: Column name for pace (sec/km)
        hr_col: Column name for heart rate (bpm)

    Returns:
        Tuple of (decoupling_percent, efficiency_factor)
    """
    df = ensure_pandas(df_pl)

    if pace_col not in df.columns or hr_col not in df.columns:
        return 0.0, 0.0

    # Filter valid data (positive pace, reasonable HR > 60 bpm)
    df_active = df[(df[pace_col] > 0) & (df[pace_col] < 2000) & (df[hr_col] > 60)].copy()

    if len(df_active) < MIN_SAMPLES_ACTIVE:
        return 0.0, 0.0

    # Convert pace to speed (m/s) for linear averaging
    # Speed = 1000m / pace_sec_per_km
    df_active["speed_ms"] = 1000.0 / df_active[pace_col]

    mid = len(df_active) // 2
    first_half = df_active.iloc[:mid]
    second_half = df_active.iloc[mid:]

    # Calculate EF for each half (Speed / HR)
    # Use harmonic mean for pace (which means arithmetic mean for speed)
    hr1 = first_half[hr_col].mean()
    hr2 = second_half[hr_col].mean()
    speed1 = first_half["speed_ms"].mean()
    speed2 = second_half["speed_ms"].mean()

    if hr1 <= 0 or hr2 <= 0:
        return 0.0, 0.0

    ef1 = speed1 / hr1  # m/s per bpm
    ef2 = speed2 / hr2

    if ef1 <= 0:
        return 0.0, 0.0

    # Decoupling percentage
    decoupling_pct = ((ef1 - ef2) / ef1) * 100

    # Overall efficiency factor
    overall_ef = df_active["speed_ms"].mean() / df_active[hr_col].mean()

    return float(decoupling_pct), float(overall_ef)


def calculate_durability_index(df_pl: Union[pd.DataFrame, Any], pace_col: str = "pace") -> float:
    """Calculate Durability Index using HARMONIC mean for pace.

    Durability = (avg_pace_first_half / avg_pace_second_half) * 100
    Uses harmonic mean because pace is nonlinear.

    Returns:
        Durability index (100 = perfect maintenance, <100 = fade)
    """
    df = ensure_pandas(df_pl)

    if pace_col not in df.columns:
        return 0.0

    df_valid = df[(df[pace_col] > 0) & (df[pace_col] < 2000)].copy()

    if len(df_valid) < 100:
        return 0.0

    mid = len(df_valid) // 2
    first_half = df_valid.iloc[:mid]
    second_half = df_valid.iloc[mid:]

    # Use harmonic mean for pace: H = n / sum(1/x)
    # Equivalent to arithmetic mean of speed
    speed1 = 1000.0 / first_half[pace_col]
    speed2 = 1000.0 / second_half[pace_col]

    avg_speed1 = speed1.mean()
    avg_speed2 = speed2.mean()

    if avg_speed1 <= 0 or avg_speed2 <= 0:
        return 0.0

    # Convert back to pace for durability ratio
    avg_pace1 = 1000.0 / avg_speed1
    avg_pace2 = 1000.0 / avg_speed2

    # Durability: ratio of first half to second half pace
    # >100 means second half was faster (negative split)
    # <100 means second half was slower (positive split/fade)
    durability = (avg_pace1 / avg_pace2) * 100

    return float(durability)


# =============================================================================
# NEW: TRIMP and hrTSS for training load without power meter
# =============================================================================


def calculate_trimp(
    df: pd.DataFrame,
    hr_col: str = "hr",
    duration_sec: float = None,
    hr_max: float = 200.0,
    hr_rest: float = 60.0,
    gender: str = "male",
) -> Optional[float]:
    """
    Calculate TRIMP (Training Impulse) - heart rate-based training load.
    Uses exponential model based on %HRR.

    Formula: TRIMP = duration_min × HRR × gender_factor
    where HRR = %Heart Rate Reserve, gender_factor = 0.64 * e^(1.92 * HRR) for males

    Args:
        df: DataFrame with HR data
        hr_col: Heart rate column name
        duration_sec: Duration in seconds (if None, calculated from time column)
        hr_max: Maximum heart rate (default: 200)
        hr_rest: Resting heart rate (default: 60)
        gender: "male" or "female" (affects exponent factor)

    Returns:
        TRIMP value (unitless training load score)
    """
    if hr_col not in df.columns:
        return None

    # Calculate duration if not provided
    if duration_sec is None:
        if "time" in df.columns:
            duration_sec = df["time"].max()
        else:
            duration_sec = len(df)

    # Calculate average HR during activity
    avg_hr = df[hr_col].mean()

    # Calculate %HRR (Heart Rate Reserve)
    hrr = (avg_hr - hr_rest) / (hr_max - hr_rest) if hr_max > hr_rest else 0.0
    hrr = max(0.0, min(1.0, hrr))  # Clamp to 0-1

    # Gender-specific exponent factor
    if gender.lower() == "female":
        k = 0.86 * np.exp(1.67 * hrr)
    else:
        k = 0.64 * np.exp(1.92 * hrr)

    # TRIMP calculation
    duration_min = duration_sec / 60.0
    trimp = duration_min * hrr * k

    return float(trimp)


def calculate_hrtss(
    df: pd.DataFrame,
    hr_col: str = "hr",
    duration_sec: float = None,
    lthr: float = 175.0,
    hr_max: float = 200.0,
    hr_rest: float = 60.0,
    gender: str = "male",
) -> Optional[Dict[str, float]]:
    """
    Calculate hrTSS (Heart Rate Training Stress Score).
    Alternative to TSS when no power meter is available.

    Formula: hrTSS = (TRIMP / TRIMP_threshold) × 100
    where TRIMP_threshold is TRIMP at LTHR for 1 hour

    Args:
        df: DataFrame with HR data
        hr_col: Heart rate column name
        duration_sec: Duration in seconds (if None, calculated from time column)
        lthr: Lactate Threshold Heart Rate (default: 175)
        hr_max: Maximum heart rate (default: 200)
        hr_rest: Resting heart rate (default: 60)
        gender: "male" or "female"

    Returns:
        Dict with hrTSS, TRIMP, IF (Intensity Factor), and normalized values
    """
    if hr_col not in df.columns:
        return None

    # Calculate actual TRIMP
    trimp = calculate_trimp(df, hr_col, duration_sec, hr_max, hr_rest, gender)
    if trimp is None:
        return None

    # Calculate duration if not provided
    if duration_sec is None:
        if "time" in df.columns:
            duration_sec = df["time"].max()
        else:
            duration_sec = len(df)

    # Calculate TRIMP at LTHR for 1 hour (threshold reference)
    # Create a synthetic 1-hour DataFrame at LTHR
    hrr_threshold = (lthr - hr_rest) / (hr_max - hr_rest)
    hrr_threshold = max(0.0, min(1.0, hrr_threshold))

    if gender.lower() == "female":
        k_threshold = 0.86 * np.exp(1.67 * hrr_threshold)
    else:
        k_threshold = 0.64 * np.exp(1.92 * hrr_threshold)

    # TRIMP at LTHR for 60 minutes
    trimp_threshold = 60.0 * hrr_threshold * k_threshold

    # Calculate hrTSS
    if trimp_threshold > 0:
        hrtss = (trimp / trimp_threshold) * 100.0
    else:
        hrtss = 0.0

    # Calculate Intensity Factor (IF) based on HR
    avg_hr = df[hr_col].mean()
    if_hrtss = avg_hr / lthr if lthr > 0 else 0.0

    return {
        "hrtss": float(hrtss),
        "trimp": float(trimp),
        "if_hrtss": float(if_hrtss),
        "duration_min": float(duration_sec / 60.0),
        "avg_hr": float(avg_hr),
        "lthr": float(lthr),
    }
