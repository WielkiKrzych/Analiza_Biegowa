"""
SRP: Moduł odpowiedzialny za obliczenia termiczne (Heat Strain Index).
"""
from typing import Union, Any
import pandas as pd
import numpy as np

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
