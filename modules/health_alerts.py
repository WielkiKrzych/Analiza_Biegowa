"""
Health Alerts System.

Automatically detects physiological anomalies and provides warnings:
- Cardiac drift detection
- HRV decline trends
- Thermal stress alerts
- Muscle fatigue patterns
- Overreaching warning
"""
from dataclasses import dataclass
from typing import List, Optional, Literal
import pandas as pd


@dataclass
class HealthAlert:
    """Represents a health warning or recommendation."""
    type: str
    severity: Literal["info", "warning", "critical"]
    message: str
    recommendation: str
    timestamp: Optional[float] = None  # Time in session (seconds)
    value: Optional[float] = None  # Measured value that triggered alert
    
    @property
    def icon(self) -> str:
        """Get emoji icon based on severity."""
        return {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨"
        }.get(self.severity, "ℹ️")
    
    @property
    def color(self) -> str:
        """Get color for UI display."""
        return {
            "info": "blue",
            "warning": "orange",
            "critical": "red"
        }.get(self.severity, "blue")


class HealthMonitor:
    """Analyzes training data for health concerns."""
    
    # Thresholds (can be made configurable)
    CARDIAC_DRIFT_WARNING = 5.0  # % drop in efficiency
    CARDIAC_DRIFT_CRITICAL = 10.0
    HRV_DECLINE_SESSIONS = 3  # Consecutive sessions
    CORE_TEMP_WARNING = 39.0  # °C
    CORE_TEMP_CRITICAL = 39.5
    SMO2_DESAT_THRESHOLD = 20.0  # %
    SMO2_DESAT_DURATION = 120  # seconds
    TSB_OVERREACH_THRESHOLD = -30
    
    def analyze_session(
        self, 
        df: pd.DataFrame, 
        metrics: dict,
        tsb: Optional[float] = None
    ) -> List[HealthAlert]:
        """Run all health checks on session data.
        
        Args:
            df: Session DataFrame with physiological data
            metrics: Calculated metrics dict
            tsb: Current Training Stress Balance (optional)
            
        Returns:
            List of HealthAlert objects
        """
        alerts = []
        
        # Run all detectors
        cardiac_alert = self.check_cardiac_drift(df, metrics)
        if cardiac_alert:
            alerts.append(cardiac_alert)
        
        thermal_alert = self.check_thermal_stress(df)
        if thermal_alert:
            alerts.append(thermal_alert)
        
        muscle_alert = self.check_muscle_fatigue(df)
        if muscle_alert:
            alerts.append(muscle_alert)
        
        if tsb is not None:
            overreach_alert = self.check_overreaching(tsb)
            if overreach_alert:
                alerts.append(overreach_alert)
        
        hydration_alert = self.check_hydration_status(df, metrics)
        if hydration_alert:
            alerts.append(hydration_alert)
        
        # Sort by severity
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 3))
        
        return alerts
    
    def check_cardiac_drift(
        self, 
        df: pd.DataFrame, 
        metrics: dict
    ) -> Optional[HealthAlert]:
        """Detect cardiac drift (decoupling of power and HR).
        
        Cardiac drift indicates fatigue, dehydration, or heat stress.
        """
        decoupling = metrics.get('decoupling_percent') or metrics.get('ef_factor_drop', 0)
        
        if not decoupling:
            # Calculate if not provided
            if 'watts_smooth' in df.columns and 'heartrate_smooth' in df.columns:
                mask = (df['watts_smooth'] > 50) & (df['heartrate_smooth'] > 90)
                df_active = df[mask]
                
                if len(df_active) < 600:  # Need at least 10 min
                    return None
                
                mid = len(df_active) // 2
                p1, p2 = df_active.iloc[:mid], df_active.iloc[mid:]
                
                hr1, hr2 = p1['heartrate_smooth'].mean(), p2['heartrate_smooth'].mean()
                if hr1 == 0 or hr2 == 0:
                    return None
                    
                ef1 = p1['watts_smooth'].mean() / hr1
                ef2 = p2['watts_smooth'].mean() / hr2
                
                if ef1 > 0:
                    decoupling = ((ef1 - ef2) / ef1) * 100
        
        if decoupling >= self.CARDIAC_DRIFT_CRITICAL:
            return HealthAlert(
                type="cardiac_drift",
                severity="critical",
                message=f"Krytyczny dryf sercowy: {decoupling:.1f}%",
                recommendation="Przerwij intensywny wysiłek. Sprawdź nawodnienie i temperaturę.",
                value=decoupling
            )
        elif decoupling >= self.CARDIAC_DRIFT_WARNING:
            return HealthAlert(
                type="cardiac_drift",
                severity="warning",
                message=f"Podwyższony dryf sercowy: {decoupling:.1f}%",
                recommendation="Rozważ zmniejszenie intensywności lub dodatkowe nawodnienie.",
                value=decoupling
            )
        
        return None
    
    def check_thermal_stress(self, df: pd.DataFrame) -> Optional[HealthAlert]:
        """Detect dangerous core temperature levels."""
        if 'core_temperature' not in df.columns and 'core_temperature_smooth' not in df.columns:
            return None
        
        temp_col = 'core_temperature_smooth' if 'core_temperature_smooth' in df.columns else 'core_temperature'
        max_temp = df[temp_col].max()
        
        if pd.isna(max_temp):
            return None
        
        if max_temp >= self.CORE_TEMP_CRITICAL:
            # Find when it happened
            critical_time = df[df[temp_col] >= self.CORE_TEMP_CRITICAL]['time'].min()
            
            return HealthAlert(
                type="thermal_critical",
                severity="critical",
                message=f"Krytyczna temperatura ciała: {max_temp:.1f}°C",
                recommendation="NATYCHMIAST przerwij wysiłek! Schłodź się, pij zimne płyny.",
                timestamp=critical_time,
                value=max_temp
            )
        elif max_temp >= self.CORE_TEMP_WARNING:
            return HealthAlert(
                type="thermal_warning",
                severity="warning",
                message=f"Podwyższona temperatura ciała: {max_temp:.1f}°C",
                recommendation="Ogranicz intensywność, zwiększ chłodzenie, pij więcej.",
                value=max_temp
            )
        
        return None
    
    def check_muscle_fatigue(self, df: pd.DataFrame) -> Optional[HealthAlert]:
        """Detect prolonged muscle deoxygenation (SmO2 desaturation)."""
        smo2_col = 'smo2_smooth' if 'smo2_smooth' in df.columns else 'smo2'
        
        if smo2_col not in df.columns:
            return None
        
        # Find periods of low SmO2
        low_smo2 = df[smo2_col] < self.SMO2_DESAT_THRESHOLD
        
        # Check for consecutive low values
        if low_smo2.sum() >= self.SMO2_DESAT_DURATION:
            # Find longest stretch
            low_smo2_numeric = low_smo2.astype(int)
            groups = (low_smo2_numeric != low_smo2_numeric.shift()).cumsum()
            stretch_lengths = low_smo2.groupby(groups).sum()
            max_stretch = stretch_lengths.max()
            
            if max_stretch >= self.SMO2_DESAT_DURATION:
                min_smo2 = df[smo2_col].min()
                return HealthAlert(
                    type="muscle_fatigue",
                    severity="warning",
                    message=f"Przedłużona desaturacja mięśni: SmO2 < {self.SMO2_DESAT_THRESHOLD}% przez {max_stretch:.0f}s",
                    recommendation="Mięśnie są silnie obciążone. Rozważ dłuższe okresy recovery między interwałami.",
                    value=min_smo2
                )
        
        return None
    
    def check_overreaching(self, tsb: float) -> Optional[HealthAlert]:
        """Check if athlete is in overreaching state based on TSB."""
        if tsb <= self.TSB_OVERREACH_THRESHOLD:
            return HealthAlert(
                type="overreaching",
                severity="warning",
                message=f"Ryzyko przetrenowania: TSB = {tsb:.0f}",
                recommendation="Zaplanuj 1-2 dni odpoczynku lub bardzo lekki trening regeneracyjny.",
                value=tsb
            )
        return None
    
    def check_hydration_status(
        self, 
        df: pd.DataFrame, 
        metrics: dict
    ) -> Optional[HealthAlert]:
        """Estimate dehydration risk based on drift + duration + HR."""
        duration_sec = len(df)
        
        if duration_sec < 3600:  # Less than 1 hour
            return None
        
        # High duration + elevated HR trend suggests dehydration
        if 'heartrate_smooth' in df.columns:
            hr_values = df['heartrate_smooth'].dropna()
            if len(hr_values) > 100:
                hr_first_half = hr_values.iloc[:len(hr_values)//2].mean()
                hr_second_half = hr_values.iloc[len(hr_values)//2:].mean()
                
                hr_rise = hr_second_half - hr_first_half
                
                # More than 10 bpm rise during steady effort suggests dehydration
                if hr_rise > 10 and duration_sec > 5400:  # >1.5h
                    return HealthAlert(
                        type="hydration",
                        severity="info",
                        message=f"Możliwe odwodnienie: HR wzrosło o {hr_rise:.0f} bpm",
                        recommendation="Pamiętaj o regularnym piciu podczas długich treningów (500-1000ml/h).",
                        value=hr_rise
                    )
        
        return None
    
    def check_hrv_trend(
        self, 
        rmssd_history: List[float],
        baseline_rmssd: Optional[float] = None
    ) -> Optional[HealthAlert]:
        """Check for declining HRV trend over multiple sessions.
        
        Args:
            rmssd_history: List of RMSSD values from recent sessions
            baseline_rmssd: Optional baseline RMSSD for comparison
        """
        if len(rmssd_history) < self.HRV_DECLINE_SESSIONS:
            return None
        
        recent = rmssd_history[-self.HRV_DECLINE_SESSIONS:]
        
        # Check if all recent values are declining
        is_declining = all(
            recent[i] < recent[i-1] 
            for i in range(1, len(recent))
        )
        
        if is_declining:
            if baseline_rmssd and recent[-1] < baseline_rmssd * 0.7:
                return HealthAlert(
                    type="hrv_decline",
                    severity="warning",
                    message=f"HRV spadło o {((baseline_rmssd - recent[-1])/baseline_rmssd)*100:.0f}% poniżej baseline",
                    recommendation="Rozważ dzień odpoczynku. Monitoruj jakość snu i stres.",
                    value=recent[-1]
                )
            else:
                return HealthAlert(
                    type="hrv_decline",
                    severity="info",
                    message=f"HRV spada przez {self.HRV_DECLINE_SESSIONS} kolejne sesje",
                    recommendation="Obserwuj samopoczucie. Może być potrzebny odpoczynek.",
                    value=recent[-1]
                )
        
        return None
