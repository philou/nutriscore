# Backend Implementation Plan — User Stories

Event-sourced meal-tracking backend (FastAPI + Python), built as vertical slices.
Each story cuts through all layers and leaves the system runnable and testable:
every story ends with a working `curl` + a passing API test. The architecture
below is built **just-in-time** by the first story that needs each piece, not
bottom-up all at once. The story order *is* the build order.

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

## Story 0 — Walking skeleton: start a meal

*As a user, I can start a meal and get back an id and the inferred meal type.*

- [ ] `POST /meals` → persists a `MealStarted` event, returns
      `{meal_id, meal_type, started_at}`.
- [ ] Meal type inferred from server time windows (breakfast/lunch/dinner/snack),
      pure function unit-tested against window boundaries.
- [ ] Introduces (minimal): `MealStarted` event, the `start_meal` command, an
      event store that can `append` + `load_stream` for one meal, the FastAPI route,
      app startup wiring (FastAPI lifespan).

**Demo:** `curl -X POST /meals` returns a lunch meal at 13:00. Test asserts the
event was persisted and reloaded. *This is the thinnest end-to-end slice — it
proves the whole pipeline (HTTP → command → SQLite → response) before adding
features.*

## Story 1 — Add food to a meal

*As a user, I can add food items one at a time to a meal in progress.*

- [ ] `POST /meals/{id}/foods` (name + quantity **or** weight; nutrition null for now).
- [ ] Introduces: `FoodItemAdded` event, `Meal` aggregate rehydration (fold events
      → validate → new event), `add_food` invariants (reject if not started /
      already concluded), `MealNotFound` → 404, `MealAlreadyConcluded` → 409.

**Demo:** start a meal, add two foods, reload the stream and see both.

## Story 2 — Conclude a meal

*As a user, I can conclude a meal so it's finalized.*

- [ ] `POST /meals/{id}/conclude` → `MealConcluded`; rejects double-conclude /
      concluding an unstarted meal.

**Demo:** full record flow start → add → add → conclude works; adding after
conclude → 409.

## Story 3 — See my meals

*As a user, I can list the meals I've eaten.*

- [ ] `GET /meals` → served from a `MealsProjection` (type, timestamps, status,
      item count).
- [ ] Introduces the **read side**: `load_all()` on the event store, projection
      rebuilt on startup + updated on append, projection registry.

**Demo:** record a couple meals, `GET /meals` lists them.

## Story 4 — Drill into one meal

*As a user, I can open a meal and see every food I recorded in it.*

- [ ] `GET /meals/{id}` → `MealDetailProjection` (full food list per meal).

**Demo:** the meal from story 3 shows its food items.

## Story 5 — Look up nutrition when adding food

*As a user, when I add a food I can search OpenFoodFacts and attach real nutrition.*

- [ ] `GET /foods/search?q=` → OFF candidates (name, brand, id).
- [ ] `POST /meals/{id}/foods` accepts a selected product id and **snapshots**
      nutriments + Nutri-Score into `FoodItemAdded`.
- [ ] Introduces: the OFF `httpx` client (behind a protocol, faked in tests),
      `NutritionInfo` value object, graceful degradation to null nutrition on OFF
      failure.

**Demo:** search "banana", add it, meal detail now shows energy/macros/grade. The
OFF-down path still records the food.

## Story 6 — Drill down by food

*As a user, I can see a food and every meal it appears in.*

- [ ] `GET /foods` (aggregated across meals) + `GET /foods/{name}`.
- [ ] Introduces `FoodProjection`.

**Demo:** a food recorded across two meals shows both.

## Story 7 — Meal nutrition totals

*As a user, I can see per-meal nutriment totals and an aggregate Nutri-Score.*

- [ ] Extend `MealDetailProjection` with per-meal nutriment totals and an
      aggregate Nutri-Score grade.

**Demo:** meal detail shows summed macros and an overall grade.

---

## Cross-cutting conventions

- Request/response Pydantic schemas kept separate from domain events.
- Domain errors mapped to HTTP status codes (404 not found, 409 conflict,
  422 validation).
- `README.md` and `CLAUDE.md` updated incrementally as endpoints land, not as a
  final doc phase.
- Tests grow per story: domain unit tests (pure), event-store round-trip +
  optimistic concurrency, OFF client with a stubbed HTTP layer, projection replay,
  and end-to-end API tests via `TestClient` with a fake OFF client.
