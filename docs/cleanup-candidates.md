# Cleanup Candidates

## Phase 1 (Completed)

- [x] Deleted stale branches: `claude/dreamy-dijkstra`, `feature/new-functions`
- [x] Added runtime deprecation warnings to 3 deprecated functions:
  - `modules/ui/header.py::extract_header_data`
  - `modules/calculations/ventilatory.py::detect_vt_vslope_savgol`
  - `modules/calculations/interpretation.py::generate_training_advice`
- [x] Moved legacy scripts to `scripts/` directory (`init_db.py`, `train_history.py`)
- [x] Cleaned up `.claude/worktrees` and `.worktrees` directories
- [x] Ran ruff + isort cleanup on all source files
- [x] Added `isort` to dev dependencies in `pyproject.toml`
- [x] Created `docs/architecture.md`

## Remaining Candidates

- Ruff whitespace warnings in docstrings (W293) across multiple files
- Ruff complexity warnings (C901) for functions exceeding McCabe complexity 10
- Unused variable assignments (F841) in a few calculation modules
- Invalid `# noqa` directives in `modules/ui/summary.py`
