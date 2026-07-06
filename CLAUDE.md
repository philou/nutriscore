# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Nutriscore is a meal-tracking app (see README for the product vision: record meals
food-by-food, auto-infer meal type from time of day, then browse/drill down by food or
meal).

Backend is Python (FastAPI); frontend is TBD.

## Commands

```bash
uv sync                                                    # install deps + dev deps into .venv
uv run pytest                                              # run all tests
uv run pytest tests/test_hello.py::test_hello_returns_hello_world  # run a single test
uv run uvicorn nutriscore.main:app --reload --app-dir src  # run dev server on :8000
```

There is no linter/formatter configured yet.

## Architecture

- **src layout**: application code lives under `src/nutriscore/`; the package is installed
  in editable mode by `uv sync`. `pyproject.toml` sets `pythonpath = ["src"]` for pytest and
  `--app-dir src` is required when running uvicorn, so tests and imports use
  `from nutriscore... import`.
- **FastAPI app** is the `app` object in `src/nutriscore/main.py`; routes are declared there.
- **Tests** (`tests/`) use FastAPI's `TestClient` against the imported `app` — no running
  server needed. Dev-only deps (pytest, httpx) live in the `[dependency-groups] dev` group.

## Conventions

- Endpoints return plain dicts serialized to JSON. Routes are path-specific (e.g. `/hello`),
  not mounted at root — browsing `/` returns 404 by design.
