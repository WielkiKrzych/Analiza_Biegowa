"""PMC (Performance Management Chart) calculations.

Computes CTL/ATL/TSB history from session TSS data using EWMA,
and predicts future PMC values from planned workouts.

Pure functions — no Streamlit imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from ..db import SessionStore
from ..training_load import TrainingLoadManager, TrainingLoadMetrics


@dataclass
class PMCDataPoint:
    """Single point on the PMC chart."""

    date: str
    tss: float
    atl: float
    ctl: float
    tsb: float
    form_status: str


def get_form_interpretation(tsb: float) -> str:
    """Polish interpretation of TSB value.

    Args:
        tsb: Training Stress Balance (CTL - ATL).

    Returns:
        Polish-language form status string.
    """
    if tsb > 25:
        return "🟢 Świeży (Peak Form)"
    elif tsb > 5:
        return "🟡 Gotowy"
    elif tsb > -10:
        return "🟠 Optymalne obciążenie"
    elif tsb > -30:
        return "🔴 Zmęczony"
    else:
        return "⛔ Przepracowany"


def calculate_pmc_history(
    store: Optional[SessionStore] = None,
    days: int = 90,
) -> List[PMCDataPoint]:
    """Calculate PMC history using TrainingLoadManager.

    Args:
        store: SessionStore instance. If None, creates a new one.
        days: Number of days to look back.

    Returns:
        List of PMCDataPoint with CTL/ATL/TSB history.
    """
    mgr = TrainingLoadManager(store)
    history: List[TrainingLoadMetrics] = mgr.calculate_load(days)

    if not history:
        return []

    # Trim to requested days (calculate_load may return more for warm-up)
    return [
        PMCDataPoint(
            date=h.date,
            tss=round(h.tss, 1),
            atl=round(h.atl, 1),
            ctl=round(h.ctl, 1),
            tsb=round(h.tsb, 1),
            form_status=get_form_interpretation(h.tsb),
        )
        for h in history
    ]


def predict_future_pmc(
    current_ctl: float,
    current_atl: float,
    planned_tss_list: List[float],
    dates_list: Optional[List[str]] = None,
) -> List[PMCDataPoint]:
    """Predict future CTL/ATL/TSB based on planned TSS values.

    Args:
        current_ctl: Current Chronic Training Load.
        current_atl: Current Acute Training Load.
        planned_tss_list: Planned daily TSS values for future days.
        dates_list: Optional list of date strings. If None, generates from today.

    Returns:
        List of PMCDataPoint predictions.
    """
    ATL_DAYS = 7
    CTL_DAYS = 42
    atl_decay = 2.0 / (ATL_DAYS + 1)
    ctl_decay = 2.0 / (CTL_DAYS + 1)

    atl = current_atl
    ctl = current_ctl

    if dates_list is None:
        today = datetime.now().date()
        dates_list = [
            (today + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            for i in range(len(planned_tss_list))
        ]

    predictions: List[PMCDataPoint] = []
    for i, tss in enumerate(planned_tss_list):
        atl = atl * (1 - atl_decay) + tss * atl_decay
        ctl = ctl * (1 - ctl_decay) + tss * ctl_decay
        tsb = ctl - atl

        date_str = dates_list[i] if i < len(dates_list) else dates_list[-1]
        predictions.append(
            PMCDataPoint(
                date=date_str,
                tss=round(tss, 1),
                atl=round(atl, 1),
                ctl=round(ctl, 1),
                tsb=round(tsb, 1),
                form_status=get_form_interpretation(tsb),
            )
        )

    return predictions


def get_current_pmc_summary(
    store: Optional[SessionStore] = None,
) -> Optional[dict]:
    """Get current PMC summary metrics.

    Returns:
        Dict with ctl, atl, tsb, ramp_rate, recommended_tss_min/max, form_status.
        None if no data available.
    """
    mgr = TrainingLoadManager(store)
    current = mgr.get_current_form()
    if not current:
        return None

    ramp_rate = mgr.calculate_ramp_rate()
    tss_min, tss_max = mgr.get_recommended_tss()

    return {
        "ctl": round(current.ctl, 1),
        "atl": round(current.atl, 1),
        "tsb": round(current.tsb, 1),
        "tss": round(current.tss, 1),
        "ramp_rate": round(ramp_rate, 1),
        "recommended_tss_min": round(tss_min, 0),
        "recommended_tss_max": round(tss_max, 0),
        "form_status": get_form_interpretation(current.tsb),
    }
