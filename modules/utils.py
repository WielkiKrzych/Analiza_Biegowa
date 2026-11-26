"""Utility functions for data loading and parsing."""

import io
import logging
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def parse_time_input(t_str: str) -> int | None:
    """Parse time string (HH:MM:SS, MM:SS, or SS) to seconds.

    Args:
        t_str: Time string in format HH:MM:SS, MM:SS, or SS

    Returns:
        Total seconds or None if parsing fails
    """
    try:
        parts = list(map(int, t_str.split(":")))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 1:
            return parts[0]
    except (ValueError, AttributeError) as e:
        logger.debug(f"Failed to parse time '{t_str}': {e}")
        return None
    return None


def _serialize_df_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to bytes for caching.

    Tries parquet first (faster), falls back to CSV.
    """
    bio = io.BytesIO()
    try:
        df.to_parquet(bio, index=False)
        return bio.getvalue()
    except (ImportError, ValueError) as e:
        logger.debug(f"Parquet serialization failed, using CSV: {e}")
        bio = io.BytesIO()
        df.to_csv(bio, index=False)
        return bio.getvalue()


def normalize_columns_pandas(df_pd: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to lowercase and apply standard mappings.

    Mappings:
    - 've' / 'ventilation' -> 'tymeventilation'
    - 'total_hemoglobin' -> 'thb'
    """
    # Lowercase all columns first (create new DataFrame to avoid mutation)
    df_pd = df_pd.rename(columns={c: str(c).lower().strip() for c in df_pd.columns})

    # Apply standard mappings using cached reverse index for O(m) complexity
    mapping = {}
    set(df_pd.columns)  # O(1) lookup
    cols_lower = {c.lower().strip() for c in df_pd.columns}

    # Pre-built reverse index: canonical -> set of aliases (module-level constant)
    for canonical, aliases in _COLUMN_ALIAS_INDEX.items():
        if canonical not in cols_lower:
            # Find first matching alias
            match = next((a for a in aliases if a in cols_lower), None)
            if match:
                # Find original case column name
                orig_col = next(c for c in df_pd.columns if c.lower().strip() == match)
                mapping[orig_col] = canonical

    if mapping:
        df_pd = df_pd.rename(columns=mapping)

    # Drop duplicate columns that mapped to the same canonical name
    # (e.g. heat_strain_index + HeatStrainIndex both become heat_strain_index)
    df_pd = df_pd.loc[:, ~df_pd.columns.duplicated(keep="first")]

    return df_pd


# Module-level constant: canonical -> set of aliases for O(1) reverse lookup
_COLUMN_ALIAS_INDEX = {
    "heartrate": {
        "hr",
        "heart rate",
        "bpm",
        "tętno",
        "heartrate",
        "heart_rate",
        "heart-rate",
        "pulse",
        "heart_rate_bpm",
        "heartrate_bpm",
        "hr_bpm",
    },
    "watts": {"power", "pwr", "moc", "w", "watts", "running_power"},
    "speed_m_s": {"speed", "velocity", "speed_m_s", "speed_mps", "speed (m/s)"},
    "core_temperature": {"core temp", "core_temp", "temp_central", "temp", "core temperature"},
    "skin_temperature": {"skin temp", "skin_temp", "skin temperature"},
    "tymeventilation": {"ve", "ventilation", "vent", "tymeventilation"},
    "tymebreathrate": {
        "br",
        "rr",
        "breath rate",
        "breathing rate",
        "respiration rate",
        "respiration",
        "respiratory_rate",
        "resprate",
        "tymebreathrate",
    },
    "cadence": {"cad", "rpm", "cadence"},
    "thb": {"total_hemoglobin", "total hemoglobin", "thb"},
    "verticaloscillation": {"vertical_oscillation", "vo_cm", "verticaloscillation"},
    "heat_strain_index": {"heatstrainindex", "heat strain index", "hsi", "heat_strain_index"},
}


def _clean_hrv_value(val: str) -> float:
    """Clean a single HRV value string.

    Handles formats: plain numbers, colon-separated values (e.g., "50:60:55")
    """
    val = val.strip().lower()
    if val == "nan" or val == "":
        return np.nan

    if ":" in val:
        try:
            parts = [float(x) for x in val.split(":") if x]
            return float(np.mean(parts)) if parts else np.nan
        except ValueError:
            # why: np.nan is this column's explicit "no reading" value; it is
            # what the blank / "nan" branch above returns too.
            return np.nan

    try:
        return float(val)
    except ValueError:
        # why: same - a value that is not a number has no reading, and np.nan
        # is how the whole HRV column says so.
        return np.nan


def _read_raw_file(file) -> pd.DataFrame:
    """Read file content into raw DataFrame using Polars/Pandas."""
    import csv
    import io

    file.seek(0)
    content = file.read()
    file.seek(0)
    sample = content[:8192].decode("utf-8-sig", errors="replace")
    try:
        separator = csv.Sniffer().sniff(sample, delimiters=",;").delimiter
    except csv.Error:
        # The header still identifies the separator when malformed rows foil sniffing.
        header = sample.splitlines()[0] if sample else ""
        separator = ";" if header.count(";") > header.count(",") else ","
    try:
        import polars as pl
    except ImportError:
        return pd.read_csv(io.BytesIO(content), sep=separator, low_memory=False)

    try:
        return pl.read_csv(io.BytesIO(content), separator=separator).to_pandas()
    except (OSError, ValueError, TypeError, pl.exceptions.PolarsError) as exc:
        logger.debug("Polars load failed, using Pandas: %s", exc)
    return pd.read_csv(io.BytesIO(content), sep=separator, low_memory=False)


def _process_hrv_column(df: pd.DataFrame) -> pd.DataFrame:
    """Process and clean HRV column if present.

    Mutates df in place.
    """
    if "hrv" in df.columns:
        df["hrv"] = df["hrv"].astype(str).apply(_clean_hrv_value)
        df["hrv"] = pd.to_numeric(df["hrv"], errors="coerce")
        df["hrv"] = df["hrv"].interpolate(method="linear").ffill().bfill()
    return df


def _convert_numeric_types(df: pd.DataFrame) -> pd.DataFrame:
    """Convert known columns to numeric types.

    Mutates df in place.
    """
    numeric_cols = [
        "watts",
        "heartrate",
        "cadence",
        "smo2",
        "thb",
        "temp",
        "torque",
        "core_temperature",
        "skin_temperature",
        "velocity_smooth",
        "tymebreathrate",
        "tymeventilation",
        "rr",
        "rr_interval",
        "hrv",
        "ibi",
        "time",
        "skin_temp",
        "core_temp",
        "power",
        # FIT running dynamics
        "stance_time",
        "stance_time_percent",
        "stance_time_balance",
        "vertical_ratio",
        "step_length",
        "speed_m_s",
        "temperature",
        "o2hb",
        "hhb",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _normalize_velocity_units(df: pd.DataFrame) -> pd.DataFrame:
    """Convert velocity_smooth from km/h to m/s when median exceeds 10.

    Mutates df in place.
    """
    if "velocity_smooth" not in df.columns:
        return df
    vs_median = df["velocity_smooth"].replace(0, np.nan).median()
    if pd.notna(vs_median) and vs_median > 10:
        df["velocity_smooth"] = df["velocity_smooth"] / 3.6
    return df


def derive_pace(df: pd.DataFrame) -> None:
    """Normalize pace to seconds per km and use GPS speed for missing values."""
    if "pace" in df:
        pace = pd.to_numeric(df["pace"], errors="coerce")
        df["pace"] = pace.where(pace.eq(0) | pace.between(60, 3600))
    for column in ("speed_m_s", "speed", "velocity_smooth"):
        if column not in df:
            continue
        speed = pd.to_numeric(df[column], errors="coerce")
        from_speed = 1000.0 / speed.where(speed.between(1000 / 3600, 1000 / 60))
        from_speed = from_speed.mask(speed.eq(0), 0)
        df["pace"] = df["pace"].fillna(from_speed) if "pace" in df else from_speed


def _normalize_cadence(df: pd.DataFrame) -> pd.DataFrame:
    """Double half-cadence values exported by Intervals.icu (~80 SPM).

    Mutates df in place.
    """
    if "cadence" not in df.columns:
        return df
    cad_median = df["cadence"].median()
    if 0 < cad_median < 120:
        df["cadence"] = df["cadence"] * 2
    return df


def _normalize_vertical_oscillation(df: pd.DataFrame) -> pd.DataFrame:
    """Convert verticaloscillation from mm to cm when median exceeds 20.

    Mutates df in place.
    """
    if "verticaloscillation" not in df.columns:
        return df
    vo_median = df["verticaloscillation"].replace(0, np.nan).median()
    if pd.notna(vo_median) and vo_median > 20:
        df["verticaloscillation"] = df["verticaloscillation"] / 10.0
    return df


_GCT_COLUMNS = ["stance_time", "ground_contact", "gct", "groundcontacttime"]


def _derive_gct(df: pd.DataFrame) -> pd.DataFrame:
    """Derive GCT from FIT stance_time or estimate from cadence.

    Mutates df in place.
    """
    has_gct = any(col in df.columns for col in _GCT_COLUMNS)
    if has_gct:
        for col in _GCT_COLUMNS:
            if col in df.columns and col != "gct":
                df["gct"] = pd.to_numeric(df[col], errors="coerce")
                break
    elif "cadence" in df.columns:
        cad = df["cadence"]
        df["gct"] = np.where(cad > 0, 60000.0 / cad * 0.65, np.nan)
        df.loc[(df["gct"] < 150) | (df["gct"] > 400), "gct"] = np.nan
    return df


def _derive_stride_length(df: pd.DataFrame) -> pd.DataFrame:
    """Derive stride_length from pace and cadence when absent.

    Mutates df in place.
    """
    if "stride_length" in df.columns or "pace" not in df.columns or "cadence" not in df.columns:
        return df
    speed = np.where(df["pace"] > 0, 1000.0 / df["pace"], 0.0)
    cadence_hz = df["cadence"] / 60.0
    df["stride_length"] = np.where(cadence_hz > 0, speed / cadence_hz, np.nan)
    return df


@st.cache_data
def load_data(file) -> pd.DataFrame:
    """Read and normalize a CSV/TXT recording."""
    df = normalize_columns_pandas(_read_raw_file(file))
    df = _process_hrv_column(df)
    df = _convert_numeric_types(df)
    df = _normalize_velocity_units(df)
    derive_pace(df)
    df = _normalize_cadence(df)
    df = _normalize_vertical_oscillation(df)
    df = _derive_gct(df)
    return _derive_stride_length(df)


@dataclass
class DataQualityReport:
    """Report on data quality and completeness."""

    available_metrics: List[str]
    missing_metrics: List[str]
    recommendations: List[str]
    quality_score: float


METRIC_GROUP_DEFINITIONS = {
    "core": {
        "watts": ["watts", "power"],
        "heartrate": ["heartrate", "hr", "heart_rate"],
    },
    "advanced": {
        "cadence": ["cadence", "cad"],
        "smo2": ["smo2"],
        "thb": ["thb", "total_hemoglobin"],
    },
    "ventilation": {
        "ve": ["tymeventilation", "ve", "ventilation"],
        "br": ["tymebreathrate", "br", "breath_rate"],
    },
    "thermal": {
        "core_temp": ["core_temperature", "core_temp"],
        "skin_temp": ["skin_temperature", "skin_temp"],
    },
    "biomechanics": {
        "vo": ["verticaloscillation", "VerticalOscillation", "vo"],
    },
    "running": {
        "pace": ["pace", "speed", "velocity_smooth"],
        "gct": ["ground_contact", "gct"],
    },
}


def validate_data_completeness(df: pd.DataFrame) -> DataQualityReport:
    """Validate data completeness and provide recommendations."""
    available = []
    missing = []
    recommendations = []

    columns_lower = {c.lower(): c for c in df.columns}

    for group, metrics in METRIC_GROUP_DEFINITIONS.items():
        for metric_name, aliases in metrics.items():
            found = any(a in columns_lower and df[columns_lower[a]].notna().any() for a in aliases)
            if found:
                available.append(f"{group}.{metric_name}")
            else:
                missing.append(f"{group}.{metric_name}")

    if "ventilation.ve" not in available:
        recommendations.append("Brak pomiaru wentylacji VE")

    total_metrics = len(available) + len(missing)
    quality_score = (len(available) / total_metrics * 100) if total_metrics > 0 else 0

    return DataQualityReport(
        available_metrics=available,
        missing_metrics=missing,
        recommendations=recommendations,
        quality_score=quality_score,
    )
