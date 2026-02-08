"""
Session Type Domain Module.

Defines the SessionType enum and classification logic.
Every CSV analysis MUST go through session type classification
before any physiological pipeline runs.
"""
from enum import Enum, auto
from typing import Optional, Tuple, List
from dataclasses import dataclass
import pandas as pd
import numpy as np


# Threshold for classifying as Ramp Test (must meet at least 75% of criteria)
RAMP_CONFIDENCE_THRESHOLD = 0.75


class SessionType(Enum):
    """Domain enum for classifying training session types."""
    RAMP_TEST = auto()
    RAMP_TEST_CONDITIONAL = auto()
    TRAINING = auto()
    UNKNOWN = auto()
    
    def __str__(self) -> str:
        if self == SessionType.RAMP_TEST_CONDITIONAL:
            return "Ramp Test (warunkowo)"
        return self.name.replace("_", " ").title()
    
    @property
    def emoji(self) -> str:
        """Return an emoji representation of the session type."""
        return {
            SessionType.RAMP_TEST: "📈",
            SessionType.RAMP_TEST_CONDITIONAL: "⚠️",
            SessionType.TRAINING: "🚴",
            SessionType.UNKNOWN: "❓",
        }.get(self, "❓")


@dataclass
class RampClassificationResult:
    """Result of deterministic ramp test classification.
    
    Attributes:
        is_ramp: True if classified as ramp test
        confidence: Confidence score 0.0-1.0
        reason: Human-readable explanation of classification
        criteria_met: List of criteria that were met
        criteria_failed: List of criteria that failed
    """
    is_ramp: bool
    confidence: float
    reason: str
    criteria_met: List[str]
    criteria_failed: List[str]
    suggested_type: Optional['SessionType'] = None


def classify_ramp_test(power: pd.Series, step_duration_range: Tuple[int, int] = (30, 60)) -> RampClassificationResult:
    """Deterministic, rule-based ramp test classifier.
    
    Does NOT use ML. Does NOT guess.
    Returns explicit confidence based on criteria fulfillment.
    
    Criteria:
        1. Monotonic power increase (steps must generally go up)
        2. Constant time steps (~30-60s per step)
        3. No recovery phases (no significant power drops mid-test)
        4. Ends with exhaustion (power drops at the end)
    
    Args:
        power: Power series (assumed 1Hz sampling)
        step_duration_range: Expected step duration (min, max) in seconds
        
    Returns:
        RampClassificationResult with is_ramp, confidence, and reason
    """
    criteria_met = []
    criteria_failed = []
    
    # Minimum data requirement
    MIN_DURATION_SEC = 300  # 5 minutes minimum
    if len(power) < MIN_DURATION_SEC:
        return RampClassificationResult(
            is_ramp=False,
            confidence=0.0,
            reason=f"Za mało danych ({len(power)}s < {MIN_DURATION_SEC}s minimum)",
            criteria_met=[],
            criteria_failed=["min_duration"]
        )
    
    # Clean and smooth power data
    power_clean = power.dropna()
    if len(power_clean) < MIN_DURATION_SEC:
        return RampClassificationResult(
            is_ramp=False,
            confidence=0.0,
            reason="Za dużo brakujących danych mocy",
            criteria_met=[],
            criteria_failed=["valid_data"]
        )
    
    power_arr = power_clean.values
    
    # --- CRITERION 1: Detect steps and check monotonic increase ---
    steps = _detect_power_steps(power_arr, step_duration_range)
    
    if len(steps) < 3:
        return RampClassificationResult(
            is_ramp=False,
            confidence=0.0,
            reason=f"Wykryto tylko {len(steps)} kroków (minimum 3)",
            criteria_met=[],
            criteria_failed=["min_steps"]
        )
    
    # Check monotonicity
    step_powers = [s['mean_power'] for s in steps]
    monotonic_increases = sum(1 for i in range(1, len(step_powers)) 
                               if step_powers[i] > step_powers[i-1])
    monotonicity_ratio = monotonic_increases / (len(step_powers) - 1)
    
    if monotonicity_ratio >= 0.8:
        criteria_met.append("monotonic_increase")
    else:
        criteria_failed.append("monotonic_increase")
    
    # --- CRITERION 2: Constant step duration ---
    step_durations = [s['duration'] for s in steps]
    mean_duration = np.mean(step_durations)
    duration_std = np.std(step_durations)
    duration_cv = duration_std / mean_duration if mean_duration > 0 else 1
    
    min_step, max_step = step_duration_range
    duration_in_range = min_step <= mean_duration <= max_step * 2  # Allow some flexibility
    
    if duration_in_range and duration_cv < 0.5:
        criteria_met.append("constant_step_duration")
    else:
        criteria_failed.append("constant_step_duration")
    
    # --- CRITERION 3: No recovery phases ---
    # Check for significant power drops (>20% of current power)
    recovery_phases = _detect_recovery_phases(power_arr, threshold_pct=0.20)
    
    if recovery_phases == 0:
        criteria_met.append("no_recovery_phases")
    else:
        criteria_failed.append("no_recovery_phases")
    
    # --- CRITERION 4: Ends with exhaustion ---
    # Power should drop significantly in the last 10% of the test
    exhaustion_detected = _detect_exhaustion_end(power_arr)
    
    if exhaustion_detected:
        criteria_met.append("exhaustion_end")
    else:
        criteria_failed.append("exhaustion_end")
    
    # --- CALCULATE CONFIDENCE ---
    total_criteria = 4
    met_count = len(criteria_met)
    confidence = met_count / total_criteria
    
    # Decisions:
    # 3-4 criteria -> RAMP_TEST (Confidence >= 0.75)
    # 2 criteria -> RAMP_TEST_CONDITIONAL (Confidence 0.50) if key criteria met
    # < 2 criteria -> TRAINING
    
    is_ramp = met_count >= 2
    
    if met_count >= 3:
        status = SessionType.RAMP_TEST
        reason = f"Ramp Test wykryty ({met_count}/{total_criteria} kryteriów)"
    elif met_count == 2:
        status = SessionType.RAMP_TEST_CONDITIONAL
        reason = f"Wykryto Ramp Test (warunkowo) - odchylenia w profilu ({met_count}/{total_criteria})"
    else:
        status = SessionType.TRAINING
        failed_str = ", ".join(criteria_failed)
        reason = f"NIE jest Ramp Testem. Niespełnione: {failed_str}"
    
    return RampClassificationResult(
        is_ramp=is_ramp,
        confidence=confidence,
        reason=reason,
        criteria_met=criteria_met,
        criteria_failed=criteria_failed,
        suggested_type=status
    )


def _detect_power_steps(power_arr: np.ndarray, duration_range: Tuple[int, int]) -> List[dict]:
    """Detect distinct power steps in the data.
    
    Args:
        power_arr: Power values array (1Hz)
        duration_range: Expected (min, max) step duration
        
    Returns:
        List of step dicts with 'start', 'end', 'mean_power', 'duration'
    """
    min_dur, max_dur = duration_range
    window = min(30, len(power_arr) // 10)
    if window < 5:
        window = 5
    
    # Smooth to find plateaus
    smoothed = pd.Series(power_arr).rolling(window=window, center=True).mean().fillna(method='bfill').fillna(method='ffill').values
    
    # Detect step changes using gradient
    gradient = np.gradient(smoothed)
    
    # Find step boundaries (where gradient exceeds threshold)
    step_threshold = 0.5  # W/s
    step_starts = [0]
    
    in_transition = False
    for i in range(1, len(gradient)):
        if abs(gradient[i]) > step_threshold and not in_transition:
            in_transition = True
        elif abs(gradient[i]) <= step_threshold and in_transition:
            in_transition = False
            if i - step_starts[-1] >= min_dur:
                step_starts.append(i)
    
    # Build step list
    steps = []
    for i in range(len(step_starts)):
        start = step_starts[i]
        end = step_starts[i + 1] if i + 1 < len(step_starts) else len(power_arr)
        duration = end - start
        
        if duration >= min_dur:
            mean_power = np.mean(power_arr[start:end])
            steps.append({
                'start': start,
                'end': end,
                'mean_power': mean_power,
                'duration': duration
            })
    
    return steps


def _detect_recovery_phases(power_arr: np.ndarray, threshold_pct: float = 0.20) -> int:
    """Detect recovery phases (significant power drops).
    
    Args:
        power_arr: Power values
        threshold_pct: Drop threshold as percentage
        
    Returns:
        Number of recovery phases detected
    """
    window = 30
    smoothed = pd.Series(power_arr).rolling(window=window, center=True).mean().fillna(method='bfill').fillna(method='ffill').values
    
    recovery_count = 0
    i = 0
    while i < len(smoothed) - window:
        current = smoothed[i]
        if current > 50:  # Only check when power is meaningful
            # Look ahead for drops
            future = smoothed[i:i+window]
            min_future = np.min(future)
            if min_future < current * (1 - threshold_pct):
                # Check if it recovers back up
                if i + 2*window < len(smoothed):
                    recovery = smoothed[i+window:i+2*window]
                    if np.mean(recovery) > min_future * 1.1:
                        recovery_count += 1
                        i += 2*window
                        continue
        i += 1
    
    return recovery_count


def _detect_exhaustion_end(power_arr: np.ndarray) -> bool:
    """Detect if the test ends with exhaustion (power failure).
    
    Args:
        power_arr: Power values
        
    Returns:
        True if exhaustion pattern detected at end
    """
    if len(power_arr) < 60:
        return False
    
    # Last 10% of data
    end_portion = int(len(power_arr) * 0.1)
    if end_portion < 30:
        end_portion = 30
    
    # Compare last portion to peak power in test
    peak_idx = np.argmax(power_arr)
    peak_power = power_arr[peak_idx]
    
    # Data after peak
    post_peak = power_arr[peak_idx:]
    
    if len(post_peak) < 10:
        return False
    
    # Check for significant drop after peak
    end_power = np.mean(power_arr[-end_portion:])
    drop_pct = (peak_power - end_power) / peak_power if peak_power > 0 else 0
    
    # Exhaustion: power drops >30% from peak at the end
    return drop_pct > 0.30


def classify_session_type(
    df: pd.DataFrame,
    filename: str = ""
) -> SessionType:
    """Classify the session type based on filename and data patterns.
    
    This function MUST be called before any physiological pipeline runs.
    
    Args:
        df: Raw DataFrame loaded from CSV
        filename: Original filename (used for heuristic matching)
        
    Returns:
        SessionType enum value
    """
    if df is None or df.empty:
        return SessionType.UNKNOWN
    
    filename_lower = filename.lower() if filename else ""
    
    # Rule 1: Explicit filename match (high confidence)
    if "ramp" in filename_lower:
        return SessionType.RAMP_TEST
    
    # Rule 2: Deterministic ramp test classification
    if "watts" in df.columns or "power" in df.columns:
        power_col = "watts" if "watts" in df.columns else "power"
        power = df[power_col].dropna()
        
        if len(power) >= 300:  # At least 5 minutes
            ramp_result = classify_ramp_test(power)
            if ramp_result.is_ramp:
                return ramp_result.suggested_type
    
    # Rule 3: Default to Training if valid power data exists
    if "watts" in df.columns or "power" in df.columns:
        power_col = "watts" if "watts" in df.columns else "power"
        valid_power = df[power_col].dropna()
        if len(valid_power) > 0 and valid_power.mean() > 0:
            return SessionType.TRAINING
    
    return SessionType.UNKNOWN
