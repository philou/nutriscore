"""Event store: append/load round-trip and optimistic-concurrency conflicts."""

from datetime import datetime

import pytest

from nutriscore.domain.events import FoodItemAdded, MealStarted, MealType, NutritionInfo
from nutriscore.eventstore.sqlite import ConcurrencyError, SqliteEventStore


def _started(meal_id="m1"):
    return MealStarted(meal_id=meal_id, meal_type=MealType.lunch, started_at=datetime(2026, 7, 6, 12))


def _food(meal_id="m1"):
    return FoodItemAdded(
        meal_id=meal_id,
        name="banana",
        weight_grams=120,
        nutrition=NutritionInfo(off_product_id="123", nutri_score_grade="a", energy_kcal_100g=89),
        added_at=datetime(2026, 7, 6, 12, 5),
    )


def test_append_and_load_round_trip(db_path):
    store = SqliteEventStore(db_path)
    store.append("m1", 0, [_started()])
    store.append("m1", 1, [_food()])

    events = store.load_stream("m1")
    assert [type(e).__name__ for e in events] == ["MealStarted", "FoodItemAdded"]
    # Nested NutritionInfo survives serialization intact.
    assert events[1].nutrition.nutri_score_grade == "a"
    assert events[1].nutrition.energy_kcal_100g == 89


def test_append_reopened_connection_sees_prior_events(db_path):
    SqliteEventStore(db_path).append("m1", 0, [_started()])
    # A fresh connection (as on projection rebuild) sees persisted events.
    reopened = SqliteEventStore(db_path)
    assert len(reopened.load_stream("m1")) == 1


def test_wrong_expected_seq_raises(db_path):
    store = SqliteEventStore(db_path)
    store.append("m1", 0, [_started()])
    with pytest.raises(ConcurrencyError):
        store.append("m1", 0, [_food()])  # expected 1, not 0


def test_load_all_is_global_order(db_path):
    store = SqliteEventStore(db_path)
    store.append("m1", 0, [_started("m1")])
    store.append("m2", 0, [_started("m2")])
    store.append("m1", 1, [_food("m1")])
    all_events = store.load_all()
    assert [e.meal_id for e in all_events] == ["m1", "m2", "m1"]
