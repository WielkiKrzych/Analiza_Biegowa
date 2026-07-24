"""Banister Performance Prediction model.

Implements the impulse-response model for performance forecasting
based on Banister et al. (1975) with updated parameters from
Busso et al. (1990) and Morton et al. (1990).

Pure functions — no Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import numpy as np


@dataclass
class BanisterModel:
    """Banister impulse-response model parameters."""

    k1: float = 1.0  # fitness gain coefficient
    k2: float = 2.0  # fatigue gain coefficient
    tau1: float = 42.0  # fitness decay time constant (days)
    tau2: float = 7.0  # fatigue decay time constant (days)
    p0: float = 0.0  # baseline performance


@dataclass
class BanisterPrediction:
    """Single day prediction from Banister model."""

    date: str
    predicted_performance: float
    ctl: float
    atl: float
    tsb: float


@dataclass
class TSSRecommendation:
    """Recommended TSS for a specific day during taper."""

    date: str
    recommended_tss: float
    taper_phase: str
    notes: str


def default_banister_model() -> BanisterModel:
    """Return default model parameters from literature.

    Default tau values from Morton et al. (1990):
    - tau1=42 (fitness/CTL decay)
    - tau2=7 (fatigue/ATL decay)
    - k1=1.0, k2=2.0 (fatigue impacts ~2x fitness)
    """
    return BanisterModel()


def predict_performance(
    model: BanisterModel,
    tss_history: List[float],
    days_ahead: int = 14,
) -> List[BanisterPrediction]:
    """Predict performance using Banister impulse-response model.

    Fitness(n) = k1 * sum(TSS(i) * exp(-(n-i)/tau1)) for i=0..n
    Fatigue(n) = k2 * sum(TSS(i) * exp(-(n-i)/tau2)) for i=0..n
    Performance = P0 + Fitness - Fatigue

    Args:
        model: BanisterModel with parameters k1, k2, tau1, tau2, p0.
        tss_history: Historical daily TSS values (most recent last).
        days_ahead: Number of future days to predict (with TSS=0).

    Returns:
        List of BanisterPrediction for each day in history + future.
    """
    if not tss_history:
        return []

    tss_arr = np.array(tss_history, dtype=float)
    n_history = len(tss_arr)
    n_total = n_history + days_ahead

    today = datetime.now().date()
    start_date = today - timedelta(days=n_history - 1)

    predictions: List[BanisterPrediction] = []

    for n in range(n_total):
        # Calculate fitness and fatigue using impulse-response
        fitness = 0.0
        fatigue = 0.0

        for i in range(n + 1):
            tss_i = tss_arr[i] if i < n_history else 0.0
            decay_days = n - i

            fitness += model.k1 * tss_i * np.exp(-decay_days / model.tau1)
            fatigue += model.k2 * tss_i * np.exp(-decay_days / model.tau2)

        performance = model.p0 + fitness - fatigue

        # Approximate CTL/ATL using EWMA for context
        ctl = fitness / model.k1 if model.k1 != 0 else 0.0
        atl = fatigue / model.k2 if model.k2 != 0 else 0.0

        date_str = (start_date + timedelta(days=n)).strftime("%Y-%m-%d")
        predictions.append(
            BanisterPrediction(
                date=date_str,
                predicted_performance=round(performance, 1),
                ctl=round(ctl, 1),
                atl=round(atl, 1),
                tsb=round(ctl - atl, 1),
            )
        )

    return predictions


def optimize_peaking(
    current_ctl: float,
    current_atl: float,
    target_date: datetime,
    days_out: int = 14,
) -> List[TSSRecommendation]:
    """Calculate optimal taper TSS to peak at target date.

    Taper strategy based on Mujika & Padilla (2003):
    - Reduce volume 40-60% over 2 weeks
    - Maintain intensity (neuromuscular stimulus)
    - Progressive reduction: 40% week 1, 60% week 2

    Args:
        current_ctl: Current Chronic Training Load.
        current_atl: Current Acute Training Load.
        target_date: Date of target event/race.
        days_out: Number of days to generate taper plan.

    Returns:
        List of TSSRecommendation for each taper day.
    """
    recommendations: List[TSSRecommendation] = []

    for d in range(days_out):
        date = target_date - timedelta(days=days_out - 1 - d)
        days_from_start = d + 1
        date_str = date.strftime("%Y-%m-%d")

        if days_from_start <= 7:
            # Week 1: reduce by 40%
            taper_pct = 0.60
            phase = "Taper — tydzień 1"
            notes = "Redukcja objętości o 40%. Utrzymuj intensywność."
        elif days_from_start <= 12:
            # Week 2: reduce by 60%
            taper_pct = 0.40
            phase = "Taper — tydzień 2"
            notes = "Redukcja objętości o 60%. Krótkie interwały (>VT2)."
        else:
            # Race week: very light
            taper_pct = 0.25
            phase = "Tydzień startowy"
            notes = "Lekkie zakładki aktywacyjne. Regeneracja."

        recommended_tss = round(current_ctl * taper_pct, 0)

        recommendations.append(
            TSSRecommendation(
                date=date_str,
                recommended_tss=recommended_tss,
                taper_phase=phase,
                notes=notes,
            )
        )

    return recommendations


def predict_performance_fast(
    model: BanisterModel,
    tss_history: List[float],
    days_ahead: int = 14,
) -> List[BanisterPrediction]:
    """Vectorized performance prediction for speed.

    Same as predict_performance but uses numpy vectorization
    for large TSS histories (>60 days).
    """
    if not tss_history:
        return []

    tss_arr = np.array(tss_history, dtype=float)
    n_history = len(tss_arr)
    n_total = n_history + days_ahead

    today = datetime.now().date()
    start_date = today - timedelta(days=n_history - 1)

    # Build index arrays
    all_tss = np.zeros(n_total)
    all_tss[:n_history] = tss_arr

    predictions: List[BanisterPrediction] = []

    # Compute cumulative CTL/ATL equivalents
    for n in range(n_total):
        decay_range = np.arange(n + 1)
        decay_fitness = np.exp(-decay_range[::-1] / model.tau1)
        decay_fatigue = np.exp(-decay_range[::-1] / model.tau2)
        tss_slice = all_tss[: n + 1]

        fitness = float(model.k1 * np.sum(tss_slice * decay_fitness))
        fatigue = float(model.k2 * np.sum(tss_slice * decay_fatigue))

        performance = model.p0 + fitness - fatigue
        ctl = fitness / model.k1 if model.k1 != 0 else 0.0
        atl = fatigue / model.k2 if model.k2 != 0 else 0.0

        date_str = (start_date + timedelta(days=n)).strftime("%Y-%m-%d")
        predictions.append(
            BanisterPrediction(
                date=date_str,
                predicted_performance=round(performance, 1),
                ctl=round(ctl, 1),
                atl=round(atl, 1),
                tsb=round(ctl - atl, 1),
            )
        )

    return predictions
