"""
SRP: Moduł odpowiedzialny za obliczenia związane z żywieniem.
"""
from typing import Union, Any
import numpy as np
import pandas as pd

from .common import (
    ensure_pandas, 
    EFFICIENCY_FACTOR, 
    KCAL_PER_JOULE, 
    KCAL_PER_GRAM_CARB,
    CARB_FRACTION_BELOW_VT1,
    CARB_FRACTION_VT1_VT2,
    CARB_FRACTION_ABOVE_VT2
)


def estimate_carbs_burned(df_pl: Union[pd.DataFrame, Any], vt1_watts: float, vt2_watts: float) -> float:
    """
    Estimate carbohydrate consumption based on power zones.
    
    Assumption: 22% mechanical efficiency.
    Carb utilization varies by zone:
    - Below VT1: ~40% carbs
    - VT1 to VT2: ~70% carbs
    - Above VT2: ~100% carbs
    
    Args:
        df_pl: DataFrame with 'watts' column
        vt1_watts: Ventilatory Threshold 1 power [W]
        vt2_watts: Ventilatory Threshold 2 power [W]
    
    Returns:
        Total carbohydrates burned [g]
    """
    df = ensure_pandas(df_pl)
    if 'watts' not in df.columns:
        return 0.0
        
    # Energy per second (kcal/s)
    # Power (W = J/s). Efficiency ~22% -> Total Energy = Power / efficiency
    energy_kcal_sec = (df['watts'] / EFFICIENCY_FACTOR) * KCAL_PER_JOULE
    
    # Carb fraction by zone
    conditions = [
        (df['watts'] < vt1_watts),
        (df['watts'] >= vt1_watts) & (df['watts'] < vt2_watts),
        (df['watts'] >= vt2_watts)
    ]
    choices = [CARB_FRACTION_BELOW_VT1, CARB_FRACTION_VT1_VT2, CARB_FRACTION_ABOVE_VT2]
    carb_fraction = np.select(conditions, choices, default=1.0)
    
    # 1 g carbs = 4 kcal
    carbs_burned_sec = (energy_kcal_sec * carb_fraction) / KCAL_PER_GRAM_CARB
    
    return carbs_burned_sec.sum()


# =============================================================================
# MULTI-FACTOR GLYCOGEN CONSUMPTION MODEL
# =============================================================================

def calculate_glycogen_consumption(
    power: float,
    cp: float,
    core_temp: float = 37.5,
    vlamax: float = 0.5,
    occlusion_index: float = 0.15,
    smo2_slope: float = -0.02,
    cadence: float = 90.0
) -> dict:
    """
    Calculate glycogen consumption rate with multi-factor adjustments.
    
    Base model: CHO consumption scales with power relative to CP.
    Modifiers applied for:
    - Core temperature (hyperthermia increases CHO usage)
    - VLaMax (glycolytic capacity)
    - Occlusion index (restricted perfusion = more anaerobic)
    - SmO2 slope (desaturation rate)
    - Cadence (low cadence = higher torque = more occlusion)
    
    Args:
        power: Power output [W]
        cp: Critical Power [W]
        core_temp: Core temperature [°C] (normal: 37-37.5)
        vlamax: VLaMax [mmol/L/s] (typical: 0.3-0.8)
        occlusion_index: Occlusion index (0-1, higher = more occlusion)
        smo2_slope: SmO2 slope [%/Nm] (negative = desaturation)
        cadence: Pedaling cadence [RPM]
        
    Returns:
        dict with CHO consumption [g/h] and breakdown
    """
    import numpy as np
    
    if power <= 0 or cp <= 0:
        return {"cho_g_per_hour": 0, "breakdown": {}, "warnings": []}
    
    # === BASE CHO CONSUMPTION ===
    # At CP, ~60g/h CHO usage; scales roughly linearly with intensity
    intensity_pct = power / cp * 100
    
    # Base formula: exponential increase above threshold
    if intensity_pct < 60:
        cho_base = 30 + (intensity_pct / 60) * 20  # 30-50 g/h
    elif intensity_pct < 100:
        cho_base = 50 + ((intensity_pct - 60) / 40) * 40  # 50-90 g/h
    else:
        cho_base = 90 + (intensity_pct - 100) * 1.5  # >90 g/h, rapid increase
    
    # === MODIFIERS ===
    modifiers = {}
    warnings = []
    
    # 1. Temperature modifier (+5% per 0.5°C above 37.5°C)
    temp_delta = max(0, core_temp - 37.5)
    temp_modifier = 1 + (temp_delta * 0.10)  # 10% per degree
    modifiers["temperature"] = temp_modifier
    if temp_delta > 1.0:
        warnings.append(f"⚠️ Wysoka temperatura rdzenia ({core_temp:.1f}°C) zwiększa zużycie CHO o {(temp_modifier-1)*100:.0f}%")
    
    # 2. VLaMax modifier (higher VLaMax = more glycolytic capacity used)
    # Reference: VLaMax 0.5 = neutral, >0.6 = glycolytic, <0.4 = oxidative
    vlamax_modifier = 1 + (vlamax - 0.5) * 0.5  # ±25% at VLaMax ±0.5
    modifiers["vlamax"] = vlamax_modifier
    
    # 3. Occlusion modifier (restricted blood flow = more anaerobic)
    # Reference: occlusion_index 0.15 = low, 0.30 = high
    occlusion_modifier = 1 + (occlusion_index * 0.8)  # up to +24% at high occlusion
    modifiers["occlusion"] = occlusion_modifier
    if occlusion_index > 0.25:
        warnings.append(f"🔴 Wysoka okluzja mechaniczna (+{(occlusion_modifier-1)*100:.0f}% CHO)")
    
    # 4. SmO2 slope modifier (steep desaturation = more anaerobic work)
    # Negative slope = desaturation per Nm
    smo2_modifier = 1 + abs(smo2_slope) * 5  # scale appropriately
    modifiers["smo2_slope"] = smo2_modifier
    
    # 5. Cadence modifier (low cadence = high torque = more occlusion)
    # Reference: 90 RPM = neutral, <70 RPM = high torque penalty
    if cadence < 70:
        cadence_modifier = 1 + (70 - cadence) * 0.01  # +1% per RPM below 70
    elif cadence > 100:
        cadence_modifier = 1 - (cadence - 100) * 0.005  # -0.5% per RPM above 100
    else:
        cadence_modifier = 1.0
    modifiers["cadence"] = cadence_modifier
    
    # === FINAL CALCULATION ===
    total_modifier = temp_modifier * vlamax_modifier * occlusion_modifier * smo2_modifier * cadence_modifier
    cho_final = cho_base * total_modifier
    
    return {
        "cho_g_per_hour": round(cho_final, 1),
        "cho_base": round(cho_base, 1),
        "total_modifier": round(total_modifier, 3),
        "intensity_pct": round(intensity_pct, 1),
        "breakdown": modifiers,
        "warnings": warnings
    }


def compare_cadence_glycogen(
    power: float,
    cp: float,
    cadence_low: float = 60.0,
    cadence_high: float = 95.0,
    core_temp: float = 37.5,
    vlamax: float = 0.5,
    occlusion_index_low: float = 0.35,  # High occlusion at low cadence
    occlusion_index_high: float = 0.12,  # Low occlusion at high cadence
    smo2_slope: float = -0.02
) -> dict:
    """
    Compare glycogen consumption at different cadences for same power.
    
    Demonstrates metabolic cost of occlusion.
    
    Args:
        power: Power output [W]
        cp: Critical Power [W]
        cadence_low: Low cadence [RPM]
        cadence_high: High cadence [RPM]
        Other params: See calculate_glycogen_consumption
        
    Returns:
        dict with comparison results
    """
    import numpy as np
    
    # Calculate for low cadence (grinding)
    result_low = calculate_glycogen_consumption(
        power=power,
        cp=cp,
        core_temp=core_temp,
        vlamax=vlamax,
        occlusion_index=occlusion_index_low,
        smo2_slope=smo2_slope,
        cadence=cadence_low
    )
    
    # Calculate for high cadence (spinning)
    result_high = calculate_glycogen_consumption(
        power=power,
        cp=cp,
        core_temp=core_temp,
        vlamax=vlamax,
        occlusion_index=occlusion_index_high,
        smo2_slope=smo2_slope,
        cadence=cadence_high
    )
    
    # Calculate delta
    delta_cho = result_low["cho_g_per_hour"] - result_high["cho_g_per_hour"]
    delta_pct = (delta_cho / result_high["cho_g_per_hour"] * 100) if result_high["cho_g_per_hour"] > 0 else 0
    
    # Occlusion cost
    torque_low = power / (2 * np.pi * (cadence_low / 60))
    torque_high = power / (2 * np.pi * (cadence_high / 60))
    
    return {
        "power": power,
        "low_cadence": {
            "cadence": cadence_low,
            "torque": round(torque_low, 1),
            "cho_g_per_hour": result_low["cho_g_per_hour"],
            "occlusion_index": occlusion_index_low
        },
        "high_cadence": {
            "cadence": cadence_high,
            "torque": round(torque_high, 1),
            "cho_g_per_hour": result_high["cho_g_per_hour"],
            "occlusion_index": occlusion_index_high
        },
        "delta_cho_g_per_hour": round(delta_cho, 1),
        "delta_pct": round(delta_pct, 1),
        "metabolic_cost_occlusion": f"+{delta_cho:.1f} g/h ({delta_pct:.1f}%) at {cadence_low:.0f} RPM vs {cadence_high:.0f} RPM"
    }
