# Backend Implementation Plan

Event-sourced meal-tracking backend (FastAPI + Python).

## Architecture decisions (confirmed)

- **Persistence & domain via event sourcing.** State is derived from an append-only
  log of domain events; the current state is never mutated in place.
- **Event store: SQLite**, single append-only `events` table.
- **Aggregate boundary: one stream per meal.** Lifecycle:
  `MealStarted → FoodItemAdded* → MealConcluded`.
- **Read side: in-memory projections**, rebuilt by replaying all events on startup
  and updated as new events are appended.
- **Recording API is incremental**: start → add food (repeatable) → conclude.
- **OpenFoodFacts (OFF) integration** for nutrition:
  - **Text-search lookup** — adding a food searches OFF by name; the client
    returns candidate products to choose from.
  - **Snapshot into the event** — the chosen product's nutriments + Nutri-Score
    grade are stored inside the `FoodItemAdded` event, so meals stay immutable
    and self-contained even if OFF data later changes.
  - **Graceful degradation** — if OFF is unavailable or no product matches, the
    food is still recorded with null nutrition; recording is never blocked.

## Assumptions (defaults chosen — change if wrong)

- **Single-user, no auth.** One implicit user; no accounts/login.
- **Food item = name + a measure** (either a `quantity` count or a `weight` in
  grams — one of the two, mirroring the README) **+ optional snapshotted OFF
  nutrition** (nutriments, Nutri-Score grade, OFF product id).
- **Meal-type inference uses fixed default time windows** (server-side, at meal
  start): breakfast 05:00–11:00, lunch 11:00–15:00, dinner 18:00–22:00, else snack.
  Inferred type is overridable per meal. Windows are constants for now.

---

## 1. Project scaffolding & dependencies

- [x] Add deps to `pyproject.toml`: `pydantic` (already via FastAPI),
      `pydantic-settings` for config, `httpx` for the OpenFoodFacts client
      (already a dev dep — promote to a runtime dep). No ORM — use `sqlite3` from
      stdlib to keep the event store explicit.
- [ ] Add `pytest` fixtures for an isolated (in-memory / temp-file) event store per test.
- [ ] Settings module (`src/nutriscore/config.py`): DB path, meal-time windows,
      OFF base URL and request timeout.

## 2. Domain layer (`src/nutriscore/domain/`)

- [ ] Define domain events as immutable Pydantic models:
      `MealStarted(meal_id, meal_type, started_at)`,
      `FoodItemAdded(meal_id, name, quantity | weight_grams, nutrition, added_at)`,
      `MealConcluded(meal_id, concluded_at)`.
- [ ] `NutritionInfo` value object (nutriments: energy/macros, `nutri_score_grade`,
      `off_product_id`) — nullable on `FoodItemAdded` for graceful degradation.
- [ ] `Meal` aggregate: `apply(event)` fold + command handlers that validate
      invariants and return new events:
      - `start_meal(now)` → infers `meal_type` from time windows.
      - `add_food(...)` → rejected if meal not started or already concluded;
        accepts an optional pre-resolved `NutritionInfo`.
      - `conclude()` → rejected if not started or already concluded.
- [ ] Meal-type inference function (pure, unit-tested against window boundaries).
- [ ] Errors: `MealNotFound`, `MealAlreadyConcluded`, `InvalidCommand`.

## 3. Event store (`src/nutriscore/eventstore/`)

- [ ] SQLite schema: `events(id INTEGER PK, stream_id TEXT, seq INTEGER,
      event_type TEXT, payload JSON, recorded_at TEXT)` with a
      `UNIQUE(stream_id, seq)` constraint for optimistic concurrency.
- [ ] `append(stream_id, expected_seq, events)` — atomic, fails on seq conflict.
- [ ] `load_stream(stream_id)` — events for one meal, ordered by seq.
- [ ] `load_all()` — all events ordered by global `id` (for projection rebuild).
- [ ] (De)serialization between event models (incl. nested `NutritionInfo`) and
      stored JSON rows.

## 4. OpenFoodFacts client (`src/nutriscore/openfoodfacts/`)

- [ ] Async `httpx` client wrapping the OFF **search API**;
      `search_products(name)` → list of candidate products (name, brand, id).
- [ ] Map an OFF product response → `NutritionInfo` (extract `nutriments` +
      `nutriscore_grade` + product id).
- [ ] Timeout + error handling that degrades to `None` (never raises into the
      recording flow); log failures.
- [ ] Define as a small interface/protocol and inject it as a dependency so tests
      can supply a fake without hitting the network.

## 5. Application / command service (`src/nutriscore/app_service.py`)

- [ ] Repository that loads a meal stream, rehydrates the aggregate, runs a
      command, and appends resulting events with the expected seq.
- [ ] Command handlers: `start_meal`, `add_food_to_meal`, `conclude_meal`.
- [ ] `add_food_to_meal` optionally resolves nutrition via the OFF client (when a
      product id/selection is supplied) and snapshots it into the event; falls
      back to null nutrition on lookup failure.
- [ ] After append, push new events to the projection registry.

## 6. Read models / projections (`src/nutriscore/projections/`)

- [ ] `MealsProjection` — list of meals with type, timestamps, status, item count.
- [ ] `MealDetailProjection` — full food list per meal with per-food nutrition,
      plus meal-level nutriment totals / aggregate Nutri-Score (drill-down by meal).
- [ ] `FoodProjection` — group by food name across meals (drill-down by food).
- [ ] Projection registry: `rebuild(load_all)` on startup + `handle(event)` on append.
- [ ] Keep projections in memory (dicts); document the trade-off (rebuild cost
      grows with event count — revisit persisted projections later).

## 7. HTTP API (`src/nutriscore/main.py` + routers)

Command endpoints (write side):
- [ ] `POST /meals` → start a meal; returns `{meal_id, meal_type, started_at}`.
- [ ] `POST /meals/{meal_id}/foods` → add a food item (name + measure, optional
      selected OFF product id to snapshot nutrition).
- [ ] `POST /meals/{meal_id}/conclude` → conclude the meal.

Lookup endpoint:
- [ ] `GET /foods/search?q=` → OFF text-search candidates to pick before adding.

Query endpoints (read side, served from projections):
- [ ] `GET /meals` → list meals (optional date/type filters).
- [ ] `GET /meals/{meal_id}` → meal detail with food items + nutrition.
- [ ] `GET /foods` → foods eaten, aggregated across meals.
- [ ] `GET /foods/{name}` → meals in which a food appears.

- [ ] Request/response Pydantic schemas separate from domain events.
- [ ] Map domain errors to HTTP status codes (404, 409 conflict, 422 validation).
- [ ] Wire event store + projections + OFF client into app startup (FastAPI
      lifespan); keep `/hello` or drop it.

## 8. Testing

- [ ] Domain unit tests: aggregate command → event outcomes, invariant rejections,
      meal-type inference boundaries (pure, no I/O).
- [ ] Event store tests: append/load round-trip (incl. nutrition payload),
      optimistic-concurrency conflict.
- [ ] OFF client tests with a stubbed HTTP layer: parse a sample response →
      `NutritionInfo`; degrade to `None` on error / not-found.
- [ ] Projection tests: replay a known event sequence → expected read model
      (including meal-level nutrition totals).
- [ ] API tests via `TestClient` with a fake OFF client: full record flow
      (search → start → add → conclude → query), and error paths (add to
      concluded meal, unknown meal, OFF unavailable → food added without nutrition).

## 9. Docs

- [ ] Update `README.md` and `CLAUDE.md` with the event-sourced architecture,
      OpenFoodFacts integration, new endpoints, and the run/test commands.

---

## Suggested build order

1. Domain layer (§2) — pure, fast to test, defines the events.
2. Event store (§3).
3. OpenFoodFacts client (§4).
4. Application service (§5) wiring domain + store + OFF.
5. Projections (§6).
6. HTTP API (§7) on top.
7. Tests throughout (§8); docs last (§9).
