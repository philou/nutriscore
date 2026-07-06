"""Domain layer: meal-type inference and aggregate command rules (pure, no I/O)."""

from datetime import datetime

import pytest

from nutriscore.config import Settings
from nutriscore.domain.errors import (
    InvalidCommand,
    MealAlreadyConcluded,
    MealNotFound,
)
from nutriscore.domain.events import MealStarted, MealType
from nutriscore.domain.meal import Meal, infer_meal_type

SETTINGS = Settings()


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 7, 6, hour, minute)


@pytest.mark.parametrize(
    "hour, expected",
    [
        (4, MealType.snack),  # before breakfast window
        (5, MealType.breakfast),  # inclusive start
        (10, MealType.breakfast),
        (11, MealType.lunch),  # breakfast end is exclusive
        (14, MealType.lunch),
        (15, MealType.snack),  # lunch end exclusive, before dinner
        (18, MealType.dinner),
        (21, MealType.dinner),
        (22, MealType.snack),  # dinner end exclusive
        (23, MealType.snack),
    ],
)
def test_meal_type_inference_boundaries(hour, expected):
    assert infer_meal_type(at(hour), SETTINGS) == expected


def test_start_produces_meal_started_event():
    event = Meal().start("m1", at(12), SETTINGS)
    assert isinstance(event, MealStarted)
    assert event.meal_id == "m1"
    assert event.meal_type == MealType.lunch


def test_cannot_start_twice():
    meal = Meal.rehydrate([Meal().start("m1", at(12), SETTINGS)])
    with pytest.raises(InvalidCommand):
        meal.start("m1", at(12), SETTINGS)


def test_add_food_requires_started_meal():
    with pytest.raises(MealNotFound):
        Meal().add_food("apple", 1, None, None, at(12))


def test_add_food_requires_exactly_one_measure():
    meal = Meal.rehydrate([Meal().start("m1", at(12), SETTINGS)])
    with pytest.raises(InvalidCommand):
        meal.add_food("apple", None, None, None, at(12))  # neither
    with pytest.raises(InvalidCommand):
        meal.add_food("apple", 1, 100, None, at(12))  # both


def test_cannot_add_food_after_conclude():
    start = Meal().start("m1", at(12), SETTINGS)
    meal = Meal.rehydrate([start])
    conclude = meal.conclude(at(12, 30))
    meal = Meal.rehydrate([start, conclude])
    with pytest.raises(MealAlreadyConcluded):
        meal.add_food("apple", 1, None, None, at(13))


def test_conclude_twice_rejected():
    start = Meal().start("m1", at(12), SETTINGS)
    meal = Meal.rehydrate([start])
    conclude = meal.conclude(at(12, 30))
    meal = Meal.rehydrate([start, conclude])
    with pytest.raises(MealAlreadyConcluded):
        meal.conclude(at(13))


def test_version_tracks_applied_events():
    start = Meal().start("m1", at(12), SETTINGS)
    meal = Meal.rehydrate([start])
    food = meal.add_food("apple", 1, None, None, at(12))
    meal = Meal.rehydrate([start, food])
    assert meal.version == 2
    assert meal.food_count == 1
