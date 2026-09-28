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

Verified 2026-09-28 against `python3 -m ruff check .` (select E,F,I,W,C90,B; ignore E501):

- None. The list previously here was stale — it promised outstanding W293, C901 and
  F841 findings plus invalid `# noqa` directives in `modules/ui/summary.py`, but
  `python3 -m ruff check .` reports "All checks passed!", `python3 -m ruff check
  --select W293,C901,F841 .` reports "All checks passed!", and
  `python3 -m ruff check --select RUF100 modules/ui/summary.py` reports
  "All checks passed!" (no unused `# noqa`).

Open items that are NOT lint findings (tracked here so they stop being re-discovered):

- `modules/cache_utils.py::_hash_arg` collapses lists and dicts to `LIST:<len>` /
  `DICT:<len>`, so two different list values of equal length produce the same cache
  key. Latent only: every `cache_result`-decorated function in that module
  (`cached_analyze_step_test`, `cached_detect_smo2_thresholds`,
  `cached_calculate_cp_wprime`, `cached_generate_summary_pdf`, `cache_1h/24h/7d`)
  currently has no call site in the repo.
- `modules/calculations/time_index.py:38`: `df_pd["time"].isna().any()` cannot be
  true there — the line above already dropped NaN timestamps — so the branch only
  ever fires on the `len(df_pd) == 0` half of the condition.
