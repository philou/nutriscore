# Nutriscore

A simple app to record what you eat, right after each meal.

## Recording workflow

- user starts recording a meal, system will infer whether this meal is breakfast, lunch, dinner or snack based on the time of the day.
- user records one food item at a time, either with a quantity of a weight.
- user concludes the meal, which is persisted.

## Viewing features

- Check the meals you ate.
- Drill down into what you have eaten, per food, or per meal.

## BackEnd

An **event-sourced** REST backend in Python (FastAPI). Meals are recorded
incrementally and every change is an immutable domain event; the current state
(meal list, per-meal detail, per-food history) is derived by folding the event
log into in-memory projections. Events are stored append-only in SQLite.

Nutrition comes from [OpenFoodFacts](https://world.openfoodfacts.org): when
adding a food you can search for a product and its nutriments + Nutri-Score grade
are snapshotted into the event. If OpenFoodFacts is unavailable or the product is
unknown, the food is still recorded (without nutrition) — recording is never
blocked.

### Endpoints

Recording (write side):

- `POST /meals` — start a meal; the meal type (breakfast/lunch/dinner/snack) is
  inferred from the time of day.
- `POST /meals/{meal_id}/foods` — add a food (`name` + one of `quantity` /
  `weight_grams`, plus an optional `off_product_id` to snapshot nutrition).
- `POST /meals/{meal_id}/conclude` — conclude the meal.

Lookup & querying (read side):

- `GET /foods/search?q=` — OpenFoodFacts product candidates.
- `GET /meals` — list meals (optional `meal_type` / `on=YYYY-MM-DD` filters).
- `GET /meals/{meal_id}` — meal detail with food items + nutrition totals.
- `GET /foods` / `GET /foods/{name}` — drill down by food across meals.

## FrontEnd

TBD

## Requirements

- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn nutriscore.main:app --reload --app-dir src
```

Then record a meal:

```bash
MEAL=$(curl -s -XPOST http://127.0.0.1:8000/meals | python -c 'import sys,json;print(json.load(sys.stdin)["meal_id"])')
curl -s -XPOST http://127.0.0.1:8000/meals/$MEAL/foods -H 'content-type: application/json' \
  -d '{"name":"banana","weight_grams":120}'
curl -s -XPOST http://127.0.0.1:8000/meals/$MEAL/conclude
curl -s http://127.0.0.1:8000/meals/$MEAL
```

## Test

```bash
uv run pytest
```
