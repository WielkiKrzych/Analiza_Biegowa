"""
AI Interval Detection Module.

Automatically detects and classifies training intervals:
- Change-point detection for interval boundaries
- Classification of interval types (Sprint, VO2max, Threshold, Tempo, Endurance)
- Quality scoring (target vs actual)
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import pandas as pd
import numpy as np
from scipy.ndimage import uniform_filter1d


class IntervalType(Enum):
    """Classification of training interval types."""
    SPRINT = "sprint"           # <30s, >150% CP
    VO2MAX = "vo2max"           # 2-8min, 105-120% CP
    THRESHOLD = "threshold"     # 8-20min, 90-105% CP
    SWEETSPOT = "sweetspot"     # 10-30min, 83-90% CP
    TEMPO = "tempo"             # 20-60min, 75-83% CP
    ENDURANCE = "endurance"     # >20min, <75% CP
    RECOVERY = "recovery"       # any duration, <55% CP
    UNKNOWN = "unknown"
    
    @property
    def color(self) -> str:
        """Color for visualization."""
        return {
            IntervalType.SPRINT: "#FF0000",
            IntervalType.VO2MAX: "#FF4500",
            IntervalType.THRESHOLD: "#FFD700",
            IntervalType.SWEETSPOT: "#FFA500",
            IntervalType.TEMPO: "#32CD32",
            IntervalType.ENDURANCE: "#00CED1",
            IntervalType.RECOVERY: "#808080",
            IntervalType.UNKNOWN: "#CCCCCC"
        }.get(self, "#CCCCCC")
    
    @property
    def description(self) -> str:
        """Polish description of interval type."""
        return {
            IntervalType.SPRINT: "Sprint (max moc)",
            IntervalType.VO2MAX: "VO2max (moc maksymalna tlenowa)",
            IntervalType.THRESHOLD: "Próg (FTP/CP)",
            IntervalType.SWEETSPOT: "Sweet Spot (83-90% FTP)",
            IntervalType.TEMPO: "Tempo (trening bazowy)",
            IntervalType.ENDURANCE: "Wytrzymałość (Z2)",
            IntervalType.RECOVERY: "Recovery (regeneracja)",
            IntervalType.UNKNOWN: "Nieznany"
        }.get(self, "Nieznany")


@dataclass
class DetectedInterval:
    """Represents a detected training interval."""
    start_sec: float
    end_sec: float
    interval_type: IntervalType
    avg_power: float
    max_power: float
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    normalized_power: Optional[float] = None
    quality_score: Optional[float] = None  # 0-100
    target_power: Optional[float] = None
    notes: str = ""
    
    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec
    
    @property
    def duration_str(self) -> str:
        """Human-readable duration."""
        mins, secs = divmod(int(self.duration_sec), 60)
        if mins > 0:
            return f"{mins}:{secs:02d}"
        return f"{secs}s"
    
    @property
    def start_min(self) -> float:
        return self.start_sec / 60
    
    @property
    def end_min(self) -> float:
        return self.end_sec / 60


class IntervalDetector:
    """AI-powered interval detection and classification."""
    
    # Detection parameters
    MIN_INTERVAL_DURATION = 10  # seconds
    POWER_CHANGE_THRESHOLD = 0.15  # 15% power change for boundary
    SMOOTHING_WINDOW = 10  # seconds for smoothing
    
    def __init__(self, cp: float = 250):
        """
        Args:
            cp: Critical Power / FTP for zone calculations
        """
        self.cp = cp
    
    def detect_intervals(self, df: pd.DataFrame) -> List[DetectedInterval]:
        """Detect all intervals in the workout.
        
        Uses change-point detection on smoothed power data.
        
        Args:
            df: DataFrame with 'watts' and 'time' columns
            
        Returns:
            List of detected intervals
        """
        if 'watts' not in df.columns:
            return []
        
        # Get power data
        watts = df['watts'].fillna(0).values
        time = df['time'].values if 'time' in df.columns else np.arange(len(watts))
        
        if len(watts) < self.MIN_INTERVAL_DURATION * 2:
            return []
        
        # Smooth power data
        watts_smooth = uniform_filter1d(watts, size=self.SMOOTHING_WINDOW)
        
        # Detect change points
        boundaries = self._detect_boundaries(watts_smooth)
        
        # Create intervals from boundaries
        intervals = []
        for i in range(len(boundaries) - 1):
            start_idx = boundaries[i]
            end_idx = boundaries[i + 1]
            
            # Skip very short intervals
            duration = time[end_idx] - time[start_idx] if len(time) > end_idx else end_idx - start_idx
            if duration < self.MIN_INTERVAL_DURATION:
                continue
            
            # Extract interval data
            interval_watts = watts[start_idx:end_idx]
            avg_power = np.mean(interval_watts)
            max_power = np.max(interval_watts)
            
            # Get HR if available
            avg_hr = None
            max_hr = None
            if 'heartrate' in df.columns:
                interval_hr = df['heartrate'].iloc[start_idx:end_idx]
                avg_hr = interval_hr.mean()
                max_hr = interval_hr.max()
            
            # Classify interval
            interval_type = self._classify_interval(avg_power, duration)
            
            # Calculate NP for interval
            np_val = self._calculate_interval_np(interval_watts)
            
            interval = DetectedInterval(
                start_sec=float(time[start_idx]) if len(time) > start_idx else float(start_idx),
                end_sec=float(time[end_idx]) if len(time) > end_idx else float(end_idx),
                interval_type=interval_type,
                avg_power=avg_power,
                max_power=max_power,
                avg_hr=avg_hr,
                max_hr=max_hr,
                normalized_power=np_val
            )
            intervals.append(interval)
        
        # Merge similar adjacent intervals
        intervals = self._merge_similar_intervals(intervals)
        
        return intervals
    
    def _detect_boundaries(self, watts_smooth: np.ndarray) -> List[int]:
        """Detect interval boundaries using derivative analysis.
        
        Returns list of indices where intervals start/end.
        """
        boundaries = [0]  # Start
        
        # Calculate derivative (rate of change)
        derivative = np.diff(watts_smooth)
        derivative_smooth = uniform_filter1d(derivative, size=5)
        
        # Find significant changes
        threshold = np.std(derivative_smooth) * 1.5
        
        # State machine to track power changes
        in_change = False
        last_boundary = 0
        
        for i in range(1, len(derivative_smooth)):
            abs_deriv = abs(derivative_smooth[i])
            
            if abs_deriv > threshold and not in_change:
                # Start of power change
                if i - last_boundary > self.MIN_INTERVAL_DURATION:
                    boundaries.append(i)
                    last_boundary = i
                in_change = True
            elif abs_deriv < threshold * 0.5:
                in_change = False
        
        boundaries.append(len(watts_smooth) - 1)  # End
        
        return boundaries
    
    def _classify_interval(self, avg_power: float, duration: float) -> IntervalType:
        """Classify interval based on power relative to CP and duration.
        
        Args:
            avg_power: Average power in watts
            duration: Duration in seconds
        """
        if self.cp <= 0:
            return IntervalType.UNKNOWN
        
        pct_cp = avg_power / self.cp
        
        # Sprint: very high power, very short
        if pct_cp > 1.5 and duration < 30:
            return IntervalType.SPRINT
        
        # VO2max: high power, short-medium duration
        if pct_cp > 1.05 and duration < 480:  # <8min
            return IntervalType.VO2MAX
        
        # Threshold: around CP, medium duration
        if 0.90 <= pct_cp <= 1.05:
            return IntervalType.THRESHOLD
        
        # Sweet Spot: just below threshold
        if 0.83 <= pct_cp < 0.90:
            return IntervalType.SWEETSPOT
        
        # Tempo: moderate intensity
        if 0.75 <= pct_cp < 0.83:
            return IntervalType.TEMPO
        
        # Recovery: very low
        if pct_cp < 0.55:
            return IntervalType.RECOVERY
        
        # Endurance: low-moderate
        if pct_cp < 0.75:
            return IntervalType.ENDURANCE
        
        return IntervalType.UNKNOWN
    
    def _calculate_interval_np(self, watts: np.ndarray) -> float:
        """Calculate Normalized Power for an interval."""
        if len(watts) < 30:
            return np.mean(watts)
        
        # 30s rolling average
        rolling = uniform_filter1d(watts, size=min(30, len(watts)))
        # 4th power
        powered = np.power(rolling, 4)
        # Mean
        mean_powered = np.mean(powered)
        # 4th root
        return np.power(mean_powered, 0.25)
    
    def _merge_similar_intervals(
        self, 
        intervals: List[DetectedInterval]
    ) -> List[DetectedInterval]:
        """Merge adjacent intervals of the same type."""
        if len(intervals) < 2:
            return intervals
        
        merged = [intervals[0]]
        
        for interval in intervals[1:]:
            last = merged[-1]
            
            # Merge if same type and close together
            time_gap = interval.start_sec - last.end_sec
            same_type = interval.interval_type == last.interval_type
            power_similar = abs(interval.avg_power - last.avg_power) < 20
            
            if same_type and time_gap < 30 and power_similar:
                # Merge into last
                merged[-1] = DetectedInterval(
                    start_sec=last.start_sec,
                    end_sec=interval.end_sec,
                    interval_type=last.interval_type,
                    avg_power=(last.avg_power + interval.avg_power) / 2,
                    max_power=max(last.max_power, interval.max_power),
                    avg_hr=(last.avg_hr + interval.avg_hr) / 2 if last.avg_hr and interval.avg_hr else None,
                    max_hr=max(last.max_hr or 0, interval.max_hr or 0) or None
                )
            else:
                merged.append(interval)
        
        return merged
    
    def score_interval_quality(
        self, 
        interval: DetectedInterval, 
        target_power: float,
        tolerance: float = 0.05
    ) -> float:
        """Score interval execution quality (0-100).
        
        Args:
            interval: The detected interval
            target_power: Target average power
            tolerance: Acceptable deviation (default 5%)
            
        Returns:
            Quality score 0-100
        """
        if target_power <= 0:
            return 0.0
        
        deviation = abs(interval.avg_power - target_power) / target_power
        
        # Perfect execution = 100
        # 5% deviation = 90
        # 10% deviation = 70
        # 20% deviation = 40
        # >30% deviation = 0
        
        if deviation <= tolerance:
            return 100.0
        elif deviation <= 0.10:
            return 90 - (deviation - tolerance) * 400
        elif deviation <= 0.20:
            return 70 - (deviation - 0.10) * 300
        elif deviation <= 0.30:
            return 40 - (deviation - 0.20) * 400
        else:
            return max(0, 10 - (deviation - 0.30) * 100)
    
    def analyze_workout_structure(
        self, 
        intervals: List[DetectedInterval]
    ) -> dict:
        """Analyze overall workout structure.
        
        Returns summary statistics about the detected intervals.
        """
        if not intervals:
            return {}
        
        total_time = sum(i.duration_sec for i in intervals)
        
        # Time in each zone
        zone_times = {}
        for interval in intervals:
            zone = interval.interval_type.value
            zone_times[zone] = zone_times.get(zone, 0) + interval.duration_sec
        
        # Count intervals by type
        zone_counts = {}
        for interval in intervals:
            zone = interval.interval_type.value
            zone_counts[zone] = zone_counts.get(zone, 0) + 1
        
        # Find work intervals (non-recovery, non-endurance)
        work_types = [IntervalType.SPRINT, IntervalType.VO2MAX, 
                      IntervalType.THRESHOLD, IntervalType.SWEETSPOT]
        work_intervals = [i for i in intervals if i.interval_type in work_types]
        
        return {
            'total_intervals': len(intervals),
            'work_intervals': len(work_intervals),
            'total_work_time': sum(i.duration_sec for i in work_intervals),
            'zone_times': zone_times,
            'zone_counts': zone_counts,
            'avg_work_power': np.mean([i.avg_power for i in work_intervals]) if work_intervals else 0,
            'max_interval_power': max(i.max_power for i in intervals) if intervals else 0
        }
