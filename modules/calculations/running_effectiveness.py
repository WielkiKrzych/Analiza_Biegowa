"""Running biomechanics metrics based on recent research (2020-2026).

References:
    - Coggan/Tredict: Running Effectiveness = speed / specific_power
    - Seminati et al. 2020 (PMC7241633): GCT asymmetry metabolic cost
    - Morin et al. 2005 / Dalleau et al. 1998: Spring-mass leg stiffness
    - Sports Medicine 2024: Updated stiffness classification
"""

import logging
from math import pi
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_GRAVITY = 9.81
_RE_WINDOW = 30
_MIN_POWER = 0.1
_MIN_SPEED = 0.1
_METABOLIC_COST_PER_PCT = 3.7  # Seminati 2020: ~3.7% extra cost per 1% asymmetry


def calculate_running_effectiveness(
    speed_ms: float,
    power_w: float,
    weight_kg: float,
) -> Optional[float]:
    """RE = speed (m/s) / specific_power (W/kg). Range: 0.95-1.10 trained.
    Ref: Coggan/Tredict analysis."""
    if (
        np.isnan(speed_ms)
        or np.isnan(power_w)
        or np.isnan(weight_kg)
        or weight_kg <= 0
        or power_w < _MIN_POWER
        or speed_ms < _MIN_SPEED
    ):
        return None
    return speed_ms / (power_w / weight_kg)


def calculate_running_effectiveness_series(
    df: pd.DataFrame,
    weight_kg: float,
) -> pd.Series:
    """Rolling 30s RE from DataFrame. Uses velocity_smooth/pace + watts columns.
    Returns pd.Series; input df is not mutated."""
    nan_series = pd.Series(np.nan, index=df.index, name="running_effectiveness")
    if weight_kg <= 0:
        logger.warning("Invalid weight_kg=%s, returning NaN series.", weight_kg)
        return nan_series
    speed = _extract_speed(df)
    power = df["watts"].astype(float) if "watts" in df.columns else None
    if speed is None or power is None:
        logger.warning("Missing speed or power columns for RE calculation.")
        return nan_series
    safe_specific = (power / weight_kg).replace(0, np.nan)
    re_raw = speed / safe_specific
    return (
        re_raw.rolling(window=_RE_WINDOW, min_periods=1, center=True)
        .mean()
        .rename("running_effectiveness")
    )


def calculate_gct_asymmetry_index(stance_time_balance: pd.Series) -> Dict[str, object]:
    """GCT asymmetry from stance_time_balance (% left foot, 50.0 = perfect).
    Ref: Seminati et al. 2020 (PMC7241633)."""
    clean = stance_time_balance.dropna()
    if clean.empty:
        return {
            k: None
            for k in (
                "mean_balance",
                "asymmetry_pct",
                "dominant_side",
                "metabolic_cost_pct",
                "classification",
            )
        }
    mean_bal = float(clean.mean())
    asym = abs(mean_bal - 50.0) * 2
    classification = (
        "excellent" if asym < 1 else "good" if asym < 2 else "moderate" if asym < 3 else "poor"
    )
    return {
        "mean_balance": round(mean_bal, 2),
        "asymmetry_pct": round(asym, 2),
        "dominant_side": "left" if mean_bal > 50.0 else "right",
        "metabolic_cost_pct": round(asym * _METABOLIC_COST_PER_PCT, 2),
        "classification": classification,
    }


def calculate_leg_spring_stiffness(
    gct_ms: float,
    vertical_oscillation_cm: float,
    body_mass_kg: float,
    cadence_spm: Optional[float] = None,
) -> Dict[str, object]:
    """Vertical stiffness via Dalleau/Morin spring-mass: kvert = m * omega^2.
    Ref: Morin et al. 2005; Dalleau et al. 1998; Sports Med 2024."""
    empty = {"kvert_kn_m": None, "kleg_kn_m": None, "classification": None}
    try:
        if (
            gct_ms <= 0
            or body_mass_kg <= 0
            or vertical_oscillation_cm <= 0
            or np.isnan(gct_ms)
            or np.isnan(vertical_oscillation_cm)
            or np.isnan(body_mass_kg)
        ):
            return empty
    except TypeError:
        return empty

    tc = gct_ms / 1000.0
    vo_m = vertical_oscillation_cm / 100.0
    tf = _estimate_flight_time(tc, vo_m, cadence_spm)
    if tf is None or tf <= 0:
        return empty

    omega = 2.0 * pi / (tc + tf)
    kvert = body_mass_kg * omega**2 / 1000.0  # N/m -> kN/m
    cls = "elite" if kvert >= 35 else "trained" if kvert >= 25 else "recreational"
    return {"kvert_kn_m": round(kvert, 2), "kleg_kn_m": None, "classification": cls}


def calculate_leg_spring_stiffness_series(
    df: pd.DataFrame,
    body_mass_kg: float,
) -> pd.DataFrame:
    """Per-row kvert from stance_time (ms), vertical_oscillation (cm), cadence.
    Returns new DataFrame with 'kvert' column. Input df is not mutated."""
    result = df.copy()
    gct_col = _find_col(df, ["stance_time", "ground_contact_time", "gct"])
    vo_col = _find_col(df, ["vertical_oscillation", "verticalOscillation"])
    cad_col = _find_col(df, ["cadence"])
    if gct_col is None or vo_col is None:
        logger.warning("Missing stance_time or vertical_oscillation columns.")
        result["kvert"] = np.nan
        return result

    def _row_kvert(row: pd.Series) -> float:
        cad = row[cad_col] if cad_col and not np.isnan(row[cad_col]) else None
        out = calculate_leg_spring_stiffness(row[gct_col], row[vo_col], body_mass_kg, cad)
        val = out["kvert_kn_m"]
        return val if val is not None else np.nan

    result["kvert"] = df.apply(_row_kvert, axis=1)
    return result


# --- Private helpers --------------------------------------------------------


def _extract_speed(df: pd.DataFrame) -> Optional[pd.Series]:
    for col in ("velocity_smooth", "speed", "enhanced_speed"):
        if col in df.columns:
            return df[col].astype(float)
    if "pace" in df.columns:
        pace = df["pace"].astype(float).replace(0, np.nan)
        return 1000.0 / (pace * 60.0)
    return None


def _estimate_flight_time(
    tc: float,
    vo_m: float,
    cadence_spm: Optional[float],
) -> Optional[float]:
    """Estimate flight time from cadence or vertical oscillation (ballistic)."""
    if cadence_spm is not None and cadence_spm > 0:
        tf = 60.0 / (cadence_spm / 2.0) - tc
        return tf if tf > 0 else None
    if vo_m > 0:  # VO ~ g*tf^2/8  =>  tf = sqrt(8*VO/g)
        tf = (8.0 * vo_m / _GRAVITY) ** 0.5
        return tf if tf > 0 else None
    return None


def _find_col(df: pd.DataFrame, candidates: list) -> Optional[str]:
    return next((c for c in candidates if c in df.columns), None)
