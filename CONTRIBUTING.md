# Contributing

- Use English docstrings for new Python code and PEP 604 type hints.
- Run `ruff check .`, `python3 -m pytest -q --tb=short` and `mypy modules/ services/ --config-file pyproject.toml` before committing.
- Format the files you change with `ruff format`. The optional hooks are in `.pre-commit-config.yaml`.
- Calculate mean pace from speed. Show missing sensor data as missing.
- Keep recorded power as an optional timeline channel. Use pace or speed in running calculations.
- Keep tests independent of real activity files and local notes. Put calculation tests in `tests/calculations/` and upload cases in `tests/integration/`.
