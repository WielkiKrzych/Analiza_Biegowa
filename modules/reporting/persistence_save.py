"""
Persistence save — main save_ramp_test_report function.

Handles saving Ramp Test results to JSON, including enrichment with
advanced analysis, canonical physiology, and index updates.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from models.results import RampTestResult

from .persistence_constants import CANONICAL_SCHEMA, CANONICAL_VERSION, METHOD_VERSION
from .persistence_helpers import (
    NumpyEncoder,
    _check_source_file_exists,
    _get_limiter_interpretation,
)
from .persistence_pdf import _auto_generate_pdf, _update_index

logger = logging.getLogger(__name__)

_TS_COLUMN_MAP: Dict[str, str] = {
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
    "core_temperature": "core_temp",
    "core_temperature_smooth": "core_temp",
    "hsi": "hsi",
    "heat_strain_index": "hsi",
    "heatstrainindex": "hsi",
}


def _check_gating(
    source_file: Optional[str],
    output_base_dir: str,
    session_type: Any,
    ramp_confidence: float,
) -> Optional[Dict]:
    """Return a gated-response dict, or *None* if saving should proceed."""
    if not st.session_state.get("report_generation_requested", False):
        logger.info("[GATING] Report generation NOT requested (Hard Trigger). Skipping save.")
        return {"gated": True, "reason": "Report generation NOT requested by user"}

    if source_file:
        if _check_source_file_exists(output_base_dir, source_file):
            logger.info(
                f"[Dedup] Source file '{source_file}' already exists in index. Skipping save."
            )
            return {
                "gated": True,
                "reason": f"Source file '{source_file}' already saved",
                "deduplicated": True,
            }

    from modules.domain import SessionType

    allowed_types = [SessionType.RAMP_TEST, SessionType.RAMP_TEST_CONDITIONAL]

    if session_type is not None and session_type not in allowed_types:
        return {"gated": True, "reason": f"SessionType is {session_type}, not a Ramp Test"}

    if ramp_confidence > 0 and ramp_confidence < 0.5:
        return {"gated": True, "reason": f"Confidence {ramp_confidence:.2f} too low to save report"}

    return None


def _extract_time_series_data(df_ts: Any) -> Dict:
    """Build a normalised time-series dict from a lowercase-stripped DataFrame."""
    ts_data: Dict[str, Any] = {}

    if "time" in df_ts.columns:
        ts_data["time_sec"] = df_ts["time"].tolist()
    elif "seconds" in df_ts.columns:
        ts_data["time_sec"] = df_ts["seconds"].tolist()
    else:
        ts_data["time_sec"] = list(range(len(df_ts)))

    for df_col, json_key in _TS_COLUMN_MAP.items():
        if df_col in df_ts.columns and json_key not in ts_data:
            ts_data[json_key] = df_ts[df_col].fillna(0).tolist()

    return ts_data


def _run_smo2_analysis(data: Dict, df_ts: Any, ts_data: Dict) -> None:
    """Run advanced SmO2 analysis when SmO2 data is available."""
    if "smo2_pct" not in ts_data and "smo2" not in df_ts.columns:
        return
    try:
        from modules.calculations.smo2_advanced import (
            analyze_smo2_advanced,
            format_smo2_metrics_for_report,
        )

        analysis_df = df_ts.copy()
        if "smo2" in analysis_df.columns:
            analysis_df["SmO2"] = analysis_df["smo2"]
        elif "smo2_pct" in analysis_df.columns:
            analysis_df["SmO2"] = analysis_df["smo2_pct"]

        if "seconds" not in analysis_df.columns and "time" in analysis_df.columns:
            analysis_df["seconds"] = range(len(analysis_df))

        smo2_metrics = analyze_smo2_advanced(analysis_df)
        data["smo2_advanced"] = format_smo2_metrics_for_report(smo2_metrics)

    except (ValueError, KeyError, ImportError) as e:  # noqa: BLE001
        logger.warning(f"[SmO2 Advanced] Analysis failed: {e}")


def _run_cardio_analysis(data: Dict, df_ts: Any, ts_data: Dict) -> None:
    """Run cardiovascular analysis when HR data is available."""
    if "hr_bpm" not in ts_data and "hr" not in df_ts.columns:
        return
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

    except (ValueError, KeyError, ImportError) as e:  # noqa: BLE001
        logger.warning(f"[Cardio Advanced] Analysis failed: {e}")


def _run_vent_analysis(data: Dict, df_ts: Any, ts_data: Dict) -> None:
    """Run ventilation analysis when VE data is available."""
    has_ve = "ve_lmin" in ts_data or any(col in df_ts.columns for col in ("ve", "tymeventilation"))
    if not has_ve:
        return
    try:
        from modules.calculations.vent_advanced import (
            analyze_ventilation,
            format_vent_metrics_for_report,
        )

        analysis_df = df_ts.copy()
        vent_metrics = analyze_ventilation(analysis_df)
        data["vent_advanced"] = format_vent_metrics_for_report(vent_metrics)

    except (ValueError, KeyError, ImportError) as e:  # noqa: BLE001
        logger.info(f"[Vent Advanced] Analysis failed: {e}")


def _run_biomech_occlusion(data: Dict, df_ts: Any, ctx: Dict) -> None:
    """Run biomechanical occlusion analysis. Populates ctx with shared state."""
    try:
        import numpy as np

        from modules.calculations.biomech_occlusion import (
            analyze_biomech_occlusion,
            format_occlusion_for_report,
        )

        analysis_df = df_ts.copy()
        ctx["analysis_df"] = analysis_df

        if "torque" in analysis_df.columns:
            torque = analysis_df["torque"].values
        elif "watts" in analysis_df.columns and (
            "cadence" in analysis_df.columns or "cad" in analysis_df.columns
        ):
            power = analysis_df["watts"].values
            cad_col = "cadence" if "cadence" in analysis_df.columns else "cad"
            cadence = analysis_df[cad_col].values
            angular_vel = 2 * np.pi * cadence / 60
            angular_vel[angular_vel < 0.1] = 0.1
            torque = power / angular_vel
        else:
            torque = np.array([])

        smo2_col = "smo2" if "smo2" in analysis_df.columns else "smo2_pct"
        ctx["smo2_col"] = smo2_col
        smo2 = analysis_df[smo2_col].values if smo2_col in analysis_df.columns else np.array([])

        cadence = None
        if "cadence" in analysis_df.columns:
            cadence = analysis_df["cadence"].values
        elif "cad" in analysis_df.columns:
            cadence = analysis_df["cad"].values

        if len(torque) > 0 and len(smo2) > 0:
            occlusion = analyze_biomech_occlusion(torque, smo2, cadence)
            data["biomech_occlusion"] = format_occlusion_for_report(occlusion)
            logger.info(
                f"[Biomech] Occlusion Index: {occlusion.occlusion_index:.3f} ({occlusion.classification})"
            )

    except (ValueError, KeyError, ImportError, IndexError) as e:  # noqa: BLE001
        logger.warning(f"[Biomech Occlusion] Analysis failed: {e}")


def _run_thermoregulation(data: Dict, df_ts: Any, ctx: Dict) -> None:
    """Run thermoregulation analysis, reading analysis_df from ctx."""
    try:
        import numpy as np

        from modules.calculations.thermoregulation import (
            analyze_thermoregulation,
            format_thermo_for_report,
        )

        analysis_df = ctx.get("analysis_df", df_ts.copy())

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
        ctx["core_col"] = core_col

        hsi_col = None
        for c in ["hsi", "heat_strain_index"]:
            if c in analysis_df.columns:
                hsi_col = c
                break
        ctx["hsi_col"] = hsi_col

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
            logger.info(
                f"[Thermal] Max Core: {thermo.max_core_temp:.1f}C, Delta/10min: {thermo.delta_per_10min:.2f}C"
            )
    except (ValueError, KeyError, ImportError) as e:  # noqa: BLE001
        logger.warning(f"[Thermoregulation] Analysis failed: {e}")


def _run_cardiac_drift(data: Dict, df_ts: Any, ctx: Dict) -> None:
    """Run cardiac drift analysis using shared *ctx* from biomech+thermo helpers."""
    try:
        import numpy as np

        from modules.calculations.cardiac_drift import (
            analyze_cardiac_drift,
            format_drift_for_report,
        )

        analysis_df = ctx.get("analysis_df")
        if analysis_df is None:
            return

        core_col = ctx.get("core_col")
        smo2_col = ctx.get("smo2_col")
        hsi_col = ctx.get("hsi_col")

        power_col = next((c for c in ["watts", "power"] if c in analysis_df.columns), None)
        hr_col = next(
            (c for c in ["hr", "heartrate", "heart_rate"] if c in analysis_df.columns), None
        )
        time_col = "timestamp" if "timestamp" in analysis_df.columns else None

        if power_col and hr_col:
            power_arr = analysis_df[power_col].values
            hr_arr = analysis_df[hr_col].values
            time_arr = analysis_df[time_col].values if time_col else np.arange(len(power_arr))

            core_arr = analysis_df[core_col].values if core_col else None
            smo2_arr = (
                analysis_df[smo2_col].values
                if smo2_col and smo2_col in analysis_df.columns
                else None
            )
            hsi_arr = analysis_df[hsi_col].values if hsi_col else None

            drift_profile = analyze_cardiac_drift(
                power_arr, hr_arr, time_arr, core_arr, smo2_arr, hsi_arr
            )

            if "thermo_analysis" not in data:
                data["thermo_analysis"] = {}
            data["thermo_analysis"]["cardiac_drift"] = format_drift_for_report(drift_profile)
            logger.info(
                f"[Cardiac Drift] EF: {drift_profile.ef_start:.2f} → {drift_profile.ef_end:.2f} ({drift_profile.delta_ef_pct:+.1f}%), Type: {drift_profile.drift_type}"
            )
    except (ValueError, KeyError, ImportError) as e:  # noqa: BLE001
        logger.warning(f"[Cardiac Drift] Analysis failed: {e}")


def _run_biomech_thermo_drift(data: Dict, df_ts: Any, ts_data: Dict) -> None:
    """Orchestrate biomech occlusion, thermoregulation, and cardiac drift analyses."""
    has_torque = "torque_nm" in ts_data or "torque" in df_ts.columns
    has_smo2 = "smo2_pct" in ts_data or "smo2" in df_ts.columns
    has_power = "power_watts" in ts_data or "watts" in df_ts.columns
    has_cadence = "cadence_rpm" in ts_data or "cadence" in df_ts.columns or "cad" in df_ts.columns

    ctx: Dict[str, Any] = {}

    if (has_torque or (has_power and has_cadence)) and has_smo2:
        _run_biomech_occlusion(data, df_ts, ctx)
        _run_thermoregulation(data, df_ts, ctx)

    _run_cardiac_drift(data, df_ts, ctx)


def _enrich_with_source_data(data: Dict, source_df: Any) -> None:
    """Extract time series and run all advanced analyses from *source_df*."""
    df_ts = source_df.copy()
    df_ts.columns = df_ts.columns.str.lower().str.strip()

    ts_data = _extract_time_series_data(df_ts)
    data["time_series"] = ts_data

    _run_smo2_analysis(data, df_ts, ts_data)
    _run_cardio_analysis(data, df_ts, ts_data)
    _run_vent_analysis(data, df_ts, ts_data)
    _run_biomech_thermo_drift(data, df_ts, ts_data)


def _calculate_vo2max(data: Dict, source_df: Any) -> None:
    """Calculate VO2max using pandas rolling (same method as UI)."""
    try:
        import pandas as pd

        from modules.calculations.metrics import calculate_vo2max

        df_calc = source_df.copy()
        df_calc.columns = df_calc.columns.str.lower().str.strip()

        weight = data.get("metadata", {}).get("rider_weight", 75) or 75

        power_col = None
        for col in ["watts", "power"]:
            if col in df_calc.columns:
                power_col = col
                break

        if power_col and weight > 0:
            mmp_5min = df_calc[power_col].rolling(window=300).mean().max()

            if pd.notna(mmp_5min) and mmp_5min > 0:
                vo2max_est = calculate_vo2max(mmp_5min, weight)

                if "metrics" not in data:
                    data["metrics"] = {}

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

                logger.info(
                    f"[VO2max] Calculated: {vo2max_est:.1f} ml/kg/min from MMP5={mmp_5min:.1f}W (method: rolling_300s_mean_max)"
                )

    except (ValueError, KeyError, ImportError) as e:  # noqa: BLE001
        logger.warning(f"[VO2max] Calculation failed: {e}")


def _build_canonical_and_metabolic(data: Dict) -> None:
    """Build canonical physiology and run metabolic engine."""
    try:
        from modules.calculations.canonical_physio import (
            build_canonical_physiology,
            format_canonical_for_report,
        )

        time_series = data.get("time_series", {})
        canonical = build_canonical_physiology(data, time_series)
        data["canonical_physiology"] = format_canonical_for_report(canonical)

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
            formatted["profile"]["vo2max_alternatives"] = canonical.vo2max.alternatives
            formatted["profile"]["data_quality"] = (
                "good"
                if canonical.vo2max.confidence >= 0.7
                else ("moderate" if canonical.vo2max.confidence >= 0.5 else "low")
            )
            data["metabolic_strategy"] = formatted

    except (ValueError, KeyError, ImportError) as e:  # noqa: BLE001
        logger.info(f"[Canonical Physio / Metabolic Engine] Analysis failed: {e}")
        import traceback

        traceback.print_exc()


def _compute_limiter_from_ftp_window(analysis_df: Any, data: Dict, pd: Any) -> Optional[Dict]:
    """Compute 20-min FTP-window limiter analysis; returns result dict or *None*."""
    window_sec = 1200
    if "watts" not in analysis_df.columns:
        return None

    analysis_df["rolling_watts_20m"] = (
        analysis_df["watts"].rolling(window=window_sec, min_periods=window_sec).mean()
    )

    if analysis_df["rolling_watts_20m"].isna().all():
        return None

    peak_idx = analysis_df["rolling_watts_20m"].idxmax()
    if pd.isna(peak_idx):
        return None

    start_idx = max(0, peak_idx - window_sec + 1)
    df_peak = analysis_df.iloc[start_idx : peak_idx + 1]

    pct_hr = 0.0
    pct_ve = 0.0
    pct_smo2_util = 0.0

    if "hr" in analysis_df.columns:
        peak_hr_avg = df_peak["hr"].mean()
        max_hr = analysis_df["hr"].max()
        pct_hr = (peak_hr_avg / max_hr * 100) if max_hr > 0 else 0

    ve_col = next(
        (c for c in ["tymeventilation", "ve", "ventilation"] if c in analysis_df.columns),
        None,
    )
    if ve_col:
        peak_ve_avg = df_peak[ve_col].mean()
        max_ve = analysis_df[ve_col].max() * 1.1
        pct_ve = (peak_ve_avg / max_ve * 100) if max_ve > 0 else 0

    if "smo2" in analysis_df.columns:
        peak_smo2_avg = df_peak["smo2"].mean()
        pct_smo2_util = 100 - peak_smo2_avg

    peak_w_avg = df_peak["watts"].mean()
    cp_watts = (
        data.get("canonical_physiology", {}).get("summary", {}).get("cp_watts", 0) or peak_w_avg
    )
    pct_power = (peak_w_avg / cp_watts * 100) if cp_watts > 0 else 0

    limiting_factor = "Serce"

    return {
        "window": "20 min (FTP)",
        "peak_power": round(peak_w_avg, 0),
        "pct_hr": round(pct_hr, 1),
        "pct_ve": round(pct_ve, 1),
        "pct_smo2_util": round(pct_smo2_util, 1),
        "pct_power": round(pct_power, 1),
        "limiting_factor": limiting_factor,
        "interpretation": _get_limiter_interpretation(limiting_factor),
    }


def _run_limiter_analysis(data: Dict, source_df: Any) -> None:
    """Run limiter analysis when source data is available."""
    if source_df is None or len(source_df) == 0:
        return
    try:
        import pandas as pd

        analysis_df = source_df.copy()
        analysis_df.columns = analysis_df.columns.str.lower().str.strip()

        result = _compute_limiter_from_ftp_window(analysis_df, data, pd)
        if result is not None:
            data["limiter_analysis"] = result
    except (ValueError, KeyError, IndexError) as e:  # noqa: BLE001
        logger.info(f"[Limiter Analysis] Calculation failed: {e}")


def _parse_test_date(test_date_str: Optional[str], now: datetime) -> Any:
    """Parse test date string, falling back to *now.date()*."""
    try:
        return datetime.strptime(test_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return now.date()


def _enrich_metadata(
    data: Dict,
    result: RampTestResult,
    athlete_id: Optional[str],
    notes: Optional[str],
    now: datetime,
    session_id: str,
    test_date: Any,
) -> None:
    """Enrich data dict with standard metadata fields."""
    analysis_timestamp = now.isoformat()

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


def _apply_data_policy(final_json: Dict, data: Dict, manual_overrides: Optional[Dict]) -> None:
    """Resolve manual overrides and attach data_policy to the report JSON."""
    if not manual_overrides:
        return

    from modules.canonical_values import build_data_policy, resolve_all_thresholds

    auto_values: Dict[str, Any] = {}
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

    resolved = resolve_all_thresholds(manual_overrides, auto_values)
    final_json["data_policy"] = build_data_policy(resolved)

    from modules.canonical_values import log_resolution

    for line in log_resolution(resolved):
        logger.info(f"[DataPolicy] {line}")


def _save_json_file(
    final_json: Dict,
    test_date: Any,
    output_base_dir: str,
    session_id: str,
    dev_mode: bool,
) -> Path:
    """Write the report JSON to disk and return the file path."""
    year_str = test_date.strftime("%Y")
    month_str = test_date.strftime("%m")

    save_dir = Path(output_base_dir) / year_str / month_str
    save_dir.mkdir(parents=True, exist_ok=True)

    short_uuid = session_id[:8]
    filename = f"ramp_test_{test_date.isoformat()}_{short_uuid}.json"
    file_path = save_dir / filename

    mode = "w" if dev_mode else "x"

    try:
        with open(file_path, mode, encoding="utf-8") as f:
            json.dump(final_json, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
        logger.info(f"Ramp Test JSON saved: {session_id}")
    except FileExistsError as err:
        if not dev_mode:
            raise FileExistsError(
                f"Ramp Test Report already exists and immutable: {file_path}"
            ) from err

    return file_path


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
    gated = _check_gating(source_file, output_base_dir, session_type, ramp_confidence)
    if gated is not None:
        return gated

    data = result.to_dict()

    if source_df is not None and len(source_df) > 0:
        _enrich_with_source_data(data, source_df)

    if source_df is not None and len(source_df) > 0:
        _calculate_vo2max(data, source_df)

    _build_canonical_and_metabolic(data)

    _run_limiter_analysis(data, source_df)

    now = datetime.now()
    session_id = str(uuid.uuid4())
    test_date = _parse_test_date(result.test_date, now)
    _enrich_metadata(data, result, athlete_id, notes, now, session_id, test_date)

    final_json = {"$schema": CANONICAL_SCHEMA, "version": CANONICAL_VERSION, **data}

    _apply_data_policy(final_json, data, manual_overrides)

    file_path = _save_json_file(final_json, test_date, output_base_dir, session_id, dev_mode)

    from modules.domain import SessionType

    validity_section = final_json.get("test_validity", {})
    test_validity_status = validity_section.get("status", "unknown")
    should_generate_pdf = test_validity_status != "invalid"
    is_conditional = session_type == SessionType.RAMP_TEST_CONDITIONAL

    pdf_path = None

    if should_generate_pdf:
        try:
            pdf_path = _auto_generate_pdf(
                str(file_path.absolute()),
                final_json,
                is_conditional,
                source_df=source_df,
                manual_overrides=manual_overrides,
            )
        except (ValueError, OSError, ImportError) as e:  # noqa: BLE001
            logger.warning(f" PDF generation failed for {session_id}: {e}")

    try:
        _update_index(
            output_base_dir,
            final_json["metadata"],
            str(file_path.absolute()),
            pdf_path,
            source_file,
        )
        logger.info(f"Ramp Test indexed: {session_id}")
    except (OSError, ValueError) as e:  # noqa: BLE001
        logger.warning(f" Failed to update report index: {e}")

    return {
        "path": str(file_path.absolute()),
        "pdf_path": pdf_path,
        "session_id": session_id,
        "uuid": session_id,
    }
