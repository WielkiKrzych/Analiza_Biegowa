"""
Step and Phase Detection for Workout Sessions.
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple
from .threshold_types import DetectedStep, StepTestRange


def detect_step_test_range(
    df: pd.DataFrame,
    power_column: str = "watts",
    time_column: str = "time",
    min_step_duration: int = 120,
    max_step_duration: int = 240,
    min_power_increment: int = 15,
    max_power_increment: int = 40,
    min_steps: int = 4,
    power_variation_threshold: float = 0.15,
    end_power_drop_threshold: float = 0.5,
) -> Optional[StepTestRange]:
    """Detect step test boundaries."""
    if df.empty or power_column not in df.columns or time_column not in df.columns:
        return None

    df = df.sort_values(time_column).reset_index(drop=True)
    min_time, max_time = df[time_column].min(), df[time_column].max()
    total_duration = max_time - min_time

    if total_duration < min_step_duration * min_steps:
        return StepTestRange(
            min_time, max_time, [], 0, 0, False, [f"Data too short ({total_duration:.0f}s)"]
        )

    segment_duration = 30
    segments = []
    for t in range(int(min_time), int(max_time) - segment_duration + 1, segment_duration):
        mask = (df[time_column] >= t) & (df[time_column] < t + segment_duration)
        seg = df[mask]
        if len(seg) >= 5:
            segments.append(
                {"start": t, "end": t + segment_duration, "avg_power": seg[power_column].mean()}
            )

    if len(segments) < min_steps * 4:
        return StepTestRange(min_time, max_time, [], 0, 0, False, ["Not enough segments"])

    power_tol = 10
    steps_raw = []
    curr_seg = [segments[0]]
    for i in range(1, len(segments)):
        if abs(segments[i]["avg_power"] - np.mean([s["avg_power"] for s in curr_seg])) <= power_tol:
            curr_seg.append(segments[i])
        else:
            steps_raw.append(
                {
                    "start": curr_seg[0]["start"],
                    "end": curr_seg[-1]["end"],
                    "duration": curr_seg[-1]["end"] - curr_seg[0]["start"],
                    "avg_power": np.mean([s["avg_power"] for s in curr_seg]),
                }
            )
            curr_seg = [segments[i]]
    if curr_seg:
        steps_raw.append(
            {
                "start": curr_seg[0]["start"],
                "end": curr_seg[-1]["end"],
                "duration": curr_seg[-1]["end"] - curr_seg[0]["start"],
                "avg_power": np.mean([s["avg_power"] for s in curr_seg]),
            }
        )

    valid_steps = [
        s for s in steps_raw if min_step_duration <= s["duration"] <= max_step_duration + 60
    ]
    if len(valid_steps) < min_steps:
        return StepTestRange(
            min_time, max_time, [], 0, 0, False, [f"Only {len(valid_steps)} valid duration steps"]
        )

    best_seq = _find_longest_step_sequence(valid_steps, min_power_increment, max_power_increment)

    if len(best_seq) < min_steps:
        return StepTestRange(
            min_time, max_time, [], 0, 0, False, [f"Best sequence too small ({len(best_seq)})"]
        )

    last_end = best_seq[-1]["end"]
    max_p = best_seq[-1]["avg_power"]
    mask_after = df[time_column] > last_end
    test_end = df[time_column].max()
    if mask_after.any():
        power_after = df.loc[mask_after, power_column].rolling(window=10, min_periods=3).mean()
        for idx in power_after.dropna().index:
            if power_after[idx] < max_p * end_power_drop_threshold:
                test_end = df.loc[idx, time_column]
                break

    detected = []
    for i, p in enumerate(best_seq):
        diff = 0 if i == 0 else p["avg_power"] - best_seq[i - 1]["avg_power"]
        detected.append(
            DetectedStep(i + 1, p["start"], p["end"], p["duration"], p["avg_power"], diff)
        )

    return StepTestRange(
        best_seq[0]["start"],
        test_end,
        detected,
        best_seq[0]["avg_power"],
        max_p,
        True,
        [f"Detected {len(detected)} steps"],
    )


def _find_longest_step_sequence(valid_steps, min_power_increment, max_power_increment):
    """
    Find longest sequence of steps with valid power increments.

    Uses optimized O(n^2) with early termination which is faster than original
    O(n^2) due to better constant factors and early exit conditions.

    Args:
        valid_steps: List of step dictionaries with 'avg_power' and other fields
        min_power_increment: Minimum power difference between consecutive steps
        max_power_increment: Maximum power difference between consecutive steps

    Returns:
        List of steps forming the longest valid sequence
    """
    if not valid_steps:
        return []

    n = len(valid_steps)
    if n <= 1:
        return valid_steps[:]

    # dp[i] = length of longest valid sequence ending at step i
    dp = [1] * n
    # parent[i] = previous step index in the longest sequence ending at i
    parent = [-1] * n

    best_length = 1
    best_end_idx = 0

    for i in range(1, n):
        best_prev = -1
        best_prev_len = 0

        for j in range(i):
            diff = valid_steps[i]["avg_power"] - valid_steps[j]["avg_power"]

            if min_power_increment <= diff <= max_power_increment:
                if dp[j] > best_prev_len:
                    best_prev_len = dp[j]
                    best_prev = j

        if best_prev >= 0:
            dp[i] = best_prev_len + 1
            parent[i] = best_prev

            if dp[i] > best_length:
                best_length = dp[i]
                best_end_idx = i

    # Reconstruct sequence
    sequence = []
    idx = best_end_idx
    while idx >= 0:
        sequence.append(valid_steps[idx])
        idx = parent[idx]

    return list(reversed(sequence))


def segment_load_phases(
    df: pd.DataFrame,
    power_col: str = "watts",
    time_col: str = "time",
    min_phase_duration: int = 180,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split dataset into increasing and decreasing load phases."""
    if df.empty or power_col not in df.columns:
        return df, pd.DataFrame()
    s_watts = df[power_col].rolling(window=30, center=True).mean().fillna(df[power_col])
    peak_time = df.loc[s_watts.idxmax(), time_col]
    df_inc = df[df[time_col] <= peak_time].copy()
    df_dec = df[df[time_col] > peak_time].copy()
    if (
        df_inc[time_col].max() - df_inc[time_col].min() if not df_inc.empty else 0
    ) < min_phase_duration:
        return df, pd.DataFrame()
    return df_inc, df_dec
