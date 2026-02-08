"""
Ramp Test Report Persistence.

Handles saving of analysis results to filesystem in canonical JSON format.
Per methodology/ramp_test/10_canonical_json_spec.md.
"""

import json
import logging
import os
import uuid
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union
import subprocess
import streamlit as st

from models.results import RampTestResult
from modules.calculations.version import RAMP_METHOD_VERSION

logger = logging.getLogger(__name__)

# canonical version of the JSON structure
CANONICAL_SCHEMA = "ramp_test_result_v1.json"
CANONICAL_VERSION = "1.0.0"
METHOD_VERSION = RAMP_METHOD_VERSION  # Pipeline version

# Index structure
INDEX_COLUMNS = [
    "session_id",
    "test_date",
    "athlete_id",
    "method_version",
    "json_path",
    "pdf_path",
    "source_file",
]


def _get_limiter_interpretation(limiting_factor: str) -> dict:
    """Get interpretation text for limiting factor."""
    interpretations = {
        "Serce": {
            "title": "Ograniczenie Centralne (Serce)",
            "description": "Twoje serce pracuje na maksymalnych obrotach, ale mięśnie mogłyby więcej.",
            "suggestions": [
                "Więcej treningu Z2 (podniesienie SV - objętości wyrzutowej)",
                "Interwały 4×8 min @ 88-94% HRmax",
                "Rozważ pracę nad VO₂max (Hill Repeats)",
            ],
        },
        "Płuca": {
            "title": "Ograniczenie Oddechowe (Płuca)",
            "description": "Wentylacja jest na limicie.",
            "suggestions": [
                "Ćwiczenia oddechowe (pranayama, Wim Hof)",
                "Trening na wysokości (lub maska hipoksyjna)",
                "Sprawdź technikę oddychania podczas wysiłku",
            ],
        },
        "Mięśnie": {
            "title": "Ograniczenie Peryferyjne (Mięśnie)",
            "description": "Mięśnie zużywają cały dostarczany tlen.",
            "suggestions": [
                "Więcej pracy siłowej (squat, deadlift)",
                "Interwały 'over-under' (93-97% / 103-107% FTP)",
                "Sprawdź pozycję na rowerze (okluzja mechaniczna?)",
            ],
        },
    }
    return interpretations.get(limiting_factor, interpretations["Serce"])


def _check_source_file_exists(base_dir: str, source_file: str) -> bool:
    """
    Check if a source file has already been saved in the index.

    Used for deduplication - prevents saving multiple reports for the same CSV file.

    Args:
        base_dir: Base directory containing index.csv
        source_file: Filename to check (e.g., 'ramp_test_2026-01-03.csv')

    Returns:
        True if source_file already exists in index, False otherwise
    """
    import csv

    index_path = Path(base_dir) / "index.csv"

    if not index_path.exists():
        return False

    try:
        with open(index_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_source = row.get("source_file", "")
                if existing_source and existing_source == source_file:
                    return True
    except Exception as e:
        print(f"Warning: Failed to check deduplication: {e}")
        return False

    return False


class NumpyEncoder(json.JSONEncoder):
    """Custom encoder for NumPy data types."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)

        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


def save_ramp_test_report(
    result: RampTestResult,
    output_base_dir: str = "reports/ramp_tests",
    athlete_id: Optional[str] = None,
    notes: Optional[str] = None,
    dev_mode: bool = False,
    session_type=None,
    ramp_confidence: float = 0.0,
    source_file: Optional[str] = None,
    source_df=None,
    manual_overrides: Optional[Dict] = None,
) -> Dict:
    """
    Save Ramp Test result to JSON file.

    GATING: Only saves if session_type is RAMP_TEST and confidence >= threshold.

    Generates path: {output_base_dir}/YYYY/MM/ramp_test_{date}_{uuid}.json
    Enriches result with metadata (UUID, timestamps).

    Safety:
    - By default, writes with 'x' mode (exclusive creation).
    - Checks for file existence to prevent overwrites.
    - 'dev_mode=True' allows overwriting.

    Args:
        result: Analysis result object
        output_base_dir: Base directory for reports
        athlete_id: Optional athlete identifier
        notes: Optional analysis notes
        dev_mode: If True, allows overwriting existing files
        session_type: SessionType enum (must be RAMP_TEST to save)
        ramp_confidence: Classification confidence (must be >= threshold)
        source_file: Original CSV filename for deduplication
        source_df: Optional source DataFrame for chart generation
        manual_overrides: Dict with manual threshold values (VT1/VT2/SmO2/CP) from session_state
            These override auto-detected values in PDF generation

    Returns:
        Dict with path, session_id, or None if gated

    Raises:
        ValueError: If called without RAMP_TEST session type
    """
    # --- HARD TRIGGER CHECK ---
    if not st.session_state.get("report_generation_requested", False):
        print("[GATING] Report generation NOT requested (Hard Trigger). Skipping save.")
        return {"gated": True, "reason": "Report generation NOT requested by user"}

    # --- DEDUPLICATION: Check if source_file already exists in index ---
    if source_file:
        if _check_source_file_exists(output_base_dir, source_file):
            print(f"[Dedup] Source file '{source_file}' already exists in index. Skipping save.")
            return {
                "gated": True,
                "reason": f"Source file '{source_file}' already saved",
                "deduplicated": True,
            }
    # --- GATING: Check SessionType and confidence ---
    from modules.domain import SessionType

    # Allowed types for saving
    ALLOWED_TYPES = [SessionType.RAMP_TEST, SessionType.RAMP_TEST_CONDITIONAL]

    if session_type is not None and session_type not in ALLOWED_TYPES:
        # NOT a ramp test - do not save
        return {"gated": True, "reason": f"SessionType is {session_type}, not a Ramp Test"}

    # Minimum confidence for any ramp save is 0.5 (2/4 criteria)
    if ramp_confidence > 0 and ramp_confidence < 0.5:
        # Confidence too low even for conditional
        return {"gated": True, "reason": f"Confidence {ramp_confidence:.2f} too low to save report"}
    # 1. Prepare data dictionary
    data = result.to_dict()

    # 1.1 Add time series if source_df is available (for regeneration support)
    if source_df is not None and len(source_df) > 0:
        df_ts = source_df.copy()
        df_ts.columns = df_ts.columns.str.lower().str.strip()

        # Mapping: df_column -> json_key
        # We save raw values to keep the JSON canonical,
        # but limited to key metrics to keep it reasonably sized.
        ts_map = {
            "watts": "power_watts",
            "power": "power_watts",
            "hr": "hr_bpm",
            "heartrate": "hr_bpm",
            "heart_rate": "hr_bpm",
            "smo2": "smo2_pct",
            "smo2_pct": "smo2_pct",
            "tymeventilation": "ve_lmin",
            "ve": "ve_lmin",
            "torque": "torque_nm",
            "cadence": "cadence_rpm",
            "cad": "cadence_rpm",
            # Thermal data for regeneration support
            "core_temperature": "core_temp",
            "core_temperature_smooth": "core_temp",
            "hsi": "hsi",
            "heat_strain_index": "hsi",
            "heatstrainindex": "hsi",
        }

        ts_data = {}
        # Always try to get time
        if "time" in df_ts.columns:
            ts_data["time_sec"] = df_ts["time"].tolist()
        elif "seconds" in df_ts.columns:
            ts_data["time_sec"] = df_ts["seconds"].tolist()
        else:
            ts_data["time_sec"] = list(range(len(df_ts)))

        for df_col, json_key in ts_map.items():
            if df_col in df_ts.columns and json_key not in ts_data:
                ts_data[json_key] = df_ts[df_col].fillna(0).tolist()

        data["time_series"] = ts_data

        # 1.2 Run advanced SmO2 analysis if SmO2 data available
        if "smo2_pct" in ts_data or "smo2" in df_ts.columns:
            try:
                from modules.calculations.smo2_advanced import (
                    analyze_smo2_advanced,
                    format_smo2_metrics_for_report,
                )

                # Prepare DataFrame for analysis
                analysis_df = df_ts.copy()
                # Normalize column names
                if "smo2" in analysis_df.columns:
                    analysis_df["SmO2"] = analysis_df["smo2"]
                elif "smo2_pct" in analysis_df.columns:
                    analysis_df["SmO2"] = analysis_df["smo2_pct"]

                if "seconds" not in analysis_df.columns and "time" in analysis_df.columns:
                    analysis_df["seconds"] = range(len(analysis_df))

                smo2_metrics = analyze_smo2_advanced(analysis_df)
                data["smo2_advanced"] = format_smo2_metrics_for_report(smo2_metrics)

            except Exception as e:
                logger.warning(f"[SmO2 Advanced] Analysis failed: {e}")

        # 1.3 Run cardiovascular analysis if HR data available
        if "hr_bpm" in ts_data or "hr" in df_ts.columns:
            try:
                from modules.calculations.cardio_advanced import (
                    analyze_cardiovascular,
                    format_cardio_metrics_for_report,
                )

                analysis_df = df_ts.copy()
                if "hr" not in analysis_df.columns and "heartrate" in analysis_df.columns:
                    analysis_df["hr"] = analysis_df["heartrate"]

                cardio_metrics = analyze_cardiovascular(analysis_df)
                data["cardio_advanced"] = format_cardio_metrics_for_report(cardio_metrics)

            except Exception as e:
                logger.warning(f"[Cardio Advanced] Analysis failed: {e}")

        # 1.4 Run ventilation analysis if VE data available
        if "ve_lmin" in ts_data or any(col in df_ts.columns for col in ["ve", "tymeventilation"]):
            try:
                from modules.calculations.vent_advanced import (
                    analyze_ventilation,
                    format_vent_metrics_for_report,
                )

                analysis_df = df_ts.copy()
                vent_metrics = analyze_ventilation(analysis_df)
                data["vent_advanced"] = format_vent_metrics_for_report(vent_metrics)

            except Exception as e:
                print(f"[Vent Advanced] Analysis failed: {e}")

        # 1.5 Run biomechanical occlusion analysis if torque and SmO2 available
        has_torque = "torque_nm" in ts_data or "torque" in df_ts.columns
        has_smo2 = "smo2_pct" in ts_data or "smo2" in df_ts.columns
        has_power = "power_watts" in ts_data or "watts" in df_ts.columns
        has_cadence = (
            "cadence_rpm" in ts_data or "cadence" in df_ts.columns or "cad" in df_ts.columns
        )

        if (has_torque or (has_power and has_cadence)) and has_smo2:
            try:
                import numpy as np
                from modules.calculations.biomech_occlusion import (
                    analyze_biomech_occlusion,
                    format_occlusion_for_report,
                )
                from modules.calculations.thermoregulation import (
                    analyze_thermoregulation,
                    format_thermo_for_report,
                )

                analysis_df = df_ts.copy()

                # Get torque (calculate from power/cadence if needed)
                if "torque" in analysis_df.columns:
                    torque = analysis_df["torque"].values
                elif "watts" in analysis_df.columns and (
                    "cadence" in analysis_df.columns or "cad" in analysis_df.columns
                ):
                    power = analysis_df["watts"].values
                    cad_col = "cadence" if "cadence" in analysis_df.columns else "cad"
                    cadence = analysis_df[cad_col].values
                    # Torque = Power / Angular Velocity, where ω = 2π * rpm / 60
                    angular_vel = 2 * np.pi * cadence / 60
                    angular_vel[angular_vel < 0.1] = 0.1  # Avoid div by zero
                    torque = power / angular_vel
                else:
                    torque = np.array([])

                # Get SmO2
                smo2_col = "smo2" if "smo2" in analysis_df.columns else "smo2_pct"
                smo2 = (
                    analysis_df[smo2_col].values
                    if smo2_col in analysis_df.columns
                    else np.array([])
                )

                # Get cadence if available
                cadence = None
                if "cadence" in analysis_df.columns:
                    cadence = analysis_df["cadence"].values
                elif "cad" in analysis_df.columns:
                    cadence = analysis_df["cad"].values

                if len(torque) > 0 and len(smo2) > 0:
                    occlusion = analyze_biomech_occlusion(torque, smo2, cadence)
                    data["biomech_occlusion"] = format_occlusion_for_report(occlusion)
                    print(
                        f"[Biomech] Occlusion Index: {occlusion.occlusion_index:.3f} ({occlusion.classification})"
                    )

            except Exception as e:
                print(f"[Biomech Occlusion] Analysis failed: {e}")

            # 1.4.2 Thermoregulation Analysis
            try:
                # Get Core Temp and HSI - use same aliases as thermal.py
                core_col = None
                for c in [
                    "core_temperature_smooth",
                    "core_temperature",
                    "core_temp",
                    "core",
                    "temperature",
                    "temp",
                ]:
                    if c in analysis_df.columns:
                        core_col = c
                        break

                hsi_col = None
                for c in ["hsi", "heat_strain_index"]:
                    if c in analysis_df.columns:
                        hsi_col = c
                        break

                if core_col:
                    core_temp = analysis_df[core_col].values
                    time_seconds = (
                        analysis_df["timestamp"].values
                        if "timestamp" in analysis_df.columns
                        else np.arange(len(core_temp))
                    )
                    hr = analysis_df["hr"].values if "hr" in analysis_df.columns else None
                    power = analysis_df["power"].values if "power" in analysis_df.columns else None
                    hsi = analysis_df[hsi_col].values if hsi_col else None

                    thermo = analyze_thermoregulation(core_temp, time_seconds, hr, power, hsi)
                    data["thermo_analysis"] = format_thermo_for_report(thermo)
                    print(
                        f"[Thermal] Max Core: {thermo.max_core_temp:.1f}C, Delta/10min: {thermo.delta_per_10min:.2f}C"
                    )
            except Exception as e:
                print(f"[Thermoregulation] Analysis failed: {e}")

        # === CARDIAC DRIFT ANALYSIS ===
        try:
            from modules.calculations.cardiac_drift import (
                analyze_cardiac_drift,
                format_drift_for_report,
            )

            # Get power and HR columns
            power_col = next((c for c in ["watts", "power"] if c in analysis_df.columns), None)
            hr_col = next(
                (c for c in ["hr", "heartrate", "heart_rate"] if c in analysis_df.columns), None
            )
            time_col = "timestamp" if "timestamp" in analysis_df.columns else None

            if power_col and hr_col:
                power_arr = analysis_df[power_col].values
                hr_arr = analysis_df[hr_col].values
                time_arr = analysis_df[time_col].values if time_col else np.arange(len(power_arr))

                # Get optional signals
                core_arr = analysis_df[core_col].values if core_col else None
                smo2_arr = analysis_df[smo2_col].values if smo2_col in analysis_df.columns else None
                hsi_arr = analysis_df[hsi_col].values if hsi_col else None

                drift_profile = analyze_cardiac_drift(
                    power_arr, hr_arr, time_arr, core_arr, smo2_arr, hsi_arr
                )

                # Store under thermo_analysis for PDF layout access
                if "thermo_analysis" not in data:
                    data["thermo_analysis"] = {}
                data["thermo_analysis"]["cardiac_drift"] = format_drift_for_report(drift_profile)
                print(
                    f"[Cardiac Drift] EF: {drift_profile.ef_start:.2f} → {drift_profile.ef_end:.2f} ({drift_profile.delta_ef_pct:+.1f}%), Type: {drift_profile.drift_type}"
                )
        except Exception as e:
            print(f"[Cardiac Drift] Analysis failed: {e}")

    # 1.5 Calculate VO2max using same method as UI (pandas rolling)
    # This ensures consistency between UI KPI display and PDF report
    if source_df is not None and len(source_df) > 0:
        try:
            import pandas as pd
            from modules.calculations.metrics import calculate_vo2max

            df_calc = source_df.copy()
            df_calc.columns = df_calc.columns.str.lower().str.strip()

            # Get weight
            weight = data.get("metadata", {}).get("rider_weight", 75) or 75

            # Find power column
            power_col = None
            for col in ["watts", "power"]:
                if col in df_calc.columns:
                    power_col = col
                    break

            if power_col and weight > 0:
                # Use SAME method as UI: rolling(window=300).mean().max()
                mmp_5min = df_calc[power_col].rolling(window=300).mean().max()

                if pd.notna(mmp_5min) and mmp_5min > 0:
                    vo2max_est = calculate_vo2max(mmp_5min, weight)

                    # Store in metrics object with RICH METADATA DEFINITION
                    if "metrics" not in data:
                        data["metrics"] = {}

                    # Structured VO2max with full traceability
                    data["metrics"]["vo2max"] = round(vo2max_est, 2)
                    data["metrics"]["vo2max_metadata"] = {
                        "value": round(vo2max_est, 2),
                        "mmp_5min_watts": round(mmp_5min, 1),
                        "method": "rolling_300s_mean_max",
                        "source": "persistence_pandas",
                        "confidence": 0.70,
                        "formula": "Sitko et al. 2021: 16.61 + 8.87 * (P / kg)",
                        "weight_kg": weight,
                    }

                    print(
                        f"[VO2max] Calculated: {vo2max_est:.1f} ml/kg/min from MMP5={mmp_5min:.1f}W (method: rolling_300s_mean_max)"
                    )

        except Exception as e:
            print(f"[VO2max] Calculation failed: {e}")

    # 1.6 Build CANONICAL PHYSIOLOGY (Single Source of Truth)
    try:
        from modules.calculations.canonical_physio import (
            build_canonical_physiology,
            format_canonical_for_report,
        )

        time_series = data.get("time_series", {})
        canonical = build_canonical_physiology(data, time_series)

        # Store canonical physiology in data
        data["canonical_physiology"] = format_canonical_for_report(canonical)

        # 1.6 Run metabolic engine with CANONICAL values
        from modules.calculations.metabolic_engine import (
            analyze_metabolic_engine,
            format_metabolic_strategy_for_report,
        )

        cp_watts = canonical.cp_watts.value
        vo2max = canonical.vo2max.value
        weight_kg = canonical.weight_kg.value
        w_prime_kj = canonical.w_prime_kj.value or 15
        pmax = canonical.pmax_watts.value

        if cp_watts > 0:
            metabolic_strategy = analyze_metabolic_engine(
                vo2max=vo2max,
                vo2max_source=canonical.vo2max.source,
                vo2max_confidence=canonical.vo2max.confidence,
                cp_watts=cp_watts,
                w_prime_kj=w_prime_kj,
                pmax_watts=pmax,
                weight_kg=weight_kg,
                ftp_watts=canonical.ftp_watts.value,
            )

            formatted = format_metabolic_strategy_for_report(metabolic_strategy)

            # Add alternatives from canonical
            formatted["profile"]["vo2max_alternatives"] = canonical.vo2max.alternatives
            formatted["profile"]["data_quality"] = (
                "good"
                if canonical.vo2max.confidence >= 0.7
                else ("moderate" if canonical.vo2max.confidence >= 0.5 else "low")
            )

            data["metabolic_strategy"] = formatted

    except Exception as e:
        print(f"[Canonical Physio / Metabolic Engine] Analysis failed: {e}")
        import traceback

        traceback.print_exc()

    # 1.7 Limiter Analysis (20min FTP window for radar chart)
    try:
        # Calculate 20min MMP window
        window_sec = 1200  # 20 min
        if "watts" in analysis_df.columns:
            analysis_df["rolling_watts_20m"] = (
                analysis_df["watts"].rolling(window=window_sec, min_periods=window_sec).mean()
            )

            if not analysis_df["rolling_watts_20m"].isna().all():
                peak_idx = analysis_df["rolling_watts_20m"].idxmax()

                if not pd.isna(peak_idx):
                    start_idx = max(0, peak_idx - window_sec + 1)
                    df_peak = analysis_df.iloc[start_idx : peak_idx + 1]

                    # Calculate percentages
                    pct_hr = 0
                    pct_ve = 0
                    pct_smo2_util = 0
                    pct_power = 0

                    # HR%
                    if "hr" in analysis_df.columns:
                        peak_hr_avg = df_peak["hr"].mean()
                        max_hr = analysis_df["hr"].max()
                        pct_hr = (peak_hr_avg / max_hr * 100) if max_hr > 0 else 0

                    # VE%
                    ve_col = next(
                        (
                            c
                            for c in ["tymeventilation", "ve", "ventilation"]
                            if c in analysis_df.columns
                        ),
                        None,
                    )
                    if ve_col:
                        peak_ve_avg = df_peak[ve_col].mean()
                        max_ve = analysis_df[ve_col].max() * 1.1  # Estimate VEmax
                        pct_ve = (peak_ve_avg / max_ve * 100) if max_ve > 0 else 0

                    # SmO2 utilization (desaturation)
                    if "smo2" in analysis_df.columns:
                        peak_smo2_avg = df_peak["smo2"].mean()
                        pct_smo2_util = 100 - peak_smo2_avg

                    # Power%
                    peak_w_avg = df_peak["watts"].mean()
                    cp_watts = (
                        data.get("canonical_physiology", {}).get("summary", {}).get("cp_watts", 0)
                        or peak_w_avg
                    )
                    pct_power = (peak_w_avg / cp_watts * 100) if cp_watts > 0 else 0

                    # Determine limiting factor
                    limiting_factor = "Serce"
                    if pct_ve >= max(pct_hr, pct_smo2_util):
                        limiting_factor = "Płuca"
                    elif pct_smo2_util >= pct_hr:
                        limiting_factor = "Mięśnie"

                    data["limiter_analysis"] = {
                        "window": "20 min (FTP)",
                        "peak_power": round(peak_w_avg, 0),
                        "pct_hr": round(pct_hr, 1),
                        "pct_ve": round(pct_ve, 1),
                        "pct_smo2_util": round(pct_smo2_util, 1),
                        "pct_power": round(pct_power, 1),
                        "limiting_factor": limiting_factor,
                        "interpretation": _get_limiter_interpretation(limiting_factor),
                    }
    except Exception as e:
        print(f"[Limiter Analysis] Calculation failed: {e}")

    # 2. Enrich metadata
    now = datetime.now()
    analysis_timestamp = now.isoformat()
    session_id = str(uuid.uuid4())

    # Parse test date for directory structure
    try:
        test_date = datetime.strptime(result.test_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        # Fallback if date missing or invalid format
        test_date = now.date()

    # Update/Enrich metadata section
    if "metadata" not in data:
        data["metadata"] = {}

    data["metadata"].update(
        {
            "test_date": result.test_date or test_date.isoformat(),
            "analysis_timestamp": analysis_timestamp,
            "method_version": METHOD_VERSION,
            "session_id": session_id,
            "athlete_id": athlete_id,
            "notes": notes,
            "analyzer": "Tri_Dashboard/ramp_pipeline",
        }
    )

    # 3. Add canonical header fields
    final_json = {"$schema": CANONICAL_SCHEMA, "version": CANONICAL_VERSION, **data}

    # 3.1 Add data_policy for provenance tracking
    if manual_overrides:
        from modules.canonical_values import resolve_all_thresholds, build_data_policy

        # Extract auto values from result data
        auto_values = {}
        thresholds = data.get("thresholds", {})
        if thresholds:
            vt1 = thresholds.get("vt1", {})
            vt2 = thresholds.get("vt2", {})
            auto_values["vt1"] = vt1.get("midpoint_watts") if isinstance(vt1, dict) else None
            auto_values["vt2"] = vt2.get("midpoint_watts") if isinstance(vt2, dict) else None

        smo2 = data.get("smo2_thresholds", {})
        if smo2:
            auto_values["smo2_lt1"] = smo2.get("lt1_watts")
            auto_values["smo2_lt2"] = smo2.get("lt2_watts")

        # Resolve all thresholds through global priority policy
        resolved = resolve_all_thresholds(manual_overrides, auto_values)

        # Build and add data_policy
        final_json["data_policy"] = build_data_policy(resolved)

        # Log resolution for debugging
        from modules.canonical_values import log_resolution

        for line in log_resolution(resolved):
            print(f"[DataPolicy] {line}")

    # 4. Generate path
    year_str = test_date.strftime("%Y")
    month_str = test_date.strftime("%m")

    # Directory: reports/ramp_tests/2026/01/
    save_dir = Path(output_base_dir) / year_str / month_str
    save_dir.mkdir(parents=True, exist_ok=True)

    # Filename: ramp_test_2026-01-02_abc123.json
    # Use short UUID (first 8 chars) for readability
    short_uuid = session_id[:8]
    filename = f"ramp_test_{test_date.isoformat()}_{short_uuid}.json"

    file_path = save_dir / filename

    # 5. Save file (Immutable by default)
    mode = "w" if dev_mode else "x"

    try:
        with open(file_path, mode, encoding="utf-8") as f:
            json.dump(final_json, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
        print(f"Ramp Test JSON saved: {session_id}")
    except FileExistsError:
        # Should be rare given UUID, but protects against collision/logic errors
        if not dev_mode:
            # Regenerate UUID and try one more time or raise
            # Simple strategy: Raise to indicate safety mechanism worked
            raise FileExistsError(f"Ramp Test Report already exists and immutable: {file_path}")

    # 6. Check validity for PDF generation
    validity_section = final_json.get("test_validity", {})
    test_validity_status = validity_section.get("status", "unknown")

    # Block PDF ONLY if test_validity_status == "invalid"
    should_generate_pdf = test_validity_status != "invalid"

    # Determine if conditional (for PDF warning)
    is_conditional = session_type == SessionType.RAMP_TEST_CONDITIONAL

    pdf_path = None

    # 7. Auto-generate PDF if valid
    if should_generate_pdf:
        try:
            pdf_path = _auto_generate_pdf(
                str(file_path.absolute()),
                final_json,
                is_conditional,
                source_df=source_df,
                manual_overrides=manual_overrides,
            )
        except Exception as e:
            # PDF failure does NOT affect JSON or index
            print(f"Warning: PDF generation failed for {session_id}: {e}")

    # 8. Update Index (CSV)
    try:
        _update_index(
            output_base_dir,
            final_json["metadata"],
            str(file_path.absolute()),
            pdf_path,
            source_file,
        )
        print(f"Ramp Test indexed: {session_id}")
    except Exception as e:
        print(f"Warning: Failed to update report index: {e}")

    return {
        "path": str(file_path.absolute()),
        "pdf_path": pdf_path,
        "session_id": session_id,
        "uuid": session_id,  # alias
    }


def _auto_generate_pdf(
    json_path: str,
    report_data: Dict,
    is_conditional: bool = False,
    source_df=None,
    manual_overrides=None,
) -> Optional[str]:
    """
    Auto-generate PDF from JSON report.

    Called automatically after save_ramp_test_report.
    PDF is saved next to JSON with same basename.

    Args:
        json_path: Absolute path to saved JSON
        report_data: The report data dictionary
        is_conditional: If True, PDF will include conditional warning
        source_df: Optional DataFrame with raw data for chart generation
        manual_overrides: Dict of manual threshold values (VT1/VT2/SmO2/CP) from session_state

    Returns:
        PDF path if successful, None otherwise
    """
    # --- HARD TRIGGER CHECK ---
    if not st.session_state.get("report_generation_requested", False):
        print("[PDF GATING] PDF generation NOT requested (Hard Trigger). Aborting.")
        return None

    from .pdf import generate_ramp_pdf, PDFConfig
    from .figures import generate_all_ramp_figures
    import tempfile

    json_path = Path(json_path)
    pdf_path = json_path.with_suffix(".pdf")

    # Generate figures in temp directory
    temp_dir = tempfile.mkdtemp()
    method_version = report_data.get("metadata", {}).get("method_version", "1.0.0")
    fig_config = {"method_version": method_version}

    # Pass source_df for chart generation
    # If source_df is missing (regeneration from index), charts will try to use report_data['time_series']
    figure_paths = generate_all_ramp_figures(report_data, temp_dir, fig_config, source_df=source_df)

    # Configure PDF with conditional flag
    pdf_config = PDFConfig(is_conditional=is_conditional)

    # Generate PDF with manual overrides
    generate_ramp_pdf(
        report_data, figure_paths, str(pdf_path), pdf_config, manual_overrides=manual_overrides
    )

    # Generate DOCX (optional)
    try:
        from .docx_builder import build_ramp_docx

        docx_path = pdf_path.with_suffix(".docx")
        build_ramp_docx(report_data, figure_paths, str(docx_path))
        print(f"Ramp Test DOCX generated: {docx_path}")
    except Exception as e:
        print(f"DOCX generation failed: {e}")

    print(f"Ramp Test PDF generated: {pdf_path}")

    # --- RESET HARD TRIGGER ---
    st.session_state["report_generation_requested"] = False

    return str(pdf_path.absolute())


def _update_index(
    base_dir: str,
    metadata: Dict,
    file_path: str,
    pdf_path: Optional[str] = None,
    source_file: Optional[str] = None,
):
    """
    Update CSV index with new test record.

    Columns: session_id, test_date, athlete_id, method_version, json_path, pdf_path, source_file
    """
    import csv

    index_path = Path(base_dir) / "index.csv"
    file_exists = index_path.exists()

    row = {
        "session_id": metadata.get("session_id", ""),
        "test_date": metadata.get("test_date", ""),
        "athlete_id": metadata.get("athlete_id") or "anonymous",
        "method_version": metadata.get("method_version", ""),
        "json_path": file_path,
        "pdf_path": pdf_path or "",
        "source_file": source_file or "",
    }

    # Validation: Ensure all columns are present and no empty critical fields
    if len(row) != len(INDEX_COLUMNS):
        print(
            f"Error: Invalid record length for index. Expected {len(INDEX_COLUMNS)}, got {len(row)}."
        )
        return

    if not row["session_id"] or not row["json_path"]:
        print(
            f"Error: Missing critical data for index (session_id or json_path). Record not saved."
        )
        return

    try:
        with open(index_path, "a", newline="", encoding="utf-8") as f:
            # quote_all ensures paths (and other strings) are in quotes as requested
            writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS, quoting=csv.QUOTE_ALL)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"Ramp Test indexed: {row['session_id']}")
    except Exception as e:
        print(f"Error: Failed to write to index at {index_path}: {e}")


def update_index_pdf_path(base_dir: str, session_id: str, pdf_path: str):
    """
    Update existing index row with PDF path.

    PDF can be regenerated, so this updates an existing row.
    JSON is never modified (immutable).

    Args:
        base_dir: Base directory containing index.csv
        session_id: Session ID to update
        pdf_path: Path to generated PDF
    """
    import csv

    index_path = Path(base_dir) / "index.csv"

    if not index_path.exists():
        print(f"Warning: Index not found at {index_path}")
        return

    # Read all rows
    rows = []

    with open(index_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("session_id") == session_id:
                row["pdf_path"] = pdf_path

            # Basic validation for existing row
            if all(k in row for k in INDEX_COLUMNS):
                rows.append(row)
            else:
                print(f"Warning: Skipping malformed index row for session {row.get('session_id')}")

    # Write back with updated row
    try:
        with open(index_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Updated PDF path for session {session_id}")
    except Exception as e:
        print(f"Error: Failed to update index at {index_path}: {e}")


def generate_and_save_pdf(
    json_path: Union[str, Path],
    output_base_dir: str = "reports/ramp_tests",
    is_conditional: bool = False,
    manual_overrides: Optional[Dict] = None,
) -> Optional[str]:
    """
    Generate PDF from existing JSON report and save alongside it.

    - PDF is saved next to the JSON with .pdf extension
    - PDF can be regenerated (overwritten)
    - JSON is NEVER modified (immutable)
    - Index is updated with PDF path

    Args:
        json_path: Path to the canonical JSON report
        output_base_dir: Base directory for index update
        is_conditional: Whether to include conditional warning
        manual_overrides: Dict of manual threshold values from session_state to override saved values

    Returns:
        Path to generated PDF or None on failure
    """
    from .pdf import generate_ramp_pdf, PDFConfig
    from .figures import generate_all_ramp_figures
    import tempfile

    json_path = Path(json_path)

    if not json_path.exists():
        print(f"Error: JSON report not found: {json_path}")
        return None

    # Load JSON report
    report_data = load_ramp_test_report(json_path)

    # Generate figure paths
    # NOTE: Charts will show "Brak danych" since source_df is not available
    # during regeneration from JSON. Full charts are only generated during
    # initial save when DataFrame is available.
    temp_dir = tempfile.mkdtemp()
    fig_config = {"method_version": report_data.get("metadata", {}).get("method_version", "1.0.0")}
    figure_paths = generate_all_ramp_figures(
        report_data, temp_dir, fig_config, source_df=None, manual_overrides=manual_overrides
    )

    # Generate PDF path (same name as JSON but .pdf)
    pdf_path = json_path.with_suffix(".pdf")

    # Configure PDF
    pdf_config = PDFConfig(is_conditional=is_conditional)

    # Generate PDF (can overwrite existing) - with manual overrides if provided
    generate_ramp_pdf(
        report_data, figure_paths, str(pdf_path), pdf_config, manual_overrides=manual_overrides
    )

    # Generate DOCX (optional)
    try:
        from .docx_builder import build_ramp_docx

        docx_path = pdf_path.with_suffix(".docx")
        build_ramp_docx(report_data, figure_paths, str(docx_path))
        print(f"DOCX generated: {docx_path}")
    except Exception as e:
        print(f"DOCX failure: {e}")

    # Update index with PDF path
    session_id = report_data.get("metadata", {}).get("session_id", "")
    if session_id:
        update_index_pdf_path(output_base_dir, session_id, str(pdf_path.absolute()))

    print(f"PDF generated: {pdf_path}")

    return str(pdf_path.absolute())


def generate_ramp_test_pdf(
    session_id: str,
    output_base_dir: str = "reports/ramp_tests",
    manual_overrides: Optional[Dict] = None,
) -> Optional[str]:
    """
    Ręczne generowanie raportu PDF na podstawie session_id.

    1. Znajduje json_path w index.csv
    2. Wczytuje JSON
    3. Generuje PDF (z opcjonalnymi wartościami manualnymi) i aktualizuje index

    Args:
        session_id: ID sesji raportu
        output_base_dir: Katalog bazowy raportów
        manual_overrides: Dict z manualnymi wartościami progów (VT1/VT2/SmO2/CP) - nadpisują zapisane
    """
    import csv

    print(f"Generating PDF for session_id: {session_id}")
    if manual_overrides:
        print(f"  With manual overrides: {list(manual_overrides.keys())}")

    index_path = Path(output_base_dir) / "index.csv"
    if not index_path.exists():
        print(f"Error: Index not found at {index_path}")
        return None

    json_path = None
    with open(index_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("session_id") == session_id:
                json_path = row.get("json_path")
                break

    if not json_path:
        print(f"Error: JSON path not found in index for session {session_id}")
        return None

    # Re-use existing logic for generation - NOW with manual_overrides
    pdf_path_str = generate_and_save_pdf(
        json_path, output_base_dir, manual_overrides=manual_overrides
    )

    if pdf_path_str:
        print(f"PDF saved to: {pdf_path_str}")
        print(f"index.csv updated for session_id: {session_id}")
        return pdf_path_str

    return None


def load_ramp_test_report(file_path: Union[str, Path]) -> Dict:
    """
    Load a Ramp Test report from JSON.

    Args:
        file_path: Path to JSON file

    Returns:
        Dictionary with report data
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_git_tracking(directory: str = "reports/ramp_tests"):
    """
    Check if a directory contains any files tracked by git.
    Display a warning in Streamlit if tracked files are found.

    This is a safeguard against accidental committing of sensitive subject data.
    """
    # Only check in local development environment (could verify env vars but simple check is enough)
    if not os.path.exists(".git"):
        return

    try:
        # Check if any files in the directory are tracked
        # git ls-files returns output if files are tracked
        result = subprocess.run(
            ["git", "ls-files", directory], capture_output=True, text=True, check=False
        )

        if result.returncode == 0 and result.stdout.strip():
            # Tracked files found!
            st.error(
                f"🚨 **SECURITY WARNING**: Folder `{directory}` zawiera pliki śledzone przez Git!\n\n"
                "Dane badanych mogą trafić do repozytorium. "
                "Usuń je z historii gita:\n"
                "```bash\n"
                f"git rm --cached -r {directory}\n"
                "```"
            )

    except Exception:
        # Git command failed or not available - ignore
        pass
