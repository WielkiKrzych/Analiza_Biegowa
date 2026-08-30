"""
Running power estimation from pace (pace-first foundation).

For runners without a power meter (pace + HR only), the physiological engine
still needs a single intensity axis. This module derives an *estimated* running
power from Grade-Adjusted Pace (GAP) — or plain pace when no elevation exists —
so every downstream analysis (thresholds, metrics, CP/W', limiters) is driven by
the athlete's PACE rather than being empty or power-centric.

Model (flat-equivalent, grade already folded into GAP):
    P [W] ≈ k · m · v
where v = grade-adjusted speed [m/s], m = body mass [kg], and
k ≈ 1.04 W per (kg · m/s), calibrated so ~5:00 min/km ≈ 260 W for a 75 kg runner
(consistent with Stryd-class running-power meters on flat ground).

The value is a transparent PROXY for intensity, always labelled as "estimated".
It is NOT presented as measured power.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from modules.config import Config

# W per (kg · m/s). ~5:00/km (3.333 m/s) × 75 kg × 1.04 ≈ 260 W.
POWER_PER_KG_PER_MS = 1.04

# Plausible moving-pace window (sec/km): 2:00 .. 20:00.
_MIN_PACE = 120.0
_MAX_PACE = 1200.0


def _equivalent_speed(df: pd.DataFrame) -> Optional[pd.Series]:
    """Return grade-adjusted equivalent speed [m/s], or None if unavailable.

    Preference: GAP (grade-adjusted) > pace > speed column.
    """
    for pace_col in ("gap", "pace"):
        if pace_col in df.columns:
            pace = pd.to_numeric(df[pace_col], errors="coerce")
            pace = pace.where((pace >= _MIN_PACE) & (pace <= _MAX_PACE))
            speed = 1000.0 / pace
            if speed.notna().any():
                return speed.fillna(0.0)
    for speed_col in ("speed", "speed_m_s", "velocity_smooth"):
        if speed_col in df.columns:
            speed = pd.to_numeric(df[speed_col], errors="coerce")
            speed = speed.where((speed >= 0.83) & (speed <= 8.33))  # 2:00..20:00 /km
            if speed.notna().any():
                return speed.fillna(0.0)
    return None


def estimate_running_power(df: pd.DataFrame, weight_kg: float = Config.DEFAULT_BODY_WEIGHT_KG) -> Optional[pd.Series]:
    """Estimate running power [W] per sample from pace/GAP.

    Returns a float Series aligned to *df*, or None when no usable pace/speed
    column is present.
    """
    if weight_kg is None or weight_kg <= 0:
        weight_kg = Config.DEFAULT_BODY_WEIGHT_KG
    speed = _equivalent_speed(df)
    if speed is None:
        return None
    power = POWER_PER_KG_PER_MS * float(weight_kg) * speed
    power = power.clip(lower=0.0)
    return power.round(1).astype(float)


def has_measured_power(df: pd.DataFrame) -> bool:
    """True if the session carries a real (non-derived) power column with signal."""
    for col in ("power", "watts"):
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            if s.fillna(0).abs().sum() > 0:
                return True
    return False


def ensure_power_column(df: pd.DataFrame, weight_kg: float = Config.DEFAULT_BODY_WEIGHT_KG) -> bool:
    """Populate ``df['watts']`` from pace when no measured power exists.

    Mutates *df* in place. Returns True when power was ESTIMATED from pace
    (so the UI can label it), False when a measured power column was used or
    nothing could be derived.
    """
    if has_measured_power(df):
        if "watts" not in df.columns and "power" in df.columns:
            df["watts"] = pd.to_numeric(df["power"], errors="coerce").fillna(0.0)
        return False
    est = estimate_running_power(df, weight_kg)
    if est is None:
        return False
    df["watts"] = est.values if hasattr(est, "values") else np.asarray(est)
    return True
