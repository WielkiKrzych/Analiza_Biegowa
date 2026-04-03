"""
SRP: Moduł odpowiedzialny za obliczenia termiczne (Heat Strain Index).
"""
from typing import Any, List, Optional, Union

import numpy as np
import pandas as pd
from scipy.stats import linregress

from .common import ensure_pandas


def calculate_heat_strain_index(df_pl: Union[pd.DataFrame, Any]) -> pd.DataFrame:
    """Calculate Heat Strain Index (HSI) based on core temp and HR.
    
    HSI is a composite index (0-10) indicating heat stress level:
    - 0-3: Low strain
    - 4-6: Moderate strain  
    - 7-10: High strain (risk of heat illness)
    
    Args:
        df_pl: DataFrame with 'core_temperature_smooth' and 'heartrate_smooth'
    
    Returns:
        DataFrame with added 'hsi' column
    """
    df = ensure_pandas(df_pl)
    core_col = 'core_temperature_smooth' if 'core_temperature_smooth' in df.columns else None

    if not core_col or 'heartrate_smooth' not in df.columns:
        df['hsi'] = None
        return df

    # HSI formula: weighted combination of temperature and HR deviation from baseline
    # Temperature contribution: (CoreTemp - 37.0) / 2.5 * 5 (max 5 points)
    # HR contribution: (HR - 60) / 120 * 5 (max 5 points)
    # Avoid SettingWithCopyWarning
    df = df.copy()
    df['hsi'] = (
        (5 * (df[core_col] - 37.0) / 2.5) +
        (5 * (df['heartrate_smooth'] - 60.0) / 120.0)
    ).clip(0.0, 10.0)

    return df
def calculate_thermal_decay(df_pl: Union[pd.DataFrame, Any]) -> dict:
    """Calculate the thermal cost of performance as % efficiency loss per 1°C.
    
    Standard WKO5/INSCYD approach:
    - Efficiency Factor (EF) = Power / Heart Rate
    - Decay = Percentage change in EF for every +1°C of Core Temperature.
    
    Returns:
        dict: {
            'decay_pct_per_c': float, # e.g. -5.2 means 5.2% drop per 1°C
            'r_squared': float,       # statistical confidence
            'is_significant': bool,
            'message': str
        }
    """
    df = ensure_pandas(df_pl)

    # Column mapping (finding best candidates)
    pwr_col = next((c for c in ['watts_smooth', 'watts', 'power'] if c in df.columns), None)
    hr_col = next((c for c in ['heartrate_smooth', 'heartrate', 'hr'] if c in df.columns), None)
    temp_col = 'core_temperature_smooth' if 'core_temperature_smooth' in df.columns else None

    if not all([pwr_col, hr_col, temp_col]):
        return {'decay_pct_per_c': 0, 'r_squared': 0, 'is_significant': False, 'message': "Brak wymaganych kolumn (Moc, HR, Temp)"}

    # Filter for active state: Power > 100W (or 50% FTP), HR > 100, Temp > 37.2
    # We focus on the "Heat Load" phase where temperature is significantly above baseline
    mask = (df[pwr_col] > 50) & (df[hr_col] > 80) & (df[temp_col] > 37.0)
    df_act = df[mask].copy()

    if len(df_act) < 300: # Min 5 minutes of data
        return {'decay_pct_per_c': 0, 'r_squared': 0, 'is_significant': False, 'message': "Zbyt mało danych aktywnych (>37°C)"}

    # Efficiency Factor
    df_act['ef'] = df_act[pwr_col] / df_act[hr_col]

    # Linear Regression (EF ~ Temp)
    # y = m*x + b
    x = df_act[temp_col].values
    y = df_act['ef'].values

    # Basic OLS
    n = len(x)
    m = (n * np.sum(x*y) - np.sum(x)*np.sum(y)) / (n * np.sum(x**2) - (np.sum(x))**2)
    b = (np.mean(y)) - m * np.mean(x)

    # R-squared
    y_pred = m * x + b
    ss_res = np.sum((y - y_pred)**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    # Calculate % decay per 1 degree
    # Decay = (Slope / Mean EF at 37.5°C) * 100
    ref_ef = m * 37.5 + b
    if ref_ef <= 0: ref_ef = np.mean(y)

    decay_pct = (m / ref_ef) * 100

    return {
        'decay_pct_per_c': round(decay_pct, 2),
        'r_squared': round(r2, 3),
        'is_significant': r2 > 0.3 and decay_pct < 0,
        'message': f"Spadek o {abs(decay_pct):.1f}% na każdy +1°C" if decay_pct < 0 else "Stabilna termoregulacja"
    }


def predict_thermal_performance(
    cp: float,
    ftp: float,
    w_prime: float,
    baseline_hr: float,
    target_temp: float,
    decay_pct_per_c: float = -3.0,
    hr_increase_per_c: float = 3.0,
    baseline_temp: float = 37.5
) -> dict:
    """
    Predict performance degradation at a given core temperature.
    
    Based on:
    - dEF/dT: Efficiency Factor decay per degree Celsius
    - dHR/dT: HR increase per degree Celsius
    - HSI: Heat Strain Index (derived from temp and HR)
    
    Args:
        cp: Critical Power [W]
        ftp: Functional Threshold Power [W]
        w_prime: W' anaerobic capacity [kJ]
        baseline_hr: Baseline heart rate at threshold [bpm]
        target_temp: Target core temperature [°C]
        decay_pct_per_c: Efficiency decay % per °C (default -3.0%)
        hr_increase_per_c: HR increase per °C [bpm] (default 3.0)
        baseline_temp: Baseline core temperature [°C] (default 37.5)
        
    Returns:
        dict with predictions: CP, FTP, W' at target temp, HR cost, TTE reduction
    """

    # Calculate temperature delta
    temp_delta = max(0, target_temp - baseline_temp)

    # === CP/FTP DEGRADATION ===
    # Power drops by decay_pct_per_c for each degree above baseline
    decay_factor = 1 + (decay_pct_per_c / 100) * temp_delta
    decay_factor = max(0.5, min(1.0, decay_factor))  # Clamp to 50-100%

    cp_degraded = cp * decay_factor
    ftp_degraded = ftp * decay_factor

    # === W' DEGRADATION ===
    # W' degrades faster than CP in heat (glycolytic cost increases)
    # Assume 1.5x the decay rate for W'
    w_prime_decay_factor = 1 + (decay_pct_per_c * 1.5 / 100) * temp_delta
    w_prime_decay_factor = max(0.3, min(1.0, w_prime_decay_factor))
    w_prime_degraded = w_prime * w_prime_decay_factor

    # === HR COST INCREASE ===
    # HR increases by hr_increase_per_c per degree
    hr_cost_increase = hr_increase_per_c * temp_delta
    hr_at_threshold = baseline_hr + hr_cost_increase

    # === TIME TO EXHAUSTION (TTE) REDUCTION ===
    # At threshold power, TTE is theoretically infinite (at CP)
    # But in practice, heat reduces sustainable time
    # Model: TTE_reduction = temp_delta * 5% per degree
    tte_reduction_pct = temp_delta * 5.0  # 5% per degree

    # For a 60-minute effort at FTP, calculate reduced time
    base_tte_min = 60.0
    tte_degraded_min = base_tte_min * (1 - tte_reduction_pct / 100)
    tte_degraded_min = max(20.0, tte_degraded_min)  # Min 20 min

    # === HSI ESTIMATE ===
    # HSI = f(temp, HR) - simplified
    hsi_estimated = min(10, max(0, (target_temp - 37.0) / 2.5 * 5 + (hr_at_threshold - 100) / 100 * 5))

    # === CLASSIFICATION ===
    if temp_delta < 1.0:
        risk_level = "low"
        risk_color = "#27AE60"
        risk_label = "Niskie"
    elif temp_delta < 2.0:
        risk_level = "moderate"
        risk_color = "#F39C12"
        risk_label = "Umiarkowane"
    else:
        risk_level = "high"
        risk_color = "#E74C3C"
        risk_label = "Wysokie"

    return {
        "target_temp": target_temp,
        "temp_delta": round(temp_delta, 1),
        "baseline_temp": baseline_temp,

        # Power degradation
        "cp_baseline": cp,
        "cp_degraded": round(cp_degraded, 0),
        "cp_loss_pct": round((1 - decay_factor) * 100, 1),

        "ftp_baseline": ftp,
        "ftp_degraded": round(ftp_degraded, 0),
        "ftp_loss_pct": round((1 - decay_factor) * 100, 1),

        "w_prime_baseline": w_prime,
        "w_prime_degraded": round(w_prime_degraded, 1),
        "w_prime_loss_pct": round((1 - w_prime_decay_factor) * 100, 1),

        # HR cost
        "hr_baseline": baseline_hr,
        "hr_at_threshold": round(hr_at_threshold, 0),
        "hr_cost_increase": round(hr_cost_increase, 1),

        # TTE
        "tte_baseline_min": base_tte_min,
        "tte_degraded_min": round(tte_degraded_min, 0),
        "tte_reduction_pct": round(tte_reduction_pct, 1),

        # HSI
        "hsi_estimated": round(hsi_estimated, 1),

        # Risk
        "risk_level": risk_level,
        "risk_color": risk_color,
        "risk_label": risk_label,

        # Decay parameters used
        "decay_pct_per_c": decay_pct_per_c,
        "hr_increase_per_c": hr_increase_per_c
    }


# ---------------------------------------------------------------------------
# CORE temperature zone thresholds (CORE sensor calibration)
# ---------------------------------------------------------------------------

_CORE_TEMP_ZONES = (
    ("normal",        38.0, "#27AE60", "Normal"),
    ("elevated",      38.5, "#F39C12", "Elevated"),
    ("heat_training", 39.0, "#E67E22", "Heat Training"),
    ("caution",       39.5, "#E74C3C", "Caution"),
    ("danger",        float("inf"), "#8E44AD", "Danger"),
)


def classify_core_temp_zone(temp_c: float) -> dict:
    """Classify a single core-temperature reading into a thermal zone.

    Zone thresholds are aligned with the CORE body-temperature sensor:
        normal        : < 38.0 C
        elevated      : 38.0 - 38.5 C
        heat_training : 38.5 - 39.0 C
        caution       : 39.0 - 39.5 C
        danger        : > 39.5 C

    Args:
        temp_c: Core temperature in degrees Celsius.

    Returns:
        dict with keys ``zone``, ``color``, ``label``.

    Raises:
        ValueError: If *temp_c* is not a finite number.
    """
    if not np.isfinite(temp_c):
        raise ValueError(f"temp_c must be a finite number, got {temp_c}")

    for zone_name, upper, color, label in _CORE_TEMP_ZONES:
        if temp_c < upper:
            return {"zone": zone_name, "color": color, "label": label}

    # Fallback (should not be reached due to inf sentinel)
    last = _CORE_TEMP_ZONES[-1]
    return {"zone": last[0], "color": last[1], "label": last[3]}


def calculate_core_temp_zones_time(
    core_temp_series: Union[pd.Series, np.ndarray, list],
    sample_rate_hz: float = 1.0,
) -> dict:
    """Calculate time (in seconds) spent in each CORE thermal zone.

    Args:
        core_temp_series: Sequence of core-temperature readings (Celsius).
        sample_rate_hz: Sampling frequency in Hz (default 1 Hz = 1 sample/s).

    Returns:
        dict mapping zone names to cumulative seconds spent in that zone.

    Raises:
        ValueError: If *sample_rate_hz* is not positive.
    """
    if sample_rate_hz <= 0:
        raise ValueError(f"sample_rate_hz must be positive, got {sample_rate_hz}")

    temps = np.asarray(core_temp_series, dtype=np.float64)
    sample_duration = 1.0 / sample_rate_hz

    zone_seconds: dict = {
        "normal": 0.0,
        "elevated": 0.0,
        "heat_training": 0.0,
        "caution": 0.0,
        "danger": 0.0,
    }

    valid_mask = np.isfinite(temps)
    valid_temps = temps[valid_mask]

    for t in valid_temps:
        zone_info = classify_core_temp_zone(t)
        zone_seconds[zone_info["zone"]] += sample_duration

    return {k: round(v, 2) for k, v in zone_seconds.items()}


def calculate_thermal_drift_rate(
    core_temp_series: Union[pd.Series, np.ndarray, list],
    time_series: Optional[Union[pd.Series, np.ndarray, list]] = None,
    steady_state_only: bool = True,
    pace_series: Optional[Union[pd.Series, np.ndarray, list]] = None,
) -> dict:
    """Calculate the rate of core-temperature rise during activity.

    Uses ordinary-least-squares regression of temperature vs elapsed time
    (in minutes).  When *steady_state_only* is ``True`` and a *pace_series*
    is provided, only segments where the coefficient of variation of pace is
    below 10 % are included.

    Args:
        core_temp_series: Core-temperature readings (Celsius).
        time_series: Elapsed-time values (seconds).  If ``None`` a 1 Hz
            sample rate is assumed (i.e. index == seconds).
        steady_state_only: When ``True``, restrict analysis to steady-state
            segments (pace CV < 10 %).
        pace_series: Pace values (e.g. min/km or m/s) used for the
            steady-state filter.

    Returns:
        dict with drift metrics -- see module docstring for full schema.
    """
    temps = np.asarray(core_temp_series, dtype=np.float64)

    if time_series is not None:
        times_s = np.asarray(time_series, dtype=np.float64)
    else:
        times_s = np.arange(len(temps), dtype=np.float64)

    # Build a boolean mask for valid data
    valid_mask = np.isfinite(temps) & np.isfinite(times_s)

    # Steady-state filtering (rolling window CV of pace < 10 %)
    if steady_state_only and pace_series is not None:
        paces = np.asarray(pace_series, dtype=np.float64)
        if len(paces) == len(temps):
            window = min(60, len(paces))
            pace_pd = pd.Series(paces)
            rolling_mean = pace_pd.rolling(window, min_periods=max(1, window // 2)).mean()
            rolling_std = pace_pd.rolling(window, min_periods=max(1, window // 2)).std()
            cv = (rolling_std / rolling_mean).fillna(0).values
            steady_mask = cv < 0.10
            valid_mask = valid_mask & steady_mask

    temps_f = temps[valid_mask]
    times_f = times_s[valid_mask]

    _empty_result = {
        "drift_c_per_min": 0.0,
        "drift_c_per_hour": 0.0,
        "r_squared": 0.0,
        "start_temp": float(temps[0]) if len(temps) > 0 else 0.0,
        "end_temp": float(temps[-1]) if len(temps) > 0 else 0.0,
        "total_rise": 0.0,
        "classification": "normal",
        "interpretation": "Insufficient data for drift analysis.",
    }

    if len(temps_f) < 60:
        return _empty_result

    # Convert seconds to minutes for regression
    times_min = times_f / 60.0

    slope, intercept, r_value, _p_value, _std_err = linregress(times_min, temps_f)
    r_squared = r_value ** 2

    start_temp = float(temps_f[0])
    end_temp = float(temps_f[-1])
    total_rise = end_temp - start_temp

    drift_c_per_min = slope
    drift_c_per_hour = slope * 60.0

    # Classification based on hourly drift
    abs_drift_h = abs(drift_c_per_hour)
    if abs_drift_h < 0.5:
        classification = "well_adapted"
        interpretation = (
            f"Thermal drift of {drift_c_per_hour:+.2f} C/h indicates "
            "good heat adaptation."
        )
    elif abs_drift_h < 1.0:
        classification = "normal"
        interpretation = (
            f"Thermal drift of {drift_c_per_hour:+.2f} C/h is within "
            "the normal range for endurance activity."
        )
    else:
        classification = "heat_sensitive"
        interpretation = (
            f"Thermal drift of {drift_c_per_hour:+.2f} C/h suggests "
            "elevated heat sensitivity -- consider heat acclimation protocols."
        )

    return {
        "drift_c_per_min": round(drift_c_per_min, 5),
        "drift_c_per_hour": round(drift_c_per_hour, 3),
        "r_squared": round(r_squared, 4),
        "start_temp": round(start_temp, 2),
        "end_temp": round(end_temp, 2),
        "total_rise": round(total_rise, 2),
        "classification": classification,
        "interpretation": interpretation,
    }


def calculate_temp_adjusted_pace(
    pace_series: Union[pd.Series, np.ndarray, list],
    core_temp_series: Union[pd.Series, np.ndarray, list],
    baseline_temp: float = 37.5,
) -> dict:
    """Estimate pace performance decrement attributable to core-temperature rise.

    Research suggests approximately 1-2 % pace loss per 1 C above baseline.
    The function groups data into 0.5 C temperature bins, computes mean speed
    in each bin, and runs a linear regression of speed vs temperature to
    quantify the relationship.

    Args:
        pace_series: Pace values expressed as speed (m/s or km/h -- any
            consistent unit where *higher = faster*).
        core_temp_series: Corresponding core-temperature readings (Celsius).
        baseline_temp: Reference temperature for "no heat penalty" (default
            37.5 C).

    Returns:
        dict with keys ``pace_loss_pct_per_c``, ``r_squared``,
        ``is_significant``, ``equivalent_flat_pace``.
    """
    speeds = np.asarray(pace_series, dtype=np.float64)
    temps = np.asarray(core_temp_series, dtype=np.float64)

    _empty = {
        "pace_loss_pct_per_c": 0.0,
        "r_squared": 0.0,
        "is_significant": False,
        "equivalent_flat_pace": 0.0,
    }

    if len(speeds) != len(temps):
        return _empty

    valid = np.isfinite(speeds) & np.isfinite(temps) & (speeds > 0)
    speeds_v = speeds[valid]
    temps_v = temps[valid]

    if len(speeds_v) < 60:
        return _empty

    # Build temperature bins (0.5 C increments)
    bin_edges = np.arange(
        np.floor(temps_v.min() * 2) / 2,
        np.ceil(temps_v.max() * 2) / 2 + 0.5,
        0.5,
    )

    if len(bin_edges) < 2:
        return _empty

    bin_indices = np.digitize(temps_v, bin_edges)

    bin_temps: List[float] = []
    bin_speeds: List[float] = []
    for i in range(1, len(bin_edges)):
        mask = bin_indices == i
        if mask.sum() >= 10:
            bin_temps.append((bin_edges[i - 1] + bin_edges[i]) / 2.0)
            bin_speeds.append(float(np.mean(speeds_v[mask])))

    if len(bin_temps) < 3:
        return _empty

    arr_temps = np.array(bin_temps)
    arr_speeds = np.array(bin_speeds)

    slope, intercept, r_value, _p_value, _std_err = linregress(arr_temps, arr_speeds)
    r_squared = r_value ** 2

    # Speed at baseline temperature (reference point)
    speed_at_baseline = slope * baseline_temp + intercept
    if speed_at_baseline <= 0:
        speed_at_baseline = float(np.mean(arr_speeds))

    # Percentage loss per 1 C
    pace_loss_pct_per_c = (slope / speed_at_baseline) * 100.0

    # Equivalent "flat" (no-heat) pace: extrapolate speed back to baseline temp
    mean_temp = float(np.mean(temps_v))
    mean_speed = float(np.mean(speeds_v))
    temp_penalty_delta = mean_temp - baseline_temp
    equivalent_flat_pace = mean_speed - slope * temp_penalty_delta

    is_significant = r_squared > 0.3 and pace_loss_pct_per_c < 0

    return {
        "pace_loss_pct_per_c": round(pace_loss_pct_per_c, 2),
        "r_squared": round(r_squared, 4),
        "is_significant": bool(is_significant),
        "equivalent_flat_pace": round(equivalent_flat_pace, 3),
    }
