# Test Coverage Report

**Date:** 2026-04-03
**Project:** Analiza_Biegowa
**Tests:** 321 passed, 0 failed
**Overall Coverage:** **7%** (1,136 / 17,355 statements)

---

## Summary

The project has 321 passing tests but only 7% overall code coverage. Tests are heavily concentrated in a few modules (signals, data validation, session store) while the vast majority of the codebase — particularly UI, reporting, and advanced calculations — has zero coverage.

---

## Per-Module Coverage

### Calculations (`modules/calculations/`)

| File | Stmts | Miss | Cover |
|------|------:|-----:|------:|
| `common.py` | 43 | 5 | **88%** |
| `d_prime.py` | 59 | 10 | **83%** |
| `pace_utils.py` | 41 | 13 | **68%** |
| `dual_mode.py` | 52 | 14 | **73%** |
| `repeatability.py` | 62 | 17 | **73%** |
| `pace.py` | 185 | 85 | **54%** |
| `gap.py` | 30 | 15 | **50%** |
| `threshold_types.py` | 192 | 69 | **64%** |
| `pipeline.py` | 249 | 146 | **41%** |
| `kinetics.py` | 249 | 141 | **43%** |
| `race_predictor.py` | 103 | 72 | **30%** |
| `w_prime.py` | 67 | 54 | **19%** |
| `running_dynamics.py` | 135 | 111 | **18%** |
| `power.py` | 109 | 92 | **16%** |
| `polars_adapter.py` | 138 | 116 | **16%** |
| `interpretation.py` | 121 | 102 | **16%** |
| `data_processing.py` | 73 | 65 | **11%** |
| `quality.py` | 64 | 57 | **11%** |
| `nutrition.py` | 56 | 49 | **12%** |
| `metrics.py` | 170 | 157 | **8%** |
| `hrv.py` | 306 | 282 | **8%** |
| `thermal.py` | 165 | 152 | **8%** |
| `stamina.py` | 93 | 85 | **9%** |
| `step_detection.py` | 93 | 86 | **8%** |
| `ventilatory_step.py` | 181 | 170 | **6%** |
| `thresholds.py` | 78 | 71 | **9%** |
| `metabolic.py` | 107 | 101 | **6%** |
| `ventilatory_cpet.py` | 531 | 517 | **3%** |
| `async_runner.py` | 74 | 49 | **34%** |
| `_smo2_utils.py` | 42 | 42 | **0%** |
| `biomech_occlusion.py` | 98 | 98 | **0%** |
| `br_analysis.py` | 97 | 97 | **0%** |
| `canonical_physio.py` | 135 | 135 | **0%** |
| `cardiac_drift.py` | 164 | 164 | **0%** |
| `cardio_advanced.py` | 199 | 199 | **0%** |
| `conflicts.py` | 118 | 118 | **0%** |
| `durability.py` | 119 | 119 | **0%** |
| `executive_summary.py` | 227 | 227 | **0%** |
| `gas_exchange_estimation.py` | 70 | 70 | **0%** |
| `hr_zones.py` | 128 | 128 | **0%** |
| `metabolic_engine.py` | 155 | 155 | **0%** |
| `report_generator.py` | 148 | 148 | **0%** |
| `running_effectiveness.py` | 86 | 86 | **0%** |
| `smo2_advanced.py` | 3 | 3 | **0%** |
| `smo2_analysis.py` | 175 | 175 | **0%** |
| `smo2_breakpoints.py` | 152 | 152 | **0%** |
| `smo2_phases.py` | 109 | 109 | **0%** |
| `smo2_thresholds.py` | 262 | 262 | **0%** |
| `thermoregulation.py` | 117 | 117 | **0%** |
| `trend_engine.py` | 179 | 179 | **0%** |
| `vent_advanced.py` | 190 | 190 | **0%** |
| `version.py` | 15 | 15 | **0%** |

### Top-Level Modules

| File | Stmts | Miss | Cover |
|------|------:|-----:|------:|
| `config.py` | 74 | 10 | **86%** |
| `settings.py` | 18 | 7 | **61%** |
| `numba_utils.py` | 146 | 118 | **19%** |
| `utils.py` | 217 | 217 | **0%** |
| `tte.py` | 176 | 176 | **0%** |
| `chart_exporters.py` | 300 | 300 | **0%** |
| `canonical_values.py` | 97 | 97 | **0%** |
| `task_queue.py` | 135 | 135 | **0%** |
| `training_load.py` | 78 | 78 | **0%** |
| `health_alerts.py` | 119 | 119 | **0%** |
| `genetics.py` | 120 | 120 | **0%** |
| `ml_logic.py` | 188 | 188 | **0%** |
| `monitoring.py` | 144 | 144 | **0%** |
| `environment.py` | 83 | 83 | **0%** |
| `history_import.py` | 92 | 92 | **0%** |
| `intervals.py` | 49 | 49 | **0%** |
| `manual_overrides.py` | 39 | 39 | **0%** |
| `notes.py` | 45 | 45 | **0%** |
| `physio_maps.py` | 180 | 180 | **0%** |
| `plots.py` | 7 | 7 | **0%** |
| `reports.py` | 135 | 135 | **0%** |
| `time_formatting.py` | 33 | 33 | **0%** |

### Database & Domain

| File | Stmts | Miss | Cover |
|------|------:|-----:|------:|
| `db/session_store.py` | 91 | 3 | **97%** |
| `domain/session_type.py` | 219 | 219 | **0%** |

### Reporting (`modules/reporting/`)

All reporting modules have **0%** coverage.

| File | Stmts |
|------|------:|
| `pdf/layout.py` | 840 |
| `persistence_save.py` | 287 |
| `pdf/builder.py` | 289 |
| `summary_export.py` | 116 |
| `pdf/summary_pdf.py` | 265 |
| `persistence_pdf.py` | 123 |
| `figures/drift.py` | 153 |
| `figures/limiters.py` | 136 |
| `pdf/layout_executive_verdict.py` | 202 |

### UI (`modules/ui/`)

All UI modules have **0%** coverage. Largest files:

| File | Stmts |
|------|------:|
| `biomech.py` | 303 |
| `running.py` | 257 |
| `smo2.py` | 221 |
| `limiters.py` | 189 |
| `summary_charts.py` | 198 |
| `vent_charts.py` | 171 |
| `summary_timeline.py` | 168 |
| `threshold_analysis_ui.py` | 145 |
| `hrv.py` | 137 |

---

## Top 5 Files That Would Benefit Most from Tests

| # | File | Stmts | Current | Impact |
|---|------|------:|--------:|--------|
| 1 | `calculations/ventilatory_cpet.py` | 531 | 3% | Core VT1/VT2 detection logic |
| 2 | `reporting/pdf/layout.py` | 840 | 0% | PDF generation — split into testable helpers |
| 3 | `calculations/hrv.py` | 306 | 8% | HRV/DFA analysis — physiological accuracy |
| 4 | `calculations/cardio_advanced.py` | 199 | 0% | Advanced cardiac metrics |
| 5 | `calculations/executive_summary.py` | 227 | 0% | Summary generation — data correctness |

---

## Recommendations

### Priority 1: Core Calculations (highest ROI)

These modules contain critical physiological calculations. Bugs here directly affect analysis accuracy.

- **`ventilatory_cpet.py`** (3%): Add tests for VT1/VT2 detection with synthetic CPET data
- **`hrv.py`** (8%): Test DFA computation, HRVT detection thresholds
- **`cardio_advanced.py`** (0%): Test HR recovery, cardiac drift calculations
- **`metrics.py`** (8%): Test RSS, TRIMP, IF computations
- **`metabolic.py`** (6%): Test VO2 estimation, metabolic cost

### Priority 2: Data Pipeline

- **`data_processing.py`** (11%): Test resampling, cleaning, column normalization
- **`polars_adapter.py`** (16%): Test I/O roundtrips, format handling
- **`quality.py`** (11%): Test data quality scoring

### Priority 3: Business Logic

- **`domain/session_type.py`** (0%): Test session classification logic
- **`canonical_values.py`** (0%): Test canonical column mapping
- **`utils.py`** (0%): Test utility functions

### Priority 4: Reporting (defer)

PDF/layout modules are large but mostly presentation logic. Consider:
- Extract pure computation from `layout.py` into testable functions
- Mock Plotly/chart rendering in figure tests
- Focus on `persistence_save.py` and `persistence_load.py` (data serialization)

### Priority 5: UI (lowest priority)

Streamlit UI components are hard to unit test and change frequently. Accept low coverage here. If needed, use component-level tests with `streamlit-testing-library`.

---

## Test Distribution by Suite

| Test Suite | Tests | Primary Module Covered |
|-----------|------:|------------------------|
| `test_signal_modules.py` | 120 | Signal processing |
| `test_signals.py` | 47 | Signal types |
| `db/test_session_store.py` | 49 | DB session store |
| `services/test_data_validation.py` | 30 | Data validation |
| `reporting/test_persistence.py` | 32 | Persistence layer |
| `calculations/test_pipeline.py` | 12 | Calculation pipeline |
| `calculations/test_pace.py` | 7 | Pace calculations |
| `calculations/test_pace_utils.py` | 6 | Pace utilities |
| `calculations/test_d_prime.py` | 5 | D' model |
| `integration/test_running_pipeline.py` | 5 | End-to-end pipeline |
| `test_settings_running.py` | 3 | Settings |
| Others | 5 | Various |

---

## How to Reproduce

```bash
cd /Users/wielkikrzychmbp/Documents/Analiza_Biegowa
python3 -m pytest --cov=modules --cov-report=term-missing --cov-report=html -q
# HTML report: open htmlcov/index.html
```
