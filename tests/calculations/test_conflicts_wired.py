"""
Regression tests for `modules.calculations.conflicts.detect_conflicts()`.

These tests document the expected behavior of the conflict detector BEFORE
it is wired into `modules.calculations/pipeline.py:integrate_signals()` (Phase 0,
step 0.2 of the v2 audit plan). They will keep catching regressions if the
wiring is wrong or the detector drifts.

References:
- Audit report v2, §6 P0-1 (wire up `modules/calculations/conflicts.py`)
- `modules/calculations/conflicts.py:detect_conflicts` (line 96)
- `modules/calculations/conflicts.py:CONFLICT_DESCRIPTIONS` (line 24)
- `models/results.py` for `SignalConflict`, `ConflictReport` dataclasses
"""

from models.results import ConflictSeverity, ConflictType
from modules.calculations.conflicts import detect_conflicts
from modules.calculations.threshold_types import (
    StepSmO2Result,
    StepVTResult,
    TransitionZone,
)


def _make_vt1_zone(midpoint: float, width: float = 20.0) -> TransitionZone:
    """Helper: build a TransitionZone whose midpoint_watts == `midpoint`."""
    half = width / 2.0
    return TransitionZone(
        range_watts=(midpoint - half, midpoint + half),
        confidence=0.7,
        stability_score=0.7,
        method="VE",
    )


def _make_vt(vt1_midpoint: float) -> StepVTResult:
    return StepVTResult(
        vt1_zone=_make_vt1_zone(vt1_midpoint),
        vt1_watts=vt1_midpoint,
    )


def _make_smo2(drop_midpoint: float) -> StepSmO2Result:
    """SmO2 with a detected drop at `drop_midpoint` watts."""
    return StepSmO2Result(
        smo2_1_zone=_make_vt1_zone(drop_midpoint, width=15.0),
        smo2_1_watts=drop_midpoint,
    )


def test_smo2_late_conflict_is_detected_with_40w_deviation():
    """SmO2 dropping 40W AFTER VT1 must produce a SMO2_LATE conflict with PL recommendation."""
    vt = _make_vt(vt1_midpoint=200.0)
    smo2 = _make_smo2(drop_midpoint=240.0)  # 40W after

    report = detect_conflicts(vt_result=vt, smo2_result=smo2, df=None)

    # No exception, no None
    assert report is not None
    assert report.conflicts is not None

    # Find the SMO2_LATE entry
    late = [c for c in report.conflicts if c.conflict_type == ConflictType.SMO2_LATE]
    assert len(late) == 1, (
        f"Expected exactly one SMO2_LATE conflict for 40W late deviation, "
        f"got: {[c.conflict_type for c in report.conflicts]}"
    )

    conflict = late[0]
    # Severity is INFO per conflicts.py:203 (positive finding, not warning)
    assert conflict.severity == ConflictSeverity.INFO
    # Must carry a non-trivial magnitude
    assert conflict.magnitude is not None and conflict.magnitude >= 30.0
    # Penalty per CONFLICT_DESCRIPTIONS SMO2_LATE is 0.05
    assert conflict.confidence_penalty > 0.0
    assert conflict.confidence_penalty <= 0.2
    # Description and interpretation must be non-empty PL strings
    assert len(conflict.description) > 10
    assert len(conflict.physiological_interpretation) > 10

    # Agreement score reflects penalty (1.0 - sum_of_penalties)
    assert 0.0 <= report.agreement_score <= 1.0
    # With at least one penalty, agreement_score must drop below 1.0
    assert report.agreement_score < 1.0

    # Recommendations are PL strings (the detector ships CONFLICT_DESCRIPTIONS['recommendation'])
    assert len(report.recommendations) >= 1
    assert all(isinstance(r, str) and len(r) > 0 for r in report.recommendations)

    # signals_analyzed should mention both VE and SmO2 LOCAL
    assert "VE" in report.signals_analyzed
    assert "SmO2 (LOCAL)" in report.signals_analyzed


def test_smo2_early_conflict_is_detected_with_30w_early_deviation():
    """SmO2 dropping 30W BEFORE VT1 must produce a SMO2_EARLY conflict (severity WARNING)."""
    vt = _make_vt(vt1_midpoint=250.0)
    smo2 = _make_smo2(drop_midpoint=220.0)  # 30W before

    report = detect_conflicts(vt_result=vt, smo2_result=smo2, df=None)

    early = [c for c in report.conflicts if c.conflict_type == ConflictType.SMO2_EARLY]
    assert len(early) == 1
    assert early[0].severity == ConflictSeverity.WARNING
    assert early[0].magnitude is not None and early[0].magnitude >= 25.0
    assert early[0].confidence_penalty > 0.0


def test_no_smo2_vs_vt_conflict_when_deviation_is_small():
    """|deviation| <= 20W must NOT produce SMO2_EARLY or SMO2_LATE (per conflicts.py:184,198)."""
    vt = _make_vt(vt1_midpoint=200.0)
    # 10W deviation - below the 20W threshold in both directions
    smo2 = _make_smo2(drop_midpoint=210.0)

    report = detect_conflicts(vt_result=vt, smo2_result=smo2, df=None)

    conflicting = [
        c
        for c in report.conflicts
        if c.conflict_type in (ConflictType.SMO2_EARLY, ConflictType.SMO2_LATE)
    ]
    assert conflicting == [], (
        f"Expected NO SmO2 vs VT conflict for 10W deviation, got: "
        f"{[(c.conflict_type, c.severity) for c in conflicting]}"
    )
    # And no penalty was applied, so agreement_score stays at 1.0
    assert report.agreement_score == 1.0


def test_smo2_flat_conflict_when_no_drop_detected():
    """If SmO2 detector returns no `smo2_1_zone`, must produce SMO2_FLAT warning."""
    vt = _make_vt(vt1_midpoint=200.0)
    smo2 = StepSmO2Result(smo2_1_zone=None, smo2_1_watts=None)

    report = detect_conflicts(vt_result=vt, smo2_result=smo2, df=None)

    flat = [c for c in report.conflicts if c.conflict_type == ConflictType.SMO2_FLAT]
    assert len(flat) == 1
    assert flat[0].severity == ConflictSeverity.WARNING
    assert flat[0].confidence_penalty > 0.0
    assert "SmO₂" in flat[0].description or "SmO" in flat[0].description


def test_no_conflicts_when_smo2_result_is_none():
    """Detector must not crash and must not invent conflicts if smo2_result is None."""
    vt = _make_vt(vt1_midpoint=200.0)

    report = detect_conflicts(vt_result=vt, smo2_result=None, df=None)

    # SMO2_* conflicts require smo2_result
    smo2_conflicts = [
        c
        for c in report.conflicts
        if c.conflict_type
        in (
            ConflictType.SMO2_EARLY,
            ConflictType.SMO2_LATE,
            ConflictType.SMO2_FLAT,
        )
    ]
    assert smo2_conflicts == []
    # signals_analyzed should NOT include SmO2
    assert "SmO2 (LOCAL)" not in report.signals_analyzed


def test_no_conflicts_when_vt_result_has_no_zone():
    """Detector must early-return if `vt_result.vt1_zone` is None (no SmO2 conflicts)."""
    vt = StepVTResult(vt1_watts=200.0)  # no vt1_zone
    smo2 = _make_smo2(drop_midpoint=240.0)

    report = detect_conflicts(vt_result=vt, smo2_result=smo2, df=None)

    smo2_conflicts = [
        c
        for c in report.conflicts
        if c.conflict_type
        in (
            ConflictType.SMO2_EARLY,
            ConflictType.SMO2_LATE,
            ConflictType.SMO2_FLAT,
        )
    ]
    assert smo2_conflicts == []
