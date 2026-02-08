"""
Threshold Detection Facade.
Orchestrates step detection, ventilatory, and metabolic threshold analysis.
"""
import pandas as pd

from .threshold_types import (
    HysteresisResult, 
    StepTestResult
)
from .ventilatory import (
    detect_vt_from_steps, detect_vt_transition_zone, 
    run_sensitivity_analysis
)
from .metabolic import detect_smo2_from_steps
# NOTE: _detect_smo2_thresholds_legacy removed - was never called
from .step_detection import (
    detect_step_test_range, segment_load_phases
)

def analyze_step_test(
    df: pd.DataFrame,
    step_duration_sec: int = 180,
    power_column: str = 'watts',
    ve_column: str = 'tymeventilation',
    smo2_column: str = 'smo2',
    hr_column: str = 'hr',
    time_column: str = 'time'
) -> StepTestResult:
    """High-level orchestration of step test analysis."""
    result = StepTestResult()
    df.columns = df.columns.str.lower().str.strip()
    
    has_ve = ve_column in df.columns
    has_smo2 = smo2_column in df.columns
    has_power = power_column in df.columns
    has_time = time_column in df.columns
    
    if not has_time:
        result.analysis_notes.append("Brak kolumny czasu")
        return result
    
    step_range = None
    df_test = df
    
    if has_power:
        step_range = detect_step_test_range(df, power_column=power_column, time_column=time_column)
        result.step_range = step_range
        if step_range and step_range.is_valid:
            mask = (df[time_column] >= step_range.start_time) & (df[time_column] <= step_range.end_time)
            df_test = df[mask].copy()
            result.steps_analyzed = len(step_range.steps)
            result.analysis_notes.append(f"✅ Wykryto test schodkowy: {len(step_range.steps)} stopni")
            result.analysis_notes.extend([f"  • {n}" for n in step_range.notes])
            
            if has_ve:
                vt_res = detect_vt_from_steps(
                    df, step_range,
                    ve_column=ve_column,
                    power_column=power_column,
                    hr_column=hr_column,
                    time_column=time_column,
                    vt1_slope_threshold=0.05,  # First breakpoint in VE slope
                    vt2_slope_threshold=0.10   # Accelerated VE rise per INSCYD/WKO5
                )
                result.vt1_watts = vt_res.vt1_watts
                result.vt1_hr = vt_res.vt1_hr
                result.vt2_watts = vt_res.vt2_watts
                result.vt2_hr = vt_res.vt2_hr
                result.vt1_ve = vt_res.vt1_ve
                result.vt1_br = vt_res.vt1_br
                result.vt2_ve = vt_res.vt2_ve
                result.vt2_br = vt_res.vt2_br
                result.analysis_notes.extend(vt_res.notes)
                result.step_ve_analysis = vt_res.step_analysis
            
            if has_smo2:
                smo2_res = detect_smo2_from_steps(df, step_range, smo2_column=smo2_column, power_column=power_column, hr_column=hr_column, time_column=time_column)
                result.smo2_1_watts = smo2_res.smo2_1_watts
                result.smo2_1_hr = smo2_res.smo2_1_hr
                result.smo2_2_watts = smo2_res.smo2_2_watts
                result.smo2_2_hr = smo2_res.smo2_2_hr
                result.smo2_1_value = smo2_res.smo2_1_value
                result.smo2_2_value = smo2_res.smo2_2_value
                result.step_smo2_analysis = smo2_res.step_analysis
        else:
            notes = step_range.notes if step_range else ["Nie znaleziono prawidłowego testu schodkowego"]
            result.analysis_notes.extend([f"⚠️ {n}" for n in notes])
            result.analysis_notes.append("Używanie detekcji legacy (sliding window)")
        
    if has_ve and has_power and result.vt1_watts is None:
        df_temp = df_test# Fallback
        df_inc, df_dec = segment_load_phases(df_temp, power_col=power_column, time_col=time_column)
        vt1_inc, vt2_inc = detect_vt_transition_zone(
            df_inc, 
            window_duration=60, 
            step_size=5,
            ve_column=ve_column, 
            power_column=power_column, 
            hr_column=hr_column, 
            time_column=time_column
        )
        result.vt1_zone, result.vt2_zone = vt1_inc, vt2_inc
        if vt1_inc:
            result.vt1_watts = sum(vt1_inc.range_watts)/2
            result.vt1_hr = sum(vt1_inc.range_hr)/2 if vt1_inc.range_hr else None
        if vt2_inc:
            result.vt2_watts = sum(vt2_inc.range_watts)/2
            result.vt2_hr = sum(vt2_inc.range_hr)/2 if vt2_inc.range_hr else None
            
        if not df_dec.empty:
            vt1_dec, vt2_dec = detect_vt_transition_zone(df_dec, ve_column=ve_column, power_column=power_column, hr_column=hr_column, time_column=time_column)
            h = HysteresisResult(vt1_inc_zone=vt1_inc, vt1_dec_zone=vt1_dec, vt2_inc_zone=vt2_inc, vt2_dec_zone=vt2_dec)
            if vt1_inc and vt1_dec: h.vt1_shift_watts = sum(vt1_dec.range_watts)/2 - sum(vt1_inc.range_watts)/2
            if vt2_inc and vt2_dec: h.vt2_shift_watts = sum(vt2_dec.range_watts)/2 - sum(vt2_inc.range_watts)/2
            result.hysteresis = h
            
        result.sensitivity = run_sensitivity_analysis(df_inc, ve_column=ve_column, power_column=power_column, hr_column=hr_column, time_column=time_column)

    return result

def calculate_training_zones_from_thresholds(vt1_watts: int, vt2_watts: int, cp=None, max_hr: int = 185) -> dict:
    """Calculate training zones based on thresholds.
    
    ENHANCED: Z3 is now split into Z3a_LowTempo and Z3b_SweetSpot to avoid
    putting metabolically different intensities into one bucket.
    
    Zone model:
    - Z1: Recovery (< 75% VT1)
    - Z2: Endurance (75% VT1 → VT1)
    - Z3a: Low Tempo (VT1 → VT1 + 35% gap)  ← NEW
    - Z3b: Sweet Spot (VT1 + 35% gap → midpoint)  ← NEW  
    - Z4: Threshold (midpoint → VT2)
    - Z5: VO2max (VT2 → 120% CP)
    - Z6: Anaerobic (120% CP → 150% CP)
    """
    if cp is None: cp = vt2_watts
    v1 = vt1_watts if vt1_watts else 0
    v2 = vt2_watts if vt2_watts else 0
    
    # Calculate zone boundaries
    gap = v2 - v1  # Gap between VT1 and VT2
    midpoint = int((v1 + v2) / 2)
    
    # Split point for Z3a/Z3b: 35% of the gap above VT1
    # This puts Low Tempo as the "comfortable tempo" zone
    # and Sweet Spot as the "hard tempo" zone closer to threshold
    z3_split = int(v1 + gap * 0.35)
    
    return {
        "power_zones": {
            "Z1_Recovery": (0, int(v1 * 0.75)),
            "Z2_Endurance": (int(v1 * 0.75), int(v1)),
            "Z3a_LowTempo": (int(v1), z3_split),
            "Z3b_SweetSpot": (z3_split, midpoint),
            "Z4_Threshold": (midpoint, int(v2)),
            "Z5_VO2max": (int(v2), int(cp * 1.2)),
            "Z6_Anaerobic": (int(cp * 1.2), int(cp * 1.5))
        },
        "hr_zones": {
            "Z1_Recovery": (0, int(max_hr * 0.6)),
            "Z2_Endurance": (int(max_hr * 0.6), int(max_hr * 0.7)),
            "Z3a_LowTempo": (int(max_hr * 0.7), int(max_hr * 0.75)),
            "Z3b_SweetSpot": (int(max_hr * 0.75), int(max_hr * 0.8)),
            "Z4_Threshold": (int(max_hr * 0.8), int(max_hr * 0.9)),
            "Z5_VO2max": (int(max_hr * 0.9), max_hr)
        },
        "zone_descriptions": {
            "Z1_Recovery": "Regeneracja",
            "Z2_Endurance": "Baza tlenowa",
            "Z3a_LowTempo": "Tempo niskie (komfortowe)",
            "Z3b_SweetSpot": "Sweet Spot (twarde tempo)",
            "Z4_Threshold": "Próg FTP",
            "Z5_VO2max": "VO2max",
            "Z6_Anaerobic": "Beztlenowa"
        }
    }
