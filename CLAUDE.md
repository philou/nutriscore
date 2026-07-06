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
uv run pytest tests/test_api.py::test_full_recording_flow  # run a single test
uv run uvicorn nutriscore.main:app --reload --app-dir src  # run dev server on :8000
```

There is no linter/formatter configured yet.

## Architecture

The backend is **event-sourced**. State is derived by folding an append-only log of
domain events; nothing is mutated in place.

- **src layout**: application code lives under `src/nutriscore/`; the package is installed
  in editable mode by `uv sync`. `pyproject.toml` sets `pythonpath = ["src"]` for pytest and
  `--app-dir src` is required when running uvicorn, so tests and imports use
  `from nutriscore... import`.
- **`domain/`** — pure, no I/O. Frozen Pydantic events (`MealStarted`, `FoodItemAdded`,
  `MealConcluded`) and the `Meal` aggregate whose command methods validate invariants and
  *return* new events. `infer_meal_type` maps time-of-day to a meal type using the windows
  in `config.py`. Domain errors live in `domain/errors.py`.
- **`eventstore/`** — `SqliteEventStore`: one append-only `events` table, one stream per
  meal (`stream_id` = meal id), `UNIQUE(stream_id, seq)` + expected-sequence checks for
  optimistic concurrency. `load_all()` replays the whole log for projection rebuild.
- **`openfoodfacts/`** — async `httpx` client behind the `NutritionSource` protocol
  (text search + nutrition lookup). Network failures degrade to `[]`/`None`; never raise
  into the recording flow. Inject a fake in tests.
- **`projections/`** — in-memory read models (`Projections`) rebuilt on startup and updated
  as events are appended. Serve the query endpoints.
- **`app_service.py`** — `MealService` (write side): rehydrate a meal from its stream, run a
  command, append the resulting event(s), forward them to projections. `add_food` snapshots
  OFF nutrition into the `FoodItemAdded` event.
- **`main.py`** — `create_app(...)` wires store + projections + OFF client into the service
  via a FastAPI lifespan (`app.state.service`); `create_app` accepts an injected store and
  nutrition source for tests. `app = create_app()` is the uvicorn entrypoint.
- **Tests** (`tests/`) use `TestClient` (as a context manager, so lifespan runs) with a fake
  nutrition source; other layers are tested in isolation. `conftest.py` provides an isolated
  per-test SQLite `db_path`.

## Conventions

- Command endpoints return operation results; query endpoints return projection read models.
- Domain errors map to HTTP status at the API boundary: `MealNotFound`→404,
  `MealAlreadyConcluded`/`ConcurrencyError`→409, `InvalidCommand`→422.
- A food carries exactly one measure: `quantity` **or** `weight_grams` (enforced in the
  aggregate).
