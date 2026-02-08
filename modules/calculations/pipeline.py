"""
Ramp Test Pipeline.

Explicit, step-by-step processing pipeline per methodology/ramp_test/08_algorithm_map.md.

Pipeline steps:
1. validate_test() - Check test validity
2. preprocess_signals() - Clean and normalize signals
3. analyze_signals_independently() - Detect thresholds per signal
4. integrate_signals() - Combine results, detect conflicts
5. build_result() - Create final result with confidence

NO OPTIMIZATION - explicit, readable, debuggable.
"""

import logging
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from models.results import (
    TestValidity,
    ValidityLevel,
    SignalQuality,
    ThresholdRange,
    ConflictReport,
    SignalConflict,
    ConflictType,
    ConflictSeverity,
    RampTestResult,
)
from modules.calculations.threshold_types import StepTestRange, StepVTResult, StepSmO2Result
from modules.calculations.step_detection import detect_step_test_range
from modules.calculations.ventilatory import detect_vt_from_steps
from modules.calculations.metabolic import detect_smo2_from_steps
from modules.calculations.power import calculate_power_duration_curve


# ============================================================
# STEP 1: TEST VALIDATION
# ============================================================


def validate_test(
    df: pd.DataFrame,
    power_column: str = "watts",
    hr_column: str = "hr",
    time_column: str = "time",
    min_ramp_duration_sec: int = 480,  # 8 min
    min_power_range_watts: float = 150.0,
) -> TestValidity:
    """
    Step 1: Validate test protocol and data quality.

    Checks:
    - Ramp duration (≥ 8 min for VALID)
    - Power range (≥ 150 W for VALID)
    - Signal quality (artifacts, gaps)
    - Warmup presence

    Returns:
        TestValidity with validity level and issues
    """
    result = TestValidity(validity=ValidityLevel.VALID)
    issues = []

    # Check required columns
    df.columns = df.columns.str.lower().str.strip()
    has_power = power_column in df.columns
    has_hr = hr_column in df.columns
    has_time = time_column in df.columns

    if not has_time or not has_power:
        result.validity = ValidityLevel.INVALID
        issues.append("Brak wymaganych kolumn (time, power)")
        result.issues = issues
        return result

    # Calculate ramp duration
    time_range = df[time_column].max() - df[time_column].min()
    result.ramp_duration_sec = int(time_range)

    if time_range < 360:  # < 6 min = INVALID
        result.validity = ValidityLevel.INVALID
        issues.append(f"Rampa za krótka: {int(time_range / 60)} min (minimum: 6 min)")
        result.ramp_duration_sufficient = False
    elif time_range < min_ramp_duration_sec:  # 6-8 min = CONDITIONAL
        if result.validity == ValidityLevel.VALID:
            result.validity = ValidityLevel.CONDITIONAL
        issues.append(f"Rampa krótka: {int(time_range / 60)} min (zalecane: ≥8 min)")
        result.ramp_duration_sufficient = False

    # Calculate power range
    power_range = df[power_column].max() - df[power_column].min()
    result.power_range_watts = float(power_range)

    if power_range < min_power_range_watts:
        if result.validity == ValidityLevel.VALID:
            result.validity = ValidityLevel.CONDITIONAL
        issues.append(
            f"Zakres mocy: {int(power_range)} W (zalecane: ≥{int(min_power_range_watts)} W)"
        )
        result.power_range_sufficient = False

    # Check signal quality
    result.signal_qualities = {}

    # Power quality
    power_quality = _check_signal_quality(df, power_column, time_column, "Power")
    result.signal_qualities["Power"] = power_quality
    if not power_quality.is_usable:
        result.validity = ValidityLevel.INVALID
        issues.append(f"Jakość Power: {power_quality.get_grade()}")

    # HR quality (if available)
    if has_hr:
        hr_quality = _check_signal_quality(df, hr_column, time_column, "HR")
        result.signal_qualities["HR"] = hr_quality
        if hr_quality.artifact_ratio > 0.20:  # >20% artifacts = INVALID
            result.validity = ValidityLevel.INVALID
            issues.append(f"Za dużo artefaktów HR: {hr_quality.artifact_ratio:.0%}")
        elif hr_quality.artifact_ratio > 0.05:  # 5-20% = CONDITIONAL
            if result.validity == ValidityLevel.VALID:
                result.validity = ValidityLevel.CONDITIONAL
            issues.append(f"Artefakty HR: {hr_quality.artifact_ratio:.0%}")

    result.issues = issues
    return result


def _check_signal_quality(
    df: pd.DataFrame, signal_column: str, time_column: str, signal_name: str
) -> SignalQuality:
    """Helper: Check quality of a single signal."""
    result = SignalQuality(signal_name=signal_name)

    if signal_column not in df.columns:
        result.is_usable = False
        result.quality_score = 0.0
        result.reasons_unusable.append(f"Brak kolumny: {signal_column}")
        return result

    data = df[signal_column]
    result.total_samples = len(data)

    # Count NaN/null
    nan_count = data.isna().sum()
    result.valid_samples = result.total_samples - nan_count

    # Artifact detection (simple: values outside expected range)
    if signal_name == "HR":
        artifacts = ((data < 40) | (data > 220)).sum()
    elif signal_name == "Power":
        artifacts = ((data < 0) | (data > 2000)).sum()
    else:
        artifacts = 0

    result.artifact_ratio = artifacts / result.total_samples if result.total_samples > 0 else 0

    # Gap detection (time jumps > 5s)
    if time_column in df.columns:
        time_diffs = df[time_column].diff()
        gaps = (time_diffs > 5).sum()
        result.gaps_detected = int(gaps)
        result.gap_ratio = gaps / len(time_diffs) if len(time_diffs) > 0 else 0

    # Calculate overall quality
    result.quality_score = max(0.0, 1.0 - result.artifact_ratio - result.gap_ratio * 0.5)
    result.is_usable = result.quality_score >= 0.5

    return result


# ============================================================
# STEP 2: SIGNAL PREPROCESSING
# ============================================================


@dataclass
class PreprocessedData:
    """Container for preprocessed signals."""

    df: pd.DataFrame
    step_range: Optional[StepTestRange] = None
    available_signals: List[str] = field(default_factory=list)
    preprocessing_notes: List[str] = field(default_factory=list)


def preprocess_signals(
    df: pd.DataFrame,
    power_column: str = "watts",
    hr_column: str = "hr",
    ve_column: str = "tymeventilation",
    smo2_column: str = "smo2",
    time_column: str = "time",
) -> PreprocessedData:
    """
    Step 2: Clean and prepare signals for analysis.

    Operations:
    - Lowercase column names
    - Detect step test range
    - Identify available signals
    - Basic cleaning (future: interpolation, filtering)

    Returns:
        PreprocessedData with cleaned df and step range
    """
    result = PreprocessedData(df=df.copy())

    # Normalize column names
    result.df.columns = result.df.columns.str.lower().str.strip()

    # Check available signals
    for col, name in [
        (power_column, "Power"),
        (hr_column, "HR"),
        (ve_column, "VE"),
        (smo2_column, "SmO2"),
    ]:
        if col in result.df.columns:
            result.available_signals.append(name)

    result.preprocessing_notes.append(f"Dostępne sygnały: {', '.join(result.available_signals)}")

    # Detect step test
    if power_column in result.df.columns and time_column in result.df.columns:
        result.step_range = detect_step_test_range(
            result.df, power_column=power_column, time_column=time_column
        )
        if result.step_range and result.step_range.is_valid:
            result.preprocessing_notes.append(
                f"Wykryto test schodkowy: {len(result.step_range.steps)} stopni"
            )
        else:
            result.preprocessing_notes.append("Nie wykryto testu schodkowego")

    return result


# ============================================================
# STEP 3: INDEPENDENT SIGNAL ANALYSIS
# ============================================================


@dataclass
class IndependentAnalysisResults:
    """Results from independent signal analysis."""

    vt_result: Optional[StepVTResult] = None
    smo2_result: Optional[StepSmO2Result] = None
    analysis_notes: List[str] = field(default_factory=list)


def analyze_signals_independently(
    preprocessed: PreprocessedData,
    power_column: str = "watts",
    hr_column: str = "hr",
    ve_column: str = "tymeventilation",
    smo2_column: str = "smo2",
    time_column: str = "time",
) -> IndependentAnalysisResults:
    """
    Step 3: Analyze each signal independently.

    Runs:
    - VE-based VT detection (if VE available)
    - SmO2-based LT detection (if SmO2 available)

    Each detector runs independently, no cross-signal logic yet.

    Returns:
        IndependentAnalysisResults with per-signal results
    """
    result = IndependentAnalysisResults()
    df = preprocessed.df
    step_range = preprocessed.step_range

    if not step_range or not step_range.is_valid:
        result.analysis_notes.append("⚠️ Brak wykrytego testu schodkowego - analiza ograniczona")
        return result

    # VE-based analysis
    if "VE" in preprocessed.available_signals:
        result.vt_result = detect_vt_from_steps(
            df,
            step_range,
            ve_column=ve_column,
            power_column=power_column,
            hr_column=hr_column,
            time_column=time_column,
        )
        if result.vt_result.vt1_zone:
            result.analysis_notes.append(
                f"VT1 (VE): {result.vt_result.vt1_zone.midpoint_watts:.0f} W "
                f"(confidence: {result.vt_result.vt1_zone.confidence:.2f})"
            )
        if result.vt_result.vt2_zone:
            result.analysis_notes.append(
                f"VT2 (VE): {result.vt_result.vt2_zone.midpoint_watts:.0f} W "
                f"(confidence: {result.vt_result.vt2_zone.confidence:.2f})"
            )

    # SmO2-based analysis
    if "SmO2" in preprocessed.available_signals:
        result.smo2_result = detect_smo2_from_steps(
            df,
            step_range,
            smo2_column=smo2_column,
            power_column=power_column,
            hr_column=hr_column,
            time_column=time_column,
        )
        if result.smo2_result.smo2_1_zone:
            result.analysis_notes.append(
                f"LT1 (SmO2, LOCAL): {result.smo2_result.smo2_1_zone.midpoint_watts:.0f} W "
                f"(confidence: {result.smo2_result.smo2_1_zone.confidence:.2f})"
            )
        if result.smo2_result.smo2_2_zone:
            result.analysis_notes.append(
                f"LT2 (SmO2, LOCAL): {result.smo2_result.smo2_2_zone.midpoint_watts:.0f} W"
            )

    return result


# ============================================================
# STEP 4: SIGNAL INTEGRATION
# ============================================================


@dataclass
class IntegrationResult:
    """Result of signal integration."""

    vt1: Optional[ThresholdRange] = None
    vt2: Optional[ThresholdRange] = None
    conflicts: ConflictReport = field(default_factory=ConflictReport)
    smo2_deviation_vt1: Optional[float] = None
    smo2_deviation_vt2: Optional[float] = None
    integration_notes: List[str] = field(default_factory=list)


def integrate_signals(analysis: IndependentAnalysisResults) -> IntegrationResult:
    """
    Step 4: Integrate results from independent signal analysis.

    IMPORTANT: SmO₂ does NOT detect thresholds independently.
    SmO₂ ONLY MODULATES VT confidence and range.

    Operations:
    - Build VT zones from VE (primary source)
    - Use SmO₂ to MODULATE confidence (boost/reduce)
    - Use SmO₂ to ADJUST range width (narrower if confirms)
    - Flag SmO₂ as LOCAL signal in all outputs

    Returns:
        IntegrationResult with combined thresholds and conflicts
    """
    result = IntegrationResult()
    result.conflicts = ConflictReport(signals_analyzed=[])

    vt_result = analysis.vt_result
    smo2_result = analysis.smo2_result

    # Build VT1 from VE result (PRIMARY and ONLY source for thresholds)
    if vt_result and vt_result.vt1_zone:
        zone = vt_result.vt1_zone
        result.vt1 = ThresholdRange(
            lower_watts=zone.range_watts[0],
            upper_watts=zone.range_watts[1],
            midpoint_watts=zone.midpoint_watts,
            confidence=zone.confidence,
            lower_hr=zone.range_hr[0] if zone.range_hr else None,
            upper_hr=zone.range_hr[1] if zone.range_hr else None,
            midpoint_hr=zone.midpoint_hr,
            midpoint_ve=zone.midpoint_ve,
            range_ve=zone.range_ve,
            sources=["VE"],
            method=zone.method,
        )
        result.conflicts.signals_analyzed.append("VE")

    # Build VT2 from VE result
    if vt_result and vt_result.vt2_zone:
        zone = vt_result.vt2_zone
        result.vt2 = ThresholdRange(
            lower_watts=zone.range_watts[0],
            upper_watts=zone.range_watts[1],
            midpoint_watts=zone.midpoint_watts,
            confidence=zone.confidence,
            lower_hr=zone.range_hr[0] if zone.range_hr else None,
            upper_hr=zone.range_hr[1] if zone.range_hr else None,
            midpoint_hr=zone.midpoint_hr,
            midpoint_ve=zone.midpoint_ve,
            range_ve=zone.range_ve,
            sources=["VE"],
            method=zone.method,
        )

    # =========================================================
    # SmO₂ MODULATION (not detection!)
    # SmO₂ is a LOCAL signal - it can only CONFIRM or QUESTION VT
    # SmO₂ does NOT create independent thresholds
    # =========================================================
    if smo2_result and result.vt1:
        result.conflicts.signals_analyzed.append("SmO2 (LOCAL)")

        # Check if SmO₂ shows a drop near VT1
        smo2_drop_power = _find_smo2_drop_power(smo2_result)

        if smo2_drop_power is not None:
            vt1_mid = result.vt1.midpoint_watts
            deviation = smo2_drop_power - vt1_mid
            result.smo2_deviation_vt1 = deviation

            # SmO₂ MODULATES VT based on agreement
            if abs(deviation) <= 10:
                # SmO₂ CONFIRMS VT → boost confidence, narrow range
                result.vt1.confidence = min(0.95, result.vt1.confidence + 0.15)
                # Narrow the range (higher certainty)
                shrink = 0.1
                mid = result.vt1.midpoint_watts
                width = result.vt1.width_watts
                result.vt1.lower_watts = mid - width * (0.5 - shrink)
                result.vt1.upper_watts = mid + width * (0.5 - shrink)
                result.vt1.sources.append("SmO2 ✓")
                result.integration_notes.append(
                    f"✓ SmO₂ (LOCAL) potwierdza VT1 (różnica: {deviation:.0f} W) → confidence +0.15"
                )
            elif abs(deviation) <= 20:
                # SmO₂ slightly off → minor confidence reduction
                result.vt1.confidence = max(0.3, result.vt1.confidence - 0.05)
                result.integration_notes.append(
                    f"ℹ️ SmO₂ (LOCAL) bliski VT1 (różnica: {deviation:.0f} W) → confidence -0.05"
                )
            else:
                # SmO₂ significantly different → conflict, reduce confidence
                conflict_type = ConflictType.SMO2_EARLY if deviation < 0 else ConflictType.SMO2_LATE
                result.conflicts.conflicts.append(
                    SignalConflict(
                        conflict_type=conflict_type,
                        severity=ConflictSeverity.WARNING,
                        signal_a="SmO2 (LOCAL)",
                        signal_b="VE",
                        description=f"SmO₂ (LOCAL) różni się od VT1 o {deviation:.0f} W",
                        physiological_interpretation=(
                            "SmO₂ jest sygnałem LOKALNYM (jeden mięsień). "
                            "Rozbieżność z VT może oznaczać różnicę między lokalną a systemową odpowiedzią."
                        ),
                        magnitude=abs(deviation),
                        confidence_penalty=0.15,
                    )
                )
                result.vt1.confidence = max(0.3, result.vt1.confidence - 0.1)
                # Widen the range (lower certainty)
                expand = 0.15
                mid = result.vt1.midpoint_watts
                width = result.vt1.width_watts
                result.vt1.lower_watts = mid - width * (0.5 + expand)
                result.vt1.upper_watts = mid + width * (0.5 + expand)
                result.integration_notes.append(
                    f"⚠️ SmO₂ (LOCAL) konflikt z VT1: {deviation:.0f} W → confidence -0.1, range +15%"
                )
        else:
            # No SmO₂ drop detected → cannot modulate, note this
            result.integration_notes.append(
                "ℹ️ SmO₂ (LOCAL): brak wyraźnego spadku - brak modulacji VT"
            )

    # Calculate agreement score
    if result.conflicts.conflicts:
        total_penalty = sum(c.confidence_penalty for c in result.conflicts.conflicts)
        result.conflicts.agreement_score = max(0.0, 1.0 - total_penalty)
    else:
        result.conflicts.agreement_score = 1.0

    return result


def _find_smo2_drop_power(smo2_result: StepSmO2Result) -> Optional[float]:
    """
    Find the power at which SmO₂ shows a significant drop.

    This is NOT a threshold - it's just a reference point for VT modulation.
    Returns midpoint if zone exists, else None.
    """
    if smo2_result.smo2_1_zone:
        return smo2_result.smo2_1_zone.midpoint_watts
    return None


# ============================================================
# STEP 5: BUILD RESULT WITH CONFIDENCE
# ============================================================


def build_result(
    validity: TestValidity,
    preprocessed: PreprocessedData,
    analysis: IndependentAnalysisResults,
    integration: IntegrationResult,
    test_date: str = "",
    protocol: str = "Ramp Test",
    cp_watts: Optional[float] = None,
    w_prime_joules: Optional[float] = None,
    smo2_manual_lt1: Optional[float] = None,
    smo2_manual_lt2: Optional[float] = None,
    mmp_curve: Optional[Dict[int, float]] = None,
    rider_weight: Optional[float] = None,
    max_hr: Optional[float] = None,
    smo2_manual_lt1_hr: Optional[float] = None,
    smo2_manual_lt2_hr: Optional[float] = None,
) -> RampTestResult:
    """
    Step 5: Build final RampTestResult with overall confidence.

    Combines:
    - Test validity
    - Integrated thresholds
    - Conflict report
    - Overall confidence calculation

    Returns:
        RampTestResult ready for report generation
    """
    result = RampTestResult(
        validity=validity,
        vt1=integration.vt1,
        vt2=integration.vt2,
        conflicts=integration.conflicts,
        test_date=test_date,
        protocol=protocol,
        detailed_step_analysis={"vt": analysis.vt_result, "smo2": analysis.smo2_result},
        cp_watts=cp_watts,
        w_prime_joules=w_prime_joules,
        smo2_manual_lt1=smo2_manual_lt1,
        smo2_manual_lt2=smo2_manual_lt2,
        smo2_manual_lt1_hr=smo2_manual_lt1_hr,
        smo2_manual_lt2_hr=smo2_manual_lt2_hr,
        mmp_curve=mmp_curve,
        rider_weight=rider_weight,
        max_hr=max_hr,
    )

    # Add SmO2 context (LOCAL signal - for information only, not as threshold)
    # SmO₂ already modulated VT in integrate_signals()
    if analysis.smo2_result:
        smo2 = analysis.smo2_result
        # Store SmO₂ drop info for reference (NOT as independent threshold)
        if smo2.smo2_1_zone:
            result.smo2_lt1 = ThresholdRange(
                lower_watts=smo2.smo2_1_zone.range_watts[0],
                upper_watts=smo2.smo2_1_zone.range_watts[1],
                midpoint_watts=smo2.smo2_1_zone.midpoint_watts,
                confidence=smo2.smo2_1_zone.confidence,
                sources=["SmO2 (LOCAL)"],
                method="local_signal_reference",  # NOT a threshold
            )
        if smo2.smo2_2_zone:
            result.smo2_lt2 = ThresholdRange(
                lower_watts=smo2.smo2_2_zone.range_watts[0],
                upper_watts=smo2.smo2_2_zone.range_watts[1],
                midpoint_watts=smo2.smo2_2_zone.midpoint_watts,
                confidence=smo2.smo2_2_zone.confidence,
                sources=["SmO2 (LOCAL)"],
                method="local_signal_reference",
            )
        result.smo2_deviation_from_vt = integration.smo2_deviation_vt1

        # Interpretation explicitly marks LOCAL signal role
        if integration.smo2_deviation_vt1 is not None:
            if abs(integration.smo2_deviation_vt1) <= 10:
                result.smo2_interpretation = "SmO₂ (LOCAL) potwierdza VT → confidence zwiększone"
            elif abs(integration.smo2_deviation_vt1) <= 20:
                result.smo2_interpretation = "SmO₂ (LOCAL) bliski VT → niewielka korekta"
            elif integration.smo2_deviation_vt1 < 0:
                result.smo2_interpretation = (
                    "SmO₂ (LOCAL) reaguje wcześniej niż VT → lokalna odpowiedź"
                )
            else:
                result.smo2_interpretation = (
                    "SmO₂ (LOCAL) reaguje później niż VT → dobra rezerwa lokalna"
                )

    # Calculate overall confidence
    confidence_factors = []

    # Test validity factor
    if validity.validity == ValidityLevel.VALID:
        confidence_factors.append(1.0)
    elif validity.validity == ValidityLevel.CONDITIONAL:
        confidence_factors.append(0.7)
    else:
        confidence_factors.append(0.3)

    # VT1 confidence
    if result.vt1:
        confidence_factors.append(result.vt1.confidence)

    # Agreement score
    confidence_factors.append(integration.conflicts.agreement_score)

    # Calculate overall
    if confidence_factors:
        result.overall_confidence = sum(confidence_factors) / len(confidence_factors)
    else:
        result.overall_confidence = 0.0

    # Collect notes
    result.analysis_notes = (
        preprocessed.preprocessing_notes + analysis.analysis_notes + integration.integration_notes
    )

    # Add warnings from validity
    result.warnings = validity.issues.copy()

    return result


# ============================================================
# MAIN PIPELINE FUNCTION
# ============================================================


def run_ramp_test_pipeline(
    df: pd.DataFrame,
    power_column: str = "watts",
    hr_column: str = "hr",
    ve_column: str = "tymeventilation",
    smo2_column: str = "smo2",
    time_column: str = "time",
    test_date: str = "",
    protocol: str = "Ramp Test",
    cp_watts: Optional[float] = None,
    w_prime_joules: Optional[float] = None,
    smo2_manual_lt1: Optional[float] = None,
    smo2_manual_lt2: Optional[float] = None,
    rider_weight: Optional[float] = None,
    max_hr: Optional[float] = None,
) -> RampTestResult:
    """
    Run complete Ramp Test analysis pipeline.

    Steps:
    1. validate_test() - Check validity
    2. preprocess_signals() - Clean data
    3. analyze_signals_independently() - Per-signal detection
    4. integrate_signals() - Combine results
    5. build_result() - Create final result

    Args:
        df: DataFrame with test data
        power_column: Column name for power
        hr_column: Column name for HR
        ve_column: Column name for ventilation
        smo2_column: Column name for SmO2
        time_column: Column name for time
        test_date: Date of test (for report)
        protocol: Protocol name (for report)

    Returns:
        RampTestResult with full analysis
    """
    # Step 1: Validate test
    validity = validate_test(
        df, power_column=power_column, hr_column=hr_column, time_column=time_column
    )

    # Early exit if invalid
    if validity.validity == ValidityLevel.INVALID:
        print(f"[Pipeline] Test INVALID: {validity.issues}")
        return RampTestResult(validity=validity, overall_confidence=0.0, warnings=validity.issues)

    # Step 2: Preprocess signals
    preprocessed = preprocess_signals(
        df,
        power_column=power_column,
        hr_column=hr_column,
        ve_column=ve_column,
        smo2_column=smo2_column,
        time_column=time_column,
    )

    # Step 3: Analyze signals independently
    analysis = analyze_signals_independently(
        preprocessed,
        power_column=power_column,
        hr_column=hr_column,
        ve_column=ve_column,
        smo2_column=smo2_column,
        time_column=time_column,
    )

    # Step 4: Integrate signals
    integration = integrate_signals(analysis)

    # Step 5: Build final result
    # Calculate MMP curve (PDC)
    mmp_curve = calculate_power_duration_curve(preprocessed.df)

    # Calculate HR for manual thresholds
    smo2_manual_lt1_hr = None
    smo2_manual_lt2_hr = None

    if not preprocessed.df.empty:
        df_p = preprocessed.df
        p_col = power_column if power_column in df_p.columns else "watts"
        h_col = hr_column if hr_column in df_p.columns else "hr"

        if p_col in df_p.columns and h_col in df_p.columns:
            if smo2_manual_lt1 is not None:
                try:
                    idx = (df_p[p_col] - smo2_manual_lt1).abs().idxmin()
                    smo2_manual_lt1_hr = float(df_p.loc[idx, h_col])
                except Exception as e:
                    logger.debug(f"Failed to find LT1 HR: {e}")

            if smo2_manual_lt2 is not None:
                try:
                    idx = (df_p[p_col] - smo2_manual_lt2).abs().idxmin()
                    smo2_manual_lt2_hr = float(df_p.loc[idx, h_col])
                except Exception as e:
                    logger.debug(f"Failed to find LT2 HR: {e}")

    result = build_result(
        validity=validity,
        preprocessed=preprocessed,
        analysis=analysis,
        integration=integration,
        mmp_curve=mmp_curve,
        test_date=test_date,
        protocol=protocol,
        cp_watts=cp_watts,
        w_prime_joules=w_prime_joules,
        smo2_manual_lt1=smo2_manual_lt1,
        smo2_manual_lt2=smo2_manual_lt2,
        smo2_manual_lt1_hr=smo2_manual_lt1_hr,
        smo2_manual_lt2_hr=smo2_manual_lt2_hr,
        rider_weight=rider_weight,
        max_hr=max_hr,
    )

    return result


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Pipeline steps
    "validate_test",
    "preprocess_signals",
    "analyze_signals_independently",
    "integrate_signals",
    "build_result",
    # Main function
    "run_ramp_test_pipeline",
    # Data containers
    "PreprocessedData",
    "IndependentAnalysisResults",
    "IntegrationResult",
]
