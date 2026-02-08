"""
VO2/VCO2 Estimation Module.

Provides estimation of oxygen consumption (VO2) and carbon dioxide production (VCO2)
from power and heart rate data when direct gas exchange measurements are unavailable.

Uses ACSM and Wasserman equations for estimation.
"""

from typing import Optional, Tuple

import numpy as np
import pandas as pd


def estimate_vo2_from_power(
    power_watts: np.ndarray,
    body_weight_kg: float = 70.0,
    efficiency: float = 0.23,
    resting_vo2_ml_min: float = 250.0,
) -> np.ndarray:
    """
    Estimate VO2 from power using ACSM cycling equation.

    VO2 (mL/min) = (Power (W) × 1000 / efficiency) + Resting VO2

    Args:
        power_watts: Array of power values in watts
        body_weight_kg: Rider body weight in kg (default 70kg)
        efficiency: Cycling efficiency (default 0.23 or 23%)
        resting_vo2_ml_min: Resting VO2 in mL/min (default 250)

    Returns:
        Array of estimated VO2 values in mL/min
    """
    # Convert power to oxygen cost
    # 1 Watt = 1 Joule/second
    # Energy cost = Power / efficiency
    # VO2 (mL/min) = (Power × 60) / (efficiency × 20.9 J/mL O2)
    # Simplified: VO2 = Power × 2.87 + resting

    power_array = np.asarray(power_watts)
    vo2_ml_min = (power_array * 60) / (efficiency * 20.9) + resting_vo2_ml_min

    return vo2_ml_min


def estimate_vo2_from_hr(
    hr_bpm: np.ndarray,
    hr_max: float = 185.0,
    hr_rest: float = 60.0,
    vo2max_ml_kg_min: float = 55.0,
    body_weight_kg: float = 70.0,
) -> np.ndarray:
    """
    Estimate VO2 from heart rate using %HRmax-%VO2max relationship.

    Args:
        hr_bpm: Array of heart rate values in bpm
        hr_max: Maximum heart rate in bpm
        hr_rest: Resting heart rate in bpm
        vo2max_ml_kg_min: VO2max in mL/kg/min
        body_weight_kg: Body weight in kg

    Returns:
        Array of estimated VO2 values in mL/min
    """
    hr_array = np.asarray(hr_bpm)

    # %HRR = (HR - HRrest) / (HRmax - HRrest)
    hrr_fraction = (hr_array - hr_rest) / (hr_max - hr_rest)
    hrr_fraction = np.clip(hrr_fraction, 0.0, 1.0)

    # %VO2max ≈ %HRR (linear relationship)
    vo2max_ml_min = vo2max_ml_kg_min * body_weight_kg
    vo2_ml_min = hrr_fraction * vo2max_ml_min

    # Add resting component
    resting_vo2_ml_min = 3.5 * body_weight_kg  # 1 MET
    vo2_ml_min = vo2_ml_min + resting_vo2_ml_min

    return vo2_ml_min


def estimate_vco2_from_vo2(
    vo2_ml_min: np.ndarray,
    rer: Optional[np.ndarray] = None,
    power_watts: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Estimate VCO2 from VO2 using RER (Respiratory Exchange Ratio).

    If RER not provided, estimate from power intensity:
    - Low intensity (<VT1): RER ≈ 0.85
    - Moderate (VT1-VT2): RER ≈ 0.90
    - High (>VT2): RER ≈ 1.00+

    Args:
        vo2_ml_min: Array of VO2 values in mL/min
        rer: Optional array of RER values
        power_watts: Optional array of power for RER estimation

    Returns:
        Array of estimated VCO2 values in mL/min
    """
    vo2_array = np.asarray(vo2_ml_min)

    if rer is not None:
        rer_array = np.asarray(rer)
    elif power_watts is not None:
        # Estimate RER from power percentiles
        power_array = np.asarray(power_watts)
        p25, p75 = np.percentile(power_array, [25, 75])

        # RER increases with intensity
        rer_array = np.where(power_array < p25, 0.85, np.where(power_array < p75, 0.90, 1.00))
    else:
        # Default moderate intensity
        rer_array = np.full_like(vo2_array, 0.90)

    vco2_ml_min = vo2_array * rer_array
    return vco2_ml_min


def add_estimated_gas_exchange(
    df: pd.DataFrame,
    power_col: str = "watts",
    hr_col: str = "heartrate",
    body_weight_kg: float = 70.0,
    hr_max: float = 185.0,
    hr_rest: float = 60.0,
    vo2max_ml_kg_min: float = 55.0,
    use_power_based: bool = True,
    use_hr_based: bool = True,
    blend_factor: float = 0.7,
) -> pd.DataFrame:
    """
    Add estimated VO2 and VCO2 columns to DataFrame.

    Args:
        df: Input DataFrame
        power_col: Column name for power (watts)
        hr_col: Column name for heart rate (bpm)
        body_weight_kg: Rider body weight
        hr_max: Maximum heart rate
        hr_rest: Resting heart rate
        vo2max_ml_kg_min: VO2max in mL/kg/min
        use_power_based: Include power-based VO2 estimation
        use_hr_based: Include HR-based VO2 estimation
        blend_factor: Weight for power-based vs HR-based (0.7 = 70% power, 30% HR)

    Returns:
        DataFrame with added 'vo2_estimated' and 'vco2_estimated' columns
    """
    df_result = df.copy()

    # Get power and HR arrays
    power = df_result[power_col].values if power_col in df_result.columns else None
    hr = df_result[hr_col].values if hr_col in df_result.columns else None

    vo2_estimates = []

    if use_power_based and power is not None:
        vo2_power = estimate_vo2_from_power(power, body_weight_kg)
        vo2_estimates.append(vo2_power)

    if use_hr_based and hr is not None:
        vo2_hr = estimate_vo2_from_hr(hr, hr_max, hr_rest, vo2max_ml_kg_min, body_weight_kg)
        vo2_estimates.append(vo2_hr)

    # Blend estimates if both available
    if len(vo2_estimates) == 2:
        vo2_final = blend_factor * vo2_estimates[0] + (1 - blend_factor) * vo2_estimates[1]
    elif len(vo2_estimates) == 1:
        vo2_final = vo2_estimates[0]
    else:
        # Fallback: estimate from power only
        vo2_final = estimate_vo2_from_power(np.linspace(100, 300, len(df_result)), body_weight_kg)

    # Estimate VCO2
    vco2_final = estimate_vco2_from_vo2(vo2_final, power_watts=power)

    df_result["vo2"] = vo2_final / 1000.0
    df_result["vco2"] = vco2_final / 1000.0
    df_result["rer_estimated"] = vco2_final / np.maximum(vo2_final, 1.0)

    return df_result


def detect_vt_with_estimated_gas_exchange(
    df: pd.DataFrame,
    ve_col: str = "TymeVentilation",
    power_col: str = "watts",
    hr_col: str = "heartrate",
    time_col: str = "time",
    body_weight_kg: float = 70.0,
    **kwargs,
) -> dict:
    """
    Detect ventilatory thresholds using estimated VO2/VCO2.

    This is a wrapper that adds estimated gas exchange data before
    calling the standard VT detection functions.

    Args:
        df: Input DataFrame with ventilation data
        ve_col: Column name for ventilation
        power_col: Column name for power
        hr_col: Column name for heart rate
        time_col: Column name for time
        body_weight_kg: Rider body weight for VO2 estimation
        **kwargs: Additional arguments passed to detect_vt_ramp_python

    Returns:
        Dictionary with VT1 and VT2 detection results
    """
    from .ventilatory import detect_vt_ramp_python

    # Add estimated VO2/VCO2
    df_with_gas = add_estimated_gas_exchange(
        df,
        power_col=power_col,
        hr_col=hr_col,
        body_weight_kg=body_weight_kg,
    )

    # Call standard detection
    result = detect_vt_ramp_python(df_with_gas, **kwargs)

    # Add estimation info
    result["gas_exchange_method"] = "estimated_from_power_hr"
    result["body_weight_kg"] = body_weight_kg

    return result


def detect_vt_percentile_based(
    df: pd.DataFrame,
    power_col: str = "watts",
    hr_col: str = "heartrate",
    ve_col: str = "TymeVentilation",
    vt1_percentile: float = 60.0,
    vt2_percentile: float = 80.0,
    min_power: float = 100.0,
) -> dict:
    """
    Detect ventilatory thresholds using percentile-based estimation.

    This is a fallback method when gas exchange data is unavailable.
    Uses power percentiles as proxy for VT1/VT2 based on typical
    distribution in ramp tests.

    Args:
        df: Input DataFrame with power and optional HR/VE data
        power_col: Column name for power
        hr_col: Column name for heart rate
        ve_col: Column name for ventilation
        vt1_percentile: Percentile for VT1 (default 60th)
        vt2_percentile: Percentile for VT2 (default 80th)
        min_power: Minimum power to consider (filters warmup/cooldown)

    Returns:
        Dictionary with VT1 and VT2 detection results
    """
    df_work = df.copy()

    # Filter to active cycling
    mask = df_work[power_col] >= min_power
    df_active = df_work[mask]

    if len(df_active) < 100:
        return {
            "error": "Insufficient active data for percentile-based detection",
            "vt1_onset": None,
            "vt2_onset": None,
        }

    power_values = df_active[power_col].values
    hr_values = df_active[hr_col].values if hr_col in df_active.columns else None
    ve_values = df_active[ve_col].values if ve_col in df_active.columns else None

    # Calculate thresholds at specified percentiles
    vt1_power = np.percentile(power_values, vt1_percentile)
    vt2_power = np.percentile(power_values, vt2_percentile)

    # Find corresponding HR and VE values
    vt1_idx = np.argmin(np.abs(power_values - vt1_power))
    vt2_idx = np.argmin(np.abs(power_values - vt2_power))

    result = {
        "vt1_onset": {
            "power": float(vt1_power),
            "hr": float(hr_values[vt1_idx]) if hr_values is not None else None,
            "ve": float(ve_values[vt1_idx]) if ve_values is not None else None,
            "percentile": vt1_percentile,
            "method": "percentile_based",
        },
        "vt2_onset": {
            "power": float(vt2_power),
            "hr": float(hr_values[vt2_idx]) if hr_values is not None else None,
            "ve": float(ve_values[vt2_idx]) if ve_values is not None else None,
            "percentile": vt2_percentile,
            "method": "percentile_based",
        },
        "analysis_log": [
            f"VT1 detected at {vt1_power:.0f}W ({vt1_percentile:.0f}th percentile)",
            f"VT2 detected at {vt2_power:.0f}W ({vt2_percentile:.0f}th percentile)",
            "Method: Percentile-based estimation (fallback when gas exchange unavailable)",
        ],
        "confidence": 0.6,
        "method": "percentile_based",
    }

    return result
