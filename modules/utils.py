"""Utility functions for data loading and parsing."""

import streamlit as st
import pandas as pd
import numpy as np
import io
import logging
from typing import Optional

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
    # Lowercase all columns first
    df_pd.columns = [str(c).lower().strip() for c in df_pd.columns]

    # Apply standard mappings using cached reverse index for O(m) complexity
    mapping = {}
    cols = set(df_pd.columns)  # O(1) lookup
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
    "watts": {"power", "pwr", "moc", "w", "watts"},
    "core_temperature": {"core temp", "core_temp", "temp_central", "temp", "core temperature"},
    "skin_temperature": {"skin temp", "skin_temp", "skin temperature"},
    "tymeventilation": {"ve", "ventilation", "vent", "tymeventilation"},
    "tymebreathrate": {
        "br",
        "rr",
        "breath rate",
        "breathing rate",
        "respiration rate",
        "tymebreathrate",
    },
    "cadence": {"cad", "rpm", "cadence"},
    "thb": {"total_hemoglobin", "total hemoglobin", "thb"},
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
            return np.mean(parts) if parts else np.nan
        except ValueError:
            return np.nan

    try:
        return float(val)
    except ValueError:
        return np.nan


def _read_raw_file(file) -> pd.DataFrame:
    """Read file content into raw DataFrame using Polars/Pandas."""
    # Try Polars first for speed
    try:
        import polars as pl

        file.seek(0)
        content = file.read()
        file.seek(0)

        # Try comma separator
        try:
            pl_df = pl.read_csv(io.BytesIO(content))
        except Exception:
            # Try semicolon
            pl_df = pl.read_csv(io.BytesIO(content), separator=";")

        df_pd = pl_df.to_pandas()
        logger.debug("Loaded data with Polars (fast mode)")
        return df_pd
    except Exception as e:
        logger.debug(f"Polars load failed, using Pandas: {e}")
        # Pandas fallback with pyarrow engine for better performance
        try:
            file.seek(0)
            # Use pyarrow engine for faster parsing of large files
            return pd.read_csv(file, low_memory=False, engine="pyarrow")
        except (pd.errors.ParserError, UnicodeDecodeError, ImportError) as e:
            logger.info(f"PyArrow CSV parse failed, trying standard engine: {e}")
            try:
                file.seek(0)
                return pd.read_csv(file, low_memory=False)
            except (pd.errors.ParserError, UnicodeDecodeError) as e:
                logger.info(f"Standard CSV parse failed, trying semicolon separator: {e}")
                file.seek(0)
                return pd.read_csv(file, sep=";", low_memory=False)


def _process_hrv_column(df: pd.DataFrame) -> pd.DataFrame:
    """Process and clean HRV column if present."""
    if "hrv" in df.columns:
        df["hrv"] = df["hrv"].astype(str).apply(_clean_hrv_value)
        df["hrv"] = pd.to_numeric(df["hrv"], errors="coerce")
        df["hrv"] = df["hrv"].interpolate(method="linear").ffill().bfill()
    return df


def _convert_numeric_types(df: pd.DataFrame) -> pd.DataFrame:
    """Convert known columns to numeric types."""
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
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data
def load_data(file, chunk_size: Optional[int] = None) -> pd.DataFrame:
    """Load CSV/TXT file into DataFrame with column normalization.

    Uses Polars for faster reading if available, falls back to Pandas.
    Supports chunked loading for large files (>100k rows) to control memory.

    Args:
        file: Uploaded file object
        chunk_size: Optional chunk size for large files (default: auto-detect)

    Returns:
        Processed DataFrame with normalized columns
    """
    # 1. IO -> Raw DataFrame
    df_pd = _read_raw_file(file)

    # Check if chunked processing needed for large files
    if len(df_pd) > 100000 and chunk_size is not False:
        return _process_large_dataframe(df_pd, chunk_size or 50000)

    # 2. Normalization -> Standard Column Names
    df_pd = normalize_columns_pandas(df_pd)

    if "pace" not in df_pd.columns and "velocity_smooth" in df_pd.columns:
        df_pd["pace"] = np.where(
            df_pd["velocity_smooth"] > 0,
            1000.0 / df_pd["velocity_smooth"],
            np.nan
        )

    # 2b. Running cadence doubling (Garmin exports half-steps as RPM)
    if "pace" in df_pd.columns and "cadence" in df_pd.columns:
        cad_median = df_pd["cadence"].median()
        if 0 < cad_median < 120:
            df_pd["cadence"] = df_pd["cadence"] * 2

    # 2c. GCT estimation from cadence (if no dedicated GCT column)
    gct_columns = ["ground_contact", "gct", "GroundContactTime"]
    has_gct = any(col in df_pd.columns for col in gct_columns)
    if not has_gct and "cadence" in df_pd.columns:
        cad = df_pd["cadence"]
        df_pd["gct"] = np.where(
            cad > 0,
            60000.0 / cad * 0.65,  # duty cycle ~65%
            np.nan
        )
        df_pd.loc[(df_pd["gct"] < 150) | (df_pd["gct"] > 400), "gct"] = np.nan

    # 2d. Stride length derivation from speed and cadence
    if "pace" in df_pd.columns and "cadence" in df_pd.columns and "stride_length" not in df_pd.columns:
        speed = np.where(df_pd["pace"] > 0, 1000.0 / df_pd["pace"], 0.0)
        cadence_hz = df_pd["cadence"] / 60.0
        df_pd["stride_length"] = np.where(
            cadence_hz > 0,
            speed / cadence_hz,
            np.nan
        )

    # 3. Data Cleaning (HRV)
    df_pd = _process_hrv_column(df_pd)

    # 4. Structure Enforcement (Time)
    if "time" not in df_pd.columns:
        df_pd["time"] = np.arange(len(df_pd)).astype(float)

    # 5. Type Conversion
    df_pd = _convert_numeric_types(df_pd)

    return df_pd


def _process_large_dataframe(df: pd.DataFrame, chunk_size: int) -> pd.DataFrame:
    """Process large DataFrames in chunks to control memory usage.

    Args:
        df: Large input DataFrame
        chunk_size: Number of rows per chunk

    Returns:
        Concatenated processed DataFrame
    """
    import gc

    chunks = []
    total_rows = len(df)

    for start_idx in range(0, total_rows, chunk_size):
        end_idx = min(start_idx + chunk_size, total_rows)
        chunk = df.iloc[start_idx:end_idx].copy()

        # Process chunk
        chunk = normalize_columns_pandas(chunk)
        if "pace" not in chunk.columns and "velocity_smooth" in chunk.columns:
            chunk["pace"] = np.where(
                chunk["velocity_smooth"] > 0,
                1000.0 / chunk["velocity_smooth"],
                np.nan
            )
        
        # Running cadence doubling (Garmin exports half-steps as RPM)
        if "pace" in chunk.columns and "cadence" in chunk.columns:
            cad_median = chunk["cadence"].median()
            if 0 < cad_median < 120:
                chunk["cadence"] = chunk["cadence"] * 2
        
        # GCT estimation from cadence (if no dedicated GCT column)
        gct_columns = ["ground_contact", "gct", "GroundContactTime"]
        has_gct = any(col in chunk.columns for col in gct_columns)
        if not has_gct and "cadence" in chunk.columns:
            cad = chunk["cadence"]
            chunk["gct"] = np.where(
                cad > 0,
                60000.0 / cad * 0.65,
                np.nan
            )
            chunk.loc[(chunk["gct"] < 150) | (chunk["gct"] > 400), "gct"] = np.nan
        
        # Stride length derivation
        if "pace" in chunk.columns and "cadence" in chunk.columns and "stride_length" not in chunk.columns:
            speed = np.where(chunk["pace"] > 0, 1000.0 / chunk["pace"], 0.0)
            cadence_hz = chunk["cadence"] / 60.0
            chunk["stride_length"] = np.where(cadence_hz > 0, speed / cadence_hz, np.nan)
        
        chunk = _process_hrv_column(chunk)

        if "time" not in chunk.columns:
            chunk["time"] = np.arange(start_idx, end_idx).astype(float)

        chunk = _convert_numeric_types(chunk)
        chunks.append(chunk)

        # Explicit cleanup
        del chunk
        gc.collect()

    return pd.concat(chunks, ignore_index=True)


from dataclasses import dataclass
from typing import List


@dataclass
class DataQualityReport:
    """Report on data quality and completeness."""

    available_metrics: List[str]
    missing_metrics: List[str]
    recommendations: List[str]
    quality_score: float
    sport_type: str

    def to_dict(self):
        return {
            "available": self.available_metrics,
            "missing": self.missing_metrics,
            "recommendations": self.recommendations,
            "quality_score": self.quality_score,
            "sport_type": self.sport_type,
        }


def validate_data_completeness(df: pd.DataFrame) -> DataQualityReport:
    """Validate data completeness and provide recommendations."""
    available = []
    missing = []
    recommendations = []

    metric_definitions = {
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

    columns_lower = [c.lower() for c in df.columns]

    for group, metrics in metric_definitions.items():
        for metric_name, aliases in metrics.items():
            found = any(a.lower() in columns_lower for a in aliases)
            if found:
                available.append(f"{group}.{metric_name}")
            else:
                missing.append(f"{group}.{metric_name}")

    if "core.watts" not in available and "running.pace" not in available:
        recommendations.append("⚠️ Brak danych mocy lub tempa - analiza ograniczona")

    if "ventilation.ve" not in available:
        recommendations.append("ℹ️ Brak wentylacji - zakładka Ventilation nieaktywna")

    if "biomechanics.vo" not in available:
        recommendations.append("ℹ️ Brak Vertical Oscillation - analiza biomechaniczna ograniczona")

    if "advanced.smo2" in available and "ventilation.ve" in available:
        recommendations.append("✅ Pełna analiza fizjologiczna dostępna (SmO2 + VE)")

    sport_type = detect_sport_type(df)
    total_metrics = len(available) + len(missing)
    quality_score = (len(available) / total_metrics * 100) if total_metrics > 0 else 0

    return DataQualityReport(
        available_metrics=available,
        missing_metrics=missing,
        recommendations=recommendations,
        quality_score=quality_score,
        sport_type=sport_type,
    )


def detect_sport_type(df: pd.DataFrame) -> str:
    """Detect sport type based on available columns."""
    has_power = any(c in df.columns for c in ["watts", "power", "Watts"])
    has_pace = any(c in df.columns for c in ["pace", "speed", "velocity", "velocity_smooth", "gap"])

    if has_power and not has_pace:
        return "cycling"
    elif has_pace and not has_power:
        return "running"
    elif has_power and has_pace:
        return "mixed"
    else:
        return "unknown"
