"""
Training Load Management System.

Implements Performance Management Chart (PMC) metrics:
- ATL (Acute Training Load) - 7-day EWMA
- CTL (Chronic Training Load) - 42-day EWMA
- TSB (Training Stress Balance) = CTL - ATL
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import pandas as pd

from .db import SessionStore


@dataclass
class TrainingLoadMetrics:
    """Current training load state."""

    date: str
    tss: float
    atl: float  # Acute Training Load (fatigue)
    ctl: float  # Chronic Training Load (fitness)
    tsb: float  # Training Stress Balance (form)

    @property
    def form_status(self) -> str:
        """Interpret TSB value."""
        if self.tsb > 25:
            return "🟢 Świeży (Peak Form)"
        elif self.tsb > 5:
            return "🟡 Gotowy"
        elif self.tsb > -10:
            return "🟠 Optymalne obciążenie"
        elif self.tsb > -30:
            return "🔴 Zmęczony"
        else:
            return "⛔ Przepracowany"


class TrainingLoadManager:
    """Manages training load calculations and history."""

    ATL_DAYS = 7  # Acute period
    CTL_DAYS = 42  # Chronic period

    def __init__(self, store: Optional[SessionStore] = None):
        self.store = store or SessionStore()

    def calculate_load(self, days: int = 90) -> List[TrainingLoadMetrics]:
        """Calculate ATL/CTL/TSB for historical data."""
        # Get daily TSS values
        tss_data = self.store.get_all_tss(days + self.CTL_DAYS)

        if not tss_data:
            return []

        # Create DataFrame with all dates
        df = pd.DataFrame(tss_data, columns=["date", "tss"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")

        # Fill missing dates with 0 TSS (rest days)
        date_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq="D")
        df = df.reindex(date_range, fill_value=0)

        # Calculate EWMA
        # ATL uses shorter span (more reactive to recent training)
        # CTL uses longer span (represents fitness base)
        df["atl"] = df["tss"].ewm(span=self.ATL_DAYS, adjust=False).mean()
        df["ctl"] = df["tss"].ewm(span=self.CTL_DAYS, adjust=False).mean()
        df["tsb"] = df["ctl"] - df["atl"]

        # Convert to list of TrainingLoadMetrics using vectorized to_records
        df_reset = df.reset_index()
        records = df_reset.to_dict("records")
        date_col = "index" if "index" in df_reset.columns else df_reset.columns[0]
        results = [
            TrainingLoadMetrics(
                date=rec[date_col].strftime("%Y-%m-%d"),
                tss=rec["tss"],
                atl=rec["atl"],
                ctl=rec["ctl"],
                tsb=rec["tsb"],
            )
            for rec in records
        ]

        return results

    def get_current_form(self) -> Optional[TrainingLoadMetrics]:
        """Get today's training load metrics."""
        history = self.calculate_load(days=7)
        return history[-1] if history else None

    def predict_future_form(
        self, planned_tss: List[float], days: int = 7
    ) -> List[TrainingLoadMetrics]:
        """Predict future form based on planned training.

        Args:
            planned_tss: List of planned daily TSS values
            days: Number of days to predict

        Returns:
            List of predicted TrainingLoadMetrics
        """
        current = self.calculate_load(days=60)
        if not current:
            return []

        # Start from current state
        last = current[-1]
        atl = last.atl
        ctl = last.ctl

        # EWMA decay factors
        atl_decay = 2 / (self.ATL_DAYS + 1)
        ctl_decay = 2 / (self.CTL_DAYS + 1)

        predictions = []
        today = datetime.now().date()

        for i, tss in enumerate(planned_tss[:days]):
            date = today + timedelta(days=i + 1)

            # Update EWMA
            atl = atl * (1 - atl_decay) + tss * atl_decay
            ctl = ctl * (1 - ctl_decay) + tss * ctl_decay

            predictions.append(
                TrainingLoadMetrics(
                    date=date.strftime("%Y-%m-%d"), tss=tss, atl=atl, ctl=ctl, tsb=ctl - atl
                )
            )

        return predictions

    def get_recommended_tss(self) -> Tuple[float, float]:
        """Get recommended TSS range for today.

        Returns:
            Tuple of (min_tss, max_tss) for optimal training
        """
        current = self.get_current_form()
        if not current:
            return (50.0, 100.0)  # Default for new users

        # If TSB is very negative (fatigued), recommend rest
        if current.tsb < -30:
            return (0.0, 30.0)

        # If TSB is very positive (fresh), can handle more load
        if current.tsb > 20:
            return (current.ctl * 1.0, current.ctl * 1.5)

        # Normal range: 80-120% of CTL
        return (current.ctl * 0.8, current.ctl * 1.2)

    def calculate_ramp_rate(self) -> float:
        """Calculate weekly CTL ramp rate (% change).

        Healthy ramp rate is 3-7% per week.
        """
        history = self.calculate_load(days=14)
        if len(history) < 14:
            return 0.0

        ctl_today = history[-1].ctl
        ctl_week_ago = history[-7].ctl  # 7 days ago (index -7 = 6 positions back)

        if ctl_week_ago == 0:
            return 0.0

        return ((ctl_today - ctl_week_ago) / ctl_week_ago) * 100
