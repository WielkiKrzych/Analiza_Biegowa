"""
Biomechanical Occlusion Analysis Module.

Analyzes the relationship between torque (muscle force) and SmO2 (oxygen delivery)
to identify mechanical occlusion patterns during high-force pedaling.

Key metrics:
- OCCLUSION INDEX = |ΔSmO₂| / ΔTorque
- Torque at SmO2 thresholds (baseline, -10%, -20%)
- Regression slope (SmO2 vs Torque)
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import numpy as np
from scipy import stats
import logging

logger = logging.getLogger("Tri_Dashboard.BiomechOcclusion")


@dataclass
class OcclusionProfile:
    """Biomechanical occlusion analysis results."""
    # Core metrics
    occlusion_index: float = 0.0          # |ΔSmO₂| / ΔTorque
    regression_slope: float = 0.0          # %SmO₂ / Nm
    regression_r2: float = 0.0             # R² of regression
    
    # Torque at SmO2 thresholds
    smo2_baseline: float = 0.0             # Baseline SmO2 %
    torque_at_baseline: float = 0.0        # Nm at baseline
    torque_at_minus_10: float = 0.0        # Nm at SmO2 -10%
    torque_at_minus_20: float = 0.0        # Nm at SmO2 -20% (significant occlusion)
    
    # Classification
    classification: str = "unknown"         # low, moderate, high
    classification_color: str = "#808080"
    
    # Interpretation
    mechanism_description: str = ""
    riding_style_impact: str = ""
    training_recommendations: List[str] = field(default_factory=list)
    
    # Data quality
    data_points: int = 0
    confidence: float = 0.0


def analyze_biomech_occlusion(
    torque: np.ndarray,
    smo2: np.ndarray,
    cadence: Optional[np.ndarray] = None
) -> OcclusionProfile:
    """
    Analyze mechanical occlusion from torque-SmO2 relationship.
    
    Args:
        torque: Moment obrotowy [Nm]
        smo2: SmO2 values [%]
        cadence: Optional cadence [rpm]
        
    Returns:
        OcclusionProfile with analysis results
    """
    profile = OcclusionProfile()
    
    # Filter valid data
    mask = (torque > 0) & (smo2 > 10) & (~np.isnan(torque)) & (~np.isnan(smo2))
    torque_valid = torque[mask]
    smo2_valid = smo2[mask]
    
    if len(torque_valid) < 30:
        logger.warning("Insufficient data for occlusion analysis")
        profile.mechanism_description = "Niewystarczające dane do analizy okluzji."
        return profile
    
    profile.data_points = len(torque_valid)
    
    # === BASELINE SmO2 ===
    # Use lower quartile of torque for baseline
    low_torque_mask = torque_valid < np.percentile(torque_valid, 25)
    if np.sum(low_torque_mask) > 5:
        profile.smo2_baseline = float(np.mean(smo2_valid[low_torque_mask]))
        profile.torque_at_baseline = float(np.mean(torque_valid[low_torque_mask]))
    else:
        profile.smo2_baseline = float(np.percentile(smo2_valid, 75))
        profile.torque_at_baseline = float(np.min(torque_valid))
    
    # === REGRESSION: SmO2 vs Torque ===
    slope, intercept, r_value, p_value, std_err = stats.linregress(torque_valid, smo2_valid)
    profile.regression_slope = float(slope)  # %SmO2 per Nm
    profile.regression_r2 = float(r_value ** 2)
    
    # === TORQUE AT SmO2 THRESHOLDS ===
    target_smo2_10 = profile.smo2_baseline - 10
    target_smo2_20 = profile.smo2_baseline - 20
    
    if slope != 0:
        # From linear regression: torque = (smo2 - intercept) / slope
        profile.torque_at_minus_10 = float((target_smo2_10 - intercept) / slope) if slope != 0 else 0
        profile.torque_at_minus_20 = float((target_smo2_20 - intercept) / slope) if slope != 0 else 0
    
    # === OCCLUSION INDEX ===
    # |ΔSmO₂| / ΔTorque over full range
    delta_smo2 = np.max(smo2_valid) - np.min(smo2_valid)
    delta_torque = np.max(torque_valid) - np.min(torque_valid)
    
    if delta_torque > 0:
        profile.occlusion_index = abs(delta_smo2) / delta_torque
    
    # === CLASSIFICATION ===
    if profile.occlusion_index < 0.15:
        profile.classification = "low"
        profile.classification_color = "#27AE60"  # Green
    elif profile.occlusion_index < 0.30:
        profile.classification = "moderate"
        profile.classification_color = "#F39C12"  # Orange
    else:
        profile.classification = "high"
        profile.classification_color = "#E74C3C"  # Red
    
    # === MECHANISM DESCRIPTION ===
    profile.mechanism_description = _generate_mechanism_description(profile)
    profile.riding_style_impact = _generate_riding_style_impact(profile, cadence)
    profile.training_recommendations = _generate_training_recommendations(profile)
    
    # Confidence based on R² and data points
    profile.confidence = min(1.0, profile.regression_r2 * (profile.data_points / 100))
    
    return profile


def _generate_mechanism_description(profile: OcclusionProfile) -> str:
    """Generate physiological mechanism description."""
    if profile.classification == "high":
        return (
            "Wysoka okluzja mechaniczna. Przy wysokich momentach obrotowych (>{}Nm) "
            "obserwujemy znaczny spadek SmO₂ o {}%. Mechanizm: wzrost napięcia izometrycznego "
            "powoduje kompresję naczyń wewnątrzmięśniowych, ograniczając perfuzję mimo "
            "dostępnego VO₂ systemowego. Przepływ krwi jest mechanicznie utrudniony, "
            "co prowadzi do przedwczesnej desaturacji i akumulacji metabolitów."
        ).format(
            int(profile.torque_at_minus_20) if profile.torque_at_minus_20 > 0 else "---",
            int(profile.smo2_baseline - (profile.smo2_baseline - 20)) if profile.smo2_baseline > 20 else "---"
        )
    elif profile.classification == "moderate":
        return (
            "Umiarkowana okluzja mechaniczna. Spadek SmO₂ jest proporcjonalny do wzrostu "
            "momentu obrotowego (nachylenie: {:.3f} %/Nm). Mięśnie wykazują tolerancję na "
            "wyższe siły bez pełnego ograniczenia perfuzji, jednak istnieje wyraźna granica "
            "powyżej której desaturacja przyspiesza."
        ).format(profile.regression_slope)
    else:
        return (
            "Niska okluzja mechaniczna. Układ mikrokrążenia skutecznie dostarcza tlen "
            "nawet przy wysokich momentach obrotowych. Kapilaryzacja mięśniowa jest "
            "wystarczająca, aby utrzymać perfuzję podczas wysiłków siłowych. "
            "Profil wskazuje na dobrą adaptację do treningu siłowego."
        )


def _generate_riding_style_impact(
    profile: OcclusionProfile, 
    cadence: Optional[np.ndarray] = None
) -> str:
    """Generate riding style impact analysis."""
    if profile.classification == "high":
        return (
            "STYL SIŁOWY (niska kadencja) jest niekorzystny. Przy każdym naciśnięciu na pedały "
            "zachodzi kompresja naczyń, co wymusza pracę w warunkach hipoksji lokalnej. "
            "Preferowany styl: KADENCYJNY (90-100 rpm), który rozkłada obciążenie w czasie "
            "i pozwala na ciągłą reperfuzję między skurczami."
        )
    elif profile.classification == "moderate":
        return (
            "Styl jazdy powinien być zróżnicowany. Na płaskim terenie preferuj wyższą kadencję "
            "(85-95 rpm), natomiast podczas wspinaczek krótkotrwałe momenty siłowe są akceptowalne. "
            "Unikaj długich odcinków w niskiej kadencji (<70 rpm) przy wysokich mocach."
        )
    else:
        return (
            "Styl jazdy może być siłowy lub kadencyjny w zależności od preferencji. "
            "Niska okluzja oznacza, że możesz efektywnie generować moc zarówno przy "
            "wysokich momentach obrotowych (wspinaczki), jak i przy wysokiej kadencji (sprint). "
            "Wykorzystuj tę elastyczność taktycznie."
        )


def _generate_training_recommendations(profile: OcclusionProfile) -> List[str]:
    """Generate specific training recommendations."""
    if profile.classification == "high":
        return [
            "Priorytet: PRACA NAD KADENCJĄ - interwały 3x5min @ 95-100rpm w Z3-Z4",
            "Treningi submaksymalne z monitoringiem SmO₂ - utrzymuj SmO₂ >55%",
            "Single Leg Drills - poprawa efektywności pedalowania",
            "Unikaj: ciężkich przełożeń przy mocach >85% CP",
        ]
    elif profile.classification == "moderate":
        return [
            "Zróżnicowany trening: 60% kadencja / 40% siła",
            "Interwały FRC z rotacją kadencji (80-90-100 rpm)",
            "Wspinaczki siedzące z kontrolowanym momentem (<{}Nm)".format(
                int(profile.torque_at_minus_10) if profile.torque_at_minus_10 > 0 else "max"
            ),
            "Ćwiczenia core - redukcja kompensacyjnych ruchów miednicy",
        ]
    else:
        return [
            "Możliwość dalszej pracy siłowej - interwały Big Gear",
            "Treningi Strength Endurance: 4x10min @ 50-60rpm, Z3",
            "Wspinaczki stojące z wysokim momentem obrotowym",
            "Rozważ trening kolarski na bieżni z oporem (hill repeats)",
        ]


def format_occlusion_for_report(profile: OcclusionProfile) -> Dict[str, Any]:
    """Format occlusion analysis for JSON/PDF reports."""
    return {
        "metrics": {
            "occlusion_index": round(profile.occlusion_index, 3),
            "regression_slope": round(profile.regression_slope, 4),
            "regression_r2": round(profile.regression_r2, 3),
            "smo2_baseline": round(profile.smo2_baseline, 1),
            "torque_at_baseline": round(profile.torque_at_baseline, 1),
            "torque_at_minus_10": round(profile.torque_at_minus_10, 1) if profile.torque_at_minus_10 > 0 else None,
            "torque_at_minus_20": round(profile.torque_at_minus_20, 1) if profile.torque_at_minus_20 > 0 else None,
        },
        "classification": {
            "level": profile.classification,
            "color": profile.classification_color,
            "thresholds": {
                "low": "<0.15",
                "moderate": "0.15-0.30",
                "high": ">0.30"
            }
        },
        "interpretation": {
            "mechanism": profile.mechanism_description,
            "riding_style": profile.riding_style_impact,
            "recommendations": profile.training_recommendations
        },
        "quality": {
            "data_points": profile.data_points,
            "confidence": round(profile.confidence, 2)
        }
    }


def minimal_safe_cadence(power: float, torque_threshold: float) -> float:
    """
    Calculate minimum safe cadence to avoid occlusion at given power.
    
    Formula: Torque = Power / (2π × Cadence)
    Rearranged: Cadence = Power / (2π × Torque_threshold) × 60 [RPM]
    
    Args:
        power: Power output [W]
        torque_threshold: Maximum safe torque before occlusion [Nm]
        
    Returns:
        Minimum safe cadence [RPM]
    """
    if torque_threshold <= 0 or power <= 0:
        return 0.0
    
    # Cadence [RPM] = Power [W] / (2π × Torque [Nm]) × 60
    # Note: Power = Torque × 2π × (Cadence/60), so Cadence/60 = Power / (2π × Torque)
    cadence_rps = power / (2 * np.pi * torque_threshold)  # revolutions per second
    cadence_rpm = cadence_rps * 60  # revolutions per minute
    
    return max(0.0, cadence_rpm)


def calculate_power_zone_cadences(
    power_zones: dict,
    torque_at_minus_10: float,
    torque_at_minus_20: float
) -> list:
    """
    Calculate minimal safe cadence for each power zone.
    
    Args:
        power_zones: Dict with zone names and (min, max) power tuples
        torque_at_minus_10: Torque threshold at SmO2 -10% [Nm]
        torque_at_minus_20: Torque threshold at SmO2 -20% [Nm]
        
    Returns:
        List of dicts with zone info and cadence thresholds
    """
    results = []
    
    for zone_name, (power_min, power_max) in power_zones.items():
        power_mid = (power_min + power_max) / 2
        
        # Calculate minimum cadence for moderate occlusion (-10%)
        cad_moderate = minimal_safe_cadence(power_mid, torque_at_minus_10) if torque_at_minus_10 > 0 else 0
        
        # Calculate minimum cadence for critical occlusion (-20%)
        cad_critical = minimal_safe_cadence(power_mid, torque_at_minus_20) if torque_at_minus_20 > 0 else 0
        
        results.append({
            "zone": zone_name,
            "power_range": f"{power_min}-{power_max} W",
            "power_mid": power_mid,
            "cadence_safe": round(cad_moderate, 0) if cad_moderate > 0 else "---",
            "cadence_critical": round(cad_critical, 0) if cad_critical > 0 else "---",
        })
    
    return results


__all__ = [
    "OcclusionProfile",
    "analyze_biomech_occlusion",
    "format_occlusion_for_report",
    "minimal_safe_cadence",
    "calculate_power_zone_cadences",
]
