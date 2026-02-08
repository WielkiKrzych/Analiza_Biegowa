"""
Signal Validation Module

Provides input validation for physiological signals:
- Missing data detection
- Artifact detection (spikes, outliers)
- Minimum length checks
- Graceful warnings (never crashes)

All functions return warnings instead of raising exceptions.
NO STREAMLIT OR UI DEPENDENCIES ALLOWED.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum
import numpy as np
import pandas as pd


class Severity(str, Enum):
    """Severity levels for validation warnings."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationWarning:
    """A single validation warning."""
    code: str
    message: str
    severity: Severity = Severity.WARNING
    details: Optional[dict] = None
    
    def __str__(self) -> str:
        emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(self.severity, "")
        return f"{emoji} [{self.code}] {self.message}"


@dataclass
class ValidationResult:
    """Complete result of signal validation."""
    is_valid: bool
    warnings: List[ValidationWarning] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    artifact_indices: List[int] = field(default_factory=list)
    
    def has_errors(self) -> bool:
        """Check if any error-level warnings exist."""
        return any(w.severity == Severity.ERROR for w in self.warnings)
    
    def has_warnings(self) -> bool:
        """Check if any warning-level warnings exist."""
        return any(w.severity == Severity.WARNING for w in self.warnings)
    
    def get_messages(self) -> List[str]:
        """Get all warning messages as strings."""
        return [str(w) for w in self.warnings]


# ============================================================
# Validation Functions
# ============================================================

def detect_missing_data(
    series: pd.Series,
    max_missing_ratio: float = 0.2
) -> Optional[ValidationWarning]:
    """
    Detect missing data in a signal.
    
    Args:
        series: Input pandas Series
        max_missing_ratio: Maximum acceptable ratio of missing data (default: 0.2 = 20%)
    
    Returns:
        ValidationWarning if issues found, None otherwise
    """
    if series is None or len(series) == 0:
        return ValidationWarning(
            code="EMPTY_SIGNAL",
            message="Signal is empty or None",
            severity=Severity.ERROR
        )
    
    missing_count = series.isna().sum()
    missing_ratio = missing_count / len(series)
    
    if missing_ratio > max_missing_ratio:
        return ValidationWarning(
            code="EXCESSIVE_MISSING_DATA",
            message=f"Missing data: {missing_ratio:.1%} (>{max_missing_ratio:.0%} threshold)",
            severity=Severity.WARNING if missing_ratio < 0.5 else Severity.ERROR,
            details={"missing_count": int(missing_count), "missing_ratio": round(missing_ratio, 3)}
        )
    
    if missing_count > 0:
        return ValidationWarning(
            code="MISSING_DATA",
            message=f"Signal has {missing_count} missing values ({missing_ratio:.1%})",
            severity=Severity.INFO,
            details={"missing_count": int(missing_count), "missing_ratio": round(missing_ratio, 3)}
        )
    
    return None


def detect_artifacts(
    series: pd.Series,
    z_threshold: float = 3.0,
    spike_threshold: float = 0.5
) -> Tuple[List[int], Optional[ValidationWarning]]:
    """
    Detect artifacts (spikes, outliers) in a signal using Z-score and spike detection.
    
    Args:
        series: Input pandas Series
        z_threshold: Z-score threshold for outliers (default: 3.0 = 3 std devs)
        spike_threshold: Max allowed change as fraction of range (default: 0.5)
    
    Returns:
        Tuple of (artifact_indices, ValidationWarning if issues found)
    """
    if series is None or len(series) < 3:
        return [], None
    
    valid_data = series.dropna()
    if len(valid_data) < 3:
        return [], None
    
    artifact_indices = []
    
    # Z-score outlier detection
    mean_val = valid_data.mean()
    std_val = valid_data.std()
    
    if std_val > 0:
        z_scores = np.abs((valid_data - mean_val) / std_val)
        outlier_mask = z_scores > z_threshold
        z_outliers = valid_data.index[outlier_mask].tolist()
        artifact_indices.extend(z_outliers)
    
    # Spike detection (sudden jumps)
    data_range = valid_data.max() - valid_data.min()
    if data_range > 0:
        diffs = np.abs(np.diff(valid_data.values))
        spike_mask = diffs > (data_range * spike_threshold)
        spike_indices = np.where(spike_mask)[0] + 1
        spike_locations = valid_data.index[spike_indices].tolist()
        artifact_indices.extend(spike_locations)
    
    # Remove duplicates
    artifact_indices = sorted(set(artifact_indices))
    
    if len(artifact_indices) > 0:
        artifact_ratio = len(artifact_indices) / len(series)
        warning = ValidationWarning(
            code="ARTIFACTS_DETECTED",
            message=f"Found {len(artifact_indices)} potential artifacts ({artifact_ratio:.1%})",
            severity=Severity.WARNING if artifact_ratio < 0.1 else Severity.ERROR,
            details={
                "artifact_count": len(artifact_indices),
                "artifact_ratio": round(artifact_ratio, 3),
                "z_threshold": z_threshold
            }
        )
        return artifact_indices, warning
    
    return [], None


def check_minimum_length(
    series: pd.Series,
    min_length: int = 30
) -> Optional[ValidationWarning]:
    """
    Check if signal meets minimum length requirement.
    
    Args:
        series: Input pandas Series
        min_length: Minimum required samples (default: 30)
    
    Returns:
        ValidationWarning if too short, None otherwise
    """
    if series is None:
        return ValidationWarning(
            code="NULL_SIGNAL",
            message="Signal is None",
            severity=Severity.ERROR
        )
    
    actual_length = len(series)
    
    if actual_length < min_length:
        return ValidationWarning(
            code="SIGNAL_TOO_SHORT",
            message=f"Signal has {actual_length} samples (minimum: {min_length})",
            severity=Severity.ERROR,
            details={"actual_length": actual_length, "min_length": min_length}
        )
    
    return None


def check_data_range(
    series: pd.Series,
    valid_range: Tuple[float, float] = None,
    column_name: str = "signal"
) -> Optional[ValidationWarning]:
    """
    Check if signal values are within expected range.
    
    Args:
        series: Input pandas Series
        valid_range: Tuple of (min, max) valid values
        column_name: Name for error messages
    
    Returns:
        ValidationWarning if out of range, None otherwise
    """
    if series is None or len(series) == 0 or valid_range is None:
        return None
    
    valid_data = series.dropna()
    if len(valid_data) == 0:
        return None
    
    min_val, max_val = valid_range
    out_of_range = ((valid_data < min_val) | (valid_data > max_val)).sum()
    
    if out_of_range > 0:
        ratio = out_of_range / len(valid_data)
        return ValidationWarning(
            code="OUT_OF_RANGE",
            message=f"{column_name}: {out_of_range} values outside [{min_val}, {max_val}] ({ratio:.1%})",
            severity=Severity.WARNING if ratio < 0.1 else Severity.ERROR,
            details={
                "out_of_range_count": int(out_of_range),
                "ratio": round(ratio, 3),
                "expected_range": valid_range
            }
        )
    
    return None


# ============================================================
# Main Validation Function
# ============================================================

def validate_signal(
    series: pd.Series,
    min_length: int = 30,
    max_missing_ratio: float = 0.2,
    z_threshold: float = 3.0,
    spike_threshold: float = 0.5,
    valid_range: Tuple[float, float] = None,
    column_name: str = "signal"
) -> ValidationResult:
    """
    Perform complete validation of a signal.
    
    This function NEVER raises exceptions - all issues are returned as warnings.
    
    Args:
        series: Input pandas Series
        min_length: Minimum signal length (default: 30)
        max_missing_ratio: Max acceptable missing data ratio (default: 0.2)
        z_threshold: Z-score threshold for artifact detection (default: 3.0)
        spike_threshold: Spike detection threshold (default: 0.5)
        valid_range: Optional (min, max) valid values
        column_name: Name for error messages
    
    Returns:
        ValidationResult with is_valid flag, warnings, and statistics
    """
    warnings = []
    artifact_indices = []
    stats = {}
    
    try:
        # Check minimum length
        length_warning = check_minimum_length(series, min_length)
        if length_warning:
            warnings.append(length_warning)
        
        # Check missing data
        missing_warning = detect_missing_data(series, max_missing_ratio)
        if missing_warning:
            warnings.append(missing_warning)
        
        # Check for artifacts
        artifact_indices, artifact_warning = detect_artifacts(
            series, z_threshold, spike_threshold
        )
        if artifact_warning:
            warnings.append(artifact_warning)
        
        # Check data range
        if valid_range:
            range_warning = check_data_range(series, valid_range, column_name)
            if range_warning:
                warnings.append(range_warning)
        
        # Compute statistics
        if series is not None and len(series) > 0:
            valid_data = series.dropna()
            stats = {
                "length": len(series),
                "valid_count": len(valid_data),
                "missing_count": len(series) - len(valid_data),
                "mean": round(valid_data.mean(), 3) if len(valid_data) > 0 else None,
                "std": round(valid_data.std(), 3) if len(valid_data) > 0 else None,
                "min": round(valid_data.min(), 3) if len(valid_data) > 0 else None,
                "max": round(valid_data.max(), 3) if len(valid_data) > 0 else None,
                "artifact_count": len(artifact_indices)
            }
        
    except Exception as e:
        # Catch any unexpected errors and convert to warning
        warnings.append(ValidationWarning(
            code="VALIDATION_ERROR",
            message=f"Validation failed: {str(e)}",
            severity=Severity.ERROR
        ))
    
    # Determine overall validity
    has_errors = any(w.severity == Severity.ERROR for w in warnings)
    is_valid = not has_errors
    
    return ValidationResult(
        is_valid=is_valid,
        warnings=warnings,
        stats=stats,
        artifact_indices=artifact_indices
    )


__all__ = [
    # Enums
    'Severity',
    # Dataclasses
    'ValidationWarning',
    'ValidationResult',
    # Functions
    'detect_missing_data',
    'detect_artifacts',
    'check_minimum_length',
    'check_data_range',
    'validate_signal',
]
