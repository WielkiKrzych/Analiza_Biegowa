# Contributing

## Code style

- **Docstrings: English.** Per audit v2 §6 P3-1, new code must use English
  docstrings. Existing mixed PL/EN docstrings are kept as-is to avoid
  noisy diffs; they are gradually being translated as files are touched
  for other reasons.
- **Type hints: PEP 604.** `int | None` not `Optional[int]`,
  `tuple[pd.DataFrame, ...]` not `Tuple[...]`.
- **Linting: ruff.** Run `ruff check .` before committing. Auto-fix
  with `ruff check --fix .`.
- **Formatting: ruff-format.** `ruff format .` (line length 100,
  target Python 3.10+).
- **Pre-commit hooks:** see `.pre-commit-config.yaml`. Install once
  with `pip install pre-commit && pre-commit install`.

## Testing

- **Test style:** pytest, in `tests/` mirroring the package structure.
  `tests/calculations/test_X.py` for unit tests, `tests/integration/`
  for cross-module flows.
- **Run all tests:** `python3 -m pytest -q` from the project root.
- **Coverage target:** 80%+ for new code. Old code is grandfathered.

## Versioning

- **Bump:** `bump2version patch|minor|major` from the project root.
  See `.bumpversion.cfg`. Each bump updates `pyproject.toml`, commits
  the change, and creates a git tag.
- **Push:** `git push --follow-tags` to publish the tag to the remote.
- **CI:** tags trigger the release workflow (if configured).

## Pull requests

- Branch from `main`.
- One commit per logical change (squash if necessary).
- Reference the audit item (e.g. "Fixes P0-3") or the GitHub issue.
- CI must pass: ruff + pytest on Python 3.10, 3.11, 3.12.

## Project-specific conventions

- **Pace is nonlinear** (sec/km = 1/speed). Always smooth/aggregate
  in the speed domain and convert back, never `.mean()` on `pace`.
- **Power estimation** (`running_power.py`): `P = 1.04 × mass × v_GAP`,
  flagged as `power_is_estimated` when derived from pace alone.
- **SmO₂ is a LOCAL signal** (one muscle group), not systemic. Use
  it to MODULATE ventilatory thresholds, never as a standalone
  threshold source.
- **Default body weight** lives in `Config.DEFAULT_BODY_WEIGHT_KG`.
  All three call sites (sidebar, orchestrator, power estimator) read
  from there. Do not hard-code a default anywhere else.
