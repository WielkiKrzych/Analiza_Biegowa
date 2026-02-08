"""
Thermoregulation Analysis Module.

Analyzes core temperature dynamics, heat tolerance, and heat adaptation status.

Key metrics:
- Max Core Temp
- ΔCore Temp / 10 min (heat accumulation rate)
- Time to critical thresholds (38.0°C, 38.5°C)
- Peak HSI (Heat Strain Index)
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import numpy as np
import logging

logger = logging.getLogger("Tri_Dashboard.Thermoregulation")


@dataclass
class ThermoProfile:
    """Thermoregulation analysis results."""
    # Core metrics
    max_core_temp: float = 0.0           # Max core temperature [°C]
    min_core_temp: float = 0.0           # Baseline temperature [°C]
    delta_core_temp: float = 0.0         # Total temperature rise [°C]
    delta_per_10min: float = 0.0         # Temperature rise rate [°C / 10min]
    
    # Critical thresholds crossing times (minutes from start)
    time_to_38_0: Optional[float] = None   # Time to reach 38.0°C
    time_to_38_5: Optional[float] = None   # Time to reach 38.5°C (critical)
    
    # Heat strain
    peak_hsi: float = 0.0                # Peak Heat Strain Index
    mean_hsi: float = 0.0                # Mean HSI
    
    # Classification
    heat_tolerance: str = "unknown"       # good, moderate, poor
    classification_color: str = "#808080"
    
    # Interpretation
    mechanism_description: str = ""
    hr_ef_connection: str = ""
    recommendations: List[str] = field(default_factory=list)
    
    # Quality
    data_points: int = 0
    confidence: float = 0.0


def analyze_thermoregulation(
    core_temp: np.ndarray,
    time_seconds: np.ndarray,
    hr: Optional[np.ndarray] = None,
    power: Optional[np.ndarray] = None,
    hsi: Optional[np.ndarray] = None,
    cardiac_drift_pct: Optional[float] = None,
    ef_drop_pct: Optional[float] = None
) -> ThermoProfile:
    """
    Analyze thermoregulation from core temperature data.
    
    ENHANCED: Now considers physiological cost (cardiac drift, EF drop) in addition
    to temperature rise rate. A slow temp rise but high EF drop = POOR tolerance.
    
    Args:
        core_temp: Core temperature values [°C]
        time_seconds: Time array [seconds]
        hr: Optional heart rate data [bpm]
        power: Optional power data [W]
        hsi: Optional pre-calculated HSI
        cardiac_drift_pct: Cardiac drift percentage (decoupling)
        ef_drop_pct: Efficiency Factor drop percentage (EF first half vs last half)
        
    Returns:
        ThermoProfile with analysis results
    """
    profile = ThermoProfile()
    
    # Filter valid data
    mask = (~np.isnan(core_temp)) & (core_temp > 35) & (core_temp < 42)
    temp_valid = core_temp[mask]
    time_valid = time_seconds[mask]
    
    if len(temp_valid) < 30:
        logger.warning("Insufficient temperature data for analysis")
        profile.mechanism_description = "Niewystarczajace dane temperatury do analizy."
        return profile
    
    profile.data_points = len(temp_valid)
    
    # === CORE METRICS ===
    profile.max_core_temp = float(np.max(temp_valid))
    profile.min_core_temp = float(np.min(temp_valid[:min(60, len(temp_valid))]))  # First minute baseline
    profile.delta_core_temp = profile.max_core_temp - profile.min_core_temp
    
    # Temperature rise rate (°C per 10 minutes)
    duration_min = (time_valid[-1] - time_valid[0]) / 60
    if duration_min > 0:
        profile.delta_per_10min = (profile.delta_core_temp / duration_min) * 10
    
    # === CRITICAL THRESHOLD TIMES ===
    time_min = (time_valid - time_valid[0]) / 60
    
    idx_38_0 = np.where(temp_valid >= 38.0)[0]
    if len(idx_38_0) > 0:
        profile.time_to_38_0 = float(time_min[idx_38_0[0]])
    
    idx_38_5 = np.where(temp_valid >= 38.5)[0]
    if len(idx_38_5) > 0:
        profile.time_to_38_5 = float(time_min[idx_38_5[0]])
    
    # === HSI ===
    if hsi is not None:
        hsi_valid = hsi[mask] if len(hsi) == len(core_temp) else hsi
        hsi_valid = hsi_valid[~np.isnan(hsi_valid)]
        if len(hsi_valid) > 0:
            profile.peak_hsi = float(np.max(hsi_valid))
            profile.mean_hsi = float(np.mean(hsi_valid))
    
    # ==========================================================================
    # ENHANCED CLASSIFICATION (Multi-Factor) 
    # Considers: temp rise rate, HSI, cardiac drift, EF drop
    # ==========================================================================
    
    # Initialize scores (0 = good, higher = worse)
    tolerance_score = 0
    
    # Factor 1: Temperature rise rate (legacy)
    if profile.delta_per_10min >= 0.5:
        tolerance_score += 2
    elif profile.delta_per_10min >= 0.3:
        tolerance_score += 1
    
    # Factor 2: Peak HSI
    if profile.peak_hsi >= 8:
        tolerance_score += 2  # Critical HSI
    elif profile.peak_hsi >= 6:
        tolerance_score += 1  # Elevated HSI
    
    # Factor 3: Cardiac Drift (CRITICAL - reflects actual physiological cost)
    if cardiac_drift_pct is not None:
        abs_drift = abs(cardiac_drift_pct)
        if abs_drift >= 15:
            tolerance_score += 3  # Extreme drift - major physiological strain
            logger.info(f"Thermal: Cardiac drift {abs_drift:.1f}% → +3 to poor tolerance")
        elif abs_drift >= 10:
            tolerance_score += 2
        elif abs_drift >= 6:
            tolerance_score += 1
    
    # Factor 4: EF Drop (CRITICAL - efficiency cost due to heat)
    if ef_drop_pct is not None:
        abs_ef_drop = abs(ef_drop_pct)
        if abs_ef_drop >= 20:
            tolerance_score += 3  # Brutal EF drop - efficiency destroyed by heat
            logger.info(f"Thermal: EF drop {abs_ef_drop:.1f}% → +3 to poor tolerance")
        elif abs_ef_drop >= 12:
            tolerance_score += 2
        elif abs_ef_drop >= 6:
            tolerance_score += 1
    
    # === FINAL CLASSIFICATION ===
    # Score >= 4: POOR (even if temp rise is slow, physiological cost is high)
    # Score 2-3: MODERATE
    # Score 0-1: GOOD
    
    if tolerance_score >= 4:
        profile.heat_tolerance = "poor"
        profile.classification_color = "#E74C3C"  # Red
    elif tolerance_score >= 2:
        profile.heat_tolerance = "moderate"
        profile.classification_color = "#F39C12"  # Orange
    else:
        profile.heat_tolerance = "good"
        profile.classification_color = "#27AE60"  # Green
    
    logger.info(f"Thermal tolerance: {profile.heat_tolerance} (score={tolerance_score}, "
                f"delta={profile.delta_per_10min:.2f}, HSI={profile.peak_hsi:.1f}, "
                f"drift={cardiac_drift_pct}, ef_drop={ef_drop_pct})")
    
    # === INTERPRETATION ===
    profile.mechanism_description = _generate_thermo_mechanism(profile, cardiac_drift_pct, ef_drop_pct)
    profile.hr_ef_connection = _generate_hr_ef_connection(profile, hr, power, cardiac_drift_pct, ef_drop_pct)
    profile.recommendations = _generate_thermo_recommendations(profile)
    
    # Confidence
    profile.confidence = min(1.0, profile.data_points / 500)
    
    return profile


def _generate_thermo_mechanism(
    profile: ThermoProfile,
    cardiac_drift_pct: Optional[float] = None,
    ef_drop_pct: Optional[float] = None
) -> str:
    """Generate thermoregulation mechanism description."""
    drift_text = f"Dryf HR: {abs(cardiac_drift_pct):.1f}%. " if cardiac_drift_pct and abs(cardiac_drift_pct) > 5 else ""
    ef_text = f"Spadek EF: {abs(ef_drop_pct):.1f}%. " if ef_drop_pct and abs(ef_drop_pct) > 5 else ""
    
    if profile.heat_tolerance == "poor":
        return (
            f"SLABA tolerancja cieplna. {drift_text}{ef_text}"
            f"Tempo narastania temperatury ({profile.delta_per_10min:.2f} C/10min) "
            "lub koszt fizjologiczny przekracza prog bezpieczny. Mechanizm: redystrybucja krwi do skory "
            "konkuruje z dostawa O2 do miesni. Efektywnosc spadla drastycznie, "
            "ryzyko przegrzania wysokie. Dlugie jednostki (>90 min) nie sa bezpieczne bez chlodzenia."
        )
    elif profile.heat_tolerance == "moderate":
        return (
            f"Umiarkowana tolerancja cieplna. {drift_text}{ef_text}"
            f"Temperatura rosla w tempie {profile.delta_per_10min:.2f} C/10min. "
            "Uklad chlodzenia radzi sobie, ale istnieje margines do poprawy. "
            "Adaptacja cieplna nie jest pelna - rozważ trening w cieple."
        )
    else:
        return (
            f"Dobra tolerancja cieplna. Tempo narastania temperatury ({profile.delta_per_10min:.2f} C/10min) "
            "miesci sie w normie. Uklad termoregulacji skutecznie balansuje miedzy chlodzeniem a perfuzja."
        )


def _generate_hr_ef_connection(
    profile: ThermoProfile,
    hr: Optional[np.ndarray],
    power: Optional[np.ndarray],
    cardiac_drift_pct: Optional[float] = None,
    ef_drop_pct: Optional[float] = None
) -> str:
    """Generate connection between thermoregulation and HR/EF."""
    if profile.heat_tolerance == "poor":
        actual_drift = f" (rzeczywisty dryf: {abs(cardiac_drift_pct):.1f}%)" if cardiac_drift_pct else ""
        actual_ef = f" Spadek EF: {abs(ef_drop_pct):.1f}%." if ef_drop_pct else ""
        return (
            f"KRYTYCZNE polaczenie z dryfem HR{actual_drift}:{actual_ef} "
            "Wysoka temperatura wymusza redystrybucje krwi do skory. "
            "Serce musi pompowac wieksza objetosc krwi. "
            "To jest kardynalny syndrom przegrzania - ryzyko metabolicznego 'ugotowania' po 90 min."
        )
    elif profile.heat_tolerance == "moderate":
        return (
            "Umiarkowany wplyw na HR/EF. Dryf tetna moze wystepowac, ale nie jest gwaltowny. "
            "Chlodzenie zewnetrzne (woda, wiatr) znaczaco zmniejszy obciazenie ukladu krazenia."
        )
    else:
        return (
            "Minimalny wplyw na HR/EF. Adaptacja cieplna pozwala na efektywne odprowadzanie "
            "ciepla bez znaczacego obciazania ukladu krazenia. EF pozostaje stabilny."
        )


def _generate_thermo_recommendations(profile: ThermoProfile) -> List[str]:
    """Generate specific thermoregulation recommendations."""
    if profile.heat_tolerance == "poor":
        return [
            "PRIORYTET: Trening w cieple (heat acclimation) - 10-14 dni, 60-90min @ Z2",
            "Strategie chlodzenia: pre-cooling (kamizelka lodowa), chlodzenie przemienne",
            "Nawodnienie: 500-800ml/h + elektrolity, pij PRZED pragnieniem",
            "Unikaj zawodow w temperaturze >28C do czasu adaptacji",
            "Obniz intensywnosc o 5-10% w ciepłe dni",
        ]
    elif profile.heat_tolerance == "moderate":
        return [
            "Rozważ 5-7 dni treningu w cieple przed ważnymi zawodami",
            "Chlodzenie zewnetrzne: woda na glowe i kark co 15-20 min",
            "Nawodnienie: kontroluj wage przed/po treningu (max -2%)",
            "W cieple preferuj poranne lub wieczorne starty",
        ]
    else:
        return [
            "Adaptacja cieplna wystarczaca - mozesz startowac w ciepłe dni",
            "Utrzymuj nawodnienie na poziomie 400-600ml/h",
            "Kontynuuj okresowy trening w cieple (1x/tydzien) dla utrzymania adaptacji",
        ]


def format_thermo_for_report(profile: ThermoProfile) -> Dict[str, Any]:
    """Format thermoregulation analysis for JSON/PDF reports."""
    return {
        "metrics": {
            "max_core_temp": round(profile.max_core_temp, 2),
            "min_core_temp": round(profile.min_core_temp, 2),
            "delta_core_temp": round(profile.delta_core_temp, 2),
            "delta_per_10min": round(profile.delta_per_10min, 3),
            "time_to_38_0_min": round(profile.time_to_38_0, 1) if profile.time_to_38_0 else None,
            "time_to_38_5_min": round(profile.time_to_38_5, 1) if profile.time_to_38_5 else None,
            "peak_hsi": round(profile.peak_hsi, 2),
            "mean_hsi": round(profile.mean_hsi, 2),
        },
        "classification": {
            "heat_tolerance": profile.heat_tolerance,
            "color": profile.classification_color,
            "thresholds": {
                "good": "<0.3 C/10min",
                "moderate": "0.3-0.5 C/10min",
                "poor": ">0.5 C/10min"
            }
        },
        "interpretation": {
            "mechanism": profile.mechanism_description,
            "hr_ef_connection": profile.hr_ef_connection,
            "recommendations": profile.recommendations
        },
        "quality": {
            "data_points": profile.data_points,
            "confidence": round(profile.confidence, 2)
        }
    }


__all__ = [
    "ThermoProfile",
    "analyze_thermoregulation",
    "format_thermo_for_report",
]
