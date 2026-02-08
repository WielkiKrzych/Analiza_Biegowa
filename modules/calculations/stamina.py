"""
Stamina Score Module.

Implements composite endurance metrics inspired by INSCYD/UCI methodologies.
"""

from typing import Optional, Dict


def calculate_stamina_score(
    vo2max: float, fri: float, w_prime: float, cp: float, weight: float
) -> float:
    """Calculate Stamina Score - composite endurance metric.

    Combines VO2max, Fatigue Resistance, and power-to-weight into
    a single score comparable across athletes.

    Formula:
    Score = (VO2max_normalized * 0.4) + (FRI_normalized * 0.3) + (CP/kg_normalized * 0.3)

    Normalized to 0-100 scale where:
    - 80+: World Tour level
    - 60-80: Elite amateur
    - 40-60: Trained cyclist
    - 20-40: Beginner

    Args:
        vo2max: VO2max in ml/kg/min
        fri: Fatigue Resistance Index (0.0-1.0)
        w_prime: W' capacity in Joules
        cp: Critical Power in watts
        weight: Rider weight in kg

    Returns:
        Stamina Score (0-100)

    Raises:
        ValueError: If any parameter is negative
    """
    if vo2max < 0 or fri < 0 or w_prime < 0 or cp <= 0 or weight <= 0:
        return 0.0

    # Normalize VO2max (range: 30-90 ml/kg/min for cyclists)
    vo2_min, vo2_max = 30.0, 90.0
    vo2_normalized = min(100, max(0, (vo2max - vo2_min) / (vo2_max - vo2_min) * 100))

    # Normalize FRI (range: 0.70-1.00)
    fri_min, fri_max = 0.70, 1.00
    fri_normalized = min(100, max(0, (fri - fri_min) / (fri_max - fri_min) * 100))

    # Normalize CP/kg (range: 2.0-7.0 W/kg)
    cp_kg = cp / weight
    cp_min, cp_max = 2.0, 7.0
    cp_normalized = min(100, max(0, (cp_kg - cp_min) / (cp_max - cp_min) * 100))

    # Weighted average
    score = (vo2_normalized * 0.4) + (fri_normalized * 0.3) + (cp_normalized * 0.3)

    return round(score, 1)


def estimate_vlamax_from_pdc(pdc: Dict[int, float], weight: float) -> Optional[float]:
    """Estimate VLamax from Power Duration Curve shape.

    VLamax (maximum lactate production rate) can be approximated from
    the relationship between short and long duration powers.

    Higher VLamax = more anaerobic, drops faster with duration
    Lower VLamax = more aerobic, maintains power longer

    Typical values:
    - Sprinters: 0.8-1.2 mmol/L/s
    - All-rounders: 0.5-0.8 mmol/L/s
    - Climbers/TT: 0.3-0.5 mmol/L/s

    Note: This is an ESTIMATION. Lab testing is required for accurate VLamax.

    Args:
        pdc: Power Duration Curve dict (duration -> watts)
        weight: Rider weight in kg

    Returns:
        Estimated VLamax in mmol/L/s or None if insufficient data
    """
    # Need 30s and 300s (5min) power for estimation
    p30 = pdc.get(30)
    p300 = pdc.get(300)

    if p30 is None or p300 is None or weight <= 0:
        return None

    if p30 <= 0 or p300 <= 0:
        return None

    # Calculate W/kg values
    p30_kg = p30 / weight
    p300_kg = p300 / weight

    # The drop from 30s to 5min power indicates anaerobic contribution
    # Empirical formula based on INSCYD model approximation
    drop_ratio = (p30_kg - p300_kg) / p30_kg

    # Map drop ratio to VLamax estimate
    # Typical drop ratios: 0.20-0.50 map to VLamax 0.3-1.0
    vlamax_estimate = 0.3 + (drop_ratio - 0.20) * 2.5

    # Clamp to reasonable range
    vlamax_estimate = max(0.2, min(1.2, vlamax_estimate))

    return round(vlamax_estimate, 2)


def get_stamina_interpretation(score: float) -> str:
    """Get human-readable interpretation of Stamina Score.

    Args:
        score: Stamina Score (0-100)

    Returns:
        Polish interpretation string
    """
    if score >= 80:
        return "🏆 Poziom World Tour"
    elif score >= 65:
        return "🥇 Elitarny amator / Continental"
    elif score >= 50:
        return "🥈 Wytrenowany kolarz klubowy"
    elif score >= 35:
        return "🥉 Średni poziom amatorski"
    else:
        return "🔰 Początkujący / rozwojowy"


def get_vlamax_interpretation(vlamax: float) -> str:
    """Get human-readable interpretation of VLamax estimate.

    Args:
        vlamax: Estimated VLamax in mmol/L/s

    Returns:
        Polish interpretation string with training recommendations
    """
    if vlamax >= 0.9:
        return "⚡ Sprinter - wysoka glikoliza (pracuj nad wytrzymałością)"
    elif vlamax >= 0.7:
        return "🔥 Puncheur - zbalansowany profil"
    elif vlamax >= 0.5:
        return "🚴 All-rounder - dobra baza tlenowa"
    elif vlamax >= 0.35:
        return "⛰️ Climber/TT - niska glikoliza (pracuj nad sprintami)"
    else:
        return "🐢 Diesel - bardzo niska glikoliza"


def calculate_aerobic_contribution(
    pdc: Dict[int, float], vo2max: float, weight: float
) -> Dict[int, float]:
    """Estimate aerobic vs anaerobic contribution at each duration.

    Uses simplified model based on VO2max and power curve shape.

    Args:
        pdc: Power Duration Curve
        vo2max: VO2max in ml/kg/min
        weight: Rider weight in kg

    Returns:
        Dict mapping duration to aerobic percentage (0-100)
    """
    if not pdc or vo2max <= 0 or weight <= 0:
        return {}

    # Estimate max aerobic power from VO2max
    # P_aero_max ≈ (VO2max - 7) * weight / 10.8 (inverse of ACSM formula)
    p_aero_max = (vo2max - 7) * weight / 10.8

    results = {}
    for duration, power in pdc.items():
        if power is None or power <= 0:
            continue

        # Aerobic contribution increases with duration
        # At very short durations (~5s), mostly anaerobic
        # At long durations (>20min), mostly aerobic

        if duration <= 10:
            time_factor = 0.3  # Short = more anaerobic
        elif duration <= 60:
            time_factor = 0.5
        elif duration <= 300:
            time_factor = 0.7
        elif duration <= 1200:
            time_factor = 0.85
        else:
            time_factor = 0.95

        # Also scale by how close power is to aerobic max
        power_factor = min(1.0, p_aero_max / power) if power > 0 else 0

        aerobic_pct = time_factor * power_factor * 100
        results[duration] = round(min(100, max(0, aerobic_pct)), 1)

    return results


# ============================================================
# NEW: Durability Index - INSCYD / WKO5 Stamina
# ============================================================


def calculate_durability_index(df, min_duration_min: int = 30) -> tuple:
    """Calculate Durability Index - power sustainability over workout.

    Compares average power in first half vs second half of workout.
    Shows how well athlete maintains performance as fatigue accumulates.

    DI = (Avg Power 2nd Half / Avg Power 1st Half) * 100

    Interpretation:
    - 100%: Perfect maintenance (rare)
    - 95-100%: Excellent durability
    - 90-95%: Good durability
    - 85-90%: Average
    - <85%: Poor durability (needs work)

    Args:
        df: DataFrame with 'watts' column
        min_duration_min: Minimum workout duration in minutes

    Returns:
        Tuple of (durability_index, first_half_avg, second_half_avg)
        Returns (None, None, None) if insufficient data
    """

    if df is None or "watts" not in df.columns:
        return None, None, None

    # Need minimum duration
    if len(df) < min_duration_min * 60:
        return None, None, None

    # Split in half
    midpoint = len(df) // 2

    first_half = df.iloc[:midpoint]
    second_half = df.iloc[midpoint:]

    avg_first = first_half["watts"].mean()
    avg_second = second_half["watts"].mean()

    if avg_first <= 0:
        return None, None, None

    durability = (avg_second / avg_first) * 100

    return round(durability, 1), round(avg_first, 0), round(avg_second, 0)


def get_durability_interpretation(di: float) -> str:
    """Get interpretation of Durability Index.

    Args:
        di: Durability Index (percentage)

    Returns:
        Polish interpretation string
    """
    if di is None:
        return "❓ Brak danych"
    elif di >= 98:
        return "🟢 Fenomenalna wytrzymałość"
    elif di >= 95:
        return "🟢 Bardzo dobra wytrzymałość"
    elif di >= 90:
        return "🟡 Dobra wytrzymałość"
    elif di >= 85:
        return "🟠 Przeciętna - do poprawy"
    else:
        return "🔴 Słaba wytrzymałość - priorytet treningowy"
