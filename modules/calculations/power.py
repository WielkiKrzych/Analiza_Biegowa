"""
SRP: Moduł odpowiedzialny za obliczenia związane z mocą.
"""

from typing import Union, Any, Tuple
import numpy as np
import pandas as pd

from .common import ensure_pandas, DEFAULT_PDC_DURATIONS


def calculate_normalized_power(
    df_pl: Union[pd.DataFrame, Any], rolling_window_sec: int = 30, return_rich: bool = False
) -> Union[float, "NormalizedPowerResult"]:
    """
    Calculate Normalized Power (NP) using Coggan's formula.

    NP = 4th root of (mean of 4th power of rolling average power)

    Args:
        df_pl: DataFrame with 'watts' or 'watts_smooth' column
        rolling_window_sec: Rolling average window in seconds (default: 30)
        return_rich: If True, return NormalizedPowerResult; if False, return float

    Returns:
        NormalizedPowerResult object (or float if return_rich=False)
    """
    from models import NormalizedPowerResult

    df = ensure_pandas(df_pl)
    col = (
        "watts"
        if "watts" in df.columns
        else ("watts_smooth" if "watts_smooth" in df.columns else None)
    )

    if col is None:
        if return_rich:
            return NormalizedPowerResult(
                value=0.0, rolling_window_sec=rolling_window_sec, samples_count=0, data_quality=0.0
            )
        return 0.0

    samples_count = len(df)

    # Calculate data quality (based on NaN ratio and variance)
    nan_ratio = df[col].isna().sum() / len(df) if len(df) > 0 else 1.0
    data_quality = max(0.0, 1.0 - nan_ratio)

    # Rolling average
    rolling_avg = df[col].rolling(window=rolling_window_sec, min_periods=1).mean()
    # 4th power
    rolling_pow4 = np.power(rolling_avg, 4)
    # Mean
    avg_pow4 = np.nanmean(rolling_pow4)
    # 4th root
    np_val = np.power(avg_pow4, 0.25)

    if pd.isna(np_val):
        mean_val = df[col].mean()
        np_val = 0.0 if pd.isna(mean_val) else float(mean_val)
    else:
        np_val = float(np_val)

    if return_rich:
        return NormalizedPowerResult(
            value=np_val,
            rolling_window_sec=rolling_window_sec,
            samples_count=samples_count,
            data_quality=data_quality,
        )
    return np_val


def calculate_pulse_power_stats(
    df_pl: Union[pd.DataFrame, Any],
    min_watts: float = 50.0,
    min_hr: float = 90.0,
    min_samples_trend: int = 100,
    return_rich: bool = False,
) -> Union[Tuple[float, float, pd.DataFrame], "PulsePowerResult"]:
    """Calculate Pulse Power (Efficiency) statistics: Avg PP, Trend Drop %.

    Pulse Power = Watts / Heart Rate - indicates cardiac efficiency.

    Args:
        df_pl: DataFrame with power and HR data
        min_watts: Minimum power threshold for valid data (default: 50W)
        min_hr: Minimum heart rate threshold for valid data (default: 90 bpm)
        min_samples_trend: Minimum samples required for trend calculation (default: 100)
        return_rich: If True, return PulsePowerResult; if False, return tuple

    Returns:
        PulsePowerResult object (or tuple if return_rich=False)
    """
    from models import PulsePowerResult

    df = ensure_pandas(df_pl)

    col_w = "watts_smooth" if "watts_smooth" in df.columns else "watts"
    col_hr = "heartrate_smooth" if "heartrate_smooth" in df.columns else "heartrate"

    if col_w not in df.columns or col_hr not in df.columns:
        if return_rich:
            return PulsePowerResult(
                avg_pulse_power=0.0,
                trend_drop_pct=0.0,
                df_filtered=pd.DataFrame(),
                min_watts=min_watts,
                min_hr=min_hr,
                min_samples_trend=min_samples_trend,
                samples_count=0,
                data_quality=0.0,
            )
        return 0.0, 0.0, pd.DataFrame()

    # Filter sensible values using explicit thresholds
    mask = (df[col_w] > min_watts) & (df[col_hr] > min_hr)
    df_pp = df[mask].copy()

    if df_pp.empty:
        if return_rich:
            return PulsePowerResult(
                avg_pulse_power=0.0,
                trend_drop_pct=0.0,
                df_filtered=pd.DataFrame(),
                min_watts=min_watts,
                min_hr=min_hr,
                min_samples_trend=min_samples_trend,
                samples_count=0,
                data_quality=0.0,
            )
        return 0.0, 0.0, pd.DataFrame()

    samples_count = len(df_pp)
    data_quality = samples_count / len(df) if len(df) > 0 else 0.0

    df_pp["pulse_power"] = df_pp[col_w] / df_pp[col_hr]
    avg_pp = df_pp["pulse_power"].mean()

    # Trend calculation
    drop_pct = 0.0
    if len(df_pp) > min_samples_trend:
        x = df_pp["time"] if "time" in df_pp.columns else np.arange(len(df_pp))
        y = df_pp["pulse_power"].values
        idx = np.isfinite(x) & np.isfinite(y)
        if np.sum(idx) > 10:
            z = np.polyfit(x[idx], y[idx], 1)
            slope = z[0]
            intercept = z[1]
            start_val = intercept + slope * x.iloc[0]
            end_val = intercept + slope * x.iloc[-1]

            if start_val != 0:
                drop_pct = (end_val - start_val) / start_val * 100

    if return_rich:
        return PulsePowerResult(
            avg_pulse_power=avg_pp,
            trend_drop_pct=drop_pct,
            df_filtered=df_pp,
            min_watts=min_watts,
            min_hr=min_hr,
            min_samples_trend=min_samples_trend,
            samples_count=samples_count,
            data_quality=data_quality,
        )
    return avg_pp, drop_pct, df_pp


# ============================================================
# NEW FEATURES: PDC, FRI, Match Burns
# Based on WKO5/INSCYD/TrainerRoad methodologies
# ============================================================


def calculate_power_duration_curve(df_pl: Union[pd.DataFrame, Any], durations: list = None) -> dict:
    """Calculate Power Duration Curve (Mean Maximal Power for each duration).

    The PDC shows the maximum average power that can be sustained for
    different durations - fundamental metric for power profiling.

    Args:
        df_pl: DataFrame with 'watts' column
        durations: List of durations in seconds (default: 1s to 1h)

    Returns:
        Dict mapping duration (seconds) to MMP (watts)

    Example:
        >>> pdc = calculate_power_duration_curve(df)
        >>> pdc[300]  # 5-minute max power
        320.5
    """
    df = ensure_pandas(df_pl)

    if "watts" not in df.columns:
        return {}

    if durations is None:
        durations = DEFAULT_PDC_DURATIONS

    watts = df["watts"].fillna(0).values
    n = len(watts)

    results = {}
    for duration in durations:
        if n < duration:
            results[duration] = None
            continue

        # Rolling mean for this duration
        rolling = pd.Series(watts).rolling(window=duration, min_periods=duration).mean()
        mmp = rolling.max()

        if pd.notna(mmp):
            results[duration] = float(mmp)
        else:
            results[duration] = None

    return results


def calculate_fatigue_resistance_index(mmp_5min: float, mmp_20min: float) -> float:
    """Calculate Fatigue Resistance Index (FRI).

    FRI = MMP20 / MMP5

    Shows how well an athlete can sustain power over longer durations.
    Key indicator of endurance capability vs anaerobic capacity.

    Interpretation:
    - 0.95+: Exceptional endurance (diesel engine)
    - 0.90-0.95: Pro-level stamina
    - 0.85-0.90: Well-trained amateur
    - 0.80-0.85: Average trained cyclist
    - <0.80: Anaerobic-dominant (sprinter profile)

    Args:
        mmp_5min: 5-minute max power in watts
        mmp_20min: 20-minute max power in watts

    Returns:
        FRI ratio (0.0-1.0+)
    """
    if mmp_5min is None or mmp_20min is None:
        return 0.0
    if mmp_5min <= 0:
        return 0.0

    return mmp_20min / mmp_5min


def count_match_burns(
    w_bal: np.ndarray, w_prime_capacity: float, threshold_pct: float = 0.3
) -> int:
    """Count how many 'matches' were burned during the workout.

    A 'match' is burned when W' balance drops below threshold.
    Each significant W' depletion event counts as burning a match.

    Concept from TrainerRoad/WKO5 - helps athletes understand
    how many high-intensity efforts they can make.

    Args:
        w_bal: W' balance array (J remaining)
        w_prime_capacity: Full W' capacity (J)
        threshold_pct: Threshold as fraction of W' (default 30%)

    Returns:
        Number of matches burned
    """
    if w_bal is None or len(w_bal) == 0 or w_prime_capacity <= 0:
        return 0

    threshold = w_prime_capacity * threshold_pct
    burns = 0
    below_threshold = False

    for val in w_bal:
        if val < threshold and not below_threshold:
            # Just dropped below threshold
            burns += 1
            below_threshold = True
        elif val >= threshold * 1.5:  # Recovery buffer
            # Recovered enough to count next drop as new match
            below_threshold = False

    return burns


def calculate_power_zones_time(
    df_pl: Union[pd.DataFrame, Any], cp: float, zones: dict = None
) -> dict:
    """Calculate time spent in each power zone.

    Default zones based on Coggan's model:
    - Z1 Recovery: <55% CP
    - Z2 Endurance: 55-75% CP
    - Z3 Tempo: 75-90% CP
    - Z4 Threshold: 90-105% CP
    - Z5 VO2max: 105-120% CP
    - Z6 Anaerobic: >120% CP

    Args:
        df_pl: DataFrame with 'watts' column
        cp: Critical Power in watts
        zones: Optional custom zone definitions

    Returns:
        Dict mapping zone name to seconds spent
    """
    df = ensure_pandas(df_pl)

    if "watts" not in df.columns or cp <= 0:
        return {}

    if zones is None:
        zones = {
            "Z1 Recovery": (0, 0.55),
            "Z2 Endurance": (0.55, 0.75),
            "Z3 Tempo": (0.75, 0.90),
            "Z4 Threshold": (0.90, 1.05),
            "Z5 VO2max": (1.05, 1.20),
            "Z6 Anaerobic": (1.20, 10.0),  # 10x as upper bound
        }

    watts = df["watts"].fillna(0)
    results = {}

    for zone_name, (low_pct, high_pct) in zones.items():
        low_watts = cp * low_pct
        high_watts = cp * high_pct

        mask = (watts >= low_watts) & (watts < high_watts)
        seconds_in_zone = mask.sum()
        results[zone_name] = int(seconds_in_zone)

    return results


def get_fri_interpretation(fri: float) -> str:
    """Get human-readable interpretation of FRI value.

    Args:
        fri: Fatigue Resistance Index value

    Returns:
        Polish interpretation string
    """
    if fri >= 0.95:
        return "🟢 Wyjątkowa wytrzymałość (diesel)"
    elif fri >= 0.90:
        return "🟢 Poziom Pro - świetna wytrzymałość"
    elif fri >= 0.85:
        return "🟡 Dobrze wytrenowany amator"
    elif fri >= 0.80:
        return "🟠 Przeciętny poziom"
    else:
        return "🔴 Profil sprinterski (niska wytrzymałość)"


# ============================================================
# NEW: Time to Exhaustion (TTE) - WKO5 Duration Model
# ============================================================


def estimate_tte(target_power: float, cp: float, w_prime: float) -> float:
    """Estimate Time to Exhaustion at given power.

    Based on the critical power model: TTE = W' / (P - CP)

    Args:
        target_power: Target power in watts
        cp: Critical Power in watts
        w_prime: W' capacity in Joules

    Returns:
        Time to exhaustion in seconds (inf if power <= CP)

    Example:
        >>> estimate_tte(350, 280, 20000)
        285.7  # ~4.8 minutes at 350W with CP=280W, W'=20kJ
    """
    if target_power <= 0:
        raise ValueError(f"target_power must be positive, got {target_power}")
    if cp < 0:
        raise ValueError(f"cp cannot be negative, got {cp}")
    if w_prime < 0:
        raise ValueError(f"w_prime cannot be negative, got {w_prime}")

    if target_power <= cp:
        return float("inf")

    if w_prime <= 0:
        return 0.0

    return w_prime / (target_power - cp)


def estimate_tte_range(pdc: dict, cp: float, w_prime: float) -> dict:
    """Estimate TTE for each power level in PDC.

    Args:
        pdc: Power Duration Curve (duration -> power)
        cp: Critical Power
        w_prime: W' capacity

    Returns:
        Dict mapping power to estimated TTE
    """
    results = {}
    for duration, power in pdc.items():
        if power is not None and power > 0:
            tte = estimate_tte(power, cp, w_prime)
            results[power] = tte
    return results


# ============================================================
# NEW: Phenotype Classification - WKO5 Power Profile
# ============================================================


def classify_phenotype(pdc: dict, weight: float) -> str:
    """Classify rider phenotype based on Power Duration Curve.

    Uses WKO5-style power profile analysis to determine
    whether rider is a Sprinter, Pursuiter, All-Rounder, TT, or Climber.

    Classification based on relative strengths:
    - Sprinter: Exceptional 5s-30s power
    - Pursuiter: Strong 1-5min power
    - All-Rounder: Balanced profile
    - Time Trialist: Strong 20min+ power, good FRI
    - Climber: High W/kg at threshold, lower absolute

    Args:
        pdc: Power Duration Curve (duration seconds -> watts)
        weight: Rider weight in kg

    Returns:
        Phenotype string identifier
    """
    if not pdc or weight <= 0:
        return "unknown"

    # Get key power values
    p5s = pdc.get(5)
    p1min = pdc.get(60)
    p5min = pdc.get(300)
    p20min = pdc.get(1200)

    # Need at least some data
    if not any([p5s, p1min, p5min, p20min]):
        return "unknown"

    # Calculate W/kg values
    p5s_kg = p5s / weight if p5s else 0
    p1min_kg = p1min / weight if p1min else 0
    p5min_kg = p5min / weight if p5min else 0
    p20min_kg = p20min / weight if p20min else 0

    # Phenotype scoring
    scores = {"sprinter": 0, "pursuiter": 0, "all_rounder": 0, "time_trialist": 0, "climber": 0}

    # Sprinter: High 5s power (>16 W/kg typical for elite)
    if p5s_kg >= 18:
        scores["sprinter"] += 3
    elif p5s_kg >= 15:
        scores["sprinter"] += 2
    elif p5s_kg >= 12:
        scores["sprinter"] += 1

    # Pursuiter: High 1-5min power ratio
    if p1min_kg >= 8:
        scores["pursuiter"] += 2
    if p5min_kg >= 6:
        scores["pursuiter"] += 2

    # Time Trialist: High sustained power, good FRI
    if p20min_kg >= 5:
        scores["time_trialist"] += 2
    if p5min and p20min and (p20min / p5min) >= 0.90:
        scores["time_trialist"] += 2

    # Climber: High W/kg across board but especially threshold
    if p20min_kg >= 5.5 and weight < 70:
        scores["climber"] += 3
    elif p20min_kg >= 5 and weight < 75:
        scores["climber"] += 2

    # All-rounder: Balanced scores (no extreme peaks)
    if p5s_kg >= 12 and p5min_kg >= 5 and p20min_kg >= 4:
        variance = np.std(
            [
                p5s_kg / 20,  # Normalize to similar scale
                p1min_kg / 10,
                p5min_kg / 7,
                p20min_kg / 5.5,
            ]
        )
        if variance < 0.15:  # Low variance = balanced
            scores["all_rounder"] += 3

    # Find highest scoring phenotype
    phenotype = max(scores, key=scores.get)

    # If no clear winner, default to all-rounder
    if scores[phenotype] == 0:
        return "all_rounder"

    return phenotype


def get_phenotype_description(phenotype: str) -> tuple:
    """Get phenotype emoji, name, and description.

    Args:
        phenotype: Phenotype identifier from classify_phenotype

    Returns:
        Tuple of (emoji, name, description)
    """
    phenotypes = {
        "sprinter": (
            "⚡",
            "Sprinter",
            "Eksplozywna moc krótkiego trwania. Świetny w sprintach i atakach.",
        ),
        "pursuiter": (
            "🎯",
            "Pursuiter / Puncheur",
            "Silny w wysiłkach 1-5 min. Dominuje na krótkich podbiegach.",
        ),
        "all_rounder": (
            "🔄",
            "All-Rounder",
            "Zbalansowany profil. Można dostosować do różnych ról w zespole.",
        ),
        "time_trialist": (
            "🚀",
            "Time Trialist",
            "Wysoka moc progowa i FRI. Dominuje w jeździe na czas.",
        ),
        "climber": ("⛰️", "Climber", "Wysoka moc względna (W/kg). Błyszczy na długich podbiegach."),
        "unknown": ("❓", "Nieznany", "Za mało danych do klasyfikacji."),
    }

    return phenotypes.get(phenotype, phenotypes["unknown"])
