"""
CPET-Grade Ventilatory Threshold Detection (VT1/VT2).

Laboratory-standard detection using ventilatory equivalents (VE/VO2, VE/VCO2),
segmented regression, and VE-only 4-point CPET mode for TymeWear data.
"""

import warnings
from typing import Any, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


def detect_vt_vslope_savgol(
    df: pd.DataFrame,
    step_range: Optional[Any] = None,
    power_column: str = "watts",
    ve_column: str = "tymeventilation",
    time_column: str = "time",
    min_power_watts: Optional[int] = None,
) -> dict:
    """
    DEPRECATED: Use detect_vt_cpet() for CPET-grade detection.
    This wrapper calls the new function for backward compatibility.
    """
    warnings.warn(
        "detect_vt_vslope_savgol is deprecated. Use detect_vt_cpet instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return detect_vt_cpet(
        df, step_range, power_column, ve_column, time_column, min_power_watts=min_power_watts
    )


def _preprocess_ventilation_data(
    df: pd.DataFrame,
    power_column: str,
    ve_column: str,
    time_column: str,
    vo2_column: str,
    vco2_column: str,
    hr_column: str,
    smoothing_window_sec: int,
) -> Tuple[pd.DataFrame, dict, dict, dict]:
    """
    Preprocess ventilation data: normalize columns, units, smooth signals, detect artifacts.

    Returns:
        Tuple of (processed_data, column_mapping, flags, result_dict_with_notes)
    """
    data = df.copy()
    data.columns = data.columns.str.lower().str.strip()

    # Normalize column names mapping
    cols = {
        "power": power_column.lower(),
        "ve": ve_column.lower(),
        "time": time_column.lower(),
        "vo2": vo2_column.lower(),
        "vco2": vco2_column.lower(),
        "hr": hr_column.lower(),
    }

    # Initialize result with notes
    preprocess_result = {"analysis_notes": [], "has_gas_exchange": False, "error": None}

    # Check required columns
    if cols["power"] not in data.columns:
        preprocess_result["error"] = f"Missing {power_column}"
        return data, cols, {}, preprocess_result
    if cols["ve"] not in data.columns:
        preprocess_result["error"] = f"Missing {ve_column}"
        return data, cols, {}, preprocess_result

    # Check for gas exchange data
    has_vo2 = cols["vo2"] in data.columns and data[cols["vo2"]].notna().sum() > 10
    has_vco2 = cols["vco2"] in data.columns and data[cols["vco2"]].notna().sum() > 10
    has_hr = cols["hr"] in data.columns and data[cols["hr"]].notna().sum() > 10
    preprocess_result["has_gas_exchange"] = has_vo2 and has_vco2

    # Unit normalization: VE L/s → L/min
    ve_max = data[cols["ve"]].max()
    if ve_max < 8.0:
        data["ve_lmin"] = data[cols["ve"]] * 60
    else:
        data["ve_lmin"] = data[cols["ve"]]

    # VO2/VCO2: ml/min → L/min
    if has_vo2:
        if data[cols["vo2"]].mean() > 100:
            data["vo2_lmin"] = data[cols["vo2"]] / 1000
        else:
            data["vo2_lmin"] = data[cols["vo2"]]

    if has_vco2:
        if data[cols["vco2"]].mean() > 100:
            data["vco2_lmin"] = data[cols["vco2"]] / 1000
        else:
            data["vco2_lmin"] = data[cols["vco2"]]

    # Smoothing
    window = min(smoothing_window_sec, len(data) // 4)
    if window < 3:
        window = 3

    data["ve_smooth"] = data["ve_lmin"].rolling(window, center=True, min_periods=1).mean()

    if has_vo2:
        data["vo2_smooth"] = data["vo2_lmin"].rolling(window, center=True, min_periods=1).mean()
    if has_vco2:
        data["vco2_smooth"] = data["vco2_lmin"].rolling(window, center=True, min_periods=1).mean()

    # Artifact detection: Remove spikes in VE without matching VO2/VCO2 change
    if has_vo2 and has_vco2:
        ve_diff = data["ve_smooth"].diff().abs()
        vo2_diff = data["vo2_smooth"].diff().abs()
        vco2_diff = data["vco2_smooth"].diff().abs()

        ve_threshold = ve_diff.std() * 3
        gas_threshold = max(vo2_diff.std(), vco2_diff.std())

        artifact_mask = (ve_diff > ve_threshold) & (
            (vo2_diff < gas_threshold) & (vco2_diff < gas_threshold)
        )
        artifact_count = artifact_mask.sum()
        if artifact_count > 0:
            preprocess_result["analysis_notes"].append(
                f"Removed {artifact_count} respiratory artifacts"
            )
            data.loc[artifact_mask, "ve_smooth"] = np.nan
            data["ve_smooth"] = data["ve_smooth"].interpolate(method="linear")

    flags = {
        "has_vo2": has_vo2,
        "has_vco2": has_vco2,
        "has_hr": has_hr,
    }

    return data, cols, flags, preprocess_result


def _detect_vt1_cpet(
    df_steps: pd.DataFrame,
    has_gas_exchange: bool,
    result: dict,
) -> dict:
    """
    Detect VT1 using segmented regression on VE/VO2 (CPET mode).

    Args:
        df_steps: DataFrame with aggregated step data
        has_gas_exchange: Whether VO2/VCO2 data is available
        result: Result dict to update with VT1 values

    Returns:
        Updated result dict with VT1 detection
    """
    if not has_gas_exchange:
        return result, None

    # Calculate ventilatory equivalents if not present
    if "ve_vo2" not in df_steps.columns:
        df_steps["ve_vo2"] = df_steps["ve"] / df_steps["vo2"].replace(0, np.nan)
        df_steps["ve_vco2"] = df_steps["ve"] / df_steps["vco2"].replace(0, np.nan)
        df_steps["rer"] = df_steps["vco2"] / df_steps["vo2"].replace(0, np.nan)

    vo2max = df_steps["vo2"].max()

    vt1_idx = _find_breakpoint_segmented(
        df_steps["power"].values, df_steps["ve_vo2"].values, min_segment_size=3
    )

    if vt1_idx is not None and 1 < vt1_idx < len(df_steps) - 1:
        # Validate: VE/VCO2 should be relatively flat at VT1
        vco2_slope_before = _calculate_segment_slope(
            df_steps["power"].values[:vt1_idx], df_steps["ve_vco2"].values[:vt1_idx]
        )
        vco2_slope_at = _calculate_segment_slope(
            df_steps["power"].values[max(0, vt1_idx - 2) : vt1_idx + 2],
            df_steps["ve_vco2"].values[max(0, vt1_idx - 2) : vt1_idx + 2],
        )

        # VE/VCO2 should not be rising significantly at VT1
        if abs(vco2_slope_at) < 0.1 or vco2_slope_at < vco2_slope_before * 1.5:
            result["vt1_watts"] = int(df_steps.loc[vt1_idx, "power"])
            result["vt1_ve"] = round(df_steps.loc[vt1_idx, "ve"], 1)
            result["vt1_vo2"] = round(df_steps.loc[vt1_idx, "vo2"], 2)
            result["vt1_step"] = int(df_steps.loc[vt1_idx, "step"])
            result["vt1_pct_vo2max"] = (
                round(df_steps.loc[vt1_idx, "vo2"] / vo2max * 100, 1) if vo2max > 0 else None
            )
            if "hr" in df_steps.columns and pd.notna(df_steps.loc[vt1_idx, "hr"]):
                result["vt1_hr"] = int(df_steps.loc[vt1_idx, "hr"])
            if "br" in df_steps.columns and pd.notna(df_steps.loc[vt1_idx, "br"]):
                result["vt1_br"] = int(df_steps.loc[vt1_idx, "br"])
            result["analysis_notes"].append(
                f"VT1 detected at step {result['vt1_step']} via VE/VO2 breakpoint"
            )
        else:
            result["analysis_notes"].append("VT1 candidate rejected: VE/VCO2 already rising")

    return result, vt1_idx


def _detect_vt2_cpet(
    df_steps: pd.DataFrame,
    has_gas_exchange: bool,
    vt1_idx: Optional[int],
    result: dict,
) -> dict:
    """
    Detect VT2 using segmented regression on VE/VCO2 + RER validation (CPET mode).

    Args:
        df_steps: DataFrame with aggregated step data
        has_gas_exchange: Whether VO2/VCO2 data is available
        vt1_idx: Index of detected VT1 (for search start)
        result: Result dict to update with VT2 values

    Returns:
        Updated result dict with VT2 detection
    """
    if not has_gas_exchange:
        return result

    vo2max = df_steps["vo2"].max() if "vo2" in df_steps.columns else None

    search_start = vt1_idx + 1 if vt1_idx else 3

    # Guard: ensure search_start is within bounds
    if search_start >= len(df_steps) - 4:
        search_start = max(3, len(df_steps) // 2)

    # Only search if we have enough data points remaining
    remaining_points = len(df_steps) - search_start
    if remaining_points < 4:
        return result

    vt2_idx = _find_breakpoint_segmented(
        df_steps["power"].values[search_start:],
        df_steps["ve_vco2"].values[search_start:],
        min_segment_size=2,
    )

    if vt2_idx is not None:
        vt2_idx += search_start  # Adjust for subset

        if vt2_idx < len(df_steps):
            # Validate: RER should be near 1.0
            rer_at_vt2 = df_steps.loc[vt2_idx, "rer"]

            if pd.notna(rer_at_vt2) and 0.95 <= rer_at_vt2 <= 1.15:
                result["vt2_watts"] = int(df_steps.loc[vt2_idx, "power"])
                result["vt2_ve"] = round(df_steps.loc[vt2_idx, "ve"], 1)
                result["vt2_vo2"] = (
                    round(df_steps.loc[vt2_idx, "vo2"], 2) if "vo2" in df_steps.columns else None
                )
                result["vt2_step"] = int(df_steps.loc[vt2_idx, "step"])
                result["vt2_pct_vo2max"] = (
                    round(df_steps.loc[vt2_idx, "vo2"] / vo2max * 100, 1)
                    if vo2max and vo2max > 0 and "vo2" in df_steps.columns
                    else None
                )
                if "hr" in df_steps.columns and pd.notna(df_steps.loc[vt2_idx, "hr"]):
                    result["vt2_hr"] = int(df_steps.loc[vt2_idx, "hr"])
                if "br" in df_steps.columns and pd.notna(df_steps.loc[vt2_idx, "br"]):
                    result["vt2_br"] = int(df_steps.loc[vt2_idx, "br"])
                result["analysis_notes"].append(
                    f"VT2 detected at step {result['vt2_step']} (RER={rer_at_vt2:.2f})"
                )
            else:
                # Accept but note RER discrepancy
                result["vt2_watts"] = int(df_steps.loc[vt2_idx, "power"])
                result["vt2_ve"] = round(df_steps.loc[vt2_idx, "ve"], 1)
                result["vt2_step"] = int(df_steps.loc[vt2_idx, "step"])
                if "hr" in df_steps.columns and pd.notna(df_steps.loc[vt2_idx, "hr"]):
                    result["vt2_hr"] = int(df_steps.loc[vt2_idx, "hr"])
                if "br" in df_steps.columns and pd.notna(df_steps.loc[vt2_idx, "br"]):
                    result["vt2_br"] = int(df_steps.loc[vt2_idx, "br"])
                rer_str = f"{rer_at_vt2:.2f}" if pd.notna(rer_at_vt2) else "N/A"
                result["analysis_notes"].append(f"VT2 detected but RER={rer_str} (expected ~1.0)")

    return result


def _run_ve_only_mode(
    df_steps: pd.DataFrame,
    data: pd.DataFrame,
    cols: dict,
    flags: dict,
    result: dict,
) -> dict:
    """
    VE-only 4-point CPET detection for TymeWear data.

    Detects: VT1_onset, VT1_steady, RCP_onset, RCP_steady
    Builds: 4 metabolic domains (Pure Aerobic, Upper Aerobic, Heavy, Severe)

    Args:
        df_steps: DataFrame with aggregated step data
        data: Original preprocessed data
        cols: Column name mapping
        flags: Flags dict with has_hr, has_br, etc.
        result: Result dict to update

    Returns:
        Updated result dict with VE-only detection
    """
    from scipy.signal import savgol_filter

    result["analysis_notes"].append("VE-only mode: 4-point CPET detection")
    result["method"] = "ve_only_4point_cpet"

    # =====================================================================
    # 1. PREPROCESSING
    # =====================================================================
    try:
        window = min(5, len(df_steps) if len(df_steps) % 2 == 1 else len(df_steps) - 1)
        if window < 3:
            window = 3
        df_steps["ve_smooth"] = savgol_filter(
            df_steps["ve"].values, window_length=window, polyorder=2
        )
    except Exception:
        df_steps["ve_smooth"] = df_steps["ve"].rolling(3, center=True, min_periods=1).mean()

    has_hr = "hr" in df_steps.columns and df_steps["hr"].notna().sum() > 3
    has_br = "br" in df_steps.columns and df_steps["br"].notna().sum() > 3

    # Smooth BR if available
    if has_br:
        df_steps["br_smooth"] = df_steps["br"].rolling(3, center=True, min_periods=1).mean()
        # Tidal Volume = VE / BR
        df_steps["vt_calc"] = df_steps["ve_smooth"] / df_steps["br_smooth"].replace(0, np.nan)
        df_steps["vt_smooth"] = df_steps["vt_calc"].rolling(3, center=True, min_periods=1).mean()

    # =====================================================================
    # 2. CALCULATE DERIVATIVES
    # =====================================================================
    ve_slope = np.gradient(df_steps["ve_smooth"].values, df_steps["power"].values)
    df_steps["ve_slope"] = ve_slope

    ve_accel = np.gradient(ve_slope, df_steps["power"].values)
    df_steps["ve_accel"] = ve_accel
    df_steps["ve_accel_smooth"] = df_steps["ve_accel"].rolling(3, center=True, min_periods=1).mean()

    # BR derivatives (if available)
    if has_br:
        br_slope = np.gradient(df_steps["br_smooth"].values, df_steps["power"].values)
        df_steps["br_slope"] = br_slope
        df_steps["br_slope_smooth"] = (
            df_steps["br_slope"].rolling(3, center=True, min_periods=1).mean()
        )

        # VT (tidal volume) derivatives
        vt_slope = np.gradient(df_steps["vt_smooth"].ffill().values, df_steps["power"].values)
        df_steps["vt_slope"] = vt_slope
        df_steps["vt_slope_smooth"] = (
            df_steps["vt_slope"].rolling(3, center=True, min_periods=1).mean()
        )

    # HR derivatives (if available)
    if has_hr:
        hr_slope = np.gradient(df_steps["hr"].values, df_steps["power"].values)
        df_steps["hr_slope"] = hr_slope
        baseline_hr_slope = np.mean(hr_slope[: min(4, len(hr_slope))])
        if baseline_hr_slope > 0:
            df_steps["hr_drift"] = hr_slope / baseline_hr_slope
        else:
            df_steps["hr_drift"] = np.ones(len(hr_slope))

    # =====================================================================
    # 3. DETECT 4 PHYSIOLOGICAL POINTS
    # =====================================================================
    baseline_ve_slope = np.mean(df_steps["ve_slope"].iloc[: min(4, len(df_steps))])
    baseline_ve_accel = np.mean(df_steps["ve_accel_smooth"].iloc[: min(4, len(df_steps))])
    baseline_br_slope = 0
    if has_br:
        baseline_br_slope = np.mean(df_steps["br_slope_smooth"].iloc[: min(4, len(df_steps))])

    vt1_onset_idx = None
    vt1_steady_idx = None
    rcp_onset_idx = None
    rcp_steady_idx = None

    # ---------------------------------------------------------------------
    # A. VT1_ONSET (GET / LT1 Onset)
    # ---------------------------------------------------------------------
    for i in range(3, len(df_steps) - 4):
        accel_prev = df_steps["ve_accel_smooth"].iloc[i - 1]
        accel_curr = df_steps["ve_accel_smooth"].iloc[i]
        sign_change = (accel_prev <= 0 and accel_curr > 0) or (accel_curr > baseline_ve_accel * 2)

        slope_rising = (
            df_steps["ve_slope"].iloc[i] > baseline_ve_slope * 1.15
            and df_steps["ve_slope"].iloc[i + 1] > baseline_ve_slope * 1.10
        )

        br_not_spiking = True
        if has_br and baseline_br_slope > 0:
            br_not_spiking = df_steps["br_slope_smooth"].iloc[i] < baseline_br_slope * 2.0

        if (sign_change or slope_rising) and br_not_spiking:
            if df_steps["ve_slope"].iloc[i + 2] > baseline_ve_slope * 1.05:
                vt1_onset_idx = i
                break

    # ---------------------------------------------------------------------
    # B. VT1_STEADY (LT1 Steady / Upper Aerobic Ceiling)
    # ---------------------------------------------------------------------
    vt1_steady_is_real = False

    if vt1_onset_idx is not None:
        for i in range(vt1_onset_idx + 2, len(df_steps) - 3):
            curr_slope = df_steps["ve_slope"].iloc[i]
            next_slope = df_steps["ve_slope"].iloc[i + 1]
            next2_slope = df_steps["ve_slope"].iloc[i + 2]

            elevated = curr_slope > baseline_ve_slope * 1.15

            delta_1 = abs(next_slope - curr_slope) / max(abs(curr_slope), 0.01)
            delta_2 = abs(next2_slope - curr_slope) / max(abs(curr_slope), 0.01)
            slope_stable = delta_1 < 0.12 and delta_2 < 0.15

            br_ok = True
            if has_br and baseline_br_slope > 0:
                br_at_i = df_steps["br_slope_smooth"].iloc[i]
                br_ok = br_at_i < baseline_br_slope * 1.5

            ve_accel_at_i = df_steps["ve_accel_smooth"].iloc[i]
            no_exponential = ve_accel_at_i < baseline_ve_accel * 2.5

            if elevated and slope_stable and br_ok and no_exponential:
                vt1_steady_idx = i
                vt1_steady_is_real = True
                break

    result["vt1_steady_is_real"] = vt1_steady_is_real

    # ---------------------------------------------------------------------
    # C. RCP_ONSET (VT2 / LT2 Onset - Respiratory Compensation Point)
    # ---------------------------------------------------------------------
    search_start = vt1_steady_idx if vt1_steady_idx else (vt1_onset_idx + 2 if vt1_onset_idx else 4)

    if search_start and search_start < len(df_steps) - 3:
        search_df = df_steps.iloc[search_start:]

        if len(search_df) >= 3:
            max_accel_idx = search_df["ve_accel_smooth"].idxmax()
            max_accel_val = df_steps.loc[max_accel_idx, "ve_accel_smooth"]

            rcp_candidates = []

            for idx in search_df.index:
                ve_accel_high = df_steps.loc[idx, "ve_accel_smooth"] > max_accel_val * 0.6

                br_spike = True
                vt_plateau = True

                if has_br:
                    br_slope_val = df_steps.loc[idx, "br_slope_smooth"]
                    br_spike = (
                        br_slope_val > baseline_br_slope * 2.0
                        if baseline_br_slope > 0
                        else br_slope_val > 0.1
                    )

                    vt_slope_val = abs(df_steps.loc[idx, "vt_slope_smooth"])
                    baseline_vt_slope = abs(
                        np.mean(df_steps["vt_slope_smooth"].iloc[: min(4, len(df_steps))])
                    )
                    vt_plateau = (
                        vt_slope_val < baseline_vt_slope * 0.7 if baseline_vt_slope > 0 else True
                    )

                if ve_accel_high and br_spike and vt_plateau:
                    rcp_candidates.append((idx, df_steps.loc[idx, "ve_accel_smooth"]))

            if rcp_candidates:
                rcp_onset_idx = max(rcp_candidates, key=lambda x: x[1])[0]
            else:
                rcp_onset_idx = max_accel_idx

    # ---------------------------------------------------------------------
    # D. RCP_STEADY (Full RCP / Severe Domain Entry)
    # ---------------------------------------------------------------------
    if rcp_onset_idx is not None:
        rcp_onset_loc = df_steps.index.get_loc(rcp_onset_idx)

        for i in range(rcp_onset_loc + 1, len(df_steps) - 1):
            idx = df_steps.index[i]

            ve_accel_high = df_steps.loc[idx, "ve_accel_smooth"] > baseline_ve_accel * 3

            br_dominates = True
            if has_br:
                br_slope_val = df_steps.loc[idx, "br_slope_smooth"]
                vt_slope_val = df_steps.loc[idx, "vt_slope_smooth"]
                br_dominates = (
                    abs(br_slope_val) > abs(vt_slope_val) * 1.5 if vt_slope_val != 0 else True
                )

            hr_drift_strong = True
            if has_hr:
                hr_drift_strong = df_steps.loc[idx, "hr_drift"] > 1.5

            if ve_accel_high and br_dominates and hr_drift_strong:
                rcp_steady_idx = idx
                break

        if rcp_steady_idx is None and rcp_onset_loc + 1 < len(df_steps):
            rcp_steady_idx = df_steps.index[min(rcp_onset_loc + 1, len(df_steps) - 1)]

    # =====================================================================
    # 4. STORE RESULTS
    # =====================================================================
    def get_point_data(idx, point_name):
        if idx is None:
            return None
        row = (
            df_steps.loc[idx]
            if isinstance(idx, (int, np.integer)) and idx in df_steps.index
            else df_steps.iloc[idx]
        )
        data = {
            "watts": int(row["power"]),
            "ve": round(row["ve"], 1),
            "step": int(row["step"]),
            "time": row.get("time", 0),
        }
        if "hr" in row and pd.notna(row["hr"]):
            data["hr"] = int(row["hr"])
        if "br" in row and pd.notna(row["br"]):
            data["br"] = int(row["br"])
        if "vt_smooth" in row and pd.notna(row["vt_smooth"]):
            data["vt"] = round(row["vt_smooth"], 2)
        return data

    # VT1 Onset
    if vt1_onset_idx is not None:
        pt = get_point_data(vt1_onset_idx, "vt1_onset")
        result["vt1_onset_watts"] = pt["watts"]
        result["vt1_watts"] = pt["watts"]
        result["vt1_ve"] = pt["ve"]
        result["vt1_step"] = pt["step"]
        result["vt1_hr"] = pt.get("hr")
        result["vt1_br"] = pt.get("br")
        result["vt1_vt"] = pt.get("vt")
        result["vt1_onset_time"] = pt.get("time")
        result["analysis_notes"].append(f"VT1_onset (GET/LT1): {pt['watts']}W @ step {pt['step']}")

    # VT1 Steady (or Virtual if no plateau)
    if vt1_steady_idx is not None and result.get("vt1_steady_is_real", False):
        pt = get_point_data(vt1_steady_idx, "vt1_steady")
        result["vt1_steady_watts"] = pt["watts"]
        result["vt1_steady_ve"] = pt["ve"]
        result["vt1_steady_hr"] = pt.get("hr")
        result["vt1_steady_br"] = pt.get("br")
        result["vt1_steady_vt"] = pt.get("vt")
        result["vt1_steady_time"] = pt.get("time")
        result["vt1_steady_is_interpolated"] = False
        result["analysis_notes"].append(
            f"VT1_steady (LT1 steady): {pt['watts']}W @ step {pt['step']} \u2713plateau"
        )
    elif result.get("vt1_onset_watts") and result.get("rcp_onset_watts"):
        # NO REAL PLATEAU - create VIRTUAL interpolated point
        vt1_onset_w = result["vt1_onset_watts"]
        rcp_onset_w = result["rcp_onset_watts"]

        vt1_steady_virtual_w = int((vt1_onset_w + rcp_onset_w) / 2)

        virtual_mask = (df_steps["power"] >= vt1_steady_virtual_w - 15) & (
            df_steps["power"] <= vt1_steady_virtual_w + 15
        )
        if virtual_mask.any():
            closest_idx = (
                df_steps.loc[virtual_mask, "power"].sub(vt1_steady_virtual_w).abs().idxmin()
            )
            pt = get_point_data(closest_idx, "vt1_steady_virtual")
            result["vt1_steady_watts"] = pt["watts"]
            result["vt1_steady_ve"] = pt["ve"]
            result["vt1_steady_hr"] = pt.get("hr")
            result["vt1_steady_br"] = pt.get("br")
            result["vt1_steady_time"] = pt.get("time")
        else:
            result["vt1_steady_watts"] = vt1_steady_virtual_w

        result["vt1_steady_is_interpolated"] = True
        result["analysis_notes"].append(
            f"VT1_steady (interpolated): {result['vt1_steady_watts']}W - no physiological plateau detected"
        )

        result["no_steady_state_interpretation"] = (
            "Pomi\u0119dzy VT1_onset a RCP_onset nie wyst\u0119puje stabilny stan ustalony wentylacji. "
            "Krzywa VE wykazuje ci\u0105g\u0142e przyspieszanie, co wskazuje na: "
            "w\u0105sk\u0105 stref\u0119 przej\u015bciow\u0105, szybkie narastanie buforowania H\u207a, "
            "wczesne wej\u015bcie w domen\u0119 heavy. "
            "Profil typowy dla sportowca o wysokiej pojemno\u015bci tlenowej i stromym przej\u015bciu do kompensacji oddechowej."
        )

    # RCP Onset (VT2)
    if rcp_onset_idx is not None:
        pt = get_point_data(rcp_onset_idx, "rcp_onset")
        result["rcp_onset_watts"] = pt["watts"]
        result["vt2_watts"] = pt["watts"]
        result["vt2_ve"] = pt["ve"]
        result["vt2_step"] = pt["step"]
        result["vt2_hr"] = pt.get("hr")
        result["vt2_br"] = pt.get("br")
        result["rcp_onset_vt"] = pt.get("vt")
        result["rcp_onset_time"] = pt.get("time")
        result["analysis_notes"].append(f"RCP_onset (VT2/LT2): {pt['watts']}W @ step {pt['step']}")

    # RCP Steady
    if rcp_steady_idx is not None:
        pt = get_point_data(rcp_steady_idx, "rcp_steady")
        result["rcp_steady_watts"] = pt["watts"]
        result["rcp_steady_ve"] = pt["ve"]
        result["rcp_steady_hr"] = pt.get("hr")
        result["rcp_steady_br"] = pt.get("br")
        result["rcp_steady_vt"] = pt.get("vt")
        result["rcp_steady_time"] = pt.get("time")
        result["analysis_notes"].append(f"RCP_steady (Full RCP): {pt['watts']}W")

    # =====================================================================
    # 5. BUILD METABOLIC ZONES
    # =====================================================================
    max_power = int(df_steps["power"].max())

    vt1_onset_w = result.get("vt1_onset_watts")
    vt1_steady_w = result.get("vt1_steady_watts")
    rcp_onset_w = result.get("rcp_onset_watts") or result.get("vt2_watts")
    rcp_steady_w = result.get("rcp_steady_watts")
    is_vt1_steady_interpolated = result.get("vt1_steady_is_interpolated", False)

    # Fallback: if VT1_onset missing, use 60th percentile
    if vt1_onset_w is None:
        vt1_onset_w = int(np.percentile(df_steps["power"].values, 60))
        result["vt1_onset_watts"] = vt1_onset_w
        result["vt1_watts"] = vt1_onset_w
        result["analysis_notes"].append(
            f"\u26a0\ufe0f VT1_onset nie wykryty - szacunek 60 percentyl ({vt1_onset_w}W)"
        )

    # Fallback: if RCP_onset missing, use 80th percentile
    if rcp_onset_w is None:
        rcp_onset_w = int(np.percentile(df_steps["power"].values, 80))
        result["rcp_onset_watts"] = rcp_onset_w
        result["vt2_watts"] = rcp_onset_w
        result["analysis_notes"].append(
            f"\u26a0\ufe0f RCP_onset nie wykryty - szacunek 80 percentyl ({rcp_onset_w}W)"
        )

    # CRITICAL: If VT1_steady still None, create virtual interpolation
    if vt1_steady_w is None:
        vt1_steady_w = int((vt1_onset_w + rcp_onset_w) / 2)
        result["vt1_steady_watts"] = vt1_steady_w
        result["vt1_steady_is_interpolated"] = True
        is_vt1_steady_interpolated = True
        result["analysis_notes"].append(
            f"\u26a0\ufe0f VT1_steady interpolowany: {vt1_steady_w}W = (VT1_onset + RCP_onset) / 2"
        )
        result["no_steady_state_interpretation"] = (
            "Nie wykryto stabilnego LT1 steady-state pomi\u0119dzy VT1_onset a RCP_onset. "
            "Wentylacja wykazuje ci\u0105g\u0142e przyspieszanie, co wskazuje na w\u0105sk\u0105 stref\u0119 przej\u015bciow\u0105 "
            "i szybkie wej\u015bcie w domen\u0119 heavy. "
            "Zastosowano interpolowany VT1_steady jako punkt referencyjny dla stref treningowych."
        )

    # RCP_steady fallback
    if rcp_steady_w is None:
        rcp_steady_w = int(rcp_onset_w + (max_power - rcp_onset_w) * 0.4)
        result["rcp_steady_watts"] = rcp_steady_w

    # VALIDATE MONOTONIC BOUNDARIES
    boundaries_valid = vt1_onset_w < vt1_steady_w < rcp_onset_w < rcp_steady_w <= max_power

    if not boundaries_valid:
        result["analysis_notes"].append(
            "\u26a0\ufe0f Korekta granic: wymuszenie monotoniczno\u015bci"
        )

        if vt1_steady_w <= vt1_onset_w:
            vt1_steady_w = vt1_onset_w + int((rcp_onset_w - vt1_onset_w) * 0.4)
            result["vt1_steady_watts"] = vt1_steady_w

        if rcp_onset_w <= vt1_steady_w:
            rcp_onset_w = vt1_steady_w + int((max_power - vt1_steady_w) * 0.5)
            result["rcp_onset_watts"] = rcp_onset_w
            result["vt2_watts"] = rcp_onset_w

        if rcp_steady_w <= rcp_onset_w:
            rcp_steady_w = rcp_onset_w + 15
            result["rcp_steady_watts"] = rcp_steady_w

    result["boundaries_valid"] = vt1_onset_w < vt1_steady_w < rcp_onset_w < rcp_steady_w

    # PERCENTILE VALIDATION
    raw_power = data[data[cols["power"]] >= 100][cols["power"]].values
    power_60th_raw = int(np.percentile(raw_power, 60))
    power_80th_raw = int(np.percentile(raw_power, 80))

    if vt1_onset_w < power_60th_raw:
        result["analysis_notes"].append(
            f"\u26a0\ufe0f VT1_onset ({vt1_onset_w}W) poni\u017cej 60 percentyla ({power_60th_raw}W) - korekta"
        )
        vt1_onset_w = power_60th_raw
        result["vt1_onset_watts"] = vt1_onset_w
        result["vt1_watts"] = vt1_onset_w

    if rcp_onset_w < power_80th_raw:
        result["analysis_notes"].append(
            f"\u26a0\ufe0f RCP_onset ({rcp_onset_w}W) poni\u017cej 80 percentyla ({power_80th_raw}W) - korekta"
        )
        rcp_onset_w = power_80th_raw
        result["rcp_onset_watts"] = rcp_onset_w
        result["vt2_watts"] = rcp_onset_w

    if vt1_steady_w <= vt1_onset_w:
        vt1_steady_w = int((vt1_onset_w + rcp_onset_w) / 2)
        result["vt1_steady_watts"] = vt1_steady_w
        result["vt1_steady_is_interpolated"] = True

    # BUILD 4 ZONES (MANDATORY)
    zones = []

    # Zone 1: Pure Aerobic (< VT1_onset)
    zones.append(
        {
            "zone": 1,
            "name": "Pure Aerobic",
            "power_min": 0,
            "power_max": vt1_onset_w,
            "hr_min": None,
            "hr_max": result.get("vt1_hr"),
            "description": "Full homeostasis, linear VE, no H\u207a buffering",
            "training": "Recovery / Endurance Base",
            "domain": "Moderate",
        }
    )

    # Zone 2: Upper Aerobic (VT1_onset → VT1_steady)
    zone2_name = "Upper Aerobic (Unstable)" if is_vt1_steady_interpolated else "Upper Aerobic"
    zone2_desc = (
        "Strefa niestabilna - brak plateau VE, ci\u0105g\u0142e przyspieszanie"
        if is_vt1_steady_interpolated
        else "Buffering onset, rising VE, stable metabolism"
    )
    zones.append(
        {
            "zone": 2,
            "name": zone2_name,
            "power_min": vt1_onset_w,
            "power_max": vt1_steady_w,
            "hr_min": result.get("vt1_hr"),
            "hr_max": result.get("vt1_steady_hr"),
            "description": zone2_desc,
            "training": "Tempo / Sweet Spot",
            "domain": "Moderate-Heavy Transition",
            "is_interpolated": is_vt1_steady_interpolated,
        }
    )

    # Zone 3: Heavy Domain (VT1_steady → RCP_onset)
    zones.append(
        {
            "zone": 3,
            "name": "Heavy Domain",
            "power_min": vt1_steady_w,
            "power_max": rcp_onset_w,
            "hr_min": result.get("vt1_steady_hr"),
            "hr_max": result.get("vt2_hr"),
            "description": "Building acidosis, VE > VO\u2082, pre-compensation",
            "training": "Threshold / FTP Work",
            "domain": "Heavy",
        }
    )

    # Zone 4: Severe Domain (≥ RCP_onset) with subzones 4a/4b
    zones.append(
        {
            "zone": 4,
            "name": "Severe Domain",
            "power_min": rcp_onset_w,
            "power_max": max_power,
            "hr_min": result.get("vt2_hr"),
            "hr_max": None,
            "description": "Compensatory hyperventilation, no steady-state possible",
            "training": "VO\u2082max / Anaerobic",
            "domain": "Severe",
            "subzones": [
                {
                    "name": "4a - Severe Onset",
                    "power_min": rcp_onset_w,
                    "power_max": rcp_steady_w,
                    "description": "RCP onset \u2192 full RCP transition",
                },
                {
                    "name": "4b - Full Severe",
                    "power_min": rcp_steady_w,
                    "power_max": max_power,
                    "description": "Full respiratory compensation, exhaustion imminent",
                },
            ],
        }
    )

    if len(zones) != 4:
        result["analysis_notes"].append(
            f"\u274c B\u0141\u0104D: Wygenerowano {len(zones)} stref zamiast 4!"
        )
    else:
        result["analysis_notes"].append("\u2713 4 strefy wygenerowane poprawnie")

    result["metabolic_zones"] = zones

    return result


def _aggregate_steps(
    data: pd.DataFrame,
    cols: dict,
    step_range: Optional[Any],
    min_power_watts: Optional[int],
) -> Tuple[pd.DataFrame, List[dict]]:
    """
    Aggregate raw data into steady-state steps.

    Args:
        data: Preprocessed DataFrame with smoothed signals
        cols: Column name mapping
        step_range: Optional detected step ranges
        min_power_watts: Manual override for minimum power

    Returns:
        Tuple of (df_steps, step_data_list)
    """
    step_data = []
    br_col = None
    for col in ["tymebreathrate", "br", "resprate", "breathing_rate", "rf", "rr"]:
        if col in data.columns:
            br_col = col
            break

    if step_range and hasattr(step_range, "steps") and step_range.steps:
        for i, step in enumerate(step_range.steps):
            mask = (data[cols["time"]] >= step.start_time) & (data[cols["time"]] <= step.end_time)
            step_df = data[mask]

            if len(step_df) < 30:
                continue

            step_duration = step.end_time - step.start_time
            ss_start_ratio = max(0.5, 1 - (90 / step_duration)) if step_duration > 90 else 0.5
            cutoff = int(len(step_df) * ss_start_ratio)
            ss_df = step_df.iloc[cutoff:]

            row = {
                "step": i + 1,
                "power": step.avg_power,
                "ve": ss_df["ve_smooth"].mean(),
                "time": step.start_time,
                "duration": step_duration,
            }

            if "vo2_smooth" in ss_df.columns:
                row["vo2"] = ss_df["vo2_smooth"].mean()
            if "vco2_smooth" in ss_df.columns:
                row["vco2"] = ss_df["vco2_smooth"].mean()
            if cols["hr"] in ss_df.columns:
                row["hr"] = ss_df[cols["hr"]].mean()
            if br_col and br_col in ss_df.columns:
                row["br"] = ss_df[br_col].mean()

            step_data.append(row)
    else:
        data["power_bin"] = (data[cols["power"]] // 20) * 20
        raw_steps = []
        for power_bin, group in data.groupby("power_bin"):
            if len(group) < 30:
                continue

            if cols["time"] in group.columns:
                duration = group[cols["time"]].max() - group[cols["time"]].min()
            else:
                duration = len(group)

            if cols["time"] in group.columns:
                step_start_time = group[cols["time"]].min()
                step_end_time = group[cols["time"]].max()

                kinetics_cutoff = step_start_time + 30
                steady_group = group[group[cols["time"]] >= kinetics_cutoff]

                if len(steady_group) > 0:
                    ss_start_time = step_end_time - 60
                    ss_df = steady_group[steady_group[cols["time"]] >= ss_start_time]
                else:
                    ss_df = group.iloc[-60:]
            else:
                if len(group) > 90:
                    ss_df = group.iloc[-60:]
                else:
                    ss_df = group.iloc[30:] if len(group) > 30 else group

            row = {
                "power": power_bin,
                "ve": ss_df["ve_smooth"].mean(),
                "time": group[cols["time"]].iloc[0] if cols["time"] in group.columns else 0,
                "duration": duration,
            }

            if "vo2_smooth" in ss_df.columns:
                row["vo2"] = ss_df["vo2_smooth"].mean()
            if "vco2_smooth" in ss_df.columns:
                row["vco2"] = ss_df["vco2_smooth"].mean()
            if cols["hr"] in ss_df.columns:
                row["hr"] = ss_df[cols["hr"]].mean()
            if br_col and br_col in ss_df.columns:
                row["br"] = ss_df[br_col].mean()

            raw_steps.append(row)

        raw_steps = sorted(raw_steps, key=lambda x: x["power"])

        ramp_start_idx = 0

        if min_power_watts is not None and min_power_watts > 0:
            for i, step in enumerate(raw_steps):
                if step["power"] >= min_power_watts:
                    ramp_start_idx = i
                    break
        else:
            min_step_duration = 120
            power_increment_range = (15, 40)

            for i in range(len(raw_steps) - 2):
                step1 = raw_steps[i]
                step2 = raw_steps[i + 1]
                step3 = raw_steps[i + 2]

                dur_ok = all(s["duration"] >= min_step_duration for s in [step1, step2, step3])

                inc1 = step2["power"] - step1["power"]
                inc2 = step3["power"] - step2["power"]
                inc_ok = (
                    power_increment_range[0] <= inc1 <= power_increment_range[1]
                    and power_increment_range[0] <= inc2 <= power_increment_range[1]
                )

                if dur_ok and inc_ok:
                    ramp_start_idx = i
                    break

        if ramp_start_idx > 0:
            pass

        for i, step in enumerate(raw_steps[ramp_start_idx:]):
            step["step"] = i + 1
            step_data.append(step)

    return pd.DataFrame(step_data).sort_values("power").reset_index(drop=True), step_data


def detect_vt_cpet(
    df: pd.DataFrame,
    step_range: Optional[Any] = None,
    power_column: str = "watts",
    ve_column: str = "tymeventilation",
    time_column: str = "time",
    vo2_column: str = "tymevo2",
    vco2_column: str = "tymevco2",
    hr_column: str = "hr",
    step_duration_sec: int = 180,
    smoothing_window_sec: int = 25,
    min_power_watts: Optional[int] = None,
) -> dict:
    """
    CPET-Grade VT1/VT2 Detection using Ventilatory Equivalents.

    Algorithm:
    1. Preprocessing: Smooth signals with rolling window, remove artifacts
    2. Calculate VE/VO2, VE/VCO2, RER for each step (steady-state)
    3. VT1: Segmented regression on VE/VO2 - find first breakpoint
    4. VT2: Segmented regression on VE/VCO2 - find breakpoint
    5. Physiological validation: VT1 < VT2 < max power
    """
    result = {
        "vt1_watts": None,
        "vt2_watts": None,
        "vt1_hr": None,
        "vt2_hr": None,
        "vt1_ve": None,
        "vt2_ve": None,
        "vt1_br": None,
        "vt2_br": None,
        "vt1_vo2": None,
        "vt2_vo2": None,
        "vt1_step": None,
        "vt2_step": None,
        "vt1_pct_vo2max": None,
        "vt2_pct_vo2max": None,
        "df_steps": None,
        "method": "cpet_segmented_regression",
        "has_gas_exchange": False,
        "analysis_notes": [],
        "validation": {"vt1_lt_vt2": False, "ve_vo2_rises_first": False},
        "ramp_start_step": None,
    }

    data, cols, flags, preprocess_result = _preprocess_ventilation_data(
        df,
        power_column,
        ve_column,
        time_column,
        vo2_column,
        vco2_column,
        hr_column,
        smoothing_window_sec,
    )
    if preprocess_result.get("error"):
        result["error"] = preprocess_result["error"]
        return result

    result["has_gas_exchange"] = preprocess_result["has_gas_exchange"]
    result["analysis_notes"].extend(preprocess_result["analysis_notes"])
    has_vo2 = flags.get("has_vo2", False)
    has_vco2 = flags.get("has_vco2", False)

    df_steps, step_data = _aggregate_steps(data, cols, step_range, min_power_watts)
    result["df_steps"] = df_steps
    if step_data:
        result["ramp_start_step"] = int(step_data[0].get("step", 1))

    if has_vo2 and has_vco2:
        result, vt1_idx = _detect_vt1_cpet(df_steps, True, result)
        result = _detect_vt2_cpet(df_steps, True, vt1_idx, result)
    else:
        result = _run_ve_only_mode(df_steps, data, cols, flags, result)

    df_steps["power"].max()
    if result["vt1_watts"] is None:
        vt1_power = int(np.percentile(df_steps["power"].values, 60))
        result["vt1_watts"] = vt1_power
        result["analysis_notes"].append(f"VT1 not detected - using 60th percentile ({vt1_power}W)")
    if result["vt2_watts"] is None:
        vt2_power = int(np.percentile(df_steps["power"].values, 80))
        result["vt2_watts"] = vt2_power
        result["analysis_notes"].append(f"VT2 not detected - using 80th percentile ({vt2_power}W)")

    if result["vt1_watts"] >= result["vt2_watts"]:
        result["analysis_notes"].append("\u26a0\ufe0f VT1 >= VT2 - adjusted VT2 to VT1 + 15%")
        result["vt2_watts"] = int(result["vt1_watts"] * 1.15)
    result["validation"]["vt1_lt_vt2"] = result["vt1_watts"] < result["vt2_watts"]
    if result["vt1_step"] and result["vt2_step"]:
        result["validation"]["ve_vo2_rises_first"] = result["vt1_step"] < result["vt2_step"]

    return result


def _find_breakpoint_segmented(
    x: np.ndarray, y: np.ndarray, min_segment_size: int = 3
) -> Optional[int]:
    """
    Find optimal breakpoint using piecewise linear regression.

    Tests each potential breakpoint and returns the one minimizing total SSE.

    Args:
        x: Independent variable (power)
        y: Dependent variable (VE/VO2 or VE/VCO2)
        min_segment_size: Minimum points in each segment

    Returns:
        Index of optimal breakpoint, or None if not found
    """
    if len(x) < 2 * min_segment_size:
        return None

    # Remove NaN values
    mask = ~(np.isnan(x) | np.isnan(y))
    x = x[mask]
    y = y[mask]

    if len(x) < 2 * min_segment_size:
        return None

    best_idx = None
    best_sse = np.inf

    for i in range(min_segment_size, len(x) - min_segment_size):
        # Fit two segments
        x1, y1 = x[:i], y[:i]
        x2, y2 = x[i:], y[i:]

        try:
            # Segment 1
            slope1, intercept1, _, _, _ = stats.linregress(x1, y1)
            pred1 = slope1 * x1 + intercept1
            sse1 = np.sum((y1 - pred1) ** 2)

            # Segment 2
            slope2, intercept2, _, _, _ = stats.linregress(x2, y2)
            pred2 = slope2 * x2 + intercept2
            sse2 = np.sum((y2 - pred2) ** 2)

            total_sse = sse1 + sse2

            # We want slope2 > slope1 (increasing trend after breakpoint)
            slope_ratio = slope2 / slope1 if slope1 != 0 else slope2

            if total_sse < best_sse and slope_ratio > 1.1:
                best_sse = total_sse
                best_idx = i

        except Exception:
            continue

    return best_idx


def _calculate_segment_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Calculate slope of a segment using linear regression."""
    if len(x) < 2:
        return 0.0

    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 2:
        return 0.0

    try:
        slope, _, _, _, _ = stats.linregress(x[mask], y[mask])
        return slope
    except Exception:
        return 0.0
