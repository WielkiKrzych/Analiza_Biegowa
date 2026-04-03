# Architecture

## Project Overview

Tri_Dashboard is a Streamlit-based dashboard for running and cycling physiological analysis. It processes CSV/FIT training data to compute metrics like ventilatory thresholds (VT1/VT2), heart rate variability (HRV), SmO2 kinetics, running dynamics, and more.

## Architecture Diagram

```
app.py (Streamlit entry point)
  |
  +-- modules/frontend/     Theme, layout, state management
  +-- modules/ui/           29 tab/view components (running, smo2, vent, etc.)
  +-- services/             Business logic orchestration
  |     +-- session_orchestrator.py   Main pipeline (data load -> metrics -> results)
  |     +-- session_analysis.py       Session-level analysis
  |     +-- data_validation.py        Input validation
  |
  +-- modules/calculations/  43+ calculation modules
  |     +-- pace.py, d_prime.py, ventilatory.py, hrv.py, smo2_advanced.py, ...
  |
  +-- modules/db/            SQLite persistence (SessionStore)
  +-- modules/reporting/     PDF report generation
  +-- models/                Domain types (Result objects, dataclasses)
  +-- signals/               Signal/slot pattern for UI updates
```

## Key Dependencies

| Package | Purpose |
|---------|---------|
| Streamlit | UI framework |
| pandas | Data manipulation |
| polars | Fast I/O and data loading |
| plotly | Interactive charts |
| scipy | Scientific computing (signal processing, statistics) |
| numpy | Numerical computing |
| numba | JIT compilation for performance-critical paths |
| neurokit2 | Physiological signal processing |
| python-dotenv | Environment configuration |

## Directory Structure

```
Analiza_Biegowa/
  app.py                    Streamlit entry point
  pyproject.toml            Project config and dependencies
  modules/
    calculations/           43+ computational modules
    ui/                     29 UI view components
    frontend/               Theme, layout, state
    domain/                 Domain types
    db/                     SQLite persistence
    reporting/              PDF generation
    ai/                     ML/AI features
  services/                 Business logic orchestration
  models/                   Domain result objects
  signals/                  Signal/slot pattern
  scripts/                  Utility scripts (init_db, train_history)
  tests/                    Test suite
  docs/                     Documentation
  methodology/              Physiological methodology notes
```

## Test Coverage

Tests are in `tests/` and run with `pytest -q`. Currently 66 tests covering calculations, data validation, session store, and settings. Coverage can be checked with `pytest --cov=modules tests/`.
