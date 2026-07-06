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

A Restish backend in Python.

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

Then call the endpoint:

```bash
curl http://127.0.0.1:8000/hello
# {"message":"hello world"}
```

## Test

```bash
uv run pytest
```
